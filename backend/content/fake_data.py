"""Shared contract and deterministic context for development seed commands.

The management commands in this project are intentionally callable on their
own.  Keeping the safety check and the clock/random contract here prevents a
child command from bypassing the protections of ``create_fake_data``.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from functools import cached_property

from django.conf import settings
from django.core.management.base import CommandError
from django.utils import timezone


DEFAULT_COUNT = 60
DEFAULT_SEED = 20_260_826


@dataclass(frozen=True)
class SeedContext:
    """Stable random stream and business clock for one seed module."""

    seed: int
    anchor_date: date
    namespace: str

    @property
    def module_seed(self) -> int:
        digest = hashlib.sha256(
            f'{self.seed}:{self.namespace}'.encode('utf-8'),
        ).digest()
        return int.from_bytes(digest[:8], byteorder='big', signed=False)

    @cached_property
    def rng(self) -> random.Random:
        return random.Random(self.module_seed)

    @property
    def anchor_now(self):
        value = datetime.combine(self.anchor_date, time(hour=12))
        return timezone.make_aware(value, timezone.get_current_timezone())

    def uuid(self, natural_key: str) -> uuid.UUID:
        return uuid.uuid5(
            uuid.NAMESPACE_URL,
            f'projectapp:fake:{self.seed}:{self.namespace}:{natural_key}',
        )


def add_seed_arguments(parser, *, count_default: int | None = None) -> None:
    """Add the cross-command deterministic options without duplicating flags."""

    if count_default is not None:
        parser.add_argument(
            '--count',
            type=int,
            default=count_default,
            help=f'Target root-record volume (default: {count_default}).',
        )
    parser.add_argument(
        '--seed',
        type=int,
        default=DEFAULT_SEED,
        help=f'Deterministic dataset seed (default: {DEFAULT_SEED}).',
    )
    parser.add_argument(
        '--anchor-date',
        type=date.fromisoformat,
        default=None,
        metavar='YYYY-MM-DD',
        help='Business-date anchor. Defaults to the current local date.',
    )


def seed_context(options, namespace: str) -> SeedContext:
    anchor_date = options.get('anchor_date') or timezone.localdate()
    return SeedContext(
        seed=int(options.get('seed', DEFAULT_SEED)),
        anchor_date=anchor_date,
        namespace=namespace,
    )


def seed_global_random(context: SeedContext) -> random.Random:
    """Seed legacy global-random consumers while returning an isolated RNG."""

    random.seed(context.module_seed)
    return context.rng


def ensure_fake_data_allowed(command_name: str) -> None:
    """Fail closed before any fake-data command can touch the database.

    The setting is deliberately a positive capability.  Base and production
    settings keep it hard-false; only dedicated development/test settings may
    enable it.  Environment naming or ``DEBUG`` alone is not accepted as proof.
    """

    if getattr(settings, 'FAKE_DATA_ALLOWED', False) is not True:
        raise CommandError(
            f'{command_name} is disabled for this settings module. '
            'Fake data requires FAKE_DATA_ALLOWED=True in a dedicated '
            'development or test configuration.',
        )


# Every concrete accounts/content model must be classified here.  The focused
# contract test compares this set with Django's app registry, turning the
# maintenance rule into an executable check for every future model delivery.
SEEDED_MODELS = {
    'accounts.BugReport', 'accounts.ChangeRequest', 'accounts.DataModelEntity',
    'accounts.CommunicationPanelPreference',
    'accounts.Deliverable', 'accounts.HostingSubscription',
    'accounts.Notification', 'accounts.Payment', 'accounts.Project',
    'accounts.ProjectAccessNote', 'accounts.ProjectAdminAccess',
    'accounts.ProjectDataModelEntity', 'accounts.Requirement',
    'accounts.SavedFilterTab', 'accounts.UserProfile',
    'content.AdsSpendRecord', 'content.BlogPost', 'content.BusinessProposal',
    'content.AdditionalModuleShareLink',
    'content.CardBalanceSnapshot', 'content.EmailCopyRecipient',
    'content.CommunicationFolder', 'content.CommunicationMessage',
    'content.CommunicationThread',
    'content.CompanySettings', 'content.Contact', 'content.CreditCard',
    'content.CreditCardStatement', 'content.Document',
    'content.DocumentThread',
    'content.DocumentFolder', 'content.DocumentState',
    'content.DocumentStateGroup', 'content.DocumentTag', 'content.EmailLog',
    'content.EmailTemplateConfig', 'content.ExpenseRecord',
    'content.FinancingAgreement',
    'content.HostingRecord', 'content.HourPackage', 'content.IncomeRecord',
    'content.IssuerProfile', 'content.LinkedInPost', 'content.Linktree',
    'content.ProjectBrandAsset', 'content.LinktreeTemplate',
    'content.McpConnector', 'content.McpRequestLog', 'content.MerchantAlias',
    'content.NotificationRecipient', 'content.PocketMovement',
    'content.PortfolioWork', 'content.ProposalDefaultConfig', 'content.QRCard',
    'content.RecurringCategory', 'content.RecurringPayment', 'content.Task',
    'content.ViewMapSettings', 'content.WebAppDiagnostic',
}

DERIVED_MODELS = {
    'accounts.BugComment', 'accounts.ChangeRequestComment',
    'accounts.DeliverableClientFolder', 'accounts.DeliverableClientUpload',
    'accounts.DeliverableFile', 'accounts.DeliverableVersion',
    'accounts.PaymentHistory', 'accounts.ProjectPhase',
    'accounts.ProjectScopeItem', 'accounts.RequirementComment',
    'accounts.RequirementHistory', 'content.AccountingChangeLog',
    'content.ClientDocumentNumberSequence', 'content.CommunicationAttachment',
    'content.CommunicationMessageDateCorrection',
    'content.CommunicationMessageRevision',
    'content.CreditCardTransaction', 'content.DiagnosticAttachment',
    'content.DiagnosticChangeLog', 'content.DiagnosticSection',
    'content.DiagnosticSectionView', 'content.DiagnosticViewEvent',
    'content.DocumentCollectionAccount', 'content.DocumentItem',
    'content.DocumentThreadItem',
    'content.DocumentNote', 'content.DocumentNoteEvent',
    'content.DocumentNumberSequence',
    'content.DocumentPaymentMethod', 'content.DocumentStateEpisode',
    'content.DocumentStateEpisodeEvent', 'content.EmailAttachmentSnapshot',
    'content.EmailBody', 'content.EmailDeliverySnapshot',
    'content.EmailLinkSnapshot', 'content.EmailLogTarget',
    'content.EntityHistory', 'content.EntityRevision',
    'content.FinancingAgreementEvent',
    'content.FinancingAgreementNumberSequence',
    'content.HostingCycle', 'content.LinktreeButton', 'content.LinktreeAsset',
    'content.LinktreeTemplateVersion', 'content.LinktreeTemplateClick',
    'content.ProposalAlert', 'content.ProposalChangeLog',
    'content.ProposalDocument', 'content.ProposalProjectStage',
    'content.ProposalSection', 'content.ProposalSectionView',
    'content.ProposalShareLink', 'content.ProposalViewEvent',
    'content.TaskAlert', 'content.TaskComment',
    'content.AdditionalModuleShareView',
}

CATALOG_MODELS = {
    'content.AccountingSettings', 'content.AdditionalModule',
    'content.AdditionalModuleCategory', 'content.ConfidentialityTemplate',
    'content.ContractTemplate', 'content.DiagnosticDefaultConfig',
    'content.DocumentType', 'content.ExplainerVideoSettings',
    'content.FinancingAgreementTemplate', 'content.FinancingPolicyRevision',
    'content.HourPackageSettings', 'content.VideoResource',
}

EXEMPT_MODELS = {
    # Ephemeral verification/confirmation/upload material and real OAuth/MCP
    # credentials must never be fabricated as reusable demo secrets.
    'accounts.VerificationCode', 'content.LinkedInToken',
    'content.ProposalFormalization', 'content.ProposalFormalizationFile',
    'content.McpActionIntent', 'content.McpCredential', 'content.McpUpload',
}


def covered_model_labels() -> set[str]:
    return SEEDED_MODELS | DERIVED_MODELS | CATALOG_MODELS | EXEMPT_MODELS
