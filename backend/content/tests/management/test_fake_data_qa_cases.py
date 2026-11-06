"""Executable data scenarios, rather than an inventory-only coverage claim."""
from datetime import date
from io import BytesIO, StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import F
from pypdf import PdfReader
from rest_framework.exceptions import NotFound

from accounts.models import Deliverable, DeliverableClientUpload, DeliverableFile, Payment, Project
from accounts.services import platform_resources
from content.models import Document, IncomeRecord
from content.services.accounting_service import paid_amount_subquery

pytestmark = pytest.mark.django_db
SEED_ARGS = ('--seed', '231', '--anchor-date', '2026-11-06')


def run(name, *args):
    call_command(name, *args, *SEED_ARGS, stdout=StringIO(), verbosity=0)


@pytest.fixture
def cases():
    run('seed_platform_data')
    run('create_fake_platform_cases')


def test_resource_versions_are_downloadable_pdfs(cases):
    resource = Deliverable.objects.get(title='[QA] Recurso PDF con tres versiones')
    texts = []
    for version in resource.versions.order_by('version_number'):
        with version.file.open('rb') as stored:
            texts.append(PdfReader(BytesIO(stored.read())).pages[0].extract_text().strip())
    assert texts == [f'ProjectApp - recurso ficticio v{number}' for number in (1, 2, 3)]


def test_resource_current_file_matches_latest_version(cases):
    resource = Deliverable.objects.get(title='[QA] Recurso PDF con tres versiones')
    latest = resource.versions.get(version_number=resource.current_version)
    with resource.file.open('rb') as current, latest.file.open('rb') as previous:
        assert current.read() == previous.read()


def test_base_resources_have_real_local_files(cases):
    resources = Deliverable.objects.exclude(file='').exclude(file=None)
    assert resources.count() >= 2
    missing = [row.title for row in resources if not row.file.storage.exists(row.file.name)]
    assert missing == []


def test_enrichment_stores_attachment_bytes(cases):
    run('enrich_platform_data', '--count', '12')
    files = list(DeliverableFile.objects.all()) + list(DeliverableClientUpload.objects.all())
    assert len(files) > 0
    for row in files:
        with row.file.open('rb') as stored:
            assert len(PdfReader(BytesIO(stored.read())).pages) == 1


def test_qa_client_has_no_projects(cases):
    assert not Project.objects.filter(client__username='qa-empty@example.test').exists()


def test_qa_empty_project_has_no_resources(cases):
    project = Project.objects.get(name='[QA] Proyecto vacío')
    assert not project.deliverables.exists()
    assert not Document.objects.filter(project=project).exists()


def test_qa_client_cannot_read_another_clients_resource(cases):
    limited = get_user_model().objects.get(username='qa-limited@example.test')
    resource = Deliverable.objects.get(title='[QA] Recurso PDF con tres versiones')
    with pytest.raises(NotFound):
        platform_resources.get_resource(resource.project_id, limited, resource.pk)


@pytest.mark.parametrize(('role', 'expected'), [
    ('superuser', (True, True, 'admin', True, True, True)),
    ('staff', (True, False, 'admin', True, True, True)),
    ('admin', (False, False, 'admin', True, True, True)),
    ('pending', (False, False, 'client', False, False, False)),
    ('profile', (False, False, 'client', True, True, False)),
])
def test_qa_identity_has_the_documented_permissions(cases, role, expected):
    user = get_user_model().objects.select_related('profile').get(username=f'qa-{role}@example.test')
    assert (user.is_staff, user.is_superuser, user.profile.role, user.profile.is_onboarded,
            user.profile.email_verified, user.profile.profile_completed) == expected


def test_qa_passwords_are_unusable_by_default(cases):
    users = get_user_model().objects.filter(username__startswith='qa-')
    assert {user.has_usable_password() for user in users} == {False}


def test_large_income_is_still_unpaid(cases):
    income = IncomeRecord.objects.annotate(paid=paid_amount_subquery()).get(concept='[QA] Ingreso grande pendiente')
    assert (income.kind, str(income.total_amount), income.paid, income.period_date) == (
        'expected', '987654321012.00', 0, date(2026, 11, 1),
    )
    assert income.gustavo_amount + income.carlos_amount == income.total_amount


def test_hosting_cases_cover_payment_states(cases):
    assert set(Payment.objects.filter(description__startswith='[QA] Pago ').values_list('status', flat=True)) == {
        status for status, _ in Payment.STATUS_CHOICES
    }


def test_platform_cases_do_not_accumulate(cases):
    before = (Project.objects.count(), Deliverable.objects.count(), Payment.objects.count(), IncomeRecord.objects.count())
    run('create_fake_platform_cases')
    assert (Project.objects.count(), Deliverable.objects.count(), Payment.objects.count(), IncomeRecord.objects.count()) == before


def test_document_long_case_keeps_renderable_content():
    run('create_fake_documents', '--count', '2')
    document = Document.objects.get(title='[QA] Documento largo de referencia')
    assert len(document.content_markdown) > 8000
    assert document.content_json


def test_generated_client_project_ownership_is_coherent(cases):
    assert not IncomeRecord.objects.filter(source_ref='fake:accounting', project__isnull=False).exclude(
        client__user=F('project__client'),
    ).exists()
