"""Review-context envelope regressions for contextualized ticket decisions."""
import hashlib
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from pypdf import PdfWriter
from rest_framework.exceptions import APIException

from accounts.models import DeliveryPublication, Project, ProjectContract, UserProfile
from accounts.services import issue_reports as issues
from accounts.services.issue_review_context import build_ticket_review_input
from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement
from content.models import Document

pytestmark = pytest.mark.django_db


@pytest.fixture
def actors():
    user = get_user_model()
    client = user.objects.create_user(username='review-client', email='review-client@example.test')
    admin = user.objects.create_user(username='review-admin', email='review-admin@example.test', is_staff=True)
    outsider = user.objects.create_user(username='review-outsider', email='review-outsider@example.test')
    UserProfile.objects.create(user=client, role='client')
    UserProfile.objects.create(user=admin, role='admin')
    UserProfile.objects.create(user=outsider, role='client')
    return client, admin, outsider


@pytest.fixture
def project(actors):
    return Project.objects.create(name='Review context project', client=actors[0])


def create_bug(project, client, **values):
    return issues.create_ticket(project.pk, client, 'bug', {'title': 'Cannot save', **values})


def review_input(project, admin, ticket, *, request_id='30000000-0000-4000-8000-000000000001', contract_id=None):
    return build_ticket_review_input(
        project.pk, admin, 'bug', ticket.pk, ticket_version=ticket.version,
        request_id=request_id, contract_id=contract_id,
    )


def pdf_bytes():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(output)
    return output.getvalue()


def foreign_contract(project, actors, source):
    other = Project.objects.create(name='Other project', client=actors[2])
    return make_delivery_stage(other).phase.scope.contract


def incompatible_contract(project, actors, source):
    return ProjectContract.objects.create(
        project=project, key='incompatible', title='Incompatible',
        document=source.stage.phase.scope.contract.document,
    )


def test_review_input_isolates_public_ticket_conversation(project, actors):
    """Falla si el proveedor recibe notas internas o conversación de otro ticket."""
    ticket = create_bug(project, actors[0])
    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {'admin_response': 'Public diagnosis.'})
    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {
        'admin_response': 'Private stack trace.', 'is_internal': True,
    })
    issues.comment_ticket(project.pk, actors[0], 'bug', ticket.pk, {'content': 'Public follow-up.'})
    issues.comment_ticket(project.pk, actors[1], 'bug', ticket.pk, {
        'content': 'Private triage.', 'is_internal': True,
    })
    other_ticket = create_bug(project, actors[0], title='Other ticket')
    issues.evaluate_ticket(project.pk, actors[1], 'bug', other_ticket.pk, {'admin_response': 'Other diagnosis.'})
    ticket.refresh_from_db()

    result = review_input(project, actors[1], ticket)

    assert len(result['conversation']) == 3
    assert {item['source_type'] for item in result['conversation']} == {
        'bug_report', 'issue_response', 'bug_comment',
    }
    assert 'Public diagnosis.' in str(result['conversation'])
    assert 'Public follow-up.' in str(result['conversation'])
    assert 'Private stack trace.' not in str(result['conversation'])
    assert 'Private triage.' not in str(result['conversation'])
    assert 'Other diagnosis.' not in str(result['conversation'])


def test_review_input_keeps_frozen_origin_after_a_later_publication_round(project, actors):
    """Falla si una revisión reinterpreta el ticket con una ronda posterior."""
    source = make_requirement(make_delivery_stage(project), title='Original guide')
    original = source.stage.publications.get()
    ticket = create_bug(project, actors[0], source_requirement_id=source.pk)
    DeliveryPublication.objects.create(stage=source.stage, round=2, published_by=actors[1], payload={
        'title': 'Later stage',
        'requirements': [{'id': source.pk, 'title': 'Later guide', 'version': source.version + 1}],
    })

    result = review_input(project, actors[1], ticket)

    assert result['origin_context']['publication_id'] == original.pk
    assert result['origin_context']['requirement_title'] == 'Original guide'


def test_general_ticket_review_input_leaves_contract_indeterminate(project, actors):
    """Falla si un bug general infiere un contrato sólo porque el proyecto tiene uno."""
    stage = make_delivery_stage(project)
    ticket = create_bug(project, actors[0])

    result = review_input(project, actors[1], ticket)

    assert stage.phase.scope.contract_id
    assert result['origin_context']['origin_kind'] == 'general'
    assert result['applicable_contract'] is None


def test_review_input_accepts_the_explicit_contract_from_the_frozen_origin(project, actors):
    """Falla si una revisión rechaza el contrato exacto que congeló el ticket."""
    source = make_requirement(make_delivery_stage(project))
    ticket = create_bug(project, actors[0], source_requirement_id=source.pk)
    contract = source.stage.phase.scope.contract

    result = review_input(project, actors[1], ticket, contract_id=contract.pk)

    assert result['applicable_contract'] == {'id': contract.pk, 'version': contract.version}


@pytest.mark.parametrize('contract_factory', [foreign_contract, incompatible_contract])
def test_review_input_rejects_an_inapplicable_contract(project, actors, contract_factory):
    """Falla si una revisión puede sustituir el contrato que congeló el ticket."""
    source = make_requirement(make_delivery_stage(project))
    ticket = create_bug(project, actors[0], source_requirement_id=source.pk)
    contract = contract_factory(project, actors, source)

    with pytest.raises(APIException) as error:
        review_input(project, actors[1], ticket, contract_id=contract.pk)

    assert error.value.status_code == 400


def test_review_input_rejects_a_stale_ticket_version(project, actors):
    """Falla si una respuesta de revisión puede prepararse desde una versión antigua."""
    ticket = create_bug(project, actors[0])

    with pytest.raises(APIException) as error:
        build_ticket_review_input(
            project.pk, actors[1], 'bug', ticket.pk, ticket_version=ticket.version - 1,
            request_id='30000000-0000-4000-8000-000000000007',
        )

    assert error.value.status_code == 409


def test_review_input_rejects_a_client_actor(project, actors):
    """Falla si un cliente puede preparar la entrada interna del proveedor de revisión."""
    ticket = create_bug(project, actors[0])

    with pytest.raises(APIException) as error:
        build_ticket_review_input(
            project.pk, actors[0], 'bug', ticket.pk, ticket_version=ticket.version,
            request_id='30000000-0000-4000-8000-000000000008',
        )

    assert error.value.status_code == 403


def test_review_input_rejects_a_ticket_from_another_project(project, actors):
    """Falla si una revisión carga un ticket ajeno usando el proyecto solicitado."""
    ticket = create_bug(project, actors[0])
    other = Project.objects.create(name='Other project', client=actors[2])

    with pytest.raises(APIException) as error:
        build_ticket_review_input(
            other.pk, actors[1], 'bug', ticket.pk, ticket_version=ticket.version,
            request_id='30000000-0000-4000-8000-000000000009',
        )

    assert error.value.status_code == 404


def test_review_input_rejects_an_invalid_request_uuid(project, actors):
    """Falla si un identificador de revisión malformado llega al proveedor."""
    ticket = create_bug(project, actors[0])

    with pytest.raises(APIException) as error:
        build_ticket_review_input(
            project.pk, actors[1], 'bug', ticket.pk, ticket_version=ticket.version,
            request_id='not-a-uuid',
        )

    assert error.value.status_code == 400


def test_review_input_keeps_captured_attachment_metadata(project, actors):
    """Falla si la revisión usa el documento actual en vez de la evidencia histórica."""
    ticket = create_bug(project, actors[0])
    original_bytes = pdf_bytes()
    document = Document.objects.create(
        title='Original evidence', project=project, client_user=actors[0], created_by=actors[1],
    )
    document.generated_file.save('original.pdf', ContentFile(original_bytes))
    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {
        'admin_response': 'Evidence attached.', 'document_ids': [document.pk],
    })
    attachment_id = ticket.issue_responses.get().attachments.get().pk
    document.title = 'Changed source title'
    document.save(update_fields=['title'])
    document.generated_file.save('changed.pdf', ContentFile(pdf_bytes()))
    ticket.refresh_from_db()

    result = review_input(
        project, actors[1], ticket,
        request_id='30000000-0000-4000-8000-000000000010',
    )

    assert result['conversation'][1]['attachments'] == [{
        'attachment_id': attachment_id,
        'document_id': document.pk, 'title': 'Original evidence',
        'sha256': hashlib.sha256(original_bytes).hexdigest(),
    }]


def test_review_input_isolates_contract_selected_responses(project, actors):
    """Falla si una revisión contractual incluye respuestas de otro contrato."""
    ticket = create_bug(project, actors[0])
    document_a = Document.objects.create(
        title='Contract A', project=project, client_user=actors[0], created_by=actors[1],
    )
    document_b = Document.objects.create(
        title='Evidence B', project=project, client_user=actors[0], created_by=actors[1],
    )
    contract_a = ProjectContract.objects.create(
        project=project, key='contract-a', title='Contract A', document=document_a,
    )
    contract_b = ProjectContract.objects.create(
        project=project, key='contract-b', title='Contract B', document=document_b,
    )
    document_b.generated_file.save('evidence-b.pdf', ContentFile(pdf_bytes()))
    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {
        'admin_response': 'Response for contract A.', 'contract_id': contract_a.pk,
    })
    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {
        'admin_response': 'Response for contract B.', 'contract_id': contract_b.pk,
        'document_ids': [document_b.pk],
    })
    issues.comment_ticket(project.pk, actors[0], 'bug', ticket.pk, {'content': 'General follow-up.'})
    ticket.refresh_from_db()
    history_count = ticket.issue_events.count()

    result = review_input(
        project, actors[1], ticket,
        request_id='30000000-0000-4000-8000-000000000011', contract_id=contract_a.pk,
    )

    assert len(result['conversation']) == 3
    assert 'Response for contract A.' in str(result['conversation'])
    assert 'General follow-up.' in str(result['conversation'])
    assert 'Response for contract B.' not in str(result['conversation'])
    assert 'Evidence B' not in str(result['conversation'])
    assert result['legacy_response'] is None
    assert ticket.issue_events.count() == history_count


def test_review_input_keeps_change_request_conversation_separate_from_same_id_bug(project, actors):
    """Falla si el contexto de una solicitud de cambio toma datos de un bug con el mismo PK."""
    source = make_requirement(make_delivery_stage(project))
    bug = create_bug(project, actors[0], title='Bug with shared id')
    change = issues.create_ticket(project.pk, actors[0], 'change', {
        'title': 'Add export', 'module_or_screen': 'Reports', 'source_requirement_id': source.pk,
    })
    issues.comment_ticket(project.pk, actors[0], 'change', change.pk, {'content': 'Export CSV is required.'})
    change.refresh_from_db()

    result = build_ticket_review_input(
        project.pk, actors[1], 'change', change.pk, ticket_version=change.version,
        request_id='30000000-0000-4000-8000-000000000012',
    )

    assert bug.pk == change.pk
    assert result['ticket_version'] == change.version
    assert result['request_id'] == '30000000-0000-4000-8000-000000000012'
    assert result['conversation'][0]['source_type'] == 'change_request'
    assert result['conversation'][0]['actor_id'] == actors[0].pk
    assert result['conversation'][0]['report']['module_or_screen'] == 'Reports'
    assert result['conversation'][1]['source_type'] == 'change_request_comment'
    assert result['conversation'][1]['content'] == 'Export CSV is required.'
