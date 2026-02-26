"""
Sync federal grant opportunities from the Simpler Grants.gov API.

Usage:
    python manage.py sync_federal_grants           # Sync posted opportunities
    python manage.py sync_federal_grants --full     # Full sync (all statuses)
    python manage.py sync_federal_grants --limit 50 # Limit number of pages

API Docs: https://api.simpler.grants.gov/v1
Auth:     Free API key via X-API-Key header (register at simpler.grants.gov)
"""
import html
import json
import logging
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from grants.models import FederalOpportunity

logger = logging.getLogger(__name__)

API_BASE_URL = 'https://api.simpler.grants.gov/v1'
SEARCH_ENDPOINT = f'{API_BASE_URL}/opportunities/search'
PAGE_SIZE = 25  # Grants.gov default; max is 25 for search
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


class Command(BaseCommand):
    help = 'Sync federal grant opportunities from Simpler Grants.gov API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Fetch all statuses (posted, closed, archived, forecasted)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Maximum number of pages to fetch (0 = unlimited)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be synced without saving',
        )

    def handle(self, *args, **options):
        api_key = getattr(settings, 'GRANTS_GOV_API_KEY', '') or ''
        if not api_key:
            raise CommandError(
                'GRANTS_GOV_API_KEY not set. Get a free key at '
                'https://simpler.grants.gov and add it to your environment.'
            )

        is_full = options['full']
        page_limit = options['limit']
        dry_run = options['dry_run']
        verbosity = options['verbosity']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no records will be saved'))

        # Build the statuses to fetch
        if is_full:
            statuses = ['posted', 'closed', 'archived', 'forecasted']
        else:
            statuses = ['posted', 'forecasted']

        total_created = 0
        total_updated = 0

        for status in statuses:
            created, updated = self._sync_status(
                api_key, status, page_limit, dry_run, verbosity,
            )
            total_created += created
            total_updated += updated

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'\nSync complete: {total_created} created, {total_updated} updated'
        ))

    def _sync_status(self, api_key, status, page_limit, dry_run, verbosity):
        """Fetch and upsert all opportunities for a given status."""
        page_offset = 1
        created_count = 0
        updated_count = 0

        self.stdout.write(f'\nFetching {status} opportunities...')

        while True:
            payload = {
                'pagination': {
                    'page_offset': page_offset,
                    'page_size': PAGE_SIZE,
                    'order_by': 'opportunity_id',
                    'sort_direction': 'descending',
                },
                'filters': {
                    'opportunity_status': {'one_of': [status]},
                    'applicant_type': {
                        'one_of': [
                            'state_governments',
                            'county_governments',
                            'city_or_township_governments',
                            'special_district_governments',
                            'independent_school_districts',
                            'public_and_state_institutions_of_higher_education',
                            'federally_recognized_native_american_tribal_governments',
                            'nonprofits_non_higher_education_with_501c3',
                            'nonprofits_non_higher_education_without_501c3',
                        ],
                    },
                },
            }

            data = self._api_request(api_key, payload)
            if data is None:
                self.stderr.write(self.style.ERROR(
                    f'  Failed to fetch page {page_offset} for status={status}'
                ))
                break

            opportunities = data.get('data', [])
            pagination_info = data.get('pagination_info', {})
            total_pages = pagination_info.get('total_pages', 1)
            total_records = pagination_info.get('total_records', 0)

            if page_offset == 1 and verbosity >= 1:
                self.stdout.write(f'  Found {total_records} {status} opportunities ({total_pages} pages)')

            if not opportunities:
                break

            for opp in opportunities:
                c, u = self._upsert_opportunity(opp, status, dry_run)
                created_count += c
                updated_count += u

            if verbosity >= 2:
                self.stdout.write(f'  Page {page_offset}/{total_pages} processed ({len(opportunities)} records)')

            page_offset += 1

            if page_offset > total_pages:
                break
            if page_limit and page_offset > page_limit:
                self.stdout.write(f'  Reached page limit ({page_limit})')
                break

            # Small delay to be respectful of rate limits
            time.sleep(0.25)

        self.stdout.write(f'  {status}: {created_count} created, {updated_count} updated')
        return created_count, updated_count

    def _api_request(self, api_key, payload):
        """Make a POST request to the Grants.gov search API with retry logic."""
        headers = {
            'X-Api-Key': api_key,
            'Content-Type': 'application/json',
        }
        body = json.dumps(payload).encode('utf-8')

        for attempt in range(MAX_RETRIES):
            try:
                req = Request(
                    SEARCH_ENDPOINT,
                    data=body,
                    headers=headers,
                    method='POST',
                )
                with urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode('utf-8'))

            except HTTPError as e:
                if e.code == 429:
                    wait = BACKOFF_BASE ** (attempt + 1)
                    self.stderr.write(
                        self.style.WARNING(f'  Rate limited (429). Waiting {wait}s...')
                    )
                    time.sleep(wait)
                    continue
                elif e.code >= 500:
                    wait = BACKOFF_BASE ** (attempt + 1)
                    self.stderr.write(
                        self.style.WARNING(f'  Server error ({e.code}). Retrying in {wait}s...')
                    )
                    time.sleep(wait)
                    continue
                else:
                    self.stderr.write(
                        self.style.ERROR(f'  HTTP {e.code}: {e.read().decode("utf-8", errors="replace")[:200]}')
                    )
                    return None
            except URLError as e:
                wait = BACKOFF_BASE ** (attempt + 1)
                self.stderr.write(
                    self.style.WARNING(f'  Connection error: {e.reason}. Retrying in {wait}s...')
                )
                time.sleep(wait)
                continue
            except Exception as e:
                logger.exception('Unexpected error calling Grants.gov API')
                self.stderr.write(self.style.ERROR(f'  Unexpected error: {e}'))
                return None

        self.stderr.write(self.style.ERROR(f'  Max retries ({MAX_RETRIES}) exceeded'))
        return None

    def _upsert_opportunity(self, opp, status_filter, dry_run):
        """Create or update a FederalOpportunity record. Returns (created, updated) counts."""
        opp_id = opp.get('opportunity_id')
        if not opp_id:
            return 0, 0

        # Extract summary info
        summary = opp.get('summary', {}) or {}

        # Parse dates safely
        post_date = self._parse_date(summary.get('post_date'))
        close_date = self._parse_date(summary.get('close_date'))
        archive_date = self._parse_date(summary.get('archive_date'))

        # Build the Grants.gov URL (simpler.grants.gov is the current working format)
        grants_gov_url = f'https://simpler.grants.gov/opportunity/{opp_id}'

        # Map opportunity status
        api_status = (opp.get('opportunity_status') or status_filter or 'posted').lower()
        status_map = {
            'posted': FederalOpportunity.OpportunityStatus.POSTED,
            'closed': FederalOpportunity.OpportunityStatus.CLOSED,
            'archived': FederalOpportunity.OpportunityStatus.ARCHIVED,
            'forecasted': FederalOpportunity.OpportunityStatus.FORECASTED,
        }
        opp_status = status_map.get(api_status, FederalOpportunity.OpportunityStatus.POSTED)

        # Extract funding instrument
        funding_instrument_raw = summary.get('funding_instrument', '') or ''
        fi_map = {
            'grant': FederalOpportunity.FundingInstrument.GRANT,
            'cooperative_agreement': FederalOpportunity.FundingInstrument.COOPERATIVE_AGREEMENT,
            'procurement_contract': FederalOpportunity.FundingInstrument.PROCUREMENT_CONTRACT,
        }
        funding_instrument = fi_map.get(
            funding_instrument_raw.lower().replace(' ', '_'),
            FederalOpportunity.FundingInstrument.OTHER,
        )

        # Extract CFDA numbers from assistance_listing
        cfda_numbers = []
        for listing in (summary.get('assistance_listing', None) or []):
            if isinstance(listing, dict) and listing.get('program_number'):
                cfda_numbers.append(listing['program_number'])

        # Applicant types
        applicant_types = summary.get('applicant_type', []) or []

        defaults = {
            'opportunity_number': opp.get('opportunity_number', '') or '',
            'title': self._strip_html(opp.get('opportunity_title', '') or ''),
            'description': self._strip_html(summary.get('summary_description', '') or ''),
            'agency_name': summary.get('agency_name', '') or opp.get('agency', '') or '',
            'agency_code': opp.get('agency_code', '') or summary.get('agency_code', '') or '',
            'category': summary.get('funding_category', '') or '',
            'funding_instrument': funding_instrument,
            'cfda_numbers': cfda_numbers,
            'award_floor': summary.get('award_floor') or None,
            'award_ceiling': summary.get('award_ceiling') or None,
            'expected_awards': summary.get('expected_number_of_awards') or None,
            'total_funding': summary.get('estimated_total_program_funding') or None,
            'post_date': post_date,
            'close_date': close_date,
            'archive_date': archive_date,
            'opportunity_status': opp_status,
            'applicant_types': applicant_types,
            'eligible_applicants': summary.get('applicant_eligibility_description', '') or '',
            'grants_gov_url': grants_gov_url,
            'synced_at': timezone.now(),
            'raw_data': opp,
        }

        if dry_run:
            self.stdout.write(f'    [DRY RUN] {opp_id}: {defaults["title"][:60]}')
            return 0, 0

        _, created = FederalOpportunity.objects.update_or_create(
            opportunity_id=opp_id,
            defaults=defaults,
        )

        return (1, 0) if created else (0, 1)

    @staticmethod
    def _strip_html(text):
        """Strip HTML tags and decode entities from API text fields."""
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', ' ', text)  # Replace tags with space
        text = html.unescape(text)             # Decode &nbsp; &amp; etc.
        text = re.sub(r'\s+', ' ', text)       # Collapse whitespace
        return text.strip()

    @staticmethod
    def _parse_date(date_str):
        """Parse a date string from the API (YYYY-MM-DD format)."""
        if not date_str:
            return None
        try:
            from datetime import date as d
            parts = date_str.split('-')
            return d(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            return None
