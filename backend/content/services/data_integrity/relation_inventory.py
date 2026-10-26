"""Which integrity rule watches each relation into the anchor records, or why none does.

The anchors are the records the panel cross-links: projects, the client (its
``User`` and its ``UserProfile``), proposals, documents, document folders,
communication threads, incomes and hostings. Every FK, one-to-one and
many-to-many pointing at one of them carries exactly one decision:

- ``covered``: the catalog rules that check its consistency;
- ``exempt``: why it is never cleaned (authorship, immutable evidence,
  append-only logs, cascade children with no copy of client or project);
- ``gap``: a known inconsistency no rule checks yet, and what it would check.

Relations are discovered by introspection, hidden ``related_name='+'`` ones
included. The inventory test fails on any discovered relation without a
decision, so a new relation cannot land unseen, and on a decision whose
relation or rule no longer exists. Authorship relations to the client are
exempt through ``client_merge_policy.AUTHORSHIP_RELATIONS``, the reviewed list
the client merge already maintains.
"""
from collections import Counter
from dataclasses import dataclass

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured

ANCHORS = (
    'accounts.Project', 'accounts.UserProfile', 'content.BusinessProposal', 'content.Document',
    'content.DocumentFolder', 'content.CommunicationThread', 'content.IncomeRecord', 'content.HostingRecord',
)
COVERED, EXEMPT, GAP = 'covered', 'exempt', 'gap'


@dataclass(frozen=True)
class Decision:
    status: str
    rules: tuple = ()
    reason: str = ''


AUTHORSHIP = Decision(EXEMPT, reason='Autoría: registra quién hizo algo, no de quién es; nunca se limpia.')
DECISIONS = {}


def _decide(decision, keys):
    for key in keys.split():
        if key in DECISIONS:
            raise ImproperlyConfigured(f'Relation {key} has two decisions')
        DECISIONS[key] = decision


def covered(*rules):
    return Decision(COVERED, tuple(rules))


def exempt(reason):
    return Decision(EXEMPT, reason=reason)


def gap(reason):
    return Decision(GAP, reason=reason)


# ── The client: UserProfile and User ─────────────────────────────────────────

_decide(covered('CL4', 'CL6', 'PR1', 'PR2'), 'content.BusinessProposal.client')
_decide(covered('CL4', 'CL6'), 'content.WebAppDiagnostic.client')
_decide(covered('CL4', 'AC1', 'AC2', 'AC10'), 'content.IncomeRecord.client')
_decide(covered('CL4', 'AC1'), 'content.HostingRecord.client')
_decide(covered('CL4', 'CM1', 'CM6'), 'content.CommunicationThread.client')
_decide(covered('CL4', 'CL5'), 'accounts.Project.client')
_decide(covered('CL6', 'PJ8'), '''
    content.CommunicationFolder.client content.FinancingAgreement.client
    accounts.DeliveryEvidenceEmail.client accounts.DeliveryNotificationEvent.client accounts.DeliveryPromptContext.client
''')
_decide(covered('CL6', 'PJ2'), 'content.ProjectRetentionContext.client')
_decide(covered('DC1', 'DC2', 'DC9', 'CM6', 'CL6'), 'content.Document.client_user')
_decide(covered('DC3', 'DC9', 'CL6'), 'content.DocumentFolder.client_user')
_decide(covered('CM5', 'CL6'), 'secure_links.SecureLink.client')
_decide(covered('CL6'), 'secure_links.SecureLinkFolder.client')
# What deleting the client leaves without client (SET_NULL): CL6 reports it.
_decide(covered('CL6'), '''
    content.EmailLog.client content.AdditionalModuleShareLink.client content.LinktreeTemplate.client
    secure_links.SecureLink.owner content.DocumentFolder.managed_client content.CommunicationThread.managed_client
    accounts.ProjectIdea.recipient accounts.ProjectIdeaCollection.recipient
    accounts.ProjectClientAccessPolicy.recipient accounts.ProjectClientAccessEvent.recipient
''')
_decide(exempt('Identidad: el perfil es el cliente.'), 'accounts.UserProfile.user')
_decide(exempt('Contador de numeración propio del cliente: se va con él.'),
        'content.ClientDocumentNumberSequence.client_profile')
_decide(exempt('Preferencias, códigos y avisos personales: se van con el usuario.'), '''
    accounts.CommunicationPanelPreference.user accounts.SavedFilterTab.user
    accounts.VerificationCode.user accounts.Notification.user
''')
_decide(exempt('Preferencias de Ayuda y recorridos vistos por esta persona; se van con el usuario, '
               'sin reasignarse al corregir relaciones comerciales.'), '''
    accounts.ClientPlatformHelpSettings.user accounts.PlatformTourProgress.user
''')
_decide(AUTHORSHIP, '''
    accounts.PlatformGuidedTourRevision.created_by accounts.PlatformHelpEvent.actor
''')
_decide(exempt('Confirmación de corta vida del administrador que revisó un cambio sensible.'),
        'content.ProposalContractChangeIntent.owner')
_decide(exempt('Identidad técnica del conector MCP, no un dato del cliente.'), 'content.McpCredential.actor')
_decide(exempt('Asignación interna de tareas del equipo.'), 'content.Task.assignee')

# ── accounts.Project ─────────────────────────────────────────────────────────

# Children owned only by their project: the one way they drift is retention.
_decide(covered('PJ2'), '''
    accounts.ProjectAdminAccess.project accounts.ProjectAccessNote.project accounts.DeliveryWorkspace.project
    accounts.ProjectContract.project accounts.DeliveryMessage.project accounts.DeliveryOperation.project
    accounts.ChangeRequest.project accounts.BugReport.project accounts.ProjectDataModelEntity.project
    accounts.Notification.project accounts.HostingSubscription.project accounts.IssueContext.project
    accounts.IssueEvent.project accounts.ProjectClientAccessPolicy.project accounts.ProjectClientAccessEvent.project
    accounts.ProjectIdea.project accounts.ProjectIdeaCollection.project content.Linktree.project
    content.ProjectBrandAsset.project monitoring.Resource.project
''')
_decide(exempt('Borrador privado temporal: se elimina con el proyecto, expira por TTL y revalida el acceso; no se reasigna ni entra en retención.'),
        'accounts.PlatformAIJob.project')
_decide(exempt('Contadores de consumo sin contenido: se conservan independientes con project SET_NULL; no son registros del contexto de retención.'),
        'accounts.PlatformAIUsage.project')
_decide(covered('PJ2', 'PJ8'), 'accounts.DeliveryNotificationEvent.project')
_decide(covered('PJ8'), '''
    accounts.DeliveryEvidenceEmail.project accounts.DeliveryPromptContext.project
    content.CommunicationFolder.project content.FinancingAgreement.source_project
''')
_decide(covered('PR3', 'PJ7', 'PR5', 'PJ2'), 'accounts.ProjectPhase.project')
_decide(covered('PR3', 'PR5', 'PJ2'), 'accounts.Deliverable.project')
_decide(covered('CM1', 'CM2', 'PJ3', 'PJ2'), 'content.CommunicationThread.project')
_decide(covered('PJ5', 'CM1', 'PJ2'), 'content.CommunicationThread.managed_project')
_decide(covered('DC1', 'DC2', 'DC10', 'PJ1', 'PJ3', 'PJ2', 'AC10'), 'content.Document.project')
_decide(covered('DC3', 'DC10', 'PJ2'), 'content.DocumentFolder.project')
_decide(covered('PJ5', 'PJ2'), 'content.DocumentFolder.managed_project')
_decide(covered('AC1', 'PJ1', 'PJ3', 'PJ2'), 'content.HostingRecord.project')
_decide(covered('AC1', 'AC2', 'AC10', 'PJ1', 'PJ3', 'PJ2'), 'content.IncomeRecord.project')
_decide(covered('CM5', 'PJ2'), 'secure_links.SecureLink.project')
_decide(covered('PJ2'), '''
    secure_links.SecureLinkFolder.project secure_links.SecureLinkFolder.managed_project
''')
_decide(exempt('Evento de auditoría de solo-anexar.'), 'accounts.BillingContextEvent.project')
_decide(exempt('Historial privado con caducidad, ligado a su actor original: no se reasigna ni se conserva '
               'al borrar el proyecto. Appi revalida la pertenencia antes de mostrarlo.'),
        'accounts.AppiConversation.project')
_decide(gap('Copia del proyecto del nivel de entrega al que pertenece (delivery_workflow.link_document); '
            'ENT-02 y H5.'), 'accounts.DeliveryDocumentLink.project')
_decide(gap('La suscripción y las fuentes contables deben ser del mismo proyecto y cliente '
            '(accounts/services/hosting_context.py).'), 'accounts.ProjectHosting.project')
_decide(gap('Un único episodio abierto por proyecto, igual a su estado actual (project_state_service); DOC-10.'),
        'content.DocumentStateEpisode.project')
_decide(gap('Proyecto, entregable, propuesta y cliente coinciden (delivery_contract_sources); PRO-06.'),
        'content.ProposalApprovalFile.project')

# ── content.BusinessProposal ─────────────────────────────────────────────────

_decide(covered('PR3', 'PR4', 'PR5'), 'accounts.ProjectPhase.business_proposal')
_decide(covered('PR7'), 'content.ProposalSection.proposal')
_decide(exempt('Hijo en cascada sin copia de cliente ni proyecto.'), '''
    content.ProposalAlert.proposal content.ProposalDocument.proposal content.ProposalProjectStage.proposal
    content.ProposalShareLink.proposal content.VideoResource.proposal
''')
_decide(exempt('Registro de envío, vista o cambio: rastro histórico.'), '''
    content.EmailLog.proposal content.ProposalChangeLog.proposal content.ProposalViewEvent.proposal
''')
_decide(exempt('Evidencia inmutable o auditoría: se informa, nunca se corrige.'), '''
    content.ProposalApprovalFile.proposal content.ProposalApprovalPackage.proposal content.ProposalContractSnapshot.proposal
    content.ProposalProjectReassignment.proposal
''')
_decide(gap('La fuente compartida conserva el mismo proyecto y cliente en propuesta y documento; '
            'requiere revisión manual, sin reasignación automática '
            '(proposal_shared_documents, proposal_project_reassignment).'), '''
    content.ProposalDocumentBinding.proposal content.ProposalDocumentBinding.document
''')
_decide(exempt('Preparación de corta vida.'), '''
    content.ProposalContractChangeIntent.proposal content.ProposalFormalization.proposal
''')
_decide(gap('Los recursos técnicos siguen al proyecto de la propuesta al reasignarla '
            '(proposal_project_reassignment).'), 'accounts.Deliverable.source_proposal')
_decide(gap('Los documentos generados siguen a la propuesta al reasignarla (proposal_project_reassignment).'),
        'content.Document.source_proposal')
_decide(gap('La propuesta de la alianza es de su cliente (financing_agreement_service).'),
        'content.FinancingAgreement.source_proposal')

# ── content.Document ─────────────────────────────────────────────────────────

_decide(covered('DC8'), 'content.DocumentThreadItem.document')
_decide(covered('CM6'), 'content.CommunicationAttachment.document content.CommunicationMessage.documents')
_decide(exempt('Hijo en cascada del documento.'), '''
    content.DocumentCollectionAccount.document content.DocumentItem.document content.DocumentNote.document
    content.DocumentPaymentMethod.document content.DocumentStateEpisode.document
''')
_decide(exempt('Evento, evidencia o instantánea inmutable: se informa, nunca se corrige.'), '''
    accounts.BillingContextEvent.document accounts.DeliveryReviewDocumentEvidence.document
    accounts.DeliveryMessage.documents accounts.DeliveryPromptSource.document accounts.IssueAttachment.document
    content.DocumentNoteEvent.document content.EmailAttachmentSnapshot.source_document
''')
_decide(exempt('Espejo de sistema de sólo lectura.'), '''
    content.BuildingOnDemandContractMirror.document
    content.BuildingWithUsContractMirror.document content.ContractTemplate.mirror_document
    content.ContractTemplateMirror.document
''')
_decide(gap('Contrato, otrosí y hosting del contexto pertenecen al proyecto del documento '
            '(accounts/services/billing_context.py).'), 'accounts.CollectionAccountContext.document')
_decide(gap('La evidencia de hosting pertenece al mismo hosting del proyecto (hosting_context).'),
        'accounts.HostingEvidence.document')
_decide(gap('El documento de una entrega es del proyecto, o un documento sin asignar de su cliente '
            '(delivery_workflow._owned_document).'), '''
    accounts.ProjectContract.document accounts.ContractAmendment.document accounts.DeliveryDocumentLink.document
''')

# ── content.DocumentFolder ───────────────────────────────────────────────────

_decide(covered('DC2', 'DC6', 'DC9', 'DC10', 'DC11'), 'content.Document.folder')
_decide(covered('DC4', 'DC6'), 'content.DocumentFolder.parent')
_decide(exempt('Fija dónde vive el espejo de sistema de la plantilla de contrato.'),
        'content.ContractTemplate.mirror_folder')
_decide(gap('Apunta a un ancestro archivado, y sólo mientras el registro está archivado '
            '(document_archive_service).'), 'content.Document.archived_via_folder content.DocumentFolder.archived_via_folder')

# ── content.CommunicationThread, content.IncomeRecord, content.HostingRecord ─

_decide(exempt('Hijo en cascada sin copia de cliente ni proyecto.'), 'content.CommunicationMessage.thread')
_decide(covered('AC2', 'AC12'), 'content.IncomeRecord.expected_income')
_decide(covered('AC9', 'AC10'), 'content.Document.income_record')
_decide(exempt('Aviso duradero del cierre del ingreso.'), 'content.IncomeCompletionNotice.income')
_decide(exempt('Evidencia de los ingresos seleccionados al liquidar: se conserva para revisión y reversa, nunca se limpia.'),
        'content.IncomeSettlement.parents')
_decide(gap('El destino es un ingreso esperado y la fila es una deducción (serializers/accounting.py).'),
        'content.ExpenseRecord.source_income')
_decide(covered('AC5'), 'content.HostingCycle.hosting_record')
_decide(gap('Proyecto y cliente de la cuenta iguales a los del hosting, que además es una fuente registrada '
            '(billing_context).'), 'content.Document.hosting_record')
_decide(gap('Proyecto y cliente del hosting iguales a los de su ProjectHosting (hosting_context).'),
        'accounts.ProjectHostingAccountingSource.hosting_record')


# ── Discovery ────────────────────────────────────────────────────────────────

def anchors():
    return [get_user_model(), *(apps.get_model(label) for label in ANCHORS)]


def discover():
    """``{'app.Model.field': anchor label}`` for every relation pointing at an anchor."""
    found = {}
    for anchor in anchors():
        for reverse in anchor._meta.get_fields(include_hidden=True):
            if not reverse.auto_created or reverse.concrete:
                continue
            model = reverse.related_model
            if model._meta.auto_created:
                continue  # an M2M's own join table: the M2M field itself is listed
            found[f'{model._meta.label}.{reverse.field.name}'] = anchor._meta.label
    return found


def decision_for(key):
    from content.services.client_merge_policy import AUTHORSHIP_RELATIONS
    if key in DECISIONS:
        return DECISIONS[key]
    return AUTHORSHIP if key in AUTHORSHIP_RELATIONS else None


def undecided(found=None):
    """Discovered relations without a decision: each one fails the inventory test."""
    found = discover() if found is None else found
    return sorted(key for key in found if decision_for(key) is None)


def stale(found=None):
    """Decisions whose relation no longer exists."""
    found = discover() if found is None else found
    return sorted(set(DECISIONS) - set(found))


def unknown_rules(catalog_ids):
    """Rule ids cited by a ``covered`` decision that the catalog does not have."""
    cited = {rule for decision in DECISIONS.values() for rule in decision.rules}
    return sorted(cited - set(catalog_ids))


def summary(found=None):
    """``{anchor: {status: count}}`` of the discovered relations, for reports."""
    found = discover() if found is None else found
    counts = {}
    for key, anchor in found.items():
        decision = decision_for(key)
        counts.setdefault(anchor, Counter())[decision.status if decision else 'undecided'] += 1
    return {anchor: dict(statuses) for anchor, statuses in sorted(counts.items())}
