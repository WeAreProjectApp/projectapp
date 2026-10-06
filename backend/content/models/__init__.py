"""
This package initializes the models for the ProjectApp application.

The following models are imported:
    - Contact: Model handling contact-related information.
    - PortfolioWork: Model for portfolio work entries.
    - HourPackage: Catalog of development hour packages per nationality.
    - BusinessProposal: Model for client business proposals.
    - ProposalSection: Individual sections within a proposal.
"""

from .contact import Contact
from .portfolio_works import PortfolioWork
from .hour_packages import (
    HourPackage,
    HourPackageSettings,
    Nationality,
    CURRENCY_BY_NATIONALITY,
    BASE_RATE_FIELD_BY_NATIONALITY,
)
from .business_proposal import BusinessProposal, ProposalAlert
from .proposal_section import ProposalSection
from .proposal_project_stage import ProposalProjectStage
from .blog_post import BlogPost
from .proposal_view_event import ProposalViewEvent
from .proposal_section_view import ProposalSectionView
from .proposal_change_log import ProposalChangeLog
from .proposal_share_link import ProposalShareLink
from .qr_cards import QRCard
from .linktree import Linktree, LinktreeButton
from .proposal_default_config import ProposalDefaultConfig
from .email_template_config import EmailTemplateConfig
from .email_body import EmailBody
from .email_log import EmailLog
from .email_log_target import EmailLogTarget
from .email_delivery_snapshot import (
    EmailAttachmentSnapshot,
    EmailDeliverySnapshot,
    EmailLinkSnapshot,
)
from .document import Document
from .document_thread import DocumentThread, DocumentThreadItem
from .document_type import DocumentType
from .document_folder import DocumentFolder
from .document_tag import DocumentTag
from .document_state import (
    DocumentState,
    DocumentStateEpisode,
    DocumentStateEpisodeEvent,
    DocumentStateGroup,
)
# Generic names for the shared PA-88 engine. The compatibility aliases keep
# existing document imports and migrations stable while projects reuse the
# exact same tables, constraints and service layer.
WorkflowState = DocumentState
WorkflowStateEpisode = DocumentStateEpisode
WorkflowStateEpisodeEvent = DocumentStateEpisodeEvent
WorkflowStateGroup = DocumentStateGroup
from .document_note import DocumentNote, DocumentNoteEvent
from .issuer_profile import IssuerProfile
from .document_number_sequence import (
    ClientDocumentNumberSequence,
    DocumentNumberSequence,
)
from .document_collection_account import DocumentCollectionAccount
from .document_item import DocumentItem
from .document_payment_method import DocumentPaymentMethod
from .company_settings import CompanySettings
from .proposal_document import ProposalDocument
from .contract_template import ContractTemplate, ContractTemplateVersion, ContractTemplateMirror
from .confidentiality_template import ConfidentialityTemplate
from .linkedin_token import LinkedInToken
from .linkedin_post import LinkedInPost
from .task import Task
from .task_alert import TaskAlert
from .task_comment import TaskComment
from .web_app_diagnostic import WebAppDiagnostic
from .diagnostic_attachment import DiagnosticAttachment
from .diagnostic_section import DiagnosticSection
from .diagnostic_change_log import DiagnosticChangeLog
from .diagnostic_view_event import DiagnosticViewEvent, DiagnosticSectionView
from .diagnostic_default_config import DiagnosticDefaultConfig
from .accounting_base import AccountingRecordBase, Ledger, PartnerSplitMixin
from .pocket_movement import PocketMovement
from .income_record import IncomeRecord
from .expense_record import ExpenseRecord
from .hosting_record import HostingRecord
from .hosting_cycle import HostingCycle
from .recurring_category import RecurringCategory
from .recurring_payment import RecurringPayment
from .ads_spend_record import AdsSpendRecord
from .card_balance_snapshot import CardBalanceSnapshot
from .credit_card import CreditCard
from .accounting_change_log import AccountingChangeLog
from .credit_card_statement import (
    CreditCardStatement,
    CreditCardTransaction,
    MerchantAlias,
    TransactionCategory,
    normalize_descriptor,
)
from .accounting_settings import AccountingSettings
from .notification_recipient import NotificationRecipient
from .email_copy_recipient import EmailCopyRecipient

# Compatibility alias for code importing the pre-0213 model name.
ClientEmailCopyRecipient = EmailCopyRecipient
from .communication import (
    CommunicationAttachment,
    CommunicationMessage,
    CommunicationMessageDateCorrection,
    CommunicationMessageRevision,
    CommunicationThread,
)
from .view_map import ViewMapSettings
from .mcp_connector import McpConnector
from .mcp_credential import McpCredential
from .mcp_action_intent import McpActionIntent
from .mcp_upload import McpUpload
from .mcp_request_log import McpRequestLog
from .additional_module import (
    AdditionalModule,
    AdditionalModuleCategory,
    AdditionalModuleShareLink,
    AdditionalModuleShareView,
)
from .explainer_video_settings import ExplainerVideoSettings
from .financing_agreement import (
    FinancingAgreement,
    FinancingAgreementEvent,
    FinancingAgreementNumberSequence,
    FinancingAgreementTemplate,
    FinancingPolicyRevision,
)
from .proposal_formalization import ProposalFormalization, ProposalFormalizationFile

from .entity_history import EntityHistory, EntityRevision

from .project_brand_asset import ProjectBrandAsset

from .linktree_template import LinktreeTemplate, LinktreeTemplateVersion, LinktreeTemplateClick
from .linktree_asset import LinktreeAsset

from .communication_folder import CommunicationFolder
from .video_resource import VideoResource

from .proposal_approval_file import ProposalApprovalFile

from .proposal_contract_snapshot import (
    ProposalContractSnapshot, ProposalContractSnapshotFile, ProposalContractChangeIntent,
)
from .project_retention import ProjectRetentionContext
