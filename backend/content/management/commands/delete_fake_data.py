from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from accounts.models import (
    BugReport, ChangeRequest, Deliverable, HostingSubscription, Notification,
    Payment, PaymentHistory, Project, ProjectAccessNote, ProjectAdminAccess,
    ProjectDataModelEntity, ProjectPhase,
)
from content.models import (
    AdditionalModuleShareLink,
    BlogPost,
    BusinessProposal,
    CommunicationMessage,
    CommunicationThread,
    CommunicationFolder,
    Contact,
    Document,
    DocumentFolder,
    DocumentStateEpisode,
    DocumentThread,
    DocumentTag,
    EmailLog,
    FinancingAgreement,
    FinancingAgreementNumberSequence,
    HostingRecord,
    IncomeRecord,
    LinkedInPost,
    Linktree,
    LinktreeTemplate,
    LinktreeTemplateVersion,
    McpRequestLog,
    PortfolioWork,
    ProjectBrandAsset,
    ProjectRetentionContext,
    QRCard,
    Task,
    WebAppDiagnostic,
)
from content.fake_data import ensure_fake_data_allowed

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Delete fake content data across features (contacts, proposals, blog, portfolio, '
        'tasks, diagnostics, commercial documents). Superusers, staff and catalog/config '
        'rows (DocumentType, IssuerProfile) are preserved.'
    )

    """
    To delete fake data via console, run:
    python3 manage.py delete_fake_data --confirm
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm that you want to delete all fake data',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        ensure_fake_data_allowed('delete_fake_data')
        if not options['confirm']:
            self.stdout.write(self.style.WARNING(
                'This will delete ALL contacts, proposals, blog posts, portfolio works, '
                'tasks, diagnostics and commercial documents.\n'
                'Run with --confirm to proceed: python manage.py delete_fake_data --confirm'
            ))
            return

        # Signed and review PDF evidence protects documents and source messages.
        # A fake reset explicitly clears that graph before those source records.
        project_ids = list(Project.objects.values_list('pk', flat=True))
        retention_context_ids = list(ProjectRetentionContext.objects.values_list('pk', flat=True))
        projects = Project.objects.filter(pk__in=project_ids)
        from accounts.management.commands._billing_seed_helpers import clear_fake_billing
        clear_fake_billing(projects, retention_context_ids=retention_context_ids)
        from accounts.management.commands._seed_helpers import clear_fake_delivery
        clear_fake_delivery(projects, retention_context_ids=retention_context_ids)
        from accounts.management.commands._project_collaboration_seed import clear_fake_project_collaboration
        clear_fake_project_collaboration(projects, retention_context_ids=retention_context_ids)

        # These rows previously cascaded from Project. Their new protection is
        # intentional; this confirmed development reset removes roots first.
        owners = Q(project_id__in=project_ids) | Q(retention_context_id__in=retention_context_ids)
        for model in (
            ProjectAdminAccess, ProjectAccessNote, ProjectDataModelEntity,
            ChangeRequest, BugReport, Notification, Deliverable, ProjectPhase,
        ):
            model.objects.filter(owners).delete()

        from secure_links.models import SecureLink
        SecureLink.objects.filter(owners).delete()

        # Order matters because of PROTECT chains:
        #   CommunicationAttachment ─PROTECT→ Document
        #   CommunicationMessage.reply_to ─PROTECT→ CommunicationMessage
        #   Payment ─PROTECT→ HostingSubscription ─PROTECT→ Project
        #   ProjectPhase ─PROTECT→ BusinessProposal
        # Project roots are protected: clear their records before projects,
        # then proposals. Catalog/configuration rows remain in place.
        # Break only the self-reply pointers inside the dataset being removed;
        # message deletion then cascades attachments and date corrections.
        signed_documents = FinancingAgreement.objects.exclude(
            signed_document='',
        ).exclude(signed_document__isnull=True)
        for agreement in signed_documents.iterator():
            agreement.signed_document.delete(save=False)
        # A full development reset removes both financing cycles together.
        # Dissolve their protected self-reference before deleting the roots.
        FinancingAgreement.objects.update(previous_agreement=None)
        deleted, _ = FinancingAgreement.objects.all().delete()
        FinancingAgreementNumberSequence.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(
            f'Deleted financing agreements ({deleted} rows)',
        ))

        CommunicationMessage.objects.update(reply_to=None)
        deleted, _ = CommunicationMessage.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(
            f'Deleted communication messages ({deleted} rows)'
        ))

        # The catalog itself is deploy-seeded configuration and is preserved.
        # Only the representative share history carries the [Demo] marker.
        deleted, _ = AdditionalModuleShareLink.objects.filter(
            recipient_label__startswith='[Demo] Catálogo',
        ).delete()
        self.stdout.write(self.style.SUCCESS(
            f'Deleted additional-module demo shares ({deleted} rows)'
        ))

        for model, label in (
            (Contact, 'contacts'),
            (CommunicationThread, 'communication threads'),
            (PaymentHistory, 'payment history'),
            (Payment, 'payments'),
            (HostingSubscription, 'hosting subscriptions'),
            (BlogPost, 'blog posts'),
            (PortfolioWork, 'portfolio works'),
            (Task, 'tasks'),
            (WebAppDiagnostic, 'diagnostics'),
        ):
            deleted, _ = model.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {label} ({deleted} rows)'))

        # Threads are gone; dissolve the protected folder tree leaf-first.
        while CommunicationFolder.objects.filter(children__isnull=True).exists():
            CommunicationFolder.objects.filter(children__isnull=True).delete()

        # Thread items protect their documents: dissolve the demo histories
        # before removing the documents themselves.
        deleted, _ = DocumentThread.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(
            f'Deleted document threads ({deleted} rows)'
        ))

        # The contract template is catalog data and survives, but it protects
        # its Document-manager window: release the link before the wipe.
        from content.models import ContractTemplate
        ContractTemplate.objects.exclude(mirror_document=None).update(mirror_document=None)

        # Documents cascade to items, collection account, payment methods.
        deleted, _ = Document.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted documents ({deleted} rows)'))

        # Tags are independent (M2M cleared with documents already).
        deleted, _ = DocumentTag.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted document tags ({deleted} rows)'))

        # Folders use a PROTECT self-FK: delete leaves first, repeat until a pass
        # deletes nothing (empty, or a cycle we can't break).
        total_folders = 0
        while True:
            count, _ = DocumentFolder.objects.filter(children__isnull=True).delete()
            if not count:
                break
            total_folders += count
        self.stdout.write(self.style.SUCCESS(f'Deleted document folders ({total_folders} rows)'))

        # Accounting: only rows tagged fake:accounting are removed (imported
        # spreadsheet data and manual records are preserved). The entity
        # registry is the single owner of "what is an accounting model".
        from content.services.accounting_service import ENTITY_MODELS

        accounting_total = 0
        for model in ENTITY_MODELS.values():
            deleted, _ = model.objects.filter(
                source_ref='fake:accounting',
            ).delete()
            accounting_total += deleted
        self.stdout.write(self.style.SUCCESS(
            f'Deleted fake accounting rows ({accounting_total} rows)'
        ))

        for model, label in (
            (EmailLog, 'email history'),
            (LinkedInPost, 'LinkedIn history'),
            (LinktreeTemplateVersion, 'linktree template versions'),
            (LinktreeTemplate, 'linktree templates'),
            (Linktree, 'linktrees'),
            (ProjectBrandAsset, 'project brand resources'),
            (QRCard, 'QR cards'),
            (McpRequestLog, 'MCP request history'),
        ):
            deleted, _ = model.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {label} ({deleted} rows)'))

        # Imported/manual accounting previously survived the project's SET_NULL
        # link. Keep that behavior; retained history remains read-only.
        for model in (IncomeRecord, HostingRecord):
            model.objects.exclude(source_ref='fake:accounting').filter(
                project__isnull=False, retention_context__isnull=True,
            ).update(project=None)

        for model, label in (
            (DocumentStateEpisode, 'project state history'),
            (Project, 'projects'),
            (BusinessProposal, 'business proposals'),
            (ProjectRetentionContext, 'project retention contexts'),
        ):
            deleted, _ = model.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {label} ({deleted} rows)'))

        # A representative refresh is a full development reset.  Removing
        # non-staff accounts last makes client/project distributions repeatable
        # while preserving operator/admin access.
        deleted_users, _ = User.objects.filter(
            is_staff=False,
            is_superuser=False,
        ).delete()
        self.stdout.write(self.style.SUCCESS(
            f'Deleted non-staff development users ({deleted_users} rows)',
        ))

        # Superusers and staff users are intentionally never deleted.
        protected = User.objects.filter(is_superuser=True).count() \
            + User.objects.filter(is_staff=True, is_superuser=False).count()
        if protected:
            self.stdout.write(self.style.WARNING(
                f'Skipped {protected} superuser/staff account(s) — protected from deletion'
            ))

        self.stdout.write(self.style.SUCCESS(
            'Fake content data deleted. DocumentType / IssuerProfile / '
            'additional-module catalogs preserved.'
        ))
