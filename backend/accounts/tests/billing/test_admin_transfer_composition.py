"""Django Admin composes financial, delivery and ticket transfer boundaries."""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from accounts.admin import ProjectAdmin
from accounts.models import (
    BugReport,
    ChangeRequest,
    DeliveryMessage,
    Project,
    ProjectContract,
    UserProfile,
)
from content.admin import admin_site
from content.models import AccountingChangeLog, Document, EntityHistory, EntityRevision
from content.services.document_type_utils import get_collection_account_document_type


User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def destination_client():
    user = User.objects.create_user(
        username='admin-transfer-destination@example.test',
        email='admin-transfer-destination@example.test',
        password='pass12345',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
    return user


@pytest.fixture
def administrator():
    user = User.objects.create_superuser(
        username='admin-transfer-operator',
        email='admin-transfer-operator@example.test',
        password='pass12345',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN)
    return user


def admin_post_data(project, client):
    return {
        'name': project.name,
        'description': project.description,
        'client': str(client.pk),
        'status': project.status,
        'progress': str(project.progress),
        'start_date': '',
        'estimated_end_date': '',
        'hosting_start_date': '',
        'payment_milestones': '[]',
        'hosting_tiers': '[]',
        'production_url': '',
        'staging_url': '',
        'repository_url': '',
        '_save': 'Save',
    }


def admin_request(user, project, client):
    request = RequestFactory().post(
        f'/admin/accounts/project/{project.pk}/change/', admin_post_data(project, client),
    )
    request.user = user
    SessionMiddleware(lambda request: None).process_request(request)
    request.session.save()
    request._dont_enforce_csrf_checks = True
    setattr(request, '_messages', FallbackStorage(request))
    return request


def public_delivery_message(project, actor):
    return DeliveryMessage.objects.create(
        project=project,
        level='project',
        target_id=project.pk,
        actor=actor,
        message='El cliente anterior confirmó esta entrega.',
        is_internal=False,
    )


def archived_bug(project, actor):
    return BugReport.objects.create(
        project=project,
        reported_by=actor,
        title='Incidencia archivada del cliente anterior',
        is_archived=True,
    )


def staff_change_request(project, actor):
    return ChangeRequest.objects.create(
        project=project,
        created_by=actor,
        title='Solicitud creada por el equipo',
    )


def unsigned_contract(project):
    document = Document.objects.create(
        title='Borrador contractual interno', project=project, client_user=project.client,
    )
    return ProjectContract.objects.create(
        project=project,
        key='unsigned-admin-transfer',
        title='Contrato sin firma',
        document=document,
    )


def issued_account(project):
    return Document.objects.create(
        title='Cuenta emitida',
        document_type=get_collection_account_document_type(),
        commercial_status=Document.CommercialStatus.ISSUED,
        public_number='PA-ADMIN-COMPOSITION-001',
        project=project,
        client_user=project.client,
        total=Decimal('120000'),
    )


class LateDeliveryProjectAdmin(ProjectAdmin):
    """Creates public delivery history after the form validates."""

    def save_form(self, request, form, change):
        obj = super().save_form(request, form, change)
        if change:
            public_delivery_message(Project.objects.get(pk=obj.pk), request.user)
        return obj


def test_admin_post_rejects_public_delivery_history(project, destination_client, administrator):
    """Falla si el Admin traslada al proyecto aunque la entrega pública conserva al cliente anterior."""
    public_delivery_message(project, administrator)

    response = ProjectAdmin(Project, admin_site).changeform_view(
        admin_request(administrator, project, destination_client), str(project.pk),
    )

    assert response.status_code == 200
    assert 'conserva entregas, firmas, fuentes o conversaciones' in response.rendered_content
    assert Project.objects.get(pk=project.pk).client_id != destination_client.pk


@pytest.mark.parametrize('history_builder', [archived_bug, staff_change_request])
def test_admin_post_rejects_ticket_history(project, destination_client, administrator, history_builder):
    """Falla si un ticket archivado o creado por staff deja de proteger a su cliente histórico."""
    history_builder(project, administrator)

    response = ProjectAdmin(Project, admin_site).changeform_view(
        admin_request(administrator, project, destination_client), str(project.pk),
    )

    assert response.status_code == 200
    assert 'conserva bugs o solicitudes' in response.rendered_content
    assert Project.objects.get(pk=project.pk).client_id != destination_client.pk


def test_admin_post_keeps_same_owner_with_history(project, administrator):
    """Falla si guardar al mismo dueño se bloquea por hechos que no cambian de destinatario."""
    public_delivery_message(project, administrator)
    archived_bug(project, administrator)

    response = ProjectAdmin(Project, admin_site).changeform_view(
        admin_request(administrator, project, project.client), str(project.pk),
    )

    assert response.status_code == 302
    assert Project.objects.get(pk=project.pk).client_id == project.client_id


def test_admin_post_transfers_empty_project(project, destination_client, administrator):
    """Falla si el Admin rechaza un traslado de proyecto que no tiene historia financiera ni cliente."""
    response = ProjectAdmin(Project, admin_site).changeform_view(
        admin_request(administrator, project, destination_client), str(project.pk),
    )

    assert response.status_code == 302
    assert Project.objects.get(pk=project.pk).client_id == destination_client.pk


def test_admin_post_transfers_nonpublic_delivery_draft(project, destination_client, administrator):
    """Falla si una nota interna o contrato sin firma congela un traslado todavía permitido."""
    DeliveryMessage.objects.create(
        project=project,
        level='project',
        target_id=project.pk,
        actor=administrator,
        message='Nota interna sin publicar.',
        is_internal=True,
    )
    unsigned_contract(project)

    response = ProjectAdmin(Project, admin_site).changeform_view(
        admin_request(administrator, project, destination_client), str(project.pk),
    )

    assert response.status_code == 302
    assert Project.objects.get(pk=project.pk).client_id == destination_client.pk


def test_admin_post_rolls_back_late_delivery_history(project, destination_client, administrator):
    """Falla si historia pública creada tras clean deja cambio, log o fila parcial al rechazar save."""
    before = (AccountingChangeLog.objects.count(), EntityHistory.objects.count(), EntityRevision.objects.count())

    response = LateDeliveryProjectAdmin(Project, admin_site).changeform_view(
        admin_request(administrator, project, destination_client), str(project.pk),
    )

    assert response.status_code == 200
    assert 'conserva entregas, firmas, fuentes o conversaciones' in response.rendered_content
    assert Project.objects.get(pk=project.pk).client_id != destination_client.pk
    assert not DeliveryMessage.objects.filter(message='El cliente anterior confirmó esta entrega.').exists()
    assert (AccountingChangeLog.objects.count(), EntityHistory.objects.count(), EntityRevision.objects.count()) == before


def test_admin_post_displays_financial_conflict_before_other_history(
    project, destination_client, administrator,
):
    """Falla si el error visible omite la historia financiera cuando también existen entrega y tickets."""
    issued_account(project)
    public_delivery_message(project, administrator)
    archived_bug(project, administrator)

    response = ProjectAdmin(Project, admin_site).changeform_view(
        admin_request(administrator, project, destination_client), str(project.pk),
    )

    assert response.status_code == 200
    assert 'historia financiera' in response.rendered_content
    assert Project.objects.get(pk=project.pk).client_id != destination_client.pk
