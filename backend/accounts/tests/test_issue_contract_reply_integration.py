"""Real JWT integration contracts for grounded replies on issue reports."""

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from accounts.models import DeliveryWorkspace, IssueResponse, RequirementReview, UserProfile
from accounts.services import issue_reports as issues
from accounts.tests.delivery_authoring_helpers import api_for, build_authoring_context, reply_payload
from accounts.tests.delivery_helpers import version
from accounts.tests._delivery_fixtures import make_requirement
from accounts.tests.issue_browser_server import assert_memory_mailers, memory_mailers

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def memory_only_mail(settings, mailoutbox):
    with override_settings(MAILERS=memory_mailers(settings)):
        assert_memory_mailers()
        yield
        assert_memory_mailers()
        assert mailoutbox == []


@pytest.fixture
def context():
    return build_authoring_context()


def ticket(context, **values):
    return issues.create_ticket(context.project.pk, context.client, 'bug', {
        'title': 'Cannot create a record', 'description': 'Save displays an error.', **values,
    })


def paths(context, report, kind='bug'):
    root = f'/api/accounts/projects/{context.project.pk}/issue-reports/{kind}/{report.pk}/reply/'
    return {
        'options': f'{root}options/', 'prepare': f'{root}contexts/', 'preview': f'{root}preview/',
        'context': lambda context_id: f'{root}contexts/{context_id}/',
        'source': lambda context_id, source_key: f'{root}contexts/{context_id}/sources/{source_key}/',
    }


def prepare(context, report, *, contract_id=None, request_id='40000000-0000-4000-8000-000000000001', kind='bug'):
    response = api_for(context.admin).post(paths(context, report, kind)['prepare'], {
        'expected_version': version(context), 'expected_ticket_version': report.version,
        'request_id': request_id, 'contract_id': contract_id,
    }, format='json')
    assert response.status_code == 201
    return response.json()


def preview(context, report, prepared, *, kind='bug'):
    response = api_for(context.admin).post(paths(context, report, kind)['preview'], {
        'expected_version': version(context), 'expected_ticket_version': report.version,
        'payload': prepared['template'],
    }, format='json')
    assert response.status_code == 200
    return response.json()


def publish_payload(context, report, prepared, reviewed, payload, *, kind='bug'):
    result = preview(context, report, {**prepared, 'template': payload}, kind=kind)
    values = {
        'expected_version': report.version,
        'admin_response': payload['response_text'], 'contract_id': prepared['contract_id'],
        'contract_reply': {
            'context_id': prepared['id'], 'expected_version': version(context),
            'expected_ticket_version': report.version, 'human_reviewed': reviewed,
            'classifications': payload['classifications'], 'source_references': result['source_references'],
        },
    }
    return values


def evaluate(context, report, values, *, actor=None, kind='bug'):
    endpoint = 'bug-reports' if kind == 'bug' else 'change-requests'
    return api_for(actor or context.admin).post(
        f'/api/accounts/projects/{context.project.pk}/{endpoint}/{report.pk}/evaluate/', values, format='json',
    )


def unreviewed(values):
    values['contract_reply']['human_reviewed'] = False


def forged_citation(values):
    values['contract_reply']['source_references'][0]['quote'] = 'Forged quote.'


def stale_ticket(context, values):
    values['contract_reply']['expected_ticket_version'] -= 1


def stale_workspace(context, values):
    DeliveryWorkspace.objects.update_or_create(project=context.project, defaults={'version': version(context) + 1})


def client_prepare(client, route, context, report, prepared):
    return client.post(route['prepare'], {
        'expected_version': version(context), 'expected_ticket_version': report.version,
        'request_id': '40000000-0000-4000-8000-000000000010', 'contract_id': context.contract.pk,
    }, format='json')


def client_context(client, route, context, report, prepared):
    return client.get(route['context'](prepared['id']))


def client_source(client, route, context, report, prepared):
    return client.get(route['source'](prepared['id'], prepared['sources'][0]['source_key']))


def test_reply_options_report_the_independent_ticket_version(context):
    """Falla si las opciones de respuesta no entregan la versión real del ticket."""
    report = ticket(context)
    options = api_for(context.admin).get(paths(context, report)['options'])

    assert options.status_code == 200
    assert options.json()['ticket_version'] == report.version


def test_general_reply_stays_indeterminate_without_changing_guide_approvals(context):
    """Falla si un ticket general fabrica alcance contractual o toca una guía aprobable."""
    report = ticket(context)
    before_status = context.first.review_status
    prepared = prepare(context, report, contract_id=None)
    payload = publish_payload(context, report, prepared, True, prepared['template'])

    response = evaluate(context, report, payload)

    report.refresh_from_db()
    assert response.status_code == 200
    assert list(IssueResponse.objects.filter(bug_report=report).values_list('scope_result', flat=True)) == ['indeterminate']
    assert report.admin_response == payload['admin_response']
    context.first.refresh_from_db()
    assert context.first.review_status == before_status
    assert RequirementReview.objects.count() == 0


def published_contract_reply(context):
    report = ticket(context)
    prepared = prepare(context, report, contract_id=context.contract.pk)
    response = evaluate(context, report, publish_payload(context, report, prepared, True, reply_payload(prepared)))
    return report, prepared, response


def test_signed_contract_reply_persists_private_provenance_for_administration(context):
    """Falla si una respuesta contractual pierde la procedencia privada administrativa."""
    report, prepared, response = published_contract_reply(context)
    stored = IssueResponse.objects.get(bug_report=report)
    admin_detail = api_for(context.admin).get(f'/api/accounts/projects/{context.project.pk}/bug-reports/{report.pk}/')

    assert response.status_code == 200
    assert stored.scope_result == 'within_scope'
    assert stored.review_evidence['private']['context_id'] == prepared['id']
    assert stored.review_evidence['private']['source_references']
    assert admin_detail.json()['responses'][0]['review_context_id'] == prepared['id']


def test_signed_contract_reply_hides_private_provenance_from_client(context):
    """Falla si una respuesta contractual expone fuentes privadas al cliente."""
    report, prepared, _ = published_contract_reply(context)
    client_detail = api_for(context.client).get(f'/api/accounts/projects/{context.project.pk}/bug-reports/{report.pk}/')

    assert client_detail.status_code == 200
    assert set(client_detail.json()['responses'][0]['review_evidence']) == {
        'scope_result', 'human_reviewed', 'contract_id', 'prepared_at', 'source_text_not_shared',
    }
    assert 'review_context_id' not in client_detail.json()['responses'][0]
    assert prepared['id'] not in str(client_detail.json())


@pytest.mark.parametrize('mutate', [unreviewed, forged_citation])
def test_invalid_review_publication_rolls_back_the_ticket(context, mutate):
    """Falla si publicar una revisión inválida cambia el ticket o inserta una respuesta."""
    report = ticket(context)
    prepared = prepare(context, report, contract_id=context.contract.pk)
    values = publish_payload(context, report, prepared, True, reply_payload(prepared))
    mutate(values)

    response = evaluate(context, report, values)

    report.refresh_from_db()
    assert response.status_code == 400
    assert report.version == 1
    assert report.admin_response == ''
    assert not IssueResponse.objects.filter(bug_report=report).exists()


@pytest.mark.parametrize('mutate', [stale_ticket, stale_workspace])
def test_stale_reply_version_rolls_back_the_ticket(context, mutate):
    """Falla si una versión vieja del ticket o del espacio publica una respuesta."""
    report = ticket(context)
    prepared = prepare(context, report, contract_id=context.contract.pk)
    values = publish_payload(context, report, prepared, True, reply_payload(prepared))
    mutate(context, values)

    response = evaluate(context, report, values)

    report.refresh_from_db()
    assert response.status_code == 409
    assert report.version == 1
    assert not IssueResponse.objects.filter(bug_report=report).exists()


def test_reply_context_cannot_publish_to_a_different_ticket(context):
    """Falla si un contexto preparado puede responder en otro ticket del proyecto."""
    prepared_for = ticket(context)
    destination = ticket(context, title='Another incident')
    prepared = prepare(context, prepared_for, contract_id=context.contract.pk)
    values = publish_payload(context, prepared_for, prepared, True, reply_payload(prepared))
    values['expected_version'] = destination.version
    values['contract_reply']['expected_ticket_version'] = destination.version

    response = evaluate(context, destination, values)

    destination.refresh_from_db()
    assert response.status_code == 400
    assert destination.version == 1
    assert not IssueResponse.objects.filter(bug_report=destination).exists()


def test_reply_context_rejects_another_administrator(context):
    """Falla si otro administrador puede compartir la preparación ajena."""
    report = ticket(context)
    prepared = prepare(context, report, contract_id=context.contract.pk)
    other = get_user_model().objects.create_user('other-reviewer', 'other-reviewer@example.test')
    UserProfile.objects.create(user=other, role='admin')

    response = evaluate(context, report, publish_payload(context, report, prepared, True, reply_payload(prepared)), actor=other)

    assert response.status_code == 400
    assert not IssueResponse.objects.filter(bug_report=report).exists()


def test_legacy_zero_version_previews_without_writing_a_response(context):
    """Falla si el ticket legado versión cero no puede preparar una revisión real."""
    report = ticket(context)
    report.version = 0
    report.save(update_fields=['version'])
    prepared = prepare(context, report, contract_id=context.contract.pk)

    result = preview(context, report, prepared)

    report.refresh_from_db()
    assert result['ticket_version'] == 0
    assert report.version == 0
    assert not IssueResponse.objects.filter(bug_report=report).exists()


def test_reply_publish_retry_keeps_a_single_response(context):
    """Falla si reintentar la misma publicación contractual duplica la respuesta."""
    report = ticket(context)
    prepared = prepare(context, report, contract_id=context.contract.pk)
    values = publish_payload(context, report, prepared, True, reply_payload(prepared))
    values['request_id'] = '40000000-0000-4000-8000-000000000009'

    first = evaluate(context, report, values)
    repeated = evaluate(context, report, values)

    assert first.status_code == 200
    assert repeated.status_code == 200
    assert IssueResponse.objects.filter(bug_report=report).count() == 1


def test_new_comment_invalidates_a_prepared_reply_without_a_ticket_version_change(context):
    """Falla si cambiar la conversación no invalida el hash del contexto preparado."""
    report = ticket(context)
    prepared = prepare(context, report, contract_id=context.contract.pk)
    values = publish_payload(context, report, prepared, True, reply_payload(prepared))
    from accounts.models import BugComment
    BugComment.objects.create(bug_report=report, user=context.client, content='A later observation.')

    response = evaluate(context, report, values)

    report.refresh_from_db()
    assert response.status_code == 409
    assert report.version == 1
    assert not IssueResponse.objects.filter(bug_report=report).exists()


@pytest.mark.parametrize('invoke', [client_prepare, client_context, client_source])
def test_client_cannot_access_private_reply_material(context, invoke):
    """Falla si el cliente puede preparar, leer contexto o descargar fuentes privadas."""
    report = ticket(context)
    prepared = prepare(context, report, contract_id=context.contract.pk)
    route = paths(context, report)
    client = api_for(context.client)
    response = invoke(client, route, context, report, prepared)

    assert response.status_code == 403


def test_change_request_reply_keeps_its_published_origin_without_conversion(context):
    """Falla si responder una ampliación cambia su guía publicada o la convierte en requisito."""
    source = make_requirement(context.stage, title='Change request source')
    request = issues.create_ticket(context.project.pk, context.client, 'change', {
        'title': 'Add export', 'module_or_screen': 'Reports', 'source_requirement_id': source.pk,
    })
    origin = (source.stage.publications.get().pk, request.issue_context.snapshot)
    approvals = (source.review_status, RequirementReview.objects.count())
    prepared = prepare(context, request, contract_id=context.contract.pk,
                       request_id='40000000-0000-4000-8000-000000000011', kind='change')
    values = publish_payload(context, request, prepared, True, reply_payload(prepared), kind='change')

    response = evaluate(context, request, values, kind='change')

    request.refresh_from_db()
    source.refresh_from_db()
    stored = IssueResponse.objects.get(change_request=request)
    assert response.status_code == 200
    assert (stored.scope_result, request.linked_requirement_id) == ('within_scope', None)
    assert (request.issue_context.publication_id, request.issue_context.snapshot) == origin
    assert (source.review_status, RequirementReview.objects.count()) == approvals
