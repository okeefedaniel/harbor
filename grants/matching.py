"""
AI-powered grant matching service using the Anthropic Claude API.

Scores opportunities against user preferences and returns a relevance
score (0-100) plus a short explanation.  Prompts adapt based on the
user's role (Applicant vs Federal Coordinator).

The ``run_matching_for_user`` helper can be called from views (after
saving preferences) or from the management command to score all open
opportunities for a single user.
"""

import json
import logging
import threading

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-20250514'
MAX_TOKENS = 250


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------

def build_preference_context(preference):
    """Format a GrantPreference into a text block for the AI prompt."""
    from grants.models import GrantPreference
    from core.models import Organization

    user = preference.user
    parts = []

    # Role context
    parts.append(f"Role: {user.get_role_display()}")
    if user.agency:
        parts.append(f"Agency: {user.agency.name} ({user.agency.abbreviation})")
    if user.organization:
        parts.append(f"Organization: {user.organization.name}")
        parts.append(f"Organization Type: {user.organization.get_org_type_display()}")
        if user.organization.city:
            parts.append(f"Location: {user.organization.city}, {user.organization.state}")

    # Focus areas
    if preference.focus_areas:
        area_labels = dict(GrantPreference.FocusArea.choices)
        areas = [str(area_labels.get(a, a)) for a in preference.focus_areas]
        parts.append(f"Focus Areas: {', '.join(areas)}")

    # Eligible org types
    if preference.eligible_org_types:
        type_labels = dict(Organization.OrgType.choices)
        types = [str(type_labels.get(t, t)) for t in preference.eligible_org_types]
        parts.append(f"Eligible Organization Types: {', '.join(types)}")

    # Funding range
    if preference.funding_range_min or preference.funding_range_max:
        low = f"${preference.funding_range_min:,.0f}" if preference.funding_range_min else "any"
        high = f"${preference.funding_range_max:,.0f}" if preference.funding_range_max else "any"
        parts.append(f"Funding Range: {low} – {high}")

    # Free-text description
    if preference.description:
        parts.append(f"Description: {preference.description}")

    return '\n'.join(parts)


def build_opportunity_summary(opportunity):
    """Format a FederalOpportunity or GrantProgram into a text block."""
    from grants.models import FederalOpportunity, GrantProgram

    parts = []

    if isinstance(opportunity, FederalOpportunity):
        parts.append(f"Title: {opportunity.title}")
        parts.append(f"Agency: {opportunity.agency_name}")
        if opportunity.category:
            parts.append(f"Category: {opportunity.category}")
        if opportunity.description:
            parts.append(f"Description: {opportunity.description[:2000]}")
        if opportunity.funding_range_display:
            parts.append(f"Funding: {opportunity.funding_range_display}")
        if opportunity.eligible_applicants:
            parts.append(f"Eligibility: {opportunity.eligible_applicants[:500]}")
        if opportunity.applicant_types:
            parts.append(f"Applicant Types: {', '.join(str(t) for t in opportunity.applicant_types)}")
        if opportunity.close_date:
            parts.append(f"Close Date: {opportunity.close_date}")
        parts.append(f"Source: Federal (Grants.gov)")

    elif isinstance(opportunity, GrantProgram):
        parts.append(f"Title: {opportunity.title}")
        parts.append(f"Agency: {opportunity.agency.name}")
        if opportunity.description:
            parts.append(f"Description: {opportunity.description[:2000]}")
        parts.append(f"Funding: ${opportunity.min_award:,.0f} – ${opportunity.max_award:,.0f}")
        if opportunity.eligibility_criteria:
            parts.append(f"Eligibility: {opportunity.eligibility_criteria[:500]}")
        parts.append(f"Grant Type: {opportunity.get_grant_type_display()}")
        if opportunity.application_deadline:
            parts.append(f"Deadline: {opportunity.application_deadline}")
        parts.append(f"Source: State grant program")

    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# AI scoring
# ---------------------------------------------------------------------------

def _build_system_prompt(user):
    """Return the system prompt adapted to the user's role."""
    from core.models import User

    if user.role == User.Role.FEDERAL_COORDINATOR:
        return (
            "You are an AI assistant helping a state Federal Fund "
            "Coordinator identify federal grant opportunities their agency should "
            "track and pursue. Score how relevant the opportunity is for the "
            "coordinator's agency and strategic priorities."
        )
    else:
        return (
            "You are an AI assistant helping a grant applicant discover relevant "
            "funding opportunities they should apply for. Score how well the "
            "opportunity matches the applicant's needs, eligible organization "
            "type, focus areas, and funding preferences."
        )


def score_opportunity(preference, opportunity):
    """Call the Claude API to score an opportunity against user preferences.

    Returns a dict ``{'score': int, 'explanation': str}`` or ``None`` on
    failure.  Scores range from 0 (no relevance) to 100 (perfect match).
    """
    api_key = getattr(preference.user, 'anthropic_api_key', '')
    if not api_key:
        logger.warning('No API key for user %s — skipping AI scoring', preference.user)
        return None

    try:
        import anthropic
    except ImportError:
        logger.error('anthropic package not installed — run pip install anthropic')
        return None

    pref_context = build_preference_context(preference)
    opp_summary = build_opportunity_summary(opportunity)
    system = _build_system_prompt(preference.user)

    user_message = (
        "Score the following opportunity for this user on a scale of 0–100.\n\n"
        "=== USER PROFILE ===\n"
        f"{pref_context}\n\n"
        "=== OPPORTUNITY ===\n"
        f"{opp_summary}\n\n"
        "Respond with ONLY a JSON object (no markdown, no explanation outside "
        "the JSON). The JSON must have exactly two keys:\n"
        '  "score": integer 0-100\n'
        '  "explanation": string (1-2 sentences explaining the score)\n'
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{'role': 'user', 'content': user_message}],
        )
        text = response.content[0].text.strip()

        # Parse JSON — strip any markdown fences if the model adds them
        if text.startswith('```'):
            text = text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()

        result = json.loads(text)
        score = int(result.get('score', 0))
        explanation = str(result.get('explanation', ''))
        return {'score': max(0, min(100, score)), 'explanation': explanation}

    except json.JSONDecodeError as exc:
        logger.warning('AI returned invalid JSON: %s', exc)
        return None
    except Exception as exc:
        logger.exception('AI scoring failed: %s', exc)
        return None


# ---------------------------------------------------------------------------
# Run matching for a single user (reusable from views and commands)
# ---------------------------------------------------------------------------

def run_matching_for_user(user, include_state=False):
    """Score open opportunities against *user*'s active preferences.

    Creates or updates :model:`grants.OpportunityMatch` records and sends
    notifications for high-scoring matches.  Safe to call from a background
    thread — uses its own DB connections.

    Returns a dict with ``scored``, ``stored``, ``notified`` counts.
    """
    from core.models import User
    from core.notifications import (
        _build_absolute_url,
        _create_notification,
        _send_notification_email,
    )
    from grants.models import (
        FederalOpportunity,
        GrantPreference,
        GrantProgram,
        OpportunityMatch,
    )

    if not getattr(user, 'anthropic_api_key', ''):
        logger.info('No API key for %s — skipping matching.', user)
        return {'scored': 0, 'stored': 0, 'notified': 0}

    min_score = getattr(settings, 'GRANT_MATCH_MIN_SCORE', 60)
    notify_score = getattr(settings, 'GRANT_MATCH_NOTIFY_SCORE', 75)

    try:
        pref = GrantPreference.objects.select_related(
            'user', 'user__agency', 'user__organization',
        ).get(user=user, is_active=True)
    except GrantPreference.DoesNotExist:
        logger.info('No active preferences for %s — skipping matching.', user)
        return {'scored': 0, 'stored': 0, 'notified': 0}

    is_fed = user.role == User.Role.FEDERAL_COORDINATOR

    # Gather opportunities
    federal_opps = list(
        FederalOpportunity.objects.filter(
            opportunity_status=FederalOpportunity.OpportunityStatus.POSTED,
        ).order_by('-post_date')[:200]
    )

    opportunities = [('federal', opp) for opp in federal_opps]

    if not is_fed and include_state:
        state_programs = list(
            GrantProgram.objects.filter(
                is_published=True,
                status__in=[
                    GrantProgram.Status.POSTED,
                    GrantProgram.Status.ACCEPTING_APPLICATIONS,
                ],
            ).select_related('agency').order_by('-posting_date')[:100]
        )
        opportunities.extend(('state', prog) for prog in state_programs)

    scored = stored = notified = 0

    # Pre-fetch all existing match IDs for this user to avoid N+1 queries
    existing_federal_ids = set(
        OpportunityMatch.objects.filter(user=user, federal_opportunity__isnull=False)
        .values_list('federal_opportunity_id', flat=True)
    )
    existing_program_ids = set(
        OpportunityMatch.objects.filter(user=user, grant_program__isnull=False)
        .values_list('grant_program_id', flat=True)
    )

    for source, opp in opportunities:
        # Skip if already matched
        if source == 'federal' and opp.pk in existing_federal_ids:
            continue
        if source != 'federal' and opp.pk in existing_program_ids:
            continue

        result = score_opportunity(pref, opp)
        scored += 1

        if result is None:
            continue

        score = result['score']
        explanation = result['explanation']

        if score < min_score:
            continue

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

        match_obj = OpportunityMatch.objects.create(**match_kwargs)
        stored += 1

        # Notify on high-scoring matches
        if score >= notify_score:
            title_text = match_obj.opportunity_title
            opp_url = match_obj.opportunity_url

            _create_notification(
                recipient=user,
                title='New Grant Recommendation',
                message=(
                    f'We found a {score}% match: "{title_text[:80]}". '
                    f'{explanation[:120]}'
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
                        'match': match_obj,
                        'title': title_text,
                        'score': score,
                        'explanation': explanation,
                        'source': match_obj.get_source_display(),
                        'detail_url': detail_url,
                    },
                )

            match_obj.notified = True
            match_obj.notified_at = timezone.now()
            match_obj.save(update_fields=['notified', 'notified_at'])
            notified += 1

    logger.info(
        'Matching complete for %s: scored=%d stored=%d notified=%d',
        user.username, scored, stored, notified,
    )
    return {'scored': scored, 'stored': stored, 'notified': notified}


def run_matching_async(user, include_state=False):
    """Fire-and-forget: run matching in a background thread.

    Called from the preferences view so the user doesn't wait for all
    API calls to finish before getting a response.
    """
    import django

    def _worker():
        try:
            # Ensure DB connections are available in the thread
            django.db.connections.close_all()
            run_matching_for_user(user, include_state=include_state)
        except Exception:
            logger.exception('Background matching failed for %s', user)
        finally:
            django.db.connections.close_all()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    logger.info('Started background matching thread for %s', user.username)
