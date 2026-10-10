"""Explicit policies for every incoming User/UserProfile relation.

Hidden ``related_name='+'`` relations are part of the inventory. New relations
fail closed until reviewed here; authorship is never inferred from a suffix.
"""
from dataclasses import dataclass

from django.contrib.auth import get_user_model

from accounts.models import UserProfile

RELINK = 'relink'
COLLISION = 'relink_with_collision'
SPECIAL = 'special'
NEVER = 'never_rewrite'
BLOCK = 'blocks_merge'


def _keys(text):
    return tuple(text.split())


AUTHORSHIP_RELATIONS = _keys('''
admin.LogEntry.user
content.AccountingChangeLog.actor
content.Document.created_by content.Document.updated_by content.Document.signed_by
content.DocumentThread.created_by content.DocumentThread.updated_by
content.DocumentThreadItem.linked_by content.DocumentThreadItem.updated_by
content.DocumentFolder.created_by
content.DocumentState.created_by content.DocumentState.updated_by
content.DocumentStateEpisode.opened_by content.DocumentStateEpisode.closed_by
content.DocumentStateEpisodeEvent.actor
content.DocumentNote.created_by content.DocumentNote.resolved_by content.DocumentNote.deleted_by
content.DocumentNoteEvent.actor content.ContractTemplateVersion.author
content.BuildingWithUsProgramRevision.author content.BuildingWithUsContractRevision.author
content.TaskComment.author content.WebAppDiagnostic.created_by content.DiagnosticAttachment.uploaded_by
content.PocketMovement.created_by content.RecurringPayment.created_by content.IncomeRecord.created_by
content.ExpenseRecord.created_by content.HostingRecord.created_by content.HostingCycle.created_by
content.AdsSpendRecord.created_by content.CardBalanceSnapshot.created_by content.CreditCard.created_by
content.CreditCardStatement.created_by content.CreditCardTransaction.created_by content.MerchantAlias.created_by
content.NotificationRecipient.created_by
content.CommunicationThread.created_by content.CommunicationThread.updated_by
content.CommunicationMessage.created_by content.CommunicationMessage.updated_by content.CommunicationMessage.voided_by
content.CommunicationMessageRevision.edited_by content.CommunicationMessageDateCorrection.corrected_by
content.AdditionalModuleShareLink.created_by content.FinancingPolicyRevision.created_by
content.FinancingAgreement.ready_by content.FinancingAgreement.activated_by content.FinancingAgreement.completed_by
content.FinancingAgreement.cancelled_by content.FinancingAgreement.second_cycle_approved_by
content.FinancingAgreement.archived_by content.FinancingAgreement.created_by content.FinancingAgreement.updated_by
content.FinancingAgreementEvent.actor content.ProposalFormalization.created_by
content.VideoResource.updated_by content.ProposalApprovalFile.created_by
content.ProjectRetentionContext.created_by content.ProjectRetentionOperation.actor
content.ProposalProjectReassignment.actor content.DataIntegrityOperation.actor
content.DocumentOwnershipOperation.actor
accounts.UserProfile.archived_by accounts.UserProfile.created_by
accounts.ProjectAdminAccess.updated_by accounts.ProjectAccessNote.created_by accounts.ProjectAccessNote.updated_by
accounts.DeliveryPublication.published_by accounts.DeliveryDocumentLink.created_by
accounts.ContractSignatureEvidence.attested_by accounts.RequirementReview.actor accounts.DeliveryMessage.actor
accounts.DeliveryOperation.actor accounts.DeliveryPromptContext.actor
accounts.ChangeRequest.created_by accounts.ChangeRequestComment.user accounts.BugReport.reported_by accounts.BugComment.user
accounts.Deliverable.uploaded_by accounts.DeliverableVersion.uploaded_by accounts.DeliverableFile.uploaded_by
accounts.DeliverableClientFolder.created_by accounts.DeliverableClientUpload.uploaded_by
accounts.ProjectIdea.author accounts.ProjectIdea.archived_by accounts.ProjectIdeaRevision.editor
accounts.ProjectIdeaCollection.created_by accounts.ProjectClientAccessPolicy.updated_by
accounts.ProjectClientAccessEvent.actor accounts.BillingContextEvent.actor accounts.IssueResponse.actor accounts.IssueEvent.actor
accounts.DeliveryEvidenceEmail.prepared_by accounts.DeliveryEvidenceEmailAttempt.actor
accounts.DeliveryNotificationEvent.actor accounts.DeliveryNotificationAttempt.requested_by
monitoring.CaseActivity.actor secure_links.SecureLink.created_by secure_links.SecureLink.sent_by
secure_links.SecureLinkEvent.actor
''')

RELATION_POLICIES = {key: NEVER for key in AUTHORSHIP_RELATIONS}
RELATION_POLICIES.update(dict.fromkeys(_keys('''
content.CommunicationFolder.client content.CommunicationThread.client
content.DocumentFolder.client_user accounts.Project.client
content.IncomeRecord.client content.HostingRecord.client content.FinancingAgreement.client
content.BusinessProposal.client content.WebAppDiagnostic.client content.EmailLog.client
secure_links.SecureLink.client content.AdditionalModuleShareLink.client
content.LinktreeTemplate.client accounts.ProjectIdea.recipient accounts.ProjectIdeaCollection.recipient
'''), RELINK))
RELATION_POLICIES.update(dict.fromkeys(_keys('''
content.DocumentFolder.managed_client content.CommunicationThread.managed_client
content.ClientDocumentNumberSequence.client_profile auth.User.username accounts.UserProfile.billing_code
secure_links.SecureLink.owner
'''), COLLISION))
# SecureLink.owner participates in UNIQUE(owner, creation_request_id): moving
# it is safe only when S has no receipt for that same idempotency key.
RELATION_POLICIES.update(dict.fromkeys(_keys('''
accounts.UserProfile.user content.Document.client_user
'''), SPECIAL))
RELATION_POLICIES.update(dict.fromkeys(_keys('''
accounts.CommunicationPanelPreference.user accounts.SavedFilterTab.user
accounts.VerificationCode.user accounts.Notification.user
accounts.DeliveryEvidenceEmail.client accounts.DeliveryNotificationEvent.client
accounts.DeliveryPromptContext.client accounts.ProjectClientAccessEvent.recipient
content.ProposalContractChangeIntent.owner
'''), NEVER))
# ProposalContractChangeIntent.owner is the admin who reviewed a sensitive
# confirmation, not the commercial owner (see views/proposal_contract_modality.py).
RELATION_POLICIES.update(dict.fromkeys(_keys('''
content.ProjectRetentionContext.client accounts.ProjectClientAccessPolicy.recipient
content.McpCredential.actor content.Task.assignee auth.User.groups auth.User.user_permissions
'''), BLOCK))
# Number sequences are conditional: with two reserved billing codes D's
# sequence stays with D. Only a transferred code carries its sequence to S.
# Type+id and JSON references have no incoming FK and deliberately never enter
# this registry or the writer (history, audit, emission/approval snapshots).

DIRECT_POLICIES = frozenset(('auth.User.username', 'accounts.UserProfile.billing_code',
                             'auth.User.groups', 'auth.User.user_permissions'))


@dataclass(frozen=True)
class Relation:
    key: str
    model: object
    field: object
    target: object

    def rows_for(self, profile):
        target_id = profile.user_id if self.target is get_user_model() else profile.pk
        return self.model._base_manager.filter(**{self.field.attname: target_id})


def discover_relations():
    """Canonical incoming FK/O2O inventory, including hidden reverse fields."""
    result = {}
    for target in (get_user_model(), UserProfile):
        for reverse in target._meta.get_fields(include_hidden=True):
            if not reverse.auto_created or reverse.concrete:
                continue
            model = reverse.related_model
            if model._meta.auto_created:
                continue  # User's two explicit M2Ms are classified directly.
            field = reverse.field
            key = f'{model._meta.label}.{field.name}'
            result[key] = Relation(key, model, field, target)
    return result


def policy_drift(relations=None):
    discovered = set(discover_relations() if relations is None else relations) | set(DIRECT_POLICIES)
    return {'missing': sorted(discovered - RELATION_POLICIES.keys()),
            'stale': sorted(RELATION_POLICIES.keys() - discovered)}
