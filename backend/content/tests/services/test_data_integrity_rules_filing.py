"""Document and communication rules DC9-DC12 and CM6: filing, numbering and attachments.

Each inconsistency is made with a raw ``QuerySet.update``, the way it slips in
for real: the serializers and services that keep these invariants never run.
"""
import pytest

from content.models import CommunicationAttachment, Document
from content.services.data_integrity.types import REPORT_ONLY
from content.tests.data_integrity_accounting_factories import make_cuenta
from content.tests.data_integrity_documents_factories import make_document, make_folder, make_message, make_thread
from content.tests.data_integrity_helpers import make_project, scan

pytestmark = pytest.mark.django_db


def _found(rule_id):
    return scan(rule_ids=[rule_id])


# ── DC9 · document of one client in another client's folder ──────────────────

def test_document_moved_into_another_clients_folder_is_reported(make_client_profile):
    """Fails if a document sitting in another client's folder is not surfaced for review."""
    owner = make_client_profile(company='Dueño')
    other = make_client_profile(company='Otro')
    document = make_document(folder=make_folder(client_user=owner.user), client_user=owner.user)
    foreign = make_folder(name='Carpeta ajena', client_user=other.user)
    Document.objects.filter(pk=document.pk).update(folder=foreign)

    [finding] = _found('DC9')

    assert finding.evidence == {'document': document.pk, 'folder': foreign.pk,
                                'client_user': [owner.user_id, other.user_id]}
    assert finding.fix_kinds == (REPORT_ONLY,)
    assert 'no es dueña' in finding.message


def test_document_in_its_own_or_an_unowned_folder_is_quiet(make_client_profile):
    """Fails if a document filed with its own client, or in a folder without client, is reported."""
    owner = make_client_profile()
    make_document(folder=make_folder(client_user=owner.user), client_user=owner.user)
    make_document(title='Suelto', folder=make_folder(name='General'), client_user=owner.user)

    assert _found('DC9') == []


# ── DC10 · document of one project in another project's folder ───────────────

def test_document_moved_into_another_projects_folder_is_reported(make_client_profile):
    """Fails if a document of one project sitting in another project's folder is not surfaced."""
    client = make_client_profile()
    project = make_project(client)
    other = make_project(client, name='Otro proyecto')
    document = make_document(folder=make_folder(project=project), project=project, client_user=client.user)
    foreign = make_folder(name='Carpeta del otro', project=other)
    Document.objects.filter(pk=document.pk).update(folder=foreign)

    [finding] = _found('DC10')

    assert finding.evidence == {'document': document.pk, 'folder': foreign.pk, 'project': [project.pk, other.pk]}
    assert finding.fix_kinds == (REPORT_ONLY,)


def test_document_filed_with_its_own_project_is_quiet(make_client_profile):
    """Fails if a document in a folder of its own project is reported."""
    client = make_client_profile()
    project = make_project(client)
    make_document(folder=make_folder(project=project), project=project, client_user=client.user)

    assert _found('DC10') == []


# ── DC11 · active document without a folder ──────────────────────────────────

def test_only_active_unfiled_documents_are_reported():
    """Fails if an active document without a folder is missed, or an archived or filed one is reported."""
    unfiled = make_document(title='Sin carpeta')
    make_document(title='Archivado', is_archived=True)
    make_document(title='Archivado en carpeta', folder=make_folder())

    assert [finding.evidence for finding in _found('DC11')] == [{'document': unfiled.pk}]


def test_draft_cuenta_waiting_to_be_filed_is_quiet(make_client_profile):
    """Fails if a draft cuenta de cobro, created unfiled on purpose and filed once issued, is reported."""
    client = make_client_profile()
    make_cuenta(client, make_project(client), status=Document.CommercialStatus.DRAFT)

    assert _found('DC11') == []


# ── DC12 · repeated public number ────────────────────────────────────────────

def test_cuentas_sharing_a_public_number_are_reported(make_client_profile):
    """Fails if two cuentas de cobro left with the same public number go unreported."""
    client = make_client_profile()
    project = make_project(client)
    first = make_cuenta(client, project)
    second = make_cuenta(client, project, public_number='PA-KORE-002')
    Document.objects.filter(pk=second.pk).update(public_number='PA-KORE-001')

    [finding] = _found('DC12')

    assert finding.evidence == {'public_number': 'PA-KORE-001', 'documents': [first.pk, second.pk]}
    assert finding.fix_kinds == (REPORT_ONLY,)


def test_unnumbered_cuentas_and_other_documents_sharing_a_number_are_quiet(make_client_profile):
    """Fails if blank numbers, or documents that are not cuentas de cobro, count as a repeated number."""
    client = make_client_profile()
    project = make_project(client)
    make_cuenta(client, project, public_number='')
    make_cuenta(client, project, public_number='')
    make_document(title='Acta', public_number='ACTA-1')
    make_document(title='Acta copia', public_number='ACTA-1')

    assert _found('DC12') == []


# ── CM6 · attachment holding another client's document ───────────────────────

def test_attachment_of_another_clients_document_is_reported(make_client_profile):
    """Fails if a message keeps another client's document attached and nobody is told."""
    owner = make_client_profile(company='Dueño')
    other = make_client_profile(company='Otro')
    thread = make_thread(owner)
    message = make_message(thread)
    document = make_document(client_user=owner.user)
    attachment = CommunicationAttachment.objects.create(message=message, document=document)
    Document.objects.filter(pk=document.pk).update(client_user=other.user)

    [finding] = _found('CM6')

    assert finding.evidence == {'attachment': attachment.pk, 'message': message.pk,
                                'document': document.pk, 'thread': thread.pk}
    assert finding.fix_kinds == (REPORT_ONLY,)


def test_attachments_of_own_or_unowned_documents_are_quiet(make_client_profile):
    """Fails if a document of the thread's client, or one without client, is reported as foreign."""
    owner = make_client_profile()
    message = make_message(make_thread(owner))
    CommunicationAttachment.objects.create(message=message, document=make_document(client_user=owner.user))
    CommunicationAttachment.objects.create(message=message, document=make_document(title='Sin dueño'))

    assert _found('CM6') == []
