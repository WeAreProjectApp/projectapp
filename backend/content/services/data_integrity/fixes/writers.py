"""Domain writers shared by fixers, plus the closures their side effects reach.

Every writer here is the same service or serializer the Panel uses, so a fix
gets the same validation and the same audit rows (EntityHistory through the
active history operation, AccountingChangeLog where the writer logs one).
Writers raise ``ValueError``/``ValidationError`` on refusal; a fixer's
``plan`` should prevent that with blockers, and the engine rolls back if not.
"""
from content.services.data_integrity.scope import (
    COMM_FOLDER, DOCUMENT, FOLDER, HOSTING, INCOME, PROFILE, PROJECT, PROPOSAL, THREAD, USER,
)
from content.services.data_integrity.snapshots import register_fields

register_fields(INCOME, 'project_id', 'client_id')
register_fields(HOSTING, 'project_id', 'client_id', 'client_name', 'client_email',
                'client_contact_name', 'client_identification')
register_fields(DOCUMENT, 'project_id', 'title')
register_fields(THREAD, 'project_id', 'folder_id', 'title', 'client_id', 'is_archived', 'archived_at')
register_fields(FOLDER, 'name', 'client_user_id', 'is_archived', 'archived_at')
register_fields(COMM_FOLDER, 'name')
register_fields(PROJECT, 'name', 'status')
register_fields(USER, 'first_name', 'last_name')
register_fields(PROFILE, 'company_name')
register_fields(PROPOSAL, 'client_name', 'client_email', 'client_phone')


# ── Closures ─────────────────────────────────────────────────────────────────

def financial_closure(model_label, record_ids):
    """Records plus what ``bulk_assign_project``/``bulk_assign_client`` cascade to:
    liquid children of expected incomes and draft collection accounts."""
    from content.models import Document, IncomeRecord
    keys = {(model_label, pk) for pk in record_ids}
    income_ids = set(record_ids) if model_label == INCOME else set()
    if income_ids:
        children = set(IncomeRecord._base_manager.filter(expected_income_id__in=income_ids)
                       .values_list('pk', flat=True))
        keys |= {(INCOME, pk) for pk in children}
        income_ids |= children
    link = 'income_record_id' if model_label == INCOME else 'hosting_record_id'
    owners = income_ids if model_label == INCOME else set(record_ids)
    drafts = Document._base_manager.filter(**{f'{link}__in': owners},
                                           commercial_status=Document.CommercialStatus.DRAFT)
    keys |= {(DOCUMENT, pk) for pk in drafts.values_list('pk', flat=True)}
    return sorted(keys)


def project_root_closure(project_id):
    """A project's managed root folder and root thread, which a rename re-syncs."""
    from content.models import CommunicationThread, DocumentFolder
    keys = [(FOLDER, pk) for pk in DocumentFolder._base_manager.filter(managed_project_id=project_id)
            .values_list('pk', flat=True)]
    keys += [(THREAD, pk) for pk in CommunicationThread._base_manager.filter(managed_project_id=project_id)
             .values_list('pk', flat=True)]
    return keys


def client_identity_closure(profile):
    """A client's user and profile plus every proposal whose snapshot an identity edit re-syncs."""
    from content.models import BusinessProposal
    keys = [(PROFILE, profile.pk), (USER, profile.user_id)]
    keys += [(PROPOSAL, pk) for pk in BusinessProposal._base_manager.filter(client_id=profile.pk)
             .values_list('pk', flat=True)]
    return keys


# ── Relink ───────────────────────────────────────────────────────────────────

def _entity_type(model_label):
    from content.services.accounting_service import EntityType
    return {INCOME: EntityType.INCOME, HOSTING: EntityType.HOSTING}[model_label]


def relink_financial_project(model_label, record_ids, project, actor):
    """Income/hosting project through ``bulk_assign_project`` (cascades included)."""
    from content.services import accounting_service
    return accounting_service.bulk_assign_project(_entity_type(model_label), list(record_ids), project, actor)


def relink_financial_client(model_label, record_ids, profile, actor):
    """Income/hosting client through ``bulk_assign_client`` (clears a foreign project)."""
    from content.services import accounting_service
    return accounting_service.bulk_assign_client(_entity_type(model_label), list(record_ids), profile, actor,
                                                 strict_ids=True)


def relink_documents_project(document_ids, project, actor):
    """Plain documents only: issued cuentas and generated snapshots are refiled by
    this writer (folders created or moved), so fixers must not send them here."""
    from content.services import accounting_service
    return accounting_service.assign_project_to_documents(list(document_ids), project, actor)


def update_thread(thread_id, actor, **values):
    from content.models import CommunicationThread
    from content.services import communication_service
    thread = CommunicationThread.objects.get(pk=thread_id)
    return communication_service.update_thread(thread, actor=actor, **values)


# ── Rename ───────────────────────────────────────────────────────────────────

def rename_project(project_id, name, actor):
    """Panel PATCH semantics: serializer validation plus one project audit row."""
    from accounts.models import Project
    from content.serializers.panel_projects import UpdatePanelProjectSerializer
    from content.services import project_service
    project = Project.objects.get(pk=project_id)
    serializer = UpdatePanelProjectSerializer(project, data={'name': name}, partial=True)
    serializer.is_valid(raise_exception=True)
    snapshot = project_service.project_snapshot(project)
    serializer.save()
    project_service.log_project_event(project, project_service.Action.UPDATED, snapshot, actor)
    return project


def rename_document_folder(folder_id, name):
    """Folder serializer: refuses duplicate siblings, managed roots and system folders."""
    from content.models import DocumentFolder
    from content.serializers.document_folder import DocumentFolderSerializer
    folder = DocumentFolder.objects.get(pk=folder_id)
    serializer = DocumentFolderSerializer(folder, data={'name': name}, partial=True)
    serializer.is_valid(raise_exception=True)
    return serializer.save()


def rename_communication_folder(folder_id, name):
    from content.models import CommunicationFolder
    from content.services.communication_folder_service import save_folder
    folder = CommunicationFolder.objects.get(pk=folder_id)
    return save_folder(data={'name': name}, folder=folder)


def rename_document(document_id, title, actor):
    from content.models import Document
    from content.serializers.document import DocumentCreateUpdateSerializer
    document = Document.objects.get(pk=document_id)
    serializer = DocumentCreateUpdateSerializer(document, data={'title': title}, partial=True)
    serializer.is_valid(raise_exception=True)
    return serializer.save(updated_by=actor)


def update_client_identity(profile_id, **values):
    """``update_client_profile``: also re-syncs every proposal snapshot of the client."""
    from accounts.models import UserProfile
    from accounts.services.proposal_client_service import update_client_profile
    profile = UserProfile.objects.select_related('user').get(pk=profile_id)
    return update_client_profile(profile, **values)
