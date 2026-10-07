"""Representative fixtures for real delivery browser tests, never production."""
import base64
import hashlib
import secrets
from contextlib import nullcontext
from unittest.mock import patch

from content.models import (
    BusinessProposal,
    Document,
    DocumentType,
    ProposalApprovalFile,
)
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import (
    Deliverable,
    DeliveryPhase,
    DeliveryScope,
    DeliveryStage,
    Project,
    ProjectContract,
    Requirement,
    UserProfile,
)
from accounts.models_delivery_notifications import DeliveryNotificationEvent
from accounts.services.tokens import get_tokens_for_user
from accounts.tests.delivery_authoring_helpers import docx_bytes, pdf_bytes


def guide(title):
    return {
        'role': 'Cliente', 'environment': 'Staging',
        'preparation': 'Iniciar sesión con la cuenta de prueba.',
        'data': 'Sucursal Norte y un registro preparado.',
        'steps': ['Abrir el registro preparado.', 'Confirmar la operación.'],
        'expected_result': title,
        'failure_signals': 'El registro no cambia o aparece un mensaje de error.',
    }


def confirmed_browser_source(project, admin, client, mode):
    """Keep synthetic originals under the same confirmation manifest as runtime."""
    formats = {
        'approval-source-docx': (
            'agreement.docx', docx_bytes,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ),
        'approval-source-pdf': ('agreement.pdf', pdf_bytes, 'application/pdf'),
        'approval-source-png': (
            'agreement.png',
            lambda: base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1EAAAAASUVORK5CYII='
            ),
            'image/png',
        ),
    }
    filename, make_bytes, content_type = formats[mode]
    raw = make_bytes()
    deliverable = Deliverable.objects.create(
        project=project, title='Paquete confirmado de prueba', uploaded_by=admin,
    )
    proposal = BusinessProposal.objects.create(
        title='Propuesta confirmada de prueba', client_name='Cliente Delivery',
        client=client.profile, status='accepted', deliverable=deliverable,
    )
    source = ProposalApprovalFile.objects.create(
        proposal=proposal, project=project, deliverable=deliverable,
        source_key='custom:0', title='Acuerdo original confirmado', document_type='contract',
        filename=filename, file=ContentFile(raw, name=filename), size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(), created_by=admin,
    )
    proposal.platform_approval_manifest = {
        'client_profile_id': client.profile.pk, 'project_id': project.pk,
        'files': [{'id': source.pk, 'source_key': source.source_key,
                   'sha256': source.sha256, 'size': source.size}],
    }
    proposal.save(update_fields=['platform_approval_manifest'])
    return {
        'id': source.pk, 'title': source.title, 'filename': filename,
        'size': len(raw), 'sha256': source.sha256, 'content_type': content_type,
        'original_base64': base64.b64encode(raw).decode('ascii'),
    }


def private_browser_resources(project, admin, *, suffix):
    """Upload real categorized resources and an older version through JWT APIs."""
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(admin)["access"]}')
    base = f'/api/accounts/projects/{project.pk}/deliverables/'
    resources = []
    for category, title in (
        ('contract', 'Contrato privado de prueba'),
        ('amendment', 'Otrosí privado de prueba'),
        ('legal_annex', 'Anexo legal privado de prueba'),
    ):
        original = pdf_bytes(f'Original private {category} version 1.')
        original_name = f'{category}-{suffix}-v1.pdf'
        created = api.post(base, {
            'title': title, 'category': category,
            'description': f'Recurso privado de la categoría {category}.',
            'file': SimpleUploadedFile(original_name, original, content_type='application/pdf'),
        }, format='multipart')
        if created.status_code != 201:
            raise RuntimeError(f'Private resource fixture failed: {created.data}')
        resource_id = created.data['id']
        current = original
        if category == 'contract':
            current = pdf_bytes('Original private contract version 2 with revised terms.')
            revised = api.post(base + f'{resource_id}/upload-version/', {
                'file': SimpleUploadedFile(
                    f'{category}-{suffix}-v2.pdf', current, content_type='application/pdf',
                ),
            }, format='multipart')
            if revised.status_code != 201:
                raise RuntimeError(f'Private version fixture failed: {revised.data}')
        detail = api.get(base + f'{resource_id}/')
        if detail.status_code != 200:
            raise RuntimeError(f'Private resource detail failed: {detail.data}')
        first = next(row for row in detail.data['versions'] if row['version_number'] == 1)
        resources.append({
            **dict(detail.data),
            'expected_current': {
                'file_name': detail.data['file_name'], 'file_url': detail.data['file_url'],
                'sha256': hashlib.sha256(current).hexdigest(),
                'original_base64': base64.b64encode(current).decode('ascii'),
            },
            'expected_previous': {
                'id': first['id'], 'version_number': 1,
                'file_name': first['file_name'], 'file_url': first['file_url'],
                'sha256': hashlib.sha256(original).hexdigest(),
                'original_base64': base64.b64encode(original).decode('ascii'),
            },
        })
    return resources


def create_browser_fixture(key, *, mode=None):
    """Create independent projects; publication passes through the real API."""
    suffix = secrets.token_hex(6)
    password = secrets.token_urlsafe(24)
    User = get_user_model()
    admin = User.objects.create_user(
        username=f'admin-{suffix}@example.com', email=f'admin-{suffix}@example.com',
        password=password, first_name='Equipo', last_name='Delivery', is_staff=True,
    )
    UserProfile.objects.update_or_create(
        user=admin, defaults={'role': UserProfile.ROLE_ADMIN,
                             'is_onboarded': True, 'profile_completed': True,
                             'email_verified': True},
    )
    client = User.objects.create_user(
        username=f'client-{suffix}@example.com', email=f'client-{suffix}@example.com',
        password=password, first_name='Cliente', last_name='Delivery',
    )
    UserProfile.objects.update_or_create(
        user=client, defaults={'role': UserProfile.ROLE_CLIENT, 'created_by': admin,
                              'is_onboarded': True, 'profile_completed': True,
                              'email_verified': True, 'company_name': f'Cliente {key}'},
    )
    project = Project.objects.create(name=f'Delivery {key}', client=client)
    approval_source = (
        confirmed_browser_source(project, admin, client, mode)
        if mode in {'approval-source-docx', 'approval-source-pdf', 'approval-source-png'}
        else None
    )
    document_type, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown'},
    )
    contract_text = '# Contrato\nAlcance acordado para las pruebas.'
    if mode == 'role-guide':
        contract_text += (
            '\n\nEl Operador de inventario puede consultar el inventario de su '
            'sucursal con una cuenta habilitada. No puede modificar registros '
            'de otras sucursales.'
        )
    contract_document = Document.objects.create(
        document_type=document_type, title=f'Contrato firmado {key}',
        content_markdown=contract_text,
        project=project, client_user=client, requires_signature=True,
        signed_at=timezone.now(), signed_by=client, signature_name='Cliente Delivery',
        is_client_visible=True,
    )
    contract = ProjectContract.objects.create(
        project=project, key=f'contract-{suffix}', title=f'Contrato {key}',
        document=contract_document, client_visible=True,
    )
    scope = DeliveryScope.objects.create(
        contract=contract, key='agreed-scope', title='Alcance acordado',
        description='Probar inventario y notificaciones.',
    )
    phase = DeliveryPhase.objects.create(scope=scope, key='phase-1-5', title='Fase 1.5')
    stage = DeliveryStage.objects.create(
        phase=phase, key='stage-review', title='Etapa de validación',
        description='Revisar los resultados de los casos preparados.',
    )
    transfer = Requirement.objects.create(
        stage=stage, key='transfer', title='Traslado entre sucursales',
        guide=guide('La sucursal de destino muestra el traslado.'), order=1,
    )
    mail = Requirement.objects.create(
        stage=stage, key='daily-mail', title='Recepción del correo diario',
        guide=guide('El correo llega con las cantidades esperadas.'), order=2,
    )
    hidden = DeliveryStage.objects.create(
        phase=phase, key='internal-draft', title='Borrador privado del equipo', order=2,
    )
    Requirement.objects.create(
        stage=hidden, key='secret-case', title='Caso privado nunca publicado',
        guide=guide('Resultado privado'),
    )
    api = APIClient()
    api.force_authenticate(admin)
    base = f'/api/accounts/projects/{project.id}/delivery/'
    workspace = api.get(base)
    if workspace.status_code != 200:
        raise RuntimeError(f'Fixture overview failed: {workspace.data}')
    if mode in {'closure-approved', 'closure-smtp-failure'}:
        public_document = Document.objects.create(
            document_type=document_type, title='Guía pública del cierre',
            content_markdown='# Guía pública\nValidar el traslado entre sucursales.',
            project=project, client_user=client, is_client_visible=True,
        )
        linked = api.post(base + 'documents/', {
            'expected_version': workspace.data['version'], 'level': 'stage',
            'target_id': stage.pk, 'document_id': public_document.pk,
        }, format='json')
        if linked.status_code not in (200, 201):
            raise RuntimeError(f'Fixture document failed: {linked.data}')
        workspace = api.get(base)
    # Reject only the SMTP boundary; the publication, snapshot and persisted
    # failed attempt still pass through the production API and gateway.
    rejection = (
        patch('accounts.services.delivery_notifications.EmailMultiAlternatives.send', return_value=0)
        if mode in {'notice-failed', 'notice-smtp-failure'} else nullcontext()
    )
    with rejection:
        publication = api.post(
            base + f'stages/{stage.id}/publish/',
            {'expected_version': workspace.data['version'], 'request_id': f'publish-{suffix}'},
            format='json',
        )
    if publication.status_code not in (200, 201):
        raise RuntimeError(f'Fixture publication failed: {publication.data}')
    if mode in {'closure-approved', 'closure-smtp-failure'}:
        api.force_authenticate(client)
        reviewed = api.post(base + f'stages/{stage.pk}/review/', {
            'expected_version': publication.data['version'], 'request_id': f'close-{suffix}',
            'decisions': [
                {'requirement_id': item.pk, 'version': item.version, 'decision': 'approved'}
                for item in (transfer, mail)
            ],
            'message': 'Conformidad registrada desde la revisión.',
        }, format='json')
        if reviewed.status_code != 200:
            raise RuntimeError(f'Fixture approval failed: {reviewed.data}')
    result = {
        'fixture_key': key,
        'project': {'id': project.id, 'name': project.name},
        'contract_id': contract.id, 'scope_id': scope.id, 'phase_id': phase.id,
        'stage_id': stage.id, 'hidden_stage_id': hidden.id,
        'requirement_ids': [transfer.id, mail.id],
        'contract_document_id': contract_document.id,
        'admin': {'email': admin.email, 'password': password},
        'client': {'email': client.email, 'password': password},
    }
    if approval_source is not None:
        result['approval_source'] = approval_source
    if mode == 'private-resources':
        result['resources'] = private_browser_resources(project, admin, suffix=suffix)
        foreign = User.objects.create_user(
            username=f'foreign-{suffix}@example.com', email=f'foreign-{suffix}@example.com',
            password=password, first_name='Otro cliente', last_name='Recursos',
        )
        UserProfile.objects.update_or_create(user=foreign, defaults={
            'role': UserProfile.ROLE_CLIENT, 'created_by': admin, 'is_onboarded': True,
            'profile_completed': True, 'email_verified': True,
        })
        result['foreign_client'] = {'email': foreign.email, 'password': password}
    if mode in {'notice-failed', 'notice-smtp-failure'}:
        event = DeliveryNotificationEvent.objects.get(project=project)
        if event.status != 'failed' or event.attempts.count() != 1:
            raise RuntimeError('Fixture notice did not retain its rejected transport')
        result['notice'] = {
            'id': str(event.pk), 'subject': event.subject,
            'recipients': event.recipients, 'text_body': event.text_body,
            'status': event.status, 'version': event.version,
        }
    return result
