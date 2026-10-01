"""Representative fixtures for real delivery browser tests, never production."""
import secrets

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import (
    DeliveryPhase, DeliveryScope, DeliveryStage, Project, ProjectContract,
    Requirement, UserProfile,
)
from content.models import Document, DocumentType


def guide(title):
    return {
        'role': 'Cliente', 'environment': 'Staging',
        'preparation': 'Iniciar sesión con la cuenta de prueba.',
        'data': 'Sucursal Norte y un registro preparado.',
        'steps': ['Abrir el registro preparado.', 'Confirmar la operación.'],
        'expected_result': title,
        'failure_signals': 'El registro no cambia o aparece un mensaje de error.',
    }


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
    document_type, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown'},
    )
    contract_document = Document.objects.create(
        document_type=document_type, title=f'Contrato firmado {key}',
        content_markdown='# Contrato\nAlcance acordado para las pruebas.',
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
    return {
        'project': {'id': project.id, 'name': project.name},
        'contract_id': contract.id, 'scope_id': scope.id, 'phase_id': phase.id,
        'stage_id': stage.id, 'hidden_stage_id': hidden.id,
        'requirement_ids': [transfer.id, mail.id],
        'contract_document_id': contract_document.id,
        'admin': {'email': admin.email, 'password': password},
        'client': {'email': client.email, 'password': password},
    }
