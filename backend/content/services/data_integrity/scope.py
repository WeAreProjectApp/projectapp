"""Where a scan looks: one id set per model, resolved once per request.

``ids is None`` means the whole database (``all``). Otherwise a model missing
from ``ids`` resolves to an empty set and the rules on it skip themselves.
Group rules (duplicates) compute groups over all data and keep the groups
that touch the scope, so a duplicate outside the scope is still reported when
its twin is inside.
"""
from dataclasses import dataclass, field

from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.shortcuts import get_object_or_404

PROFILE = 'accounts.userprofile'
USER = 'auth.user'
PROJECT = 'accounts.project'
PHASE = 'accounts.projectphase'
PROPOSAL = 'content.businessproposal'
SECTION = 'content.proposalsection'
DOCUMENT = 'content.document'
FOLDER = 'content.documentfolder'
DOCUMENT_THREAD = 'content.documentthread'
THREAD = 'content.communicationthread'
COMM_FOLDER = 'content.communicationfolder'
INCOME = 'content.incomerecord'
HOSTING = 'content.hostingrecord'
SECURE_LINK = 'secure_links.securelink'
RECURRING = 'content.recurringpayment'

SCOPE_KINDS = ('all', 'client', 'project', 'proposal', 'document', 'thread')
QUERYABLE_KINDS = ('client', 'project')
MAX_CANDIDATES = 10


@dataclass
class Scope:
    kind: str = 'all'
    id: int = None
    label: str = 'Toda la base'
    ids: dict = field(default=None)

    @property
    def is_all(self):
        return self.ids is None

    def ids_for(self, model_label):
        """``None`` for every row, else the (possibly empty) id set of that model."""
        if self.ids is None:
            return None
        return self.ids.get(model_label, set())

    def skips(self, model_label):
        return self.ids is not None and not self.ids.get(model_label)

    def limit(self, queryset, model_label, field_name='pk'):
        ids = self.ids_for(model_label)
        return queryset if ids is None else queryset.filter(**{f'{field_name}__in': ids})

    def touches(self, model_label, pks):
        ids = self.ids_for(model_label)
        return ids is None or bool(ids & set(pks))

    def payload(self):
        return {'kind': self.kind, 'id': self.id, 'label': self.label}


def _ids(queryset):
    return set(queryset.values_list('pk', flat=True))


def _folder_ancestors(folder_id):
    from content.models import DocumentFolder
    found = set()
    while folder_id and folder_id not in found:
        found.add(folder_id)
        folder_id = DocumentFolder._base_manager.filter(pk=folder_id).values_list('parent_id', flat=True).first()
    return found


def _client_scope(profile):
    from accounts.models import Project, ProjectPhase
    from content.models import (
        BusinessProposal, CommunicationFolder, CommunicationThread, Document, DocumentFolder,
        DocumentThreadItem, HostingRecord, IncomeRecord, ProposalSection,
    )
    from secure_links.models import SecureLink

    user_id = profile.user_id
    projects = _ids(Project._base_manager.filter(client_id=user_id))
    proposals = _ids(BusinessProposal._base_manager.filter(
        Q(client_id=profile.pk) | Q(project_phases__project_id__in=projects)))
    documents = _ids(Document._base_manager.filter(Q(client_user_id=user_id) | Q(project_id__in=projects)))
    return {
        PROFILE: {profile.pk}, USER: {user_id}, PROJECT: projects, PROPOSAL: proposals,
        PHASE: _ids(ProjectPhase._base_manager.filter(
            Q(project_id__in=projects) | Q(business_proposal_id__in=proposals))),
        SECTION: _ids(ProposalSection._base_manager.filter(proposal_id__in=proposals)),
        DOCUMENT: documents,
        FOLDER: _ids(DocumentFolder._base_manager.filter(
            Q(client_user_id=user_id) | Q(managed_client_id=user_id) | Q(project_id__in=projects))),
        DOCUMENT_THREAD: set(DocumentThreadItem._base_manager.filter(document_id__in=documents)
                             .values_list('thread_id', flat=True)),
        THREAD: _ids(CommunicationThread._base_manager.filter(Q(client_id=profile.pk) | Q(project_id__in=projects))),
        COMM_FOLDER: _ids(CommunicationFolder._base_manager.filter(Q(client_id=profile.pk) | Q(project_id__in=projects))),
        INCOME: _ids(IncomeRecord._base_manager.filter(Q(client_id=profile.pk) | Q(project_id__in=projects))),
        HOSTING: _ids(HostingRecord._base_manager.filter(Q(client_id=profile.pk) | Q(project_id__in=projects))),
        SECURE_LINK: _ids(SecureLink._base_manager.filter(Q(client_id=profile.pk) | Q(project_id__in=projects))),
    }


def _project_scope(project):
    from accounts.models import ProjectPhase, UserProfile
    from content.models import (
        BusinessProposal, CommunicationFolder, CommunicationThread, Document, DocumentFolder,
        DocumentThreadItem, HostingRecord, IncomeRecord, ProposalSection,
    )
    from secure_links.models import SecureLink

    proposals = _ids(BusinessProposal._base_manager.filter(
        Q(project_phases__project_id=project.pk) | Q(deliverable__project_id=project.pk)))
    documents = _ids(Document._base_manager.filter(project_id=project.pk))
    return {
        # The owner, so client rules and the unlinked-records rule see this
        # project's client the same way ``list_project_unlinked_records`` does.
        PROFILE: _ids(UserProfile._base_manager.filter(user_id=project.client_id)),
        USER: {project.client_id},
        PROJECT: {project.pk}, PROPOSAL: proposals,
        PHASE: _ids(ProjectPhase._base_manager.filter(Q(project_id=project.pk) | Q(business_proposal_id__in=proposals))),
        SECTION: _ids(ProposalSection._base_manager.filter(proposal_id__in=proposals)),
        DOCUMENT: documents,
        FOLDER: _ids(DocumentFolder._base_manager.filter(Q(project_id=project.pk) | Q(managed_project_id=project.pk))),
        DOCUMENT_THREAD: set(DocumentThreadItem._base_manager.filter(document_id__in=documents)
                             .values_list('thread_id', flat=True)),
        THREAD: _ids(CommunicationThread._base_manager.filter(project_id=project.pk)),
        COMM_FOLDER: _ids(CommunicationFolder._base_manager.filter(project_id=project.pk)),
        INCOME: _ids(IncomeRecord._base_manager.filter(project_id=project.pk)),
        HOSTING: _ids(HostingRecord._base_manager.filter(project_id=project.pk)),
        SECURE_LINK: _ids(SecureLink._base_manager.filter(project_id=project.pk)),
    }


def _proposal_scope(proposal):
    from accounts.models import Project, ProjectPhase, UserProfile
    from content.models import Document, ProposalSection

    projects = _ids(Project._base_manager.filter(
        Q(phases__business_proposal_id=proposal.pk) | Q(deliverables__business_proposal=proposal.pk)))
    profiles = {proposal.client_id} if proposal.client_id else set()
    users = set(UserProfile._base_manager.filter(pk__in=profiles).values_list('user_id', flat=True))
    return {
        PROFILE: profiles, USER: users, PROJECT: projects, PROPOSAL: {proposal.pk},
        PHASE: _ids(ProjectPhase._base_manager.filter(business_proposal_id=proposal.pk)),
        SECTION: _ids(ProposalSection._base_manager.filter(proposal_id=proposal.pk)),
        DOCUMENT: _ids(Document._base_manager.filter(source_proposal_id=proposal.pk)),
    }


def _document_scope(document):
    from content.models import DocumentThreadItem
    return {
        DOCUMENT: {document.pk},
        FOLDER: _folder_ancestors(document.folder_id),
        DOCUMENT_THREAD: set(DocumentThreadItem._base_manager.filter(document_id=document.pk)
                             .values_list('thread_id', flat=True)),
    }


def _thread_scope(thread):
    return {THREAD: {thread.pk}, COMM_FOLDER: {thread.folder_id} if thread.folder_id else set()}


def resolve_scope(kind, scope_id=None):
    """Build the scope; unknown ids raise 404 through ``get_object_or_404``."""
    from accounts.models import Project, UserProfile
    from content.models import BusinessProposal, CommunicationThread, Document

    if kind == 'all':
        return Scope()
    if kind == 'client':
        profile = get_object_or_404(UserProfile.objects.clients(), pk=scope_id)
        return Scope(kind, profile.pk, client_label(profile), _client_scope(profile))
    if kind == 'project':
        project = get_object_or_404(Project._base_manager, pk=scope_id)
        return Scope(kind, project.pk, project.name, _project_scope(project))
    if kind == 'proposal':
        proposal = get_object_or_404(BusinessProposal._base_manager, pk=scope_id)
        return Scope(kind, proposal.pk, proposal.title, _proposal_scope(proposal))
    if kind == 'document':
        document = get_object_or_404(Document._base_manager, pk=scope_id)
        return Scope(kind, document.pk, document.title, _document_scope(document))
    if kind == 'thread':
        thread = get_object_or_404(CommunicationThread._base_manager, pk=scope_id)
        return Scope(kind, thread.pk, thread.title, _thread_scope(thread))
    raise ValueError(f'Unknown scope kind: {kind}')


def client_label(profile):
    user = profile.user
    name = ' '.join(part for part in (user.first_name, user.last_name) if part).strip()
    company = (profile.company_name or '').strip()
    if name and company:
        return f'{name} ({company})'
    return name or company or user.email or f'Cliente {profile.pk}'


def scope_candidates(kind, query):
    """Up to ten {id, label} matches for a free-text scope (client or project)."""
    from accounts.models import Project, UserProfile

    text = (query or '').strip()
    if kind == 'client':
        rows = (UserProfile.objects.clients()
                .annotate(full_name=Concat('user__first_name', Value(' '), 'user__last_name'))
                .filter(Q(company_name__icontains=text) | Q(full_name__icontains=text)
                        | Q(user__email__icontains=text))
                .order_by('pk')[:MAX_CANDIDATES])
        return [{'id': row.pk, 'label': client_label(row), 'email': row.user.email} for row in rows]
    if kind == 'project':
        rows = Project._base_manager.filter(name__icontains=text).select_related('client').order_by('pk')[:MAX_CANDIDATES]
        return [{'id': row.pk, 'label': row.name, 'client_email': row.client.email} for row in rows]
    raise ValueError(f'Scope kind {kind} does not accept a query')
