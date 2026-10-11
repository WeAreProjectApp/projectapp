"""
Unit tests for accounts.services.proposal_client_service.

Covers the get-or-create, update, delete, and snapshot helpers used by the
proposal admin panel to wire ``BusinessProposal.client`` to a real
``UserProfile``.
"""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import Project, UserProfile
from accounts.services import proposal_client_service
from content.models.business_proposal import BusinessProposal

User = get_user_model()


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# get_or_create_client_for_proposal
# ---------------------------------------------------------------------------

class TestGetOrCreateClientForProposal:
    def test_creates_new_user_and_profile_from_inline_email(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Sofia Aguirre',
            email='sofia@gmail.com',
            phone='+57 300 1111',
            company='Aguirre Studio',
        )
        assert profile.role == UserProfile.ROLE_CLIENT
        assert profile.user.email == 'sofia@gmail.com'
        assert profile.user.first_name == 'Sofia'
        assert profile.user.last_name == 'Aguirre'
        assert profile.phone == '+57 300 1111'
        assert profile.company_name == 'Aguirre Studio'
        assert profile.is_email_placeholder is False

    def test_reuses_existing_client_when_email_matches_case_insensitive(self):
        first = proposal_client_service.get_or_create_client_for_proposal(
            name='Mateo Ruiz', email='mateo@gmail.com',
        )
        second = proposal_client_service.get_or_create_client_for_proposal(
            name='Mateo R.', email='MATEO@gmail.com',
        )
        assert first.pk == second.pk

    def test_fills_missing_company_on_existing_profile(self):
        first = proposal_client_service.get_or_create_client_for_proposal(
            name='Carmen', email='carmen@gmail.com',
        )
        assert first.company_name == ''
        second = proposal_client_service.get_or_create_client_for_proposal(
            name='Carmen', email='carmen@gmail.com', company='LateCo',
        )
        assert second.pk == first.pk
        assert second.company_name == 'LateCo'

    def test_does_not_overwrite_existing_company(self):
        first = proposal_client_service.get_or_create_client_for_proposal(
            name='Lucia', email='lucia@gmail.com', company='OriginalCo',
        )
        second = proposal_client_service.get_or_create_client_for_proposal(
            name='Lucia', email='lucia@gmail.com', company='OtherCo',
        )
        assert second.company_name == 'OriginalCo'

    def test_generates_placeholder_when_email_is_blank(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Sin Email', email='',
        )
        assert profile.is_email_placeholder is True
        assert profile.user.email == f'cliente_{profile.pk}@temp.example.com'
        assert profile.user.username == f'cliente_{profile.pk}'

    def test_generates_unique_placeholders_for_each_blank_email(self):
        first = proposal_client_service.get_or_create_client_for_proposal(name='A', email='')
        second = proposal_client_service.get_or_create_client_for_proposal(name='B', email='')
        assert first.pk != second.pk
        assert first.user.email != second.user.email

    def test_falls_through_to_placeholder_when_email_belongs_to_admin(self):
        admin_user = User.objects.create_user(
            username='admin@gmail.com',
            email='admin@gmail.com',
            password='pwd',
        )
        UserProfile.objects.create(
            user=admin_user, role=UserProfile.ROLE_ADMIN, is_onboarded=True,
        )
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Reuser', email='admin@gmail.com',
        )
        # Did NOT reuse the admin user — got a fresh placeholder profile.
        assert profile.user.pk != admin_user.pk
        assert profile.is_email_placeholder is True


# ---------------------------------------------------------------------------
# update_client_profile + sync_snapshot
# ---------------------------------------------------------------------------

class TestUpdateClientProfile:
    def test_update_client_profile_changes_user_and_cascades_snapshots(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Ana Vega', email='ana@gmail.com',
        )
        # Create two proposals via service to mirror real wiring.
        p1 = BusinessProposal.objects.create(
            title='P1', client_name='Ana Vega', client_email='ana@gmail.com',
            client=profile, total_investment=1000,
        )
        p2 = BusinessProposal.objects.create(
            title='P2', client_name='Ana Vega', client_email='ana@gmail.com',
            client=profile, total_investment=2000,
        )

        proposal_client_service.update_client_profile(
            profile, name='Ana Maria Vega', phone='+57 300 9999',
        )

        p1.refresh_from_db()
        p2.refresh_from_db()
        assert p1.client_name == 'Ana Maria Vega'
        assert p1.client_phone == '+57 300 9999'
        assert p2.client_name == 'Ana Maria Vega'
        assert p2.client_phone == '+57 300 9999'

    def test_update_client_profile_rejects_email_collision_with_other_user(self):
        a = proposal_client_service.get_or_create_client_for_proposal(
            name='A', email='a@gmail.com',
        )
        proposal_client_service.get_or_create_client_for_proposal(
            name='B', email='b@gmail.com',
        )
        with pytest.raises(ValueError, match='b@gmail.com'):
            proposal_client_service.update_client_profile(a, email='b@gmail.com')

    def test_clearing_email_to_blank_falls_back_to_placeholder(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='To Clear', email='clear@gmail.com',
        )
        proposal_client_service.update_client_profile(profile, email='')
        profile.user.refresh_from_db()
        assert profile.user.email == f'cliente_{profile.pk}@temp.example.com'

    def test_archiving_does_not_cascade_snapshots(self):
        from accounts.services.client_archive_service import (
            archive_client, unarchive_client,
        )

        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Archivable Test', email='archivable@gmail.com',
        )
        # Stale snapshot on purpose: a cascade would overwrite it.
        proposal = BusinessProposal.objects.create(
            title='Stale', client_name='Nombre Viejo',
            client_email='archivable@gmail.com', client=profile,
            total_investment=1000,
        )

        archive_client(profile, transitions=[], actor=None)

        profile.refresh_from_db()
        assert profile.archived_at is not None
        # Putting a client away says nothing about who they are, so the
        # proposal keeps the identity it was sent with.
        proposal.refresh_from_db()
        assert proposal.client_name == 'Nombre Viejo'

        unarchive_client(profile, actor=None)
        profile.refresh_from_db()
        assert profile.archived_at is None

    def test_sync_snapshot_copies_canonical_fields_to_proposal(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Sync Test', email='sync@gmail.com', phone='+57 300', company='SyncCo',
        )
        # Build a proposal with stale snapshot fields, then sync.
        proposal = BusinessProposal.objects.create(
            title='Sync',
            client_name='Stale Name',
            client_email='stale@example.com',
            client_phone='000',
            client=profile,
            total_investment=500,
        )
        proposal_client_service.sync_snapshot(proposal)
        proposal.refresh_from_db()
        assert proposal.client_name == 'Sync Test'
        assert proposal.client_email == 'sync@gmail.com'
        assert proposal.client_phone == '+57 300'

    def test_sync_snapshot_preserves_typed_email_when_linked_user_is_placeholder(self):
        # Simulate the admin-collision flow: an admin user already exists with
        # email X; when an admin creates a proposal typing X as client_email,
        # get_or_create_client_for_proposal returns a placeholder profile —
        # but the proposal's snapshot client_email must keep the real X so
        # the client email can still be sent.
        admin_user = User.objects.create_user(
            username='colliding-admin', email='admin@gmail.com', password='x',
        )
        UserProfile.objects.create(user=admin_user, role=UserProfile.ROLE_ADMIN)

        placeholder_profile = (
            proposal_client_service.get_or_create_client_for_proposal(
                name='Tester', email='admin@gmail.com',
            )
        )
        assert placeholder_profile.is_email_placeholder is True

        proposal = BusinessProposal.objects.create(
            title='Admin collision',
            client_name='Tester',
            client_email='admin@gmail.com',  # real typed email
            client=placeholder_profile,
            total_investment=1000,
        )

        proposal_client_service.sync_snapshot(proposal)
        proposal.refresh_from_db()

        assert proposal.client_email == 'admin@gmail.com'
        assert not proposal.client_email.endswith(
            UserProfile.PLACEHOLDER_EMAIL_DOMAIN
        )

    def test_sync_snapshot_for_profile_does_not_propagate_placeholder_email(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='No Email', email='',
        )
        assert profile.is_email_placeholder is True

        proposal = BusinessProposal.objects.create(
            title='Typed email kept',
            client_name='Typed',
            client_email='typed@gmail.com',  # snapshot pre-set by the view
            client=profile,
            total_investment=1500,
        )

        proposal_client_service.sync_snapshot_for_profile(profile)
        proposal.refresh_from_db()

        assert proposal.client_email == 'typed@gmail.com'


# ---------------------------------------------------------------------------
# delete_orphan_client
# ---------------------------------------------------------------------------

class TestDeleteOrphanClient:
    def test_deletes_orphan_with_zero_proposals_and_projects(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Orphan', email='orphan@gmail.com',
        )
        user_pk = profile.user.pk
        proposal_client_service.delete_orphan_client(profile)
        assert not UserProfile.objects.filter(pk=profile.pk).exists()
        assert not User.objects.filter(pk=user_pk).exists()

    def test_blocks_deletion_when_client_has_proposals(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Has Proposal', email='hasprop@gmail.com',
        )
        BusinessProposal.objects.create(
            title='X', client_name='Has Proposal', client_email='hasprop@gmail.com',
            client=profile, total_investment=1,
        )
        with pytest.raises(ValueError, match='client_has_proposals:1'):
            proposal_client_service.delete_orphan_client(profile)

    def test_blocks_deletion_when_client_has_platform_projects(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Has Project', email='hasproj@gmail.com',
        )
        Project.objects.create(
            name='Live Project', client=profile.user, status=Project.STATUS_ACTIVE,
        )
        with pytest.raises(ValueError, match='client_has_projects:1'):
            proposal_client_service.delete_orphan_client(profile)

    def test_blocks_deletion_when_client_has_hostings(self):
        from decimal import Decimal

        from content.models import HostingRecord

        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Has Hosting', email='hashosting@gmail.com',
        )
        HostingRecord.objects.create(
            client=profile,
            client_name='Has Hosting - Marca',
            monthly_value=Decimal('50000.00'),
        )
        with pytest.raises(ValueError, match='client_has_hostings:1'):
            proposal_client_service.delete_orphan_client(profile)
        assert UserProfile.objects.filter(pk=profile.pk).exists()

    def test_blocks_deletion_when_client_has_incomes(self):
        from datetime import date

        from content.models import IncomeRecord

        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Has Income', email='hasincome@gmail.com',
        )
        IncomeRecord.objects.create(
            concept='Has Income - Inicio 40%',
            kind=IncomeRecord.Kind.EXPECTED,
            period_date=date(2026, 8, 1),
            total_amount=1000,
            client=profile,
        )
        with pytest.raises(ValueError, match='client_has_incomes:1'):
            proposal_client_service.delete_orphan_client(profile)
        assert UserProfile.objects.filter(pk=profile.pk).exists()

    def test_blocks_deletion_when_client_has_a_communication_folder(self):
        """Fails if a client whose only row is a communication folder passes the guard
        and the delete ends in an unhandled ProtectedError."""
        from accounts.services.client_deletion import ClientDeletionBlocked
        from content.models import CommunicationFolder

        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Carpeta Sola', email='carpeta@gmail.com',
        )
        CommunicationFolder.objects.create(client=profile, name='Temporal')

        with pytest.raises(ClientDeletionBlocked) as blocked:
            proposal_client_service.delete_orphan_client(profile)

        assert str(blocked.value) == 'client_has_protected_references:1'
        assert blocked.value.relations == {'content.communicationfolder.client': 1}
        assert UserProfile.objects.filter(pk=profile.pk).exists()

    def test_deleting_a_client_leaves_its_documents_and_folders_without_client(self):
        """Fails if documents or folders start blocking the delete, or are deleted with it:
        their client link is SET_NULL on purpose (content/models/document_folder.py)."""
        from content.models import Document, DocumentFolder

        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Solo Documentos', email='documentos@gmail.com',
        )
        document = Document.objects.create(title='Acta', client_user=profile.user)
        folder = DocumentFolder.objects.create(name='Carpeta del cliente', client_user=profile.user)

        proposal_client_service.delete_orphan_client(profile)

        document.refresh_from_db()
        folder.refresh_from_db()
        assert not UserProfile.objects.filter(pk=profile.pk).exists()
        assert document.client_user_id is None
        assert folder.client_user_id is None


# ---------------------------------------------------------------------------
# generate_placeholder_email
# ---------------------------------------------------------------------------

class TestGeneratePlaceholderEmail:
    def test_format_includes_profile_id_and_temp_domain(self):
        assert (
            proposal_client_service.generate_placeholder_email(42)
            == 'cliente_42@temp.example.com'
        )


# ---------------------------------------------------------------------------
# _split_name
# ---------------------------------------------------------------------------

class TestSplitName:
    def test_splits_full_name_into_first_and_last(self):
        assert proposal_client_service._split_name('Sofia Aguirre') == ('Sofia', 'Aguirre')

    def test_single_word_returns_only_first_name(self):
        assert proposal_client_service._split_name('Madonna') == ('Madonna', '')

    def test_empty_string_returns_two_empty_strings(self):
        assert proposal_client_service._split_name('') == ('', '')

    def test_none_returns_two_empty_strings(self):
        assert proposal_client_service._split_name(None) == ('', '')

    def test_multiple_spaces_treated_as_single_split(self):
        first, last = proposal_client_service._split_name('Ana Maria Vega Torres')
        assert first == 'Ana'
        assert last == 'Maria Vega Torres'

    def test_long_name_is_capped_at_150_chars(self):
        long_name = 'A' * 200 + ' ' + 'B' * 200
        first, last = proposal_client_service._split_name(long_name)
        assert len(first) <= 150
        assert len(last) <= 150


# ---------------------------------------------------------------------------
# build_client_display_name
# ---------------------------------------------------------------------------

class TestBuildClientDisplayName:
    def test_returns_full_name_when_set(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Clara Montoya', email='clara@example.com',
        )
        assert proposal_client_service.build_client_display_name(profile) == 'Clara Montoya'

    def test_falls_back_to_company_name_when_no_full_name(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='', email='corp@example.com', company='LatinCorp',
        )
        assert proposal_client_service.build_client_display_name(profile) == 'LatinCorp'

    def test_falls_back_to_email_when_no_name_or_company(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='', email='nonnameuser@example.com',
        )
        result = proposal_client_service.build_client_display_name(profile)
        assert result == 'nonnameuser@example.com'

    def test_falls_back_to_cliente_when_user_email_is_empty(self):
        user = User.objects.create_user(username='noemail_user', email='', password='x')
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        result = proposal_client_service.build_client_display_name(profile)
        assert result == 'Cliente'


# ---------------------------------------------------------------------------
# _create_user_shell
# ---------------------------------------------------------------------------

class TestCreateUserShell:
    def test_creates_inactive_user_with_unusable_password(self):
        user = proposal_client_service._create_user_shell(
            username='shell_user',
            email='shell@example.com',
            first_name='Shell',
            last_name='User',
        )
        assert not user.is_active
        assert not user.has_usable_password()
        assert user.email == 'shell@example.com'
        assert user.username == 'shell_user'

    def test_username_is_truncated_to_150_chars(self):
        long_username = 'u' * 200
        user = proposal_client_service._create_user_shell(
            username=long_username, email='x@example.com', first_name='', last_name='',
        )
        assert len(user.username) <= 150


# ---------------------------------------------------------------------------
# _resolve_existing_user — username fallback
# ---------------------------------------------------------------------------

class TestResolveExistingUser:
    def test_finds_user_by_email_case_insensitive(self):
        user = User.objects.create_user(username='fnduser', email='found@example.com', password='x')
        result = proposal_client_service._resolve_existing_user('Found@example.com')
        assert result.pk == user.pk

    def test_falls_back_to_username_when_email_not_found(self):
        user = User.objects.create_user(username='byusername@example.com', email='other@example.com', password='x')
        result = proposal_client_service._resolve_existing_user('byusername@example.com')
        assert result.pk == user.pk

    def test_returns_none_when_no_match(self):
        result = proposal_client_service._resolve_existing_user('nonexistent@example.com')
        assert result is None


# ---------------------------------------------------------------------------
# get_or_create_client_for_proposal — bare user with no profile
# ---------------------------------------------------------------------------

class TestGetOrCreateBareUser:
    def test_adopts_existing_bare_user_without_profile(self):
        bare_user = User.objects.create_user(
            username='bare@example.com', email='bare@example.com', password='x',
        )
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Bare User', email='bare@example.com',
        )
        assert profile.user.pk == bare_user.pk
        assert profile.role == UserProfile.ROLE_CLIENT


# ---------------------------------------------------------------------------
# update_client_profile — additional branches
# ---------------------------------------------------------------------------

class TestUpdateClientProfileEdgeCases:
    def test_no_op_when_all_args_are_none(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='No Change', email='nochange@example.com',
        )
        original_name = profile.user.first_name
        result = proposal_client_service.update_client_profile(profile)
        assert result.user.first_name == original_name

    def test_whitespace_only_email_converts_to_placeholder(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Whitespace', email='whitespace@example.com',
        )
        proposal_client_service.update_client_profile(profile, email='   ')
        profile.user.refresh_from_db()
        assert profile.user.email.endswith(UserProfile.PLACEHOLDER_EMAIL_DOMAIN)

    def test_cascades_update_to_web_app_diagnostics(self):
        from content.models.web_app_diagnostic import WebAppDiagnostic

        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Diag Client', email='diagclient@example.com',
        )
        diag = WebAppDiagnostic.objects.create(
            client=profile,
            client_name='Diag Client',
            client_email='diagclient@example.com',
            language='es',
        )
        proposal_client_service.update_client_profile(profile, name='Diag Updated')
        diag.refresh_from_db()
        assert diag.client_name == 'Diag Updated'


# ---------------------------------------------------------------------------
# sync_snapshot — None client guard
# ---------------------------------------------------------------------------

class TestSyncSnapshotNoneClient:
    def test_sync_snapshot_returns_proposal_unchanged_when_client_is_none(self):
        proposal = BusinessProposal.objects.create(
            title='No Client',
            client_name='Old Name',
            client_email='old@example.com',
            total_investment=100,
        )
        result = proposal_client_service.sync_snapshot(proposal)
        assert result.client_name == 'Old Name'


# ---------------------------------------------------------------------------
# delete_orphan_client — diagnostics guard
# ---------------------------------------------------------------------------

class TestDeleteOrphanClientDiagnosticsGuard:
    def test_blocks_deletion_when_client_has_diagnostics(self):
        from content.models.web_app_diagnostic import WebAppDiagnostic

        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Has Diag', email='hasdiag@example.com',
        )
        WebAppDiagnostic.objects.create(
            client=profile,
            client_name='Has Diag',
            client_email='hasdiag@example.com',
            language='es',
        )
        with pytest.raises(ValueError, match='client_has_diagnostics:1'):
            proposal_client_service.delete_orphan_client(profile)
