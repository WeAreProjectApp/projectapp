"""NM1 detection: names and titles with leading, trailing or repeated whitespace."""
import pytest
from accounts.models import UserProfile
from django.contrib.auth.models import User

from content.models import (
    CommunicationFolder,
    CommunicationThread,
    Document,
    DocumentFolder,
    DocumentType,
)
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.tests.data_integrity_helpers import make_project, make_proposal, only, scan

pytestmark = pytest.mark.django_db


def nm1(scope_kind='all', scope_id=None):
    return only(scan(scope_kind, scope_id, rule_ids=['NM1']), 'NM1')


@pytest.fixture
def profile(make_client_profile):
    return make_client_profile(company='Kore SAS', first_name='Ana', last_name='Pérez')


# ── Covered values, each made dirty in its own way ───────────────────────────

def dirty_company(profile):
    UserProfile.objects.filter(pk=profile.pk).update(company_name='Kore  SAS')
    return ('accounts.userprofile', profile.pk, 'company_name', 'Kore  SAS'), 'Kore SAS'


def dirty_first_name(profile):
    User.objects.filter(pk=profile.user_id).update(first_name='Ana ')
    return ('auth.user', profile.user_id, 'first_name', 'Ana '), 'Ana'


def dirty_last_name(profile):
    User.objects.filter(pk=profile.user_id).update(last_name='Pérez\tGómez')
    return ('auth.user', profile.user_id, 'last_name', 'Pérez\tGómez'), 'Pérez Gómez'


def dirty_project(profile):
    project = make_project(profile, ' Kore App')
    return ('accounts.project', project.pk, 'name', ' Kore App'), 'Kore App'


def dirty_folder(profile):
    folder = DocumentFolder.objects.create(name='Actas  2026')
    return ('content.documentfolder', folder.pk, 'name', 'Actas  2026'), 'Actas 2026'


def dirty_document(profile):
    document = Document.objects.create(title='Acta final\n')
    return ('content.document', document.pk, 'title', 'Acta final\n'), 'Acta final'


def dirty_proposal(profile):
    proposal = make_proposal(profile, title='Propuesta  web ')
    return ('content.businessproposal', proposal.pk, 'title', 'Propuesta  web '), 'Propuesta web'


def dirty_communication_folder(profile):
    folder = CommunicationFolder.objects.create(name='Soporte ', client=profile)
    return ('content.communicationfolder', folder.pk, 'name', 'Soporte '), 'Soporte'


def dirty_thread(profile):
    thread = CommunicationThread.objects.create(client=profile, title='Hilo  de soporte')
    return ('content.communicationthread', thread.pk, 'title', 'Hilo  de soporte'), 'Hilo de soporte'


@pytest.mark.parametrize('make_dirty', [
    dirty_company, dirty_first_name, dirty_last_name, dirty_project, dirty_folder, dirty_document,
    dirty_proposal, dirty_communication_folder, dirty_thread,
], ids=['company', 'first_name', 'last_name', 'project', 'folder', 'document', 'proposal', 'communication_folder', 'thread'])
def test_a_value_with_extra_spaces_is_reported_once_with_its_clean_value(profile, make_dirty):
    """Fails if a covered name with stray whitespace is missed, reported twice or suggests another value."""
    (model, pk, field, value), clean = make_dirty(profile)

    [finding] = nm1()

    assert finding.evidence == {'model': model, 'pk': pk, 'field': field, 'value': value}
    assert finding.suggestion == {'value': clean}
    assert finding.fix_kinds == ('rename',)


def test_names_with_single_inner_spaces_are_not_reported(profile):
    """Fails if ordinary multi-word names are flagged as having extra spaces."""
    make_project(profile, 'Kore App')
    DocumentFolder.objects.create(name='Actas de obra')
    Document.objects.create(title='Acta de entrega final')
    make_proposal(profile, title='Propuesta web')
    CommunicationFolder.objects.create(name='Soporte técnico', client=profile)
    CommunicationThread.objects.create(client=profile, title='Hilo de soporte')

    assert nm1() == []


# ── Names the system owns ────────────────────────────────────────────────────

def generated_snapshot(profile):
    Document.objects.create(title='Propuesta comercial ', generated_file='documents/generated/2026/10/propuesta.pdf')


def collection_account(profile):
    kind, _ = DocumentType.objects.get_or_create(code=COLLECTION_ACCOUNT, defaults={'name': 'Cuenta de cobro'})
    Document.objects.create(title='Cuenta de cobro  PA-001', document_type=kind)


def system_folder(profile):
    DocumentFolder.objects.create(name='Archivo  automático', system_key='generated:test:archive')


def project_root_folder(profile):
    project = make_project(profile, 'Kore')
    DocumentFolder.objects.filter(managed_project=project).update(name='Kore ')


def project_root_thread(profile):
    project = make_project(profile, 'Kore')
    CommunicationThread.objects.filter(managed_project=project).update(title='Kore ')


@pytest.mark.parametrize('make_owned', [
    generated_snapshot, collection_account, system_folder, project_root_folder, project_root_thread,
], ids=['generated_snapshot', 'collection_account', 'system_folder', 'project_root_folder', 'project_root_thread'])
def test_names_the_system_owns_are_not_reported(profile, make_owned):
    """Fails if NM1 offers to rename a generated, accounting, system or managed-root name."""
    make_owned(profile)

    assert nm1() == []


def test_a_client_scope_reports_only_that_clients_names(profile, make_client_profile):
    """Fails if a client-scoped scan leaks another client's names or misses its own."""
    other = make_client_profile(company='Otra  SAS')
    own = make_project(profile, 'Kore  App')
    make_project(other, 'Otro  proyecto')

    findings = nm1('client', profile.pk)

    assert [(finding.evidence['model'], finding.evidence['pk']) for finding in findings] == [
        ('accounts.project', own.pk)]
    assert len(nm1()) == 3
