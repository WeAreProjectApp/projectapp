"""The complete workspace preserves visibility, evidence and bounded read cost."""
import io
import hashlib
import json

import pytest
from django.core.files.base import ContentFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from reportlab.pdfgen.canvas import Canvas

from accounts.models import DeliveryDocumentLink, DeliveryDocumentSnapshot, DeliveryMessage, DeliveryPhase, Requirement
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import GUIDE, build_delivery_context, decisions, publish, version
from content.models import Document

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    return build_delivery_context()


def extension(context):
    return {'schema_version': 1, 'scopes': [{
        'key': context.scope.key, 'title': context.scope.title, 'contract_id': context.contract.pk,
        'phases': [{'key': context.phase.key, 'title': context.phase.title, 'stages': [{
            'key': 'next-stage', 'title': 'Preparar la próxima revisión', 'requirements': [{
                'key': 'next-case', 'title': 'Comprobar el resumen', 'guide': GUIDE,
            }],
        }]}],
    }]}


def test_json_extends_published_ancestors_with_drafts(context):
    publish(context)
    phase_version = context.phase.version

    delivery.import_payload(context.project.pk, context.admin, extension(context), version(context), apply=True, request_id='extend')

    requirement = Requirement.objects.get(key='next-case')
    context.phase.refresh_from_db()
    assert requirement.stage.phase_id == context.phase.pk
    assert requirement.review_status == 'pending'
    assert requirement.stage.editorial_status == 'draft'
    assert context.phase.version == phase_version


def test_json_cannot_extend_a_closed_phase(context):
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk, decisions(context, (context.first, 'approved'), (context.second, 'approved')))

    with pytest.raises(ValidationError, match='fase aprobada'):
        delivery.import_payload(context.project.pk, context.admin, extension(context), version(context), apply=True, request_id='extend')

    assert not Requirement.objects.filter(key='next-case').exists()


def test_private_phase_prevents_scope_closure(context):
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk, decisions(context, (context.first, 'approved'), (context.second, 'approved')))
    DeliveryPhase.objects.create(scope=context.scope, key='next-phase', title='Fase interna pendiente')

    workspace = delivery.overview(context.project.pk, context.client)

    assert workspace['scopes'][0]['status'] == 'in_review'
    assert len(workspace['scopes'][0]['phases']) == 1
    assert 'Fase interna pendiente' not in json.dumps(workspace)


def test_prompt_uses_signed_content_after_source_edit(context):
    publish(context)
    context.document.content_markdown = '# Un borrador que el cliente no firmó'
    context.document.save(update_fields=['content_markdown'])

    prompt = delivery.authoring_prompt(context.project.pk, context.admin)['prompt']

    assert 'Alcance acordado.' in prompt
    assert 'Un borrador que el cliente no firmó' not in prompt


@pytest.mark.parametrize('route, expected_content', [('list', 'Guía publicada'.encode()), ('pdf', b'%PDF-')])
def test_archived_source_keeps_published_evidence(context, route, expected_content):
    document = Document.objects.create(title='Guía publicada', project=context.project, client_user=context.client, content_markdown='# Guía original', is_client_visible=True)
    delivery.link_document(context.project.pk, context.admin, {'expected_version': 0, 'level': 'stage', 'target_id': context.stage.pk, 'document_id': document.pk})
    publish(context)
    document.is_archived = True
    document.save(update_fields=['is_archived'])
    api = APIClient()
    api.force_authenticate(context.client)
    paths = {'list': '/api/accounts/documents/', 'pdf': f'/api/accounts/documents/{document.uuid}/pdf/'}

    response = api.get(paths[route])

    assert response.status_code == 200
    assert expected_content in response.content


def attach_read_samples(context, count, start=0):
    publication = context.stage.publications.first()
    stream = io.BytesIO()
    canvas = Canvas(stream)
    canvas.drawString(50, 700, 'Evidence for read scalability')
    canvas.save()
    for position in range(start, start + count):
        document = Document.objects.create(title=f'Evidence {position}', project=context.project, client_user=context.client, is_client_visible=True)
        link = DeliveryDocumentLink.objects.create(project=context.project, document=document, level='stage', stage=context.stage, created_by=context.admin)
        snapshot = DeliveryDocumentSnapshot(publication=publication, link=link, title=document.title, sha256=hashlib.sha256(stream.getvalue()).hexdigest())
        snapshot.file.save('evidence.pdf', ContentFile(stream.getvalue()), save=True)
        message = DeliveryMessage.objects.create(project=context.project, actor=context.admin, level='stage', target_id=context.stage.pk, message=f'Read sample {position}')
        message.documents.add(document)
        message.requirements.add(context.first)


@pytest.mark.parametrize('role', ['admin', 'client'])
def test_workspace_queries_do_not_grow_per_attachment(context, role):
    """Extra documents and replies must remain visible without one query each."""
    publish(context)
    actor = getattr(context, role)
    attach_read_samples(context, 2)
    delivery.overview(context.project.pk, actor)
    with CaptureQueriesContext(connection) as small_queries:
        delivery.overview(context.project.pk, actor)
    attach_read_samples(context, 18, start=2)

    with CaptureQueriesContext(connection) as large_queries:
        workspace = delivery.overview(context.project.pk, actor)

    stage = workspace['scopes'][0]['phases'][0]['stages'][0]
    assert len(stage['documents']) == 20
    assert len(stage['messages']) == 20
    assert len(large_queries) <= len(small_queries)
    assert len(json.dumps(workspace).encode()) < 256 * 1024
