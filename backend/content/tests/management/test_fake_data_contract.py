"""Behavioral contract for the representative development dataset."""

from collections import Counter
from datetime import date
from io import StringIO

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count, F, Q

from accounts.models import (
    BugReport,
    ChangeRequest,
    CommunicationPanelPreference,
    Deliverable,
    Project,
    ProjectAdminAccess,
    Requirement,
    UserProfile,
)
from accounts.services.credential_cipher import decrypt_secret
from content.fake_data import SeedContext, covered_model_labels
from content.models import (
    AdditionalModule,
    AdditionalModuleShareLink,
    AdditionalModuleShareView,
    BlogPost,
    BusinessProposal,
    CommunicationMessage,
    CommunicationMessageDateCorrection,
    CommunicationThread,
    Contact,
    Document,
    DocumentCollectionAccount,
    DocumentThread,
    DocumentThreadItem,
    FinancingAgreement,
    HostingRecord,
    IncomeRecord,
    LinkedInPost,
    Linktree,
    McpConnector,
    McpRequestLog,
    ProposalProjectReassignment,
    ProposalShareLink,
    QRCard,
    ProjectRetentionContext,
    Task,
    WebAppDiagnostic,
)


pytestmark = pytest.mark.django_db


def run_command(name, *args, **options):
    options.setdefault('stdout', StringIO())
    options.setdefault('verbosity', 0)
    call_command(name, *args, **options)


@pytest.fixture
def seeded_accounting():
    """Create the full accounting distribution for one focused assertion."""

    run_command(
        'create_fake_accounting', '--count', '60',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )


@pytest.fixture
def seeded_documents():
    """Create related clients, accounting rows and documents."""

    run_command(
        'create_fake_clients_projects', '--count', '30',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )
    run_command(
        'create_fake_accounting', '--count', '30',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )
    run_command(
        'create_fake_documents', '--count', '15',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )


@pytest.fixture
def seeded_communications():
    """Create the representative communication-history distribution."""

    get_user_model().objects.create_user(
        username='fake-admin', email='fake-admin@example.test', is_staff=True,
    )
    run_command(
        'create_fake_clients_projects', '--count', '60',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )
    run_command(
        'create_fake_communications', '--count', '60',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )


def complete_dataset_snapshot():
    """Return stable business values, excluding PKs and auto-managed clocks."""

    return {
        'contacts': list(Contact.objects.order_by('email').values_list(
            'email', 'subject', 'message',
        )),
        'blog_posts': list(BlogPost.objects.order_by('title_es').values_list(
            'title_es', 'category', 'read_time_minutes', 'is_published',
            'published_at', 'sources',
        )),
        'projects': list(Project.objects.order_by(
            'client__email', 'name',
        ).values_list(
            'client__email', 'name', 'status', 'start_date', 'estimated_end_date',
        )),
        'documents': list(Document.objects.order_by(
            'title', 'document_type__code', 'client_user__email', 'uuid',
        ).values_list(
            'uuid', 'document_type__code', 'title', 'status', 'commercial_status',
            'public_number', 'folder__name', 'project__name', 'client_user__email',
            'income_record__concept', 'income_record__period_date',
            'issue_date', 'due_date', 'subtotal', 'tax_total', 'total',
        )),
        'document_threads': list(DocumentThreadItem.objects.order_by(
            'thread__title', 'occurred_on', 'position', 'document__title',
        ).values_list(
            'thread__title', 'document__title', 'occurred_on', 'position',
        )),
        'incomes': list(IncomeRecord.objects.filter(
            source_ref='fake:accounting',
        ).order_by(
            'concept', 'kind', 'period_date', 'client__user__email',
        ).values_list(
            'concept', 'kind', 'client__user__email', 'project__name',
            'period_date', 'total_amount', 'expected_income__concept',
            'expected_income__period_date', 'source_ref',
        )),
        'proposals': list(BusinessProposal.objects.order_by(
            'title', 'uuid',
        ).values_list(
            'uuid', 'title', 'client__user__email', 'status', 'expires_at',
            'sent_at', 'first_viewed_at', 'responded_at',
        )),
        'proposal_shares': list(ProposalShareLink.objects.order_by(
            'proposal__title', 'recipient_email', 'uuid',
        ).values_list(
            'uuid', 'proposal__title', 'recipient_email', 'view_count',
            'first_viewed_at',
        )),
        'diagnostics': list(WebAppDiagnostic.objects.order_by(
            'title', 'client__user__email', 'uuid',
        ).values_list(
            'uuid', 'title', 'client__user__email', 'status', 'currency',
            'investment_amount', 'duration_label', 'size_category', 'view_count',
        )),
        # Seeded conversations only. A project's auto-provisioned mother
        # thread defaults ``last_activity_at`` to the wall clock, so including
        # it would make this snapshot differ between two runs of the SAME seed
        # — turning a determinism check into a clock check. That every project
        # gets a mother is asserted on its own, where it belongs.
        'threads': list(CommunicationThread.objects.filter(
            managed_project__isnull=True, managed_client__isnull=True,
        ).order_by(
            'title',
        ).values_list(
            'title', 'client__user__email', 'project__name', 'status',
            'last_activity_at', 'closed_at',
        )),
        'mcp_history': list(McpRequestLog.objects.order_by(
            'connector__slug', 'detail',
        ).values_list(
            'connector__slug', 'event', 'ok', 'detail', 'created_at',
        )),
    }


def test_model_contract_classifies_every_concrete_business_model():
    actual = {
        model._meta.label
        for app_name in ('accounts', 'content')
        for model in apps.get_app_config(app_name).get_models()
        if not model._meta.proxy
    }

    assert covered_model_labels() == actual


def test_fake_reset_clears_retained_document_ownership(admin_user):
    client = get_user_model().objects.create_user(username='retained-demo-client')
    context = ProjectRetentionContext.objects.create(
        client=client, created_by=admin_user,
        original_project_id=999001, project_name='Removed demo project',
    )
    document = Document.objects.create(
        title='Retained demo document', retention_context=context,
    )

    run_command('delete_fake_data', '--confirm')

    assert not Document.objects.filter(pk=document.pk).exists()
    assert not ProjectRetentionContext.objects.filter(pk=context.pk).exists()
    assert not get_user_model().objects.filter(pk=client.pk).exists()
    assert get_user_model().objects.filter(pk=admin_user.pk).exists()


def test_fake_reset_removes_retained_access_owner_graph(admin_user):
    client = get_user_model().objects.create_user(username='retained-access-client')
    context = ProjectRetentionContext.objects.create(
        client=client, created_by=admin_user,
        original_project_id=999002, project_name='Removed access project',
    )
    access = ProjectAdminAccess.objects.create(
        retention_context=context,
        environment=ProjectAdminAccess.Environment.PRODUCTION,
        admin_url='https://retained-access.example.test/admin/',
        updated_by=admin_user,
    )

    assert access.retention_context_id == context.pk

    run_command('delete_fake_data', '--confirm')

    assert not ProjectAdminAccess.objects.filter(pk=access.pk).exists()
    assert not ProjectRetentionContext.objects.filter(pk=context.pk).exists()
    assert not get_user_model().objects.filter(pk=client.pk).exists()
    assert get_user_model().objects.filter(pk=admin_user.pk).exists()


def test_fake_reset_removes_reassignment_receipt_before_proposal(admin_user):
    proposal = BusinessProposal.objects.create(
        title='Proposal with reassignment audit',
        client_email='audit-client@example.test',
    )
    receipt = ProposalProjectReassignment.objects.create(
        proposal=proposal,
        request_id='fake-reset-reassignment',
        payload_hash='a' * 64,
        source_project_id=101,
        target_project_id=202,
        reason='Development reset regression',
        impact={},
        result={},
        actor=admin_user,
    )

    run_command('delete_fake_data', '--confirm')

    assert not ProposalProjectReassignment.objects.filter(pk=receipt.pk).exists()
    assert not BusinessProposal.objects.filter(pk=proposal.pk).exists()
    assert get_user_model().objects.filter(pk=admin_user.pk).exists()


def test_fake_reset_scopes_secure_link_cleanup_to_project_owners():
    from secure_links.models import SecureLink, SecureLinkEvent

    run_command('create_fake_secure_links')
    platform_project_ids = set(Project.objects.filter(
        name__startswith='Secure links demo ',
    ).values_list('pk', flat=True))
    platform_link_ids = set(SecureLink.objects.filter(
        project_id__in=platform_project_ids,
    ).values_list('pk', flat=True))
    platform_event_ids = set(SecureLinkEvent.objects.filter(
        link_id__in=platform_link_ids,
    ).values_list('pk', flat=True))
    standalone_link = SecureLink.objects.filter(
        project__isnull=True, retention_context__isnull=True,
    ).order_by('pk').first()

    assert len(platform_event_ids) >= len(platform_link_ids) > len(platform_project_ids) > 0
    assert standalone_link is not None

    run_command('delete_fake_data', '--confirm')

    assert not Project.objects.filter(pk__in=platform_project_ids).exists()
    assert not SecureLink.objects.filter(pk__in=platform_link_ids).exists()
    assert not SecureLinkEvent.objects.filter(pk__in=platform_event_ids).exists()
    assert SecureLink.objects.filter(pk=standalone_link.pk).exists()


def test_seed_context_replays_the_same_random_stream():
    first = SeedContext(20260826, date(2026, 8, 26), 'documents')
    second = SeedContext(20260826, date(2026, 8, 26), 'documents')

    assert [first.rng.randint(1, 10_000) for _ in range(5)] == [
        second.rng.randint(1, 10_000) for _ in range(5)
    ]


def test_fake_command_fails_closed_without_explicit_capability(settings):
    settings.FAKE_DATA_ALLOWED = False

    with pytest.raises(CommandError, match='FAKE_DATA_ALLOWED=True'):
        run_command('create_contacts', '1')

    assert not Contact.objects.exists()


def test_contact_seed_replays_identical_natural_data():
    args = ('4', '--seed', '19', '--anchor-date', '2026-08-26')
    run_command('create_contacts', *args)
    first = list(Contact.objects.order_by('pk').values_list(
        'email', 'subject', 'message',
    ))

    run_command('delete_fake_data', '--confirm')
    run_command('create_contacts', *args)
    second = list(Contact.objects.order_by('pk').values_list(
        'email', 'subject', 'message',
    ))

    assert second == first


def test_client_project_seed_has_the_target_skew():
    run_command(
        'create_fake_clients_projects', '--count', '60',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )
    project_counts = Counter(
        UserProfile.objects.clients()
        .annotate(project_total=Count('user__projects'))
        .values_list('project_total', flat=True)
    )

    assert UserProfile.objects.clients().count() == 60
    assert Project.objects.count() == 67
    assert project_counts == Counter({0: 30, 1: 20, 3: 9, 20: 1})


def test_client_project_seed_covers_the_real_lifecycle():
    run_command(
        'create_fake_clients_projects', '--count', '60',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )

    assert set(Project.objects.values_list(
        'current_state__system_key', flat=True,
    )) == {
        'development', 'active', 'evolving', 'suspended', 'completed',
        'decommissioned',
    }
    assert not Project.objects.filter(current_state__isnull=True).exists()
    assert not Project.objects.filter(state_review_required=True).exists()


def test_client_project_seed_populates_secure_access_detail():
    run_command(
        'create_fake_clients_projects', '--count', '1',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )

    project = Project.objects.order_by('pk').first()
    accesses = list(project.admin_accesses.order_by('environment'))
    notes = list(project.access_notes.order_by('title'))

    assert {access.environment for access in accesses} == {
        ProjectAdminAccess.Environment.PRODUCTION,
        ProjectAdminAccess.Environment.STAGING,
    }
    assert (
        project.admin_url,
        project.admin_username,
        project.admin_password_encrypted,
    ) == ('', '', '')
    assert all(
        decrypt_secret(access.admin_password_encrypted).startswith('demo-only-')
        for access in accesses
    )
    assert {note.title for note in notes} == {
        'Contacto técnico de respaldo',
        'Token de integración demo',
    }
    assert all(
        note.content_encrypted not in {
            'Canal de soporte demo: soporte@example.test',
            f'demo-token-not-secret-{project.pk}',
        }
        for note in notes
    )


def test_accounting_seed_links_each_record_to_a_client(seeded_accounting):
    assert not IncomeRecord.objects.filter(client__isnull=True).exists()
    assert not HostingRecord.objects.filter(client__isnull=True).exists()


def test_accounting_seed_spans_past_future_dates(seeded_accounting):
    assert IncomeRecord.objects.filter(period_date__lt=date(2026, 8, 26)).exists()
    assert IncomeRecord.objects.filter(period_date__gt=date(2026, 8, 26)).exists()
    assert HostingRecord.objects.filter(valid_to__lt=date(2026, 8, 26)).exists()
    assert HostingRecord.objects.filter(valid_to__gt=date(2026, 8, 26)).exists()


def test_platform_seed_reaches_the_per_list_volume_target():
    run_command(
        'seed_platform_data', '--skip-collection-accounts',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )
    run_command(
        'enrich_platform_data', '--count', '60', '--notifications', '60',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )
    project = Project.objects.order_by('pk').first()

    assert Requirement.objects.filter(stage__phase__scope__contract__project=project).count() == 60
    assert Deliverable.objects.filter(project=project).count() == 60
    assert ChangeRequest.objects.filter(project=project).count() == 60
    assert BugReport.objects.filter(project=project).count() == 60


@pytest.fixture
def seeded_review_workflow():
    """Representative contract, amendment, partial reviews and internal drafts."""
    run_command(
        'seed_platform_data', '--skip-collection-accounts',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )
    return Project.objects.order_by('pk').first()


def test_platform_seed_links_current_scope_to_signed_contract_amendment(seeded_review_workflow):
    from accounts.models import DeliveryScope
    from accounts.services.delivery_workflow import signature_state
    scope = DeliveryScope.objects.get(contract__project=seeded_review_workflow, is_current=True)

    assert scope.amendment.contract_id == scope.contract_id
    assert signature_state(scope.contract)['signature_status'] == 'portal'
    assert signature_state(scope.amendment)['signature_status'] == 'external'


def test_platform_seed_preserves_partial_client_decisions(seeded_review_workflow):
    from accounts.models import RequirementReview
    decisions = set(RequirementReview.objects.filter(
        requirement__stage__phase__scope__contract__project=seeded_review_workflow,
    ).values_list('decision', flat=True))

    assert decisions == {'approved', 'objected', 'rejected'}


def test_platform_seed_hides_internal_draft_stage_from_client(seeded_review_workflow):
    from accounts.models import DeliveryStage
    from accounts.services.delivery_workflow import overview
    project = seeded_review_workflow
    draft = DeliveryStage.objects.get(phase__scope__contract__project=project, key='demo-draft')

    body = overview(project.pk, project.client)

    client_stage_ids = {
        stage['id'] for scope in body['scopes'] for phase in scope['phases'] for stage in phase['stages']
    }
    assert draft.pk not in client_stage_ids
    assert draft.requirements.exists()


def test_platform_fake_reset_clears_protected_review_graph(
    seeded_review_workflow, django_capture_on_commit_callbacks,
):
    from django.core.files.base import ContentFile
    from accounts.management.commands._seed_helpers import _demo_pdf
    from accounts.models import (
        DeliveryPublication, DeliveryReviewDocumentEvidence, ProjectContract,
        RequirementReview,
    )
    review = RequirementReview.objects.filter(
        publication__stage__phase__scope__contract__project=seeded_review_workflow,
    ).first()
    evidence = DeliveryReviewDocumentEvidence.objects.create(
        review=review, document=review.publication.stage.document_links.first().document,
        title='Respaldo de conformidad externa', sha256='f' * 64,
    )
    evidence.file.save('approval-evidence.pdf', ContentFile(_demo_pdf(evidence.title)))
    storage, filename = evidence.file.storage, evidence.file.name

    with django_capture_on_commit_callbacks(execute=True):
        run_command('delete_fake_data', '--confirm')

    assert not ProjectContract.objects.exists()
    assert not DeliveryPublication.objects.exists()
    assert not DeliveryReviewDocumentEvidence.objects.exists()
    assert not storage.exists(filename)


def test_mihuella_flush_replays_document_identity():
    """Recreating the same seed must retain the documents' public identities."""
    from accounts.management.commands.seed_mihuella import CLIENT_EMAIL

    seed_args = ('--seed', '19', '--anchor-date', '2026-08-26')
    run_command('seed_mihuella', *seed_args)
    first_snapshot = list(Document.objects.filter(
        client_user__email=CLIENT_EMAIL, title__startswith='[Seed]',
    ).order_by('title').values_list('uuid', 'title'))

    run_command('seed_mihuella', '--flush', *seed_args)

    assert len(first_snapshot) == 4
    assert list(Document.objects.filter(
        client_user__email=CLIENT_EMAIL, title__startswith='[Seed]',
    ).order_by('title').values_list('uuid', 'title')) == first_snapshot


def test_mihuella_flush_preserves_records_outside_its_seed(seeded_review_workflow):
    """Resetting this demo must preserve other agreements and client history."""
    from accounts.management.commands.seed_mihuella import CLIENT_EMAIL, PROJECT_NAME
    from accounts.models import ProjectContract
    from content.models import CommunicationThread

    seed_args = ('--seed', '19', '--anchor-date', '2026-08-26')
    run_command('seed_mihuella', *seed_args)
    client = get_user_model().objects.get(email=CLIENT_EMAIL)
    role = client.profile.role
    client_thread = CommunicationThread.objects.get(client=client.profile, project__name=PROJECT_NAME)
    original_project_id = client_thread.project_id
    document = Document.objects.create(
        title='Contrato externo del cliente', client_user=client,
    )
    other_project = Project.objects.create(name='Proyecto fuera de Mi Huella', client=client)
    other_document = Document.objects.create(
        title='[Seed] Documento de otro proyecto', project=other_project, client_user=client,
    )
    other_proposal = BusinessProposal.objects.create(
        title='Propuesta fuera de Mi Huella', client_email=CLIENT_EMAIL,
    )
    foreign_contract = ProjectContract.objects.get(
        project=seeded_review_workflow, key='demo-contract',
    )
    preserved_ids = [document.pk, other_document.pk, foreign_contract.document_id]

    run_command('seed_mihuella', '--flush', *seed_args)

    assert Document.objects.filter(pk__in=preserved_ids).count() == 3
    assert ProjectContract.objects.get(pk=foreign_contract.pk).document_id == foreign_contract.document_id
    assert Project.objects.get(pk=other_project.pk).client_id == client.pk
    assert BusinessProposal.objects.filter(pk=other_proposal.pk).exists()
    assert get_user_model().objects.get(pk=client.pk).profile.role == role
    client_thread.refresh_from_db()
    assert client_thread.client_id == client.profile.pk
    assert client_thread.project_id is None
    assert client_thread.managed_project_id is None
    assert client_thread.retention_context.original_project_id == original_project_id
    assert client_thread.retention_context.retained_records == {
        'content.communicationthread': [str(client_thread.pk)],
    }


def test_platform_seed_configures_communication_preferences():
    admin = get_user_model().objects.create_user(
        username='preference-admin',
        email='preference-admin@example.test',
        is_staff=True,
    )
    CommunicationPanelPreference.objects.create(user=admin)

    run_command(
        'enrich_platform_data', '--count', '1', '--notifications', '1',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )

    assert CommunicationPanelPreference.objects.filter(user=admin).values(
        'navigation_mode', 'thread_order', 'page_size', 'default_channel',
        'show_manual_help', 'navigation_width',
    ).get() == {
        'navigation_mode': CommunicationPanelPreference.NAVIGATION_CLIENT,
        'thread_order': CommunicationPanelPreference.ORDER_TITLE,
        'page_size': 50,
        'default_channel': CommunicationPanelPreference.CHANNEL_EMAIL,
        'show_manual_help': False,
        'navigation_width': 336,
    }


def test_document_seed_links_every_document_to_client_project(seeded_documents):
    assert not Document.objects.filter(client_user__isnull=True).exists()
    assert not Document.objects.filter(project__isnull=True).exists()


def test_document_seed_distributes_folder_presence(seeded_documents):
    assert Document.objects.filter(folder__isnull=True).exists()
    assert Document.objects.filter(folder__isnull=False).exists()


def test_collection_account_seed_links_each_income_origin(seeded_documents):
    assert DocumentCollectionAccount.objects.count() == 10
    assert not DocumentCollectionAccount.objects.filter(
        document__income_record__isnull=True,
    ).exists()


def test_collection_account_seed_matches_income_total(seeded_documents):
    assert not Document.objects.filter(
        collection_account__isnull=False,
    ).exclude(total=F('income_record__total_amount')).exists()


def test_collection_account_seed_uses_automatic_filing(seeded_documents):
    accounts = list(
        Document.objects.filter(collection_account__isnull=False)
        .select_related('folder', 'project')
        .order_by('pk')
    )

    for document in accounts:
        if document.commercial_status == Document.CommercialStatus.DRAFT:
            assert document.folder_id is None
            assert not document.generated_file
            continue
        assert document.generated_file
        path = [
            *(folder.name for folder in document.folder.get_ancestors()),
            document.folder.name,
        ]
        expected_prefix = [
            document.project.name, 'Cuentas de cobro',
            str(document.issue_date.year),
            f'{document.issue_date.month:02d} - '
        ]
        assert path[:3] == expected_prefix[:3]
        assert path[3].startswith(expected_prefix[3])
        root = document.folder.get_ancestors()[0]
        assert root.managed_project_id == document.project_id
        assert document.folder.system_key


def test_document_seed_creates_representative_cross_scope_threads(seeded_documents):
    cross_scope = DocumentThread.objects.get(
        title='Entrega, revisión y aprobación',
    )
    association_signatures = set(cross_scope.items.values_list(
        'document__folder_id',
        'document__client_user_id',
        'document__project_id',
    ))

    assert DocumentThread.objects.count() >= 2
    assert min(
        DocumentThread.objects.annotate(total=Count('items')).values_list(
            'total', flat=True,
        )
    ) >= 2
    assert len(association_signatures) >= 2
    assert DocumentThreadItem.objects.filter(document__is_archived=True).exists()
    assert DocumentThreadItem.objects.filter(
        document__document_type__code='collection_account',
    ).exists()


def test_document_seed_honors_a_small_volume_target():
    run_command(
        'create_fake_documents', '--count', '2',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )

    # Required contractual sources are supporting documents, separate from
    # the requested markdown/account fixture volume.
    sources = Document.objects.filter(metadata__billing_fixture='source').values('pk')
    assert Document.objects.exclude(pk__in=sources).count() == 2
    assert Document.objects.get(document_type__code='collection_account').billing_context.contract_id


def test_communication_seed_distributes_thread_lengths(seeded_communications):
    # Only the seeded conversations: auto-provisioned mother threads are born
    # empty, and letting them into the tally would turn any change in the
    # seeder's own distribution into a change in the 0-message bucket.
    lengths = Counter(
        CommunicationThread.objects.filter(
            managed_project__isnull=True, managed_client__isnull=True,
        )
        .annotate(total=Count('messages'))
        .values_list('total', flat=True)
    )

    assert lengths == Counter({1: 12, 3: 36, 12: 12})


def test_communication_seed_covers_message_statuses(seeded_communications):
    assert set(CommunicationMessage.objects.values_list('status', flat=True)) == {
        CommunicationMessage.Status.DRAFT,
        CommunicationMessage.Status.FAILED,
        CommunicationMessage.Status.RECEIVED,
        CommunicationMessage.Status.SENT,
    }


def test_communication_seed_closes_quarter_of_threads(seeded_communications):
    assert CommunicationThread.objects.filter(closed_at__isnull=False).count() == 15


def test_communication_seed_creates_date_corrections(seeded_communications):
    assert CommunicationMessageDateCorrection.objects.exists()


def test_communication_seed_creates_voided_messages(seeded_communications):
    assert CommunicationMessage.objects.filter(voided_at__isnull=False).exists()


def test_auxiliary_seed_populates_visible_history_without_credentials():
    run_command(
        'create_fake_clients_projects', '--count', '12',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )
    run_command(
        'create_fake_auxiliary', '--count', '12',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )

    assert Linktree.objects.count() == 2
    assert QRCard.objects.count() == 6
    assert McpRequestLog.objects.count() == 12
    assert McpConnector.objects.filter(is_active=True).count() == 0


def test_auxiliary_seed_populates_additional_module_share_history():
    """The auxiliary seed exposes realistic catalog-link tracking history."""
    run_command(
        'create_fake_clients_projects', '--count', '12',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )
    run_command(
        'create_fake_auxiliary', '--count', '12',
        '--seed', '19', '--anchor-date', '2026-08-26',
    )

    assert AdditionalModuleShareLink.objects.count() == 5
    assert AdditionalModuleShareView.objects.count() == 4
    assert AdditionalModuleShareLink.objects.filter(view_count=0).count() == 2
    assert AdditionalModuleShareLink.objects.filter(is_active=False).count() == 1
    assert AdditionalModuleShareLink.objects.filter(show_explainer_video=False).count() == 1
    assert AdditionalModule.objects.filter(share_links__isnull=False).exists()


def test_orchestrator_rolls_back_a_failed_stage(monkeypatch):
    from content.management.commands import create_fake_data as orchestrator

    real_call_command = orchestrator.call_command

    def fail_in_contacts(command, *args, **options):
        if command == 'create_contacts':
            Contact.objects.create(
                email='rollback@example.test', subject='rollback', message='rollback',
            )
            raise RuntimeError('seed stage failed')
        return real_call_command(command, *args, **options)

    monkeypatch.setattr(orchestrator, 'call_command', fail_in_contacts)

    with pytest.raises(RuntimeError, match='seed stage failed'):
        run_command(
            'create_fake_data', '--count', '3', '--skip-platform',
            '--skip-proposals', '--skip-blog', '--skip-portfolio', '--skip-tasks',
            '--skip-diagnostics', '--skip-accounting', '--skip-documents',
            '--skip-communications', '--skip-auxiliary',
        )

    assert not Contact.objects.exists()
    assert not UserProfile.objects.clients().exists()


def test_orchestrator_replace_rebuilds_the_existing_graph():
    run_command('create_fake_clients_projects', '--count', '3')
    run_command('create_contacts', '1')
    replaced_project_ids = set(Project.objects.values_list('pk', flat=True))

    run_command(
        'create_fake_data', '--replace', '--count', '2', '--skip-platform',
        '--skip-proposals', '--skip-blog', '--skip-portfolio', '--skip-tasks',
        '--skip-diagnostics', '--skip-accounting', '--skip-documents',
        '--skip-communications', '--skip-auxiliary',
    )

    replacement_project_ids = set(Project.objects.values_list('pk', flat=True))
    assert len(replaced_project_ids) > 0
    assert len(replacement_project_ids) > 0
    assert replaced_project_ids.isdisjoint(replacement_project_ids)
    assert UserProfile.objects.clients().count() == 2
    assert Contact.objects.count() == 2


def test_orchestrator_rejects_an_existing_graph_without_replace():
    Contact.objects.create(
        email='existing@example.test',
        subject='existing',
        message='existing business data',
    )

    with pytest.raises(CommandError, match='Run again with --replace'):
        run_command(
            'create_fake_data', '--count', '2', '--skip-platform',
            '--skip-proposals', '--skip-blog', '--skip-portfolio', '--skip-tasks',
            '--skip-diagnostics', '--skip-accounting', '--skip-documents',
            '--skip-communications', '--skip-auxiliary',
        )

    assert Contact.objects.count() == 1


def test_orchestrator_replays_cross_module_natural_values():
    seed_args = (
        '--count', '5', '--seed', '19', '--anchor-date', '2026-08-26',
    )
    run_command('create_fake_data', *seed_args)
    first_snapshot = complete_dataset_snapshot()

    run_command('create_fake_data', '--replace', *seed_args)

    assert complete_dataset_snapshot() == first_snapshot


def test_orchestrator_keeps_cross_module_relationships_coherent():
    run_command(
        'create_fake_data', '--count', '5', '--seed', '19',
        '--anchor-date', '2026-08-26',
    )

    violations = {
        'income_without_client': tuple(IncomeRecord.objects.filter(
            source_ref='fake:accounting', client__isnull=True,
        ).values_list('concept', 'period_date')),
        'income_project_owner_mismatch': tuple(IncomeRecord.objects.filter(
            source_ref='fake:accounting', project__isnull=False,
        ).exclude(
            project__client=F('client__user'),
        ).values_list('concept', 'period_date')),
        'hosting_without_client': tuple(HostingRecord.objects.filter(
            source_ref='fake:accounting', client__isnull=True,
        ).values_list('domain_url', 'valid_to')),
        'hosting_project_owner_mismatch': tuple(HostingRecord.objects.filter(
            source_ref='fake:accounting', project__isnull=False,
        ).exclude(
            project__client=F('client__user'),
        ).values_list('domain_url', 'valid_to')),
        'document_missing_client_or_project': tuple(Document.objects.filter(
            Q(client_user__isnull=True) | Q(project__isnull=True),
        ).values_list('title', flat=True)),
        'document_project_owner_mismatch': tuple(Document.objects.filter(
            project__isnull=False,
        ).exclude(
            project__client=F('client_user'),
        ).values_list('title', flat=True)),
        'collection_account_missing_origin': tuple(
            DocumentCollectionAccount.objects.filter(
                document__income_record__isnull=True,
            ).values_list('document__title', flat=True)
        ),
        'collection_account_total_mismatch': tuple(
            DocumentCollectionAccount.objects.exclude(
                document__total=F('document__income_record__total_amount'),
            ).values_list('document__title', flat=True)
        ),
        'thread_project_owner_mismatch': tuple(
            CommunicationThread.objects.filter(
                project__isnull=False,
            ).exclude(
                project__client=F('client__user'),
            ).values_list('title', flat=True)
        ),
    }

    assert all(not rows for rows in violations.values()), violations


# quality: disable too_many_assertions (17 assertions verify the one orchestrator contract that every public module root is populated)
def test_orchestrator_populates_every_visible_module_root():
    run_command(
        'create_fake_data', '--count', '5', '--seed', '19',
        '--anchor-date', '2026-08-26',
    )

    assert UserProfile.objects.clients().exists()
    assert Project.objects.exists()
    assert Contact.objects.count() == 5
    assert BusinessProposal.objects.exists()
    assert FinancingAgreement.objects.exists()
    assert BlogPost.objects.count() == 5
    assert Task.objects.count() == 5
    # The diagnostic seeder adds one linked, backdated edge record in addition
    # to the requested list volume.
    assert WebAppDiagnostic.objects.count() == 6
    assert IncomeRecord.objects.exists()
    assert HostingRecord.objects.exists()
    assert Document.objects.exists()
    # Split on purpose: the seeder asks for 5 conversations, and every project
    # is additionally auto-provisioned a mother thread. Asserting one total
    # would silently absorb a seeder that stopped creating conversations.
    assert CommunicationThread.objects.filter(
        managed_project__isnull=True, managed_client__isnull=True,
    ).count() == 5
    assert CommunicationThread.objects.filter(
        managed_project__isnull=False,
    ).count() == Project.objects.count()
    assert Linktree.objects.exists()
    assert QRCard.objects.exists()
    assert LinkedInPost.objects.exists()
    assert McpRequestLog.objects.count() == 5
