from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import HostingSubscription, Payment, PaymentHistory, Project
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
    DocumentThread,
    DocumentTag,
    EmailLog,
    FinancingAgreement,
    FinancingAgreementNumberSequence,
    LinkedInPost,
    Linktree,
    LinktreeTemplate,
    LinktreeTemplateVersion,
    McpRequestLog,
    PortfolioWork,
    ProjectBrandAsset,
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

        # Order matters because of PROTECT chains:
        #   CommunicationAttachment ─PROTECT→ Document
        #   CommunicationMessage.reply_to ─PROTECT→ CommunicationMessage
        #   Payment ─PROTECT→ HostingSubscription ─PROTECT→ Project
        #   ProjectPhase ─PROTECT→ BusinessProposal
        # So: payments → subscriptions → projects (cascades the platform graph:
        # phases, requirements, deliverables, change requests, bugs) → proposals.
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
            (Project, 'projects (+ platform graph)'),
            (BusinessProposal, 'business proposals'),
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
