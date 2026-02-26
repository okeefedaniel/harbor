"""
AI-powered grant matching command.

Queries active GrantPreference profiles and scores open opportunities
against each user's preferences using the Claude API.

Usage:
    python manage.py match_opportunities
    python manage.py match_opportunities --include-state
    python manage.py match_opportunities --user jdoe --dry-run
    python manage.py match_opportunities --rescore
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import User
from core.notifications import _build_absolute_url, _create_notification, _send_notification_email
from grants.matching import score_opportunity
from grants.models import (
    FederalOpportunity,
    GrantPreference,
    GrantProgram,
    OpportunityMatch,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Score open opportunities against user preferences using AI'

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-state',
            action='store_true',
            help='Also match against published state grant programs',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Only match for a specific username',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print scores without saving to the database',
        )
        parser.add_argument(
            '--rescore',
            action='store_true',
            help='Re-score existing matches (by default, existing matches are skipped)',
        )

    def handle(self, *args, **options):
        include_state = options['include_state']
        target_user = options['user']
        dry_run = options['dry_run']
        rescore = options['rescore']

        min_score = getattr(settings, 'GRANT_MATCH_MIN_SCORE', 60)
        notify_score = getattr(settings, 'GRANT_MATCH_NOTIFY_SCORE', 75)

        # ---- Gather preferences ----
        prefs_qs = GrantPreference.objects.filter(is_active=True).select_related(
            'user', 'user__agency', 'user__organization',
        )
        if target_user:
            prefs_qs = prefs_qs.filter(user__username=target_user)

        prefs = list(prefs_qs)
        if not prefs:
            self.stdout.write(self.style.WARNING('No active grant preferences found.'))
            return

        self.stdout.write(f'Found {len(prefs)} active preference profile(s).')

        # ---- Gather opportunities ----
        federal_opps = list(
            FederalOpportunity.objects.filter(
                opportunity_status=FederalOpportunity.OpportunityStatus.POSTED,
            ).order_by('-post_date')[:200]  # Cap to avoid excessive API calls
        )
        self.stdout.write(f'Found {len(federal_opps)} open federal opportunities.')

        state_programs = []
        if include_state:
            state_programs = list(
                GrantProgram.objects.filter(
                    is_published=True,
                    status__in=[
                        GrantProgram.Status.POSTED,
                        GrantProgram.Status.ACCEPTING_APPLICATIONS,
                    ],
                ).select_related('agency').order_by('-posting_date')[:100]
            )
            self.stdout.write(f'Found {len(state_programs)} published state programs.')

        total_scored = 0
        total_stored = 0
        total_notified = 0

        for pref in prefs:
            user = pref.user

            if not user.anthropic_api_key:
                self.stdout.write(
                    self.style.WARNING(
                        f'Skipping {user.username} — no API key configured.'
                    )
                )
                continue

            is_fed_coordinator = user.role == User.Role.FEDERAL_COORDINATOR

            # Federal coordinators only get federal matches
            opportunities = []
            for opp in federal_opps:
                opportunities.append(('federal', opp))

            if not is_fed_coordinator and include_state:
                for prog in state_programs:
                    opportunities.append(('state', prog))

            self.stdout.write(
                f'\nScoring {len(opportunities)} opportunities for {user.username} '
                f'({user.get_role_display()})...'
            )

            for source, opp in opportunities:
                # Check for existing match
                if source == 'federal':
                    existing = OpportunityMatch.objects.filter(
                        user=user, federal_opportunity=opp,
                    ).first()
                else:
                    existing = OpportunityMatch.objects.filter(
                        user=user, grant_program=opp,
                    ).first()

                if existing and not rescore:
                    continue

                result = score_opportunity(pref, opp)
                total_scored += 1

                if result is None:
                    self.stdout.write(
                        self.style.WARNING(f'  ✗ Scoring failed for: {opp}')
                    )
                    continue

                score = result['score']
                explanation = result['explanation']
                title = opp.title if hasattr(opp, 'title') else str(opp)

                if dry_run:
                    self.stdout.write(
                        f'  [{score:3d}] {title[:60]} — {explanation[:80]}'
                    )
                    continue

                if score < min_score:
                    continue

                # Store or update match
                if existing:
                    existing.relevance_score = score
                    existing.explanation = explanation
                    existing.save(update_fields=[
                        'relevance_score', 'explanation', 'updated_at',
                    ])
                    total_stored += 1
                else:
                    match_kwargs = {
                        'user': user,
                        'source': source,
                        'relevance_score': score,
                        'explanation': explanation,
                    }
                    if source == 'federal':
                        match_kwargs['federal_opportunity'] = opp
                    else:
                        match_kwargs['grant_program'] = opp

                    existing = OpportunityMatch.objects.create(**match_kwargs)
                    total_stored += 1

                # Notify if score is high enough and not already notified
                if score >= notify_score and not existing.notified:
                    self._notify_match(user, existing)
                    existing.notified = True
                    existing.notified_at = timezone.now()
                    existing.save(update_fields=['notified', 'notified_at'])
                    total_notified += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. Scored: {total_scored}, Stored: {total_stored}, '
                f'Notified: {total_notified}'
            )
        )

    @staticmethod
    def _notify_match(user, match):
        """Send an in-app notification and email for a high-scoring match."""
        title_text = match.opportunity_title
        opp_url = match.opportunity_url

        _create_notification(
            recipient=user,
            title='New Grant Recommendation',
            message=(
                f'We found a {match.relevance_score}% match: "{title_text[:80]}". '
                f'{match.explanation[:120]}'
            ),
            link=opp_url,
            priority='medium',
        )

        if user.email:
            detail_url = _build_absolute_url(opp_url)
            _send_notification_email(
                recipient_email=user.email,
                subject=f'Grant Recommendation: {title_text[:60]}',
                template_name='emails/grant_match.html',
                context={
                    'user': user,
                    'match': match,
                    'title': title_text,
                    'score': match.relevance_score,
                    'explanation': match.explanation,
                    'source': match.get_source_display(),
                    'detail_url': detail_url,
                },
            )
