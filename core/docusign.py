"""
DocuSign e-Signature API wrapper for the Beacon platform.

Provides JWT grant authentication and envelope management for
sending award agreements for electronic signature.
"""

import logging
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

import docusign_esign as ds
from docusign_esign import (
    ApiClient,
    ApiException,
    CarbonCopy,
    DateSigned,
    Document,
    EnvelopeDefinition,
    EnvelopesApi,
    Recipients,
    SignHere,
    Signer,
    Tabs,
)

logger = logging.getLogger(__name__)


class DocuSignService:
    """Service class for interacting with the DocuSign eSignature API.

    Uses JWT grant authentication with an RSA private key.
    """

    SCOPES = ['signature', 'impersonation']

    def __init__(self):
        self.integration_key = settings.DOCUSIGN_INTEGRATION_KEY
        self.account_id = settings.DOCUSIGN_ACCOUNT_ID
        self.base_url = settings.DOCUSIGN_BASE_URL
        self.oauth_base = settings.DOCUSIGN_OAUTH_BASE
        self.user_id = settings.DOCUSIGN_USER_ID
        self._api_client = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _get_private_key(self):
        """Return the RSA private key bytes.

        Prefers the ``DOCUSIGN_RSA_PRIVATE_KEY`` env var (inline PEM) so
        the key can be stored as a Railway variable instead of a file.
        Falls back to reading ``DOCUSIGN_RSA_KEY_FILE`` from disk.
        """
        # Prefer inline key from env var (ideal for Railway / Heroku)
        inline_key = getattr(settings, 'DOCUSIGN_RSA_PRIVATE_KEY', '')
        if inline_key:
            return inline_key.encode('utf-8')

        # Fallback: read from file
        key_path = Path(settings.BASE_DIR) / settings.DOCUSIGN_RSA_KEY_FILE
        if not key_path.exists():
            raise FileNotFoundError(
                f'DocuSign RSA private key not found at {key_path}. '
                'Set DOCUSIGN_RSA_PRIVATE_KEY env var or ensure '
                'DOCUSIGN_RSA_KEY_FILE points to a valid file.'
            )
        return key_path.read_bytes()

    def get_access_token(self):
        """Obtain an access token via JWT grant authentication.

        Returns the access token string.  Raises ``ApiException`` on failure.
        """
        api_client = ApiClient()
        api_client.set_base_path(self.oauth_base)

        private_key = self._get_private_key()

        token_response = api_client.request_jwt_user_token(
            client_id=self.integration_key,
            user_id=self.user_id,
            oauth_host_name=self.oauth_base.replace('https://', ''),
            private_key_bytes=private_key,
            expires_in=3600,
            scopes=self.SCOPES,
        )

        access_token = token_response.access_token
        logger.debug('DocuSign JWT access token obtained successfully.')
        return access_token

    def _get_api_client(self):
        """Return a configured ``ApiClient`` with a valid access token."""
        if self._api_client is None:
            access_token = self.get_access_token()
            self._api_client = ApiClient()
            self._api_client.set_base_path(self.base_url)
            self._api_client.set_default_header(
                'Authorization', f'Bearer {access_token}',
            )
        return self._api_client

    # ------------------------------------------------------------------
    # Envelope creation
    # ------------------------------------------------------------------

    def _build_agreement_html(self, award):
        """Generate an HTML document for the award agreement.

        Contains award details, terms, conditions, and signature placeholders.
        """
        org_name = award.organization.name if award.organization else 'N/A'
        agency_name = award.agency.name if award.agency else 'N/A'

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
    body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; line-height: 1.6; }}
    h1 {{ color: #00457C; text-align: center; border-bottom: 3px solid #00457C; padding-bottom: 10px; }}
    h2 {{ color: #00457C; margin-top: 30px; }}
    .header {{ text-align: center; margin-bottom: 30px; }}
    .header p {{ color: #666; }}
    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #ddd; }}
    th {{ background-color: #f8f9fa; font-weight: bold; color: #555; width: 35%; }}
    .terms {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
    .signature-block {{ margin-top: 60px; page-break-inside: avoid; }}
    .signature-line {{ border-bottom: 1px solid #333; width: 300px; display: inline-block; margin-top: 40px; }}
    .sig-label {{ color: #666; font-size: 0.9em; }}
</style>
</head>
<body>
    <div class="header">
        <h1>Grant Award Agreement</h1>
        <p>State of DOK</p>
        <p>{agency_name}</p>
    </div>

    <h2>Award Information</h2>
    <table>
        <tr><th>Award Number</th><td>{award.award_number}</td></tr>
        <tr><th>Title</th><td>{award.title}</td></tr>
        <tr><th>Recipient Organization</th><td>{org_name}</td></tr>
        <tr><th>Award Amount</th><td>${award.award_amount:,.2f}</td></tr>
        <tr><th>Award Date</th><td>{award.award_date or 'TBD'}</td></tr>
        <tr><th>Start Date</th><td>{award.start_date or 'TBD'}</td></tr>
        <tr><th>End Date</th><td>{award.end_date or 'TBD'}</td></tr>
    </table>

    {"<table><tr><th>Match Required</th><td>Yes &mdash; ${:,.2f}</td></tr></table>".format(award.match_amount) if award.requires_match and award.match_amount else ""}

    <h2>Terms and Conditions</h2>
    <div class="terms">
        {award.terms_and_conditions.replace(chr(10), '<br>')}
    </div>

    {"<h2>Special Conditions</h2><div class='terms'>{}</div>".format(award.special_conditions.replace(chr(10), '<br>')) if award.special_conditions else ""}

    <h2>Agreement</h2>
    <p>By signing this document, the undersigned agrees to the terms and conditions
    set forth in this Grant Award Agreement. The recipient acknowledges receipt of
    the award and agrees to comply with all applicable federal and state regulations.</p>

    <div class="signature-block">
        <p><strong>Recipient Signature:</strong></p>
        <p class="sig-label">Signed by: /sn1/</p>
        <p class="sig-label">Date: /ds1/</p>
    </div>
</body>
</html>"""
        return html

    def create_envelope(self, award, signer_name, signer_email, cc_email=None):
        """Create and send a DocuSign envelope for an award agreement.

        Parameters
        ----------
        award : awards.models.Award
            The award to generate an agreement for.
        signer_name : str
            Full name of the signer.
        signer_email : str
            Email address of the signer (receives the signing link).
        cc_email : str, optional
            Email address to receive a carbon copy of the signed document.

        Returns
        -------
        str
            The DocuSign envelope ID.

        Raises
        ------
        ApiException
            If the DocuSign API call fails.
        """
        api_client = self._get_api_client()
        envelopes_api = EnvelopesApi(api_client)

        # Build the HTML agreement document
        html_content = self._build_agreement_html(award)

        import base64
        doc_b64 = base64.b64encode(html_content.encode('utf-8')).decode('ascii')

        document = Document(
            document_base64=doc_b64,
            name=f'Award Agreement - {award.award_number}',
            file_extension='html',
            document_id='1',
        )

        # Signer with Sign Here and Date Signed tabs
        sign_here = SignHere(
            anchor_string='/sn1/',
            anchor_units='pixels',
            anchor_y_offset='10',
            anchor_x_offset='0',
        )
        date_signed = DateSigned(
            anchor_string='/ds1/',
            anchor_units='pixels',
            anchor_y_offset='10',
            anchor_x_offset='0',
        )

        signer = Signer(
            email=signer_email,
            name=signer_name,
            recipient_id='1',
            routing_order='1',
            tabs=Tabs(
                sign_here_tabs=[sign_here],
                date_signed_tabs=[date_signed],
            ),
        )

        recipients = Recipients(signers=[signer])

        # Optional CC recipient
        if cc_email:
            cc = CarbonCopy(
                email=cc_email,
                name='CC Recipient',
                recipient_id='2',
                routing_order='2',
            )
            recipients.carbon_copies = [cc]

        envelope_definition = EnvelopeDefinition(
            email_subject=f'Award Agreement for Signature - {award.award_number}',
            email_blurb=(
                f'Please review and sign the award agreement for '
                f'{award.title} ({award.award_number}).'
            ),
            documents=[document],
            recipients=recipients,
            status='sent',  # Send immediately
        )

        try:
            envelope_summary = envelopes_api.create_envelope(
                account_id=self.account_id,
                envelope_definition=envelope_definition,
            )
            envelope_id = envelope_summary.envelope_id
            logger.info(
                'DocuSign envelope created: %s for award %s',
                envelope_id,
                award.award_number,
            )
            return envelope_id
        except ApiException:
            logger.exception(
                'Failed to create DocuSign envelope for award %s',
                award.award_number,
            )
            raise

    # ------------------------------------------------------------------
    # Envelope status & document download
    # ------------------------------------------------------------------

    def get_envelope_status(self, envelope_id):
        """Retrieve the current status of a DocuSign envelope.

        Returns
        -------
        str
            The envelope status (e.g. 'sent', 'delivered', 'completed', 'declined', 'voided').
        """
        api_client = self._get_api_client()
        envelopes_api = EnvelopesApi(api_client)

        try:
            envelope = envelopes_api.get_envelope(
                account_id=self.account_id,
                envelope_id=envelope_id,
            )
            return envelope.status
        except ApiException:
            logger.exception(
                'Failed to get DocuSign envelope status for %s',
                envelope_id,
            )
            raise

    def download_signed_document(self, envelope_id):
        """Download the signed document from a completed envelope.

        Returns
        -------
        bytes
            The PDF content of the signed document.
        """
        api_client = self._get_api_client()
        envelopes_api = EnvelopesApi(api_client)

        try:
            # Download the combined document (all docs merged into one PDF)
            document = envelopes_api.get_document(
                account_id=self.account_id,
                envelope_id=envelope_id,
                document_id='combined',
            )

            # The SDK returns a temporary file path; read the bytes
            if hasattr(document, 'read'):
                return document.read()
            else:
                with open(document, 'rb') as f:
                    return f.read()
        except ApiException:
            logger.exception(
                'Failed to download signed document for envelope %s',
                envelope_id,
            )
            raise
