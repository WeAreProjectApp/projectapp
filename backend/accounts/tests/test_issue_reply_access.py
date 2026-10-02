"""Reply preparation rejects invented destinations and preserves private sources."""
import pytest
from rest_framework.test import APIClient

from accounts.models import DeliveryPromptContext, DeliveryPromptSource, IssueResponse
from accounts.services import issue_reports as issues
from accounts.tests._issue_evidence_helpers import context as context, memory_only_mail as memory_only_mail
from accounts.tests.delivery_helpers import publish, version

pytestmark = pytest.mark.django_db


@pytest.fixture
def report(context):
    return issues.create_ticket(context.project.pk, context.client, 'bug', {'title': 'Bug general'})


def root_path(context, report):
    return f'/api/accounts/projects/{context.project.pk}/issue-reports/bug/{report.pk}/reply/'


def admin_api(context):
    api = APIClient()
    api.force_authenticate(user=context.admin)
    return api


@pytest.mark.parametrize('payload', [[], 'invented conversation'])
def test_reply_preparation_rejects_nonobject_payload(context, report, payload):
    """Falla si una entrada sin estructura prepara evidencia contractual o escribe una respuesta."""
    api = admin_api(context)

    response = api.post(root_path(context, report) + 'contexts/', payload, format='json')

    assert response.status_code == 400
    assert response.data['code'] == 'issue_reply_payload'
    assert DeliveryPromptContext.objects.count() == 0
    assert IssueResponse.objects.count() == 0


def test_reply_preparation_rejects_client_supplied_destination(context, report):
    """Falla si el destino de la respuesta se obtiene de datos enviados por el cliente."""
    api = admin_api(context)

    response = api.post(root_path(context, report) + 'contexts/', {
        'destination': {'kind': 'bug', 'id': report.pk},
    }, format='json')

    assert response.status_code == 400
    assert response.data['code'] == 'context_destination'
    assert DeliveryPromptContext.objects.count() == 0
    assert IssueResponse.objects.count() == 0


def test_admin_reply_source_download_returns_captured_bytes(context, report):
    """Falla si el adaptador REST devuelve otra fuente o sirve la captura sin privacidad HTTP."""
    publish(context)
    api = admin_api(context)
    prepared = api.post(root_path(context, report) + 'contexts/', {
        'expected_version': version(context), 'expected_ticket_version': report.version,
        'request_id': '70000000-0000-4000-8000-000000000001', 'contract_id': context.contract.pk,
    }, format='json')
    assert prepared.status_code == 201
    source = DeliveryPromptSource.objects.get(context_id=prepared.data['id'], role='contract')
    with source.file.open('rb') as captured:
        original = captured.read()

    response = api.get(root_path(context, report) + f'contexts/{prepared.data["id"]}/sources/{source.source_key}/')

    assert response.status_code == 200
    assert b''.join(response.streaming_content) == original
    assert response['Cache-Control'] == 'private, no-store'
    assert response['X-Content-Type-Options'] == 'nosniff'
    response.close()
