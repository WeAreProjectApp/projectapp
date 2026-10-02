"""Transfer rejections leave approved client access and its sources untouched."""
from decimal import Decimal

import pytest
from content.admin import admin_site
from content.models import AccountingChangeLog, Document, EntityHistory, EntityRevision
from content.services.document_type_utils import get_collection_account_document_type
from content.services.project_service import MODE_MOVE, change_client_apply
from django.test import RequestFactory
from rest_framework.exceptions import APIException

from accounts.admin import ProjectAdmin
from accounts.forms_billing import BillingProjectAdminConflict
from accounts.models import BugReport, DeliveryMessage, Project, ProjectAdminAccess
from accounts.models_project_client_access import (
    ProjectClientAccessEvent,
    ProjectClientAccessPolicy,
)
from accounts.services import project_client_access as access
from accounts.tests.project_collaboration_helpers import context, enable, sources

pytestmark = pytest.mark.django_db


def delivery_history(c):
    """Freeze public delivery history under its original project recipient."""
    DeliveryMessage.objects.create(
        project=c.project, level='project', target_id=c.project.pk, actor=c.client,
        message='Entrega revisada por su cliente original.', is_internal=False,
    )


def issue_history(c):
    """Preserve an archived issue as protected client history."""
    BugReport.objects.create(
        project=c.project, reported_by=c.client, title='Historia archivada', is_archived=True,
    )


def financial_history(c):
    """Combine issued billing with delivery and issue history."""
    # Coexisting history must not change the first, financial rejection.
    delivery_history(c)
    issue_history(c)
    Document.objects.create(
        title='Cuenta ya emitida', document_type=get_collection_account_document_type(),
        commercial_status=Document.CommercialStatus.ISSUED,
        public_number='P4-TRANSFER-001', total=Decimal('120000'),
        project=c.project, client_user=c.client,
    )


def approved_project():
    """Create an owner with explicitly approved URL and password fields."""
    c = context()
    sources(c)
    enable(c, 'production.site_url', 'production.admin_password')
    return c


def transfer_in_admin(c):
    """Exercise the actual Admin writer with a simultaneous URL change."""
    project = Project.objects.get(pk=c.project.pk)
    project.client_id = c.other.pk
    project.production_url = 'https://rejected.example.test/'
    request = RequestFactory().post('/admin/accounts/project/')
    request.user = c.admin
    ProjectAdmin(Project, admin_site).save_model(request, project, None, change=True)


def transfer_in_panel_service(c):
    """Exercise the shared Panel project transfer service."""
    change_client_apply(c.project, c.other.profile, MODE_MOVE, c.admin)


def unchanged_state(c):
    """Snapshot observable persisted state, including value-free audit rows."""
    return {
        'project': Project.objects.values().get(pk=c.project.pk),
        'sources': list(ProjectAdminAccess.objects.filter(project=c.project).values().order_by('pk')),
        'policy': ProjectClientAccessPolicy.objects.values().get(project=c.project),
        'projection': access.client_access(c.project.pk, c.client),
        'access_events': list(ProjectClientAccessEvent.objects.filter(project=c.project).values().order_by('pk')),
        'finances': list(Document.objects.filter(project=c.project).values().order_by('pk')),
        'delivery': list(DeliveryMessage.objects.filter(project=c.project).values().order_by('pk')),
        'issues': list(BugReport.objects.filter(project=c.project).values().order_by('pk')),
        'audit_counts': (
            AccountingChangeLog.objects.count(), EntityHistory.objects.count(), EntityRevision.objects.count(),
        ),
    }


@pytest.mark.parametrize(('history', 'message'), [
    pytest.param(financial_history, 'historia financiera', id='finance-before-history'),
    pytest.param(delivery_history, 'conserva entregas', id='delivery-history'),
    pytest.param(issue_history, 'conserva bugs', id='archived-issue-history'),
])
@pytest.mark.parametrize(('writer', 'error'), [
    pytest.param(transfer_in_admin, BillingProjectAdminConflict, id='django-admin'),
    pytest.param(transfer_in_panel_service, APIException, id='panel-service'),
])
def test_rejected_transfer_preserves_approved_access(history, message, writer, error):
    """Fails if a real transfer rejection changes any access, recipient or audit state."""
    c = approved_project()
    history(c)
    before = unchanged_state(c)

    with pytest.raises(error, match=message):
        writer(c)

    assert unchanged_state(c) == before


def test_admin_rename_with_protected_history_preserves_approved_access():
    """Fails if protected history prevents an innocent edit or revokes valid grants."""
    c = approved_project()
    financial_history(c)
    before = unchanged_state(c)
    project = Project.objects.get(pk=c.project.pk)
    project.name = 'Nombre aclarado sin cambiar propietario ni accesos'
    request = RequestFactory().post('/admin/accounts/project/')
    request.user = c.admin

    ProjectAdmin(Project, admin_site).save_model(request, project, None, change=True)

    after = unchanged_state(c)
    assert after.pop('project')['name'] == project.name
    before.pop('project')
    # A permitted rename legitimately records an entity revision.
    after.pop('audit_counts')
    before.pop('audit_counts')
    assert after == before
