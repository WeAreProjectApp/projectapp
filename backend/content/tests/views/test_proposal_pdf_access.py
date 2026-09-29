"""PDF access distinguishes public readers from authenticated panel staff."""
import io
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from pypdf import PdfReader

from content.models import ProposalSection
from content.throttles import ProposalPdfThrottle

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def pdf_throttle_clock(monkeypatch):
    # DRF stores time.time as a class attribute; freezegun replaces it with a
    # Python function, so preserve static binding while controlling the clock.
    monkeypatch.setattr(ProposalPdfThrottle, 'timer', staticmethod(lambda: timezone.now().timestamp()))


@pytest.fixture
def pdf_proposal(sent_proposal):
    ProposalSection.objects.create(
        proposal=sent_proposal, section_type='greeting', title='Greeting',
        order=0, content_json={'clientName': 'Beta Inc'},
    )
    ProposalSection.objects.create(
        proposal=sent_proposal, section_type='executive_summary', title='Summary',
        order=1, content_json={'paragraphs': ['Observable commercial content']},
    )
    ProposalSection.objects.create(
        proposal=sent_proposal, section_type='technical_document', title='Technical',
        order=2, content_json={'purpose': 'Observable technical content'},
    )
    return sent_proposal


@freeze_time('2026-09-29T12:00:00Z')
@pytest.mark.parametrize(('doc', 'expected_text'), [('', 'Observable commercial content'), ('technical', 'Observable technical content')])
@pytest.mark.parametrize(('proposal_status', 'expiry_days'), [
    ('sent', 1), ('sent', -1), ('expired', 1),
])
def test_staff_downloads_readable_pdf(admin_client, pdf_proposal, doc, expected_text, proposal_status, expiry_days):
    """The panel retrieves each real document regardless of expiry source."""
    pdf_proposal.status = proposal_status
    pdf_proposal.expires_at = timezone.now() + timedelta(days=expiry_days)
    pdf_proposal.save()
    url = reverse('download-admin-proposal-pdf', kwargs={'proposal_id': pdf_proposal.pk})

    response = admin_client.get(url, {'doc': doc})

    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
    assert response['Cache-Control'] == 'private, no-store'
    assert '.pdf"' in response['Content-Disposition']
    pdf_text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
    assert expected_text in pdf_text
    pdf_proposal.refresh_from_db()
    assert pdf_proposal.status == proposal_status


@pytest.mark.parametrize(('doc', 'expected_text'), [('', 'Observable commercial content'), ('technical', 'Observable technical content')])
def test_public_active_pdf_is_readable(api_client, pdf_proposal, doc, expected_text):
    url = reverse('download-proposal-pdf', kwargs={'proposal_uuid': pdf_proposal.uuid})

    response = api_client.get(url, {'doc': doc})

    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
    pdf_text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
    assert expected_text in pdf_text


@freeze_time('2026-09-29T12:00:00Z')
@pytest.mark.parametrize('doc', ['', 'technical'])
@pytest.mark.parametrize(('proposal_status', 'expiry_days'), [('sent', -1), ('expired', 1)])
def test_public_expired_pdf_returns_expiry_code(api_client, pdf_proposal, doc, proposal_status, expiry_days):
    pdf_proposal.status = proposal_status
    pdf_proposal.expires_at = timezone.now() + timedelta(days=expiry_days)
    pdf_proposal.save()
    url = reverse('download-proposal-pdf', kwargs={'proposal_uuid': pdf_proposal.uuid})

    response = api_client.get(url, {'doc': doc})

    assert response.status_code == 410
    assert response.json()['code'] == 'proposal_expired'


@pytest.mark.parametrize('doc', ['', 'technical'])
def test_staff_cannot_bypass_public_expiry(admin_client, expired_proposal, doc):
    url = reverse('download-proposal-pdf', kwargs={'proposal_uuid': expired_proposal.uuid})

    response = admin_client.get(url, {'doc': doc})

    assert response.status_code == 410


def test_guest_cannot_download_panel_pdf(api_client, sent_proposal):
    url = reverse('download-admin-proposal-pdf', kwargs={'proposal_id': sent_proposal.pk})

    response = api_client.get(url)

    assert response.status_code == 401


def test_non_staff_cannot_download_panel_pdf(admin_client, admin_user, sent_proposal):
    admin_user.is_staff = False
    admin_user.save(update_fields=['is_staff'])
    url = reverse('download-admin-proposal-pdf', kwargs={'proposal_id': sent_proposal.pk})

    response = admin_client.get(url)

    assert response.status_code == 403


def test_staff_missing_proposal_returns_404(admin_client):
    url = reverse('download-admin-proposal-pdf', kwargs={'proposal_id': 999999})

    response = admin_client.get(url)

    assert response.status_code == 404


def test_public_missing_proposal_returns_404(api_client):
    url = reverse('download-proposal-pdf', kwargs={'proposal_uuid': uuid4()})

    response = api_client.get(url)

    assert response.status_code == 404


def test_staff_missing_technical_document_returns_404(admin_client, sent_proposal):
    url = reverse('download-admin-proposal-pdf', kwargs={'proposal_id': sent_proposal.pk})

    response = admin_client.get(url, {'doc': 'technical'})

    assert response.status_code == 404
    assert response['Cache-Control'] == 'private, no-store'


def test_panel_session_downloads_pdf(api_client, admin_user, pdf_proposal):
    api_client.force_login(admin_user)
    url = reverse('download-admin-proposal-pdf', kwargs={'proposal_id': pdf_proposal.pk})

    response = api_client.get(url)

    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
