"""REST options retain public historical context without requiring a guide."""
from copy import deepcopy

import pytest
from rest_framework.test import APIClient

from accounts.models import (
    BugReport, DeliveryPublication, DeliveryStage, IssueEvent,
    Project, ProjectContract, Requirement,
)
from accounts.services import issue_reports as issues
from accounts.tests._issue_evidence_helpers import (
    context as context, evidence_document, memory_only_mail as memory_only_mail,
)
from accounts.tests.delivery_helpers import GUIDE, publish
from content.models import Document

pytestmark = pytest.mark.django_db


def options_url(context):
    return f'/api/accounts/projects/{context.project.pk}/issue-reports/context-options/'


def api_for(actor):
    api = APIClient()
    api.force_authenticate(user=actor)
    return api


def private_contract(context):
    document = evidence_document(context, title='Contrato privado')
    return ProjectContract.objects.create(
        project=context.project, document=document, key='private-contract',
        title='Contrato privado', client_visible=False,
    )


@pytest.mark.parametrize('actor_name,status', [
    ('client', 200), ('admin', 200), ('outsider', 404), ('anonymous', 401),
])
def test_options_enforce_project_membership(context, actor_name, status):
    """Falla si las opciones de un proyecto quedan abiertas a otro cliente o anónimo."""
    actors = {'client': context.client, 'admin': context.admin,
              'outsider': context.outsider, 'anonymous': None}
    api = api_for(actors[actor_name])

    response = api.get(options_url(context))

    assert response.status_code == status


def test_general_project_options_do_not_require_publication(context):
    """Falla si abrir el reporte general exige una entrega o crea historia auxiliar."""
    api = api_for(context.client)

    response = api.get(options_url(context))

    assert response.status_code == 200
    assert response.data['requirements'] == []
    assert response.data['scope_review_available'] is False
    assert IssueEvent.objects.count() == 0


@pytest.mark.parametrize('query,field', [
    ({'ticket_id': 1}, 'kind'),
    ({'source_publication_id': 1}, 'source_requirement_id'),
])
def test_incomplete_option_context_is_rejected(context, query, field):
    """Falla si una referencia parcial de ticket/publicación se interpreta en otro contexto."""
    api = api_for(context.client)

    response = api.get(options_url(context), query)

    assert response.status_code == 400
    assert field in response.data


def test_options_return_published_requirement_hierarchy(context):
    """Falla si el formulario pierde fase, etapa, versión o ronda de la guía pública."""
    publish(context)
    publication = context.stage.publications.get()
    api = api_for(context.client)

    response = api.get(options_url(context))

    assert response.status_code == 200
    first = response.data['requirements'][0]
    expected = {
        'id': context.first.pk, 'contract_id': context.contract.pk,
        'scope_id': context.scope.pk, 'phase_id': context.phase.pk,
        'stage_id': context.stage.pk, 'source_publication_id': publication.pk,
        'source_requirement_version': context.first.version, 'publication_round': 1,
    }
    assert {key: first[key] for key in expected} == expected


def test_draft_requirement_is_absent_from_report_options(context):
    """Falla si reportar un bug hace visible una guía editorial todavía no publicada."""
    publish(context)
    draft = DeliveryStage.objects.create(phase=context.phase, key='draft-stage', title='Borrador')
    Requirement.objects.create(stage=draft, key='draft-guide', title='Guía privada', guide=GUIDE)
    api = api_for(context.client)

    response = api.get(options_url(context))

    assert response.status_code == 200
    assert [row['id'] for row in response.data['requirements']] == [context.first.pk, context.second.pk]


def test_explicit_original_round_replaces_the_latest_option(context):
    """Falla si responder desde una entrega antigua autocompleta la guía de una ronda posterior."""
    publish(context)
    original = context.stage.publications.get()
    later = deepcopy(original.payload)
    later['requirements'][0]['title'] = 'Guía de la ronda nueva'
    later['requirements'][0]['version'] = context.first.version + 1
    DeliveryPublication.objects.create(stage=context.stage, round=2, published_by=context.admin, payload=later)
    api = api_for(context.client)

    response = api.get(options_url(context), {
        'source_requirement_id': context.first.pk, 'source_publication_id': original.pk,
    })

    assert response.status_code == 200
    first = response.data['requirements'][0]
    assert first['title'] == 'Guardar registro'
    assert first['source_publication_id'] == original.pk
    assert first['source_requirement_version'] == 1
    assert first['publication_round'] == 1
    assert [row['id'] for row in response.data['requirements']] == [context.first.pk, context.second.pk]


def test_client_options_hide_private_contracts(context):
    """Falla si el selector del cliente revela contratos que no se le han publicado."""
    private_contract(context)
    api = api_for(context.client)

    response = api.get(options_url(context))

    assert response.status_code == 200
    assert response.data['contracts'] == [{'id': context.contract.pk, 'title': 'Contrato original'}]


def test_admin_options_include_private_contracts(context):
    """Falla si el equipo no puede seleccionar un contrato privado para fundamentar la respuesta."""
    hidden = private_contract(context)
    api = api_for(context.admin)

    response = api.get(options_url(context))

    assert response.status_code == 200
    assert response.data['contracts'] == [
        {'id': context.contract.pk, 'title': 'Contrato original'},
        {'id': hidden.pk, 'title': 'Contrato privado'},
    ]
    assert response.data['scope_review_available'] is True


def test_foreign_contract_option_is_rejected(context):
    """Falla si se mezcla otro proyecto al escoger el contrato aplicable de un bug general."""
    other = Project.objects.create(name='Otro proyecto', client=context.client)
    source = Document.objects.create(title='Otro contrato', project=other, client_user=context.client)
    contract = ProjectContract.objects.create(
        project=other, document=source, key='other', title='Otro contrato', client_visible=True,
    )
    api = api_for(context.admin)

    response = api.get(options_url(context), {'contract_id': contract.pk})

    assert response.status_code == 400
    assert response.data['code'] == 'issue_contract_context'


def test_foreign_ticket_option_is_rejected(context):
    """Falla si consultar evidencia de un ticket acepta el ID de un proyecto diferente."""
    other = Project.objects.create(name='Otro proyecto', client=context.client)
    ticket = BugReport.objects.create(project=other, reported_by=context.client, title='Bug de otro proyecto')
    api = api_for(context.admin)

    response = api.get(options_url(context), {'kind': 'bug', 'ticket_id': ticket.pk})

    assert response.status_code == 404


def test_explicit_contract_makes_its_document_available(context):
    """Falla si un bug general pierde el documento del contrato escogido explícitamente."""
    ticket = issues.create_ticket(context.project.pk, context.client, 'bug', {'title': 'Bug general'})
    api = api_for(context.admin)

    response = api.get(options_url(context), {
        'kind': 'bug', 'ticket_id': ticket.pk, 'contract_id': context.contract.pk,
    })

    assert response.status_code == 200
    assert response.data['documents'] == [{'id': context.document.pk, 'title': 'Contrato firmado'}]
    assert ticket.issue_context.snapshot['origin_kind'] == 'general'


@pytest.mark.parametrize('extra', [
    {'source_publication_id': 123}, {'source_requirement_version': 1},
])
def test_general_report_rejects_orphan_source_metadata(context, extra):
    """Falla si se conserva una ronda/versión sin el requerimiento al que pertenece."""
    api = api_for(context.client)

    response = api.post(f'/api/accounts/projects/{context.project.pk}/bug-reports/',
                        {'title': 'General', **extra}, format='json')

    assert response.status_code == 400
    assert response.data['code'] == 'issue_source_required'
    assert BugReport.objects.count() == 0


def test_unpublished_source_cannot_be_used_for_a_ticket(context):
    """Falla si la referencia a una guía sin publicar se convierte en origen de un ticket."""
    api = api_for(context.client)

    response = api.post(f'/api/accounts/projects/{context.project.pk}/bug-reports/', {
        'title': 'Desde borrador', 'source_requirement_id': context.first.pk,
    }, format='json')

    assert response.status_code == 400
    assert response.data['source_requirement_id'] == [
        'Requerimiento no encontrado o no está publicado para este proyecto.',
    ]
    assert BugReport.objects.count() == 0


def test_private_contract_source_cannot_be_reported_by_client(context):
    """Falla si conocer un ID de guía expone el contrato privado del equipo."""
    publish(context)
    context.contract.client_visible = False
    context.contract.save(update_fields=['client_visible'])
    api = api_for(context.client)

    response = api.post(f'/api/accounts/projects/{context.project.pk}/bug-reports/', {
        'title': 'Desde contrato privado', 'source_requirement_id': context.first.pk,
    }, format='json')

    assert response.status_code == 400
    assert response.data['source_requirement_id'] == [
        'Requerimiento no encontrado o no está publicado para este proyecto.',
    ]
    assert BugReport.objects.count() == 0


def test_private_publication_cannot_be_selected_in_options(context):
    """Falla si la URL de una ronda permite leer el contrato que ahora es privado."""
    publish(context)
    publication = context.stage.publications.get()
    context.contract.client_visible = False
    context.contract.save(update_fields=['client_visible'])
    api = api_for(context.client)

    response = api.get(options_url(context), {
        'source_requirement_id': context.first.pk, 'source_publication_id': publication.pk,
    })

    assert response.status_code == 400
    assert response.data['code'] == 'issue_source_invalid'
