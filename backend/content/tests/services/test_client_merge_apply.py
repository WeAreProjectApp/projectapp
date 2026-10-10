"""Client merges through real writers and the integrity engine."""
import uuid

import pytest
from accounts.models import Project, UserProfile
from accounts.models_project_ideas import ProjectIdea, ProjectIdeaCollection
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

from content.models import (
    AccountingChangeLog,
    BuildingWithUsContractRevision,
    BuildingWithUsProgramRevision,
    BusinessProposal,
    ClientDocumentNumberSequence,
    CommunicationFolder,
    CommunicationThread,
    DataIntegrityOperation,
    Document,
    DocumentCollectionAccount,
    DocumentFolder,
    EntityRevision,
    WebAppDiagnostic,
)
from content.services import client_merge
from content.services.entity_history import history_operation
from content.tests.data_integrity_helpers import only, scan
from content.tests.data_integrity_merge_factories import (
    client_pair,
    make_client,
    make_client_project,
    make_collection_account,
    make_document,
    make_folder,
    make_hosting,
    make_income,
    make_secure_link,
    run_client_merge,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('revision_model,content', [
    (BuildingWithUsProgramRevision, {'content': {}}),
    (BuildingWithUsContractRevision, {'markdown': '# Alianza'}),
], ids=['program', 'contract'])
def test_merge_preserves_alliance_revision_author(superuser, revision_model, content):
    survivor, duplicate = client_pair()
    revision = revision_model.objects.create(
        version=revision_model.objects.count() + 1, author=duplicate.user,
        change_note='Autoría original', **content,
    )

    run_client_merge(superuser, survivor, duplicate)

    revision.refresh_from_db()
    assert revision.author_id == duplicate.user_id


def test_engine_retires_the_duplicate_without_deleting_it(superuser):
    """Fails if the engine deletes D or leaves the duplicate-email finding unresolved."""
    survivor, duplicate = client_pair()
    document = make_document('Contrato', client_user=duplicate.user)

    _, result = run_client_merge(superuser, survivor, duplicate)

    duplicate.refresh_from_db()
    user = get_user_model().objects.get(pk=duplicate.user_id)
    assert (user.email, user.username, user.is_active) == (
        f'merged_{duplicate.pk}@temp.example.com', f'merged_{duplicate.pk}', False)
    assert duplicate.archived_at is not None
    assert Document.objects.get(pk=document.pk).client_user_id == survivor.user_id
    assert only(scan(rule_ids=['CL1']), 'CL1') == []
    operation = DataIntegrityOperation.objects.get(pk=result['operation_id'])
    assert operation.steps[0]['fix_kind'] == 'merge_clients'
    assert EntityRevision.objects.filter(operation_id=operation.history_operation_id,
                                          history__entity_type='client', history__object_id=duplicate.pk).exists()
    receipt = AccountingChangeLog.objects.filter(entity_type='client', object_id=duplicate.pk).first()
    assert any(row['field'] == 'merged_into' and row['new'] == survivor.pk for row in receipt.changes)


def test_contact_fills_preserve_account_scoped_preferences(superuser):
    """Fails if contact reconciliation changes S's theme, onboarding or navigation settings."""
    survivor, duplicate = client_pair(phone='57300123', address='Calle 1', theme_color='#ff0000', is_onboarded=True)
    UserProfile.objects.filter(pk=survivor.pk).update(theme_color='#00ff00', document_navigation_mode='client',
                                                     phone='+57 (300) 123')

    run_client_merge(superuser, survivor, duplicate)

    survivor.refresh_from_db()
    assert survivor.phone == '+57 (300) 123'
    assert survivor.address == 'Calle 1'
    assert survivor.theme_color == '#00ff00'
    assert survivor.document_navigation_mode == 'client'
    assert survivor.is_onboarded is False


def test_chosen_conflict_value_is_applied(superuser):
    """Fails if the selected duplicate address is ignored or a different field is changed."""
    survivor, duplicate = client_pair(address='Nueva')
    UserProfile.objects.filter(pk=survivor.pk).update(address='Anterior')

    run_client_merge(superuser, survivor, duplicate, resolutions={'address': 'duplicate'})

    assert UserProfile.objects.get(pk=survivor.pk).address == 'Nueva'


def test_secure_link_owner_collision_is_refused_before_writing(superuser):
    """Fails if relinking owners collides with S's existing idempotency receipt."""
    from secure_links.models import SecureLink
    survivor, duplicate = client_pair()
    request = uuid.UUID('12345678-1234-5678-1234-567812345678')
    make_secure_link(survivor, '1' * 64, request)
    link = make_secure_link(duplicate, '2' * 64, request)
    plan = client_merge.plan_client_merge(survivor, duplicate, actor=superuser)

    with pytest.raises(client_merge.ClientMergeError, match='bloqueos'):
        with history_operation(actor=superuser, source='http'):
            client_merge.apply_client_merge(plan, actor=superuser)

    assert 'association_collision' in {row['code'] for row in plan['preview']['blockers']}
    assert SecureLink.objects.get(pk=link.pk).owner_id == duplicate.pk


def test_placeholder_survivor_receives_the_real_login_identity(superuser):
    """Fails if retiring D fails to release its unique username before S adopts the real email."""
    survivor = make_client('provisional')
    duplicate = make_client('real@example.com', email='real@example.com')

    run_client_merge(superuser, survivor, duplicate, rule_id='CL2')

    survivor.user.refresh_from_db()
    assert (survivor.user.email, survivor.user.username) == ('real@example.com', 'real@example.com')


def test_billing_code_transfer_carries_its_number_sequence(superuser):
    """Fails if transferring the code resets numbering or violates its unique reservation."""
    survivor, duplicate = client_pair(billing_code='DUP')
    sequence = ClientDocumentNumberSequence.objects.create(client_profile=duplicate, last_value=42)

    run_client_merge(superuser, survivor, duplicate)

    assert UserProfile.objects.get(pk=survivor.pk).billing_code == 'DUP'
    assert UserProfile.objects.get(pk=duplicate.pk).billing_code is None
    sequence.refresh_from_db()
    assert (sequence.client_profile_id, sequence.last_value) == (survivor.pk, 42)


def test_existing_billing_codes_keep_their_separate_sequences(superuser):
    """Fails if two reserved billing codes or their counters are combined."""
    survivor, duplicate = client_pair(billing_code='DUP')
    UserProfile.objects.filter(pk=survivor.pk).update(billing_code='SUR')
    kept = ClientDocumentNumberSequence.objects.create(client_profile=survivor, last_value=3)
    reserved = ClientDocumentNumberSequence.objects.create(client_profile=duplicate, last_value=42)

    run_client_merge(superuser, survivor, duplicate)

    assert list(UserProfile.objects.filter(pk__in=[survivor.pk, duplicate.pk]).order_by('pk')
                .values_list('billing_code', flat=True)) == ['SUR', 'DUP']
    assert ClientDocumentNumberSequence.objects.get(pk=kept.pk).client_profile_id == survivor.pk
    assert ClientDocumentNumberSequence.objects.get(pk=reserved.pk).client_profile_id == duplicate.pk


def test_communication_root_transfers_when_survivor_has_none(superuser):
    """Fails if the communication root transfer violates its CHECK or loses the managed pointer."""
    survivor, duplicate = client_pair()
    root = CommunicationThread.objects.create(title='Cliente', client=duplicate, managed_client=duplicate)
    folder = CommunicationFolder.objects.create(name='Mensajes', client=duplicate)
    other = CommunicationThread.objects.create(title='Tema', client=duplicate, folder=folder)

    run_client_merge(superuser, survivor, duplicate)

    root.refresh_from_db()
    assert (root.client_id, root.managed_client_id) == (survivor.pk, survivor.pk)
    assert CommunicationThread.objects.get(pk=other.pk).client_id == survivor.pk
    assert CommunicationFolder.objects.get(pk=folder.pk).client_id == survivor.pk


def test_two_communication_roots_preserve_the_demoted_thread(superuser):
    """Fails if a collision deletes the duplicate's communication root or changes the survivor root."""
    survivor, duplicate = client_pair()
    kept = CommunicationThread.objects.create(title='Principal', client=survivor, managed_client=survivor)
    demoted = CommunicationThread.objects.create(title='Anterior', client=duplicate, managed_client=duplicate)

    run_client_merge(superuser, survivor, duplicate)

    demoted.refresh_from_db()
    assert (demoted.client_id, demoted.managed_client_id, demoted.title) == (survivor.pk, None, 'Anterior')
    assert CommunicationThread.objects.get(pk=kept.pk).managed_client_id == survivor.pk


def test_document_root_transfers_when_survivor_has_none(superuser):
    """Fails if the unique document root loses its active/managed invariant while changing client."""
    survivor, duplicate = client_pair()
    root = make_folder('Cliente', managed_client=duplicate.user, client_user=duplicate.user)
    document = make_document('Contenido', client_user=duplicate.user, folder=root)

    run_client_merge(superuser, survivor, duplicate)

    root.refresh_from_db()
    assert (root.managed_client_id, root.client_user_id, root.is_archived) == (survivor.user_id, survivor.user_id, False)
    assert Document.objects.get(pk=document.pk).folder_id == root.pk


def test_two_document_roots_merge_active_content_recursively(superuser):
    """Fails if colliding roots bypass the recursive folder writer or archive active content."""
    survivor, duplicate = client_pair()
    kept = make_folder('Clientes', managed_client=survivor.user, client_user=survivor.user)
    old = make_folder('clientes ', managed_client=duplicate.user, client_user=duplicate.user)
    child_s = make_folder('Anexos', parent=kept, client_user=survivor.user)
    child_d = make_folder('anexos', parent=old, client_user=duplicate.user)
    document = make_document('Anexo', folder=child_d, client_user=duplicate.user)
    first = make_folder('Nuevos', parent=old, client_user=duplicate.user)
    second = make_folder('nuevos ', parent=old, client_user=duplicate.user)
    repeated = make_document('Repetido en D', folder=second, client_user=duplicate.user)

    run_client_merge(superuser, survivor, duplicate)

    old.refresh_from_db()
    document.refresh_from_db()
    assert (old.managed_client_id, old.client_user_id, old.is_archived) == (None, survivor.user_id, True)
    assert (document.folder_id, document.client_user_id, document.is_archived) == (child_s.pk, survivor.user_id, False)
    assert DocumentFolder.objects.get(pk=child_d.pk).is_archived is True
    assert Document.objects.get(pk=repeated.pk).folder_id == first.pk
    assert DocumentFolder.objects.get(pk=first.pk).parent_id == kept.pk
    assert DocumentFolder.objects.get(pk=second.pk).is_archived is True


def test_project_roots_follow_the_project_without_new_containers(superuser):
    """Fails if project signals create or detach roots after the merge has already moved their owners."""
    survivor, duplicate = client_pair()
    project = make_client_project(duplicate)
    root = DocumentFolder.objects.get(managed_project=project)
    thread = CommunicationThread.objects.get(managed_project=project)
    count = DocumentFolder.objects.count()

    run_client_merge(superuser, survivor, duplicate)

    assert Project.objects.get(pk=project.pk).client_id == survivor.user_id
    assert DocumentFolder.objects.get(pk=root.pk).client_user_id == survivor.user_id
    assert CommunicationThread.objects.get(pk=thread.pk).client_id == survivor.pk
    assert DocumentFolder.objects.count() == count
    assert set(DocumentFolder.objects.filter(project=project).values_list('client_user_id', flat=True)) == {survivor.user_id}


@pytest.mark.parametrize('status', ['issued', 'paid', 'cancelled'])
def test_emitted_accounts_keep_their_customer_facts(superuser, status):
    """Fails if a historical cuenta's customer snapshot changes during client reassignment."""
    survivor, duplicate = client_pair()
    document = make_collection_account('Emitida', duplicate.user, status, client_name='Hecho emitido')
    account = DocumentCollectionAccount.objects.create(document=document, customer_name='Cliente emitido',
                                                        customer_email='emitted@example.com')

    run_client_merge(superuser, survivor, duplicate)

    document.refresh_from_db()
    account.refresh_from_db()
    assert (document.client_user_id, document.client_name) == (survivor.user_id, 'Hecho emitido')
    assert (account.customer_name, account.customer_email) == ('Cliente emitido', 'emitted@example.com')


def test_draft_account_refreshes_its_provisional_customer_snapshot(superuser):
    """Fails if a draft follows D's old billing contact after its client pointer moves to S."""
    survivor, duplicate = client_pair()
    document = make_collection_account('Borrador', duplicate.user, 'draft')
    account = DocumentCollectionAccount.objects.create(document=document, customer_name='Anterior')

    run_client_merge(superuser, survivor, duplicate)

    account.refresh_from_db()
    assert account.customer_name == 'Ana Cliente'
    assert account.customer_email == 'ana@example.com'


def test_financial_records_refresh_the_hosting_contact_snapshot(superuser):
    """Fails if a relinked hosting keeps D's billing contact or income authorship changes."""
    survivor, duplicate = client_pair()
    income = make_income(duplicate, created_by=duplicate.user)
    hosting = make_hosting(duplicate, client_email='old@example.com')

    run_client_merge(superuser, survivor, duplicate)

    income.refresh_from_db()
    hosting.refresh_from_db()
    assert (income.client_id, income.created_by_id) == (survivor.pk, duplicate.user_id)
    assert (hosting.client_id, hosting.client_name, hosting.client_email) == (survivor.pk, 'Ana Cliente', 'ana@example.com')


def test_identity_signals_capture_existing_survivor_snapshots(superuser):
    """Fails if S's identity-save cascade refreshes a proposal outside the recorded closure."""
    survivor, duplicate = client_pair(phone='300123')
    existing = BusinessProposal.objects.create(title='Existente', client=survivor, client_phone='Anterior')
    moved = WebAppDiagnostic.objects.create(title='Diagnóstico', client=duplicate, client_company='Anterior')

    _, result = run_client_merge(superuser, survivor, duplicate)

    assert BusinessProposal.objects.get(pk=existing.pk).client_phone == '300123'
    moved.refresh_from_db()
    assert (moved.client_id, moved.client_phone, moved.client_company) == (survivor.pk, '300123', 'Ejemplo SAS')
    operation = DataIntegrityOperation.objects.get(pk=result['operation_id'])
    assert any(item['model'] == 'content.businessproposal' and item['pk'] == existing.pk
               and item['field'] == 'client_phone' for item in operation.steps[0]['items'])


def test_hidden_recipient_pointers_preserve_their_authors(superuser):
    """Fails if hidden suggestion recipients stay with D or their original authors are rewritten."""
    survivor, duplicate = client_pair()
    idea = ProjectIdea.objects.create(recipient=duplicate.user, author=duplicate.user, author_label='Ana',
                                     origin='client', text='Propuesta')
    collection = ProjectIdeaCollection.objects.create(recipient=duplicate.user, created_by=duplicate.user,
                                                       creator_label='Ana', title='Ideas')

    run_client_merge(superuser, survivor, duplicate)

    idea.refresh_from_db()
    collection.refresh_from_db()
    assert (idea.recipient_id, idea.author_id) == (survivor.user_id, duplicate.user_id)
    assert (collection.recipient_id, collection.created_by_id) == (survivor.user_id, duplicate.user_id)


def test_residual_association_rolls_the_entire_merge_back(superuser):
    """Fails if a late association to D survives P11 or a partial merge commits before the refusal."""
    survivor, duplicate = client_pair()
    project = make_client_project(duplicate)
    original_email = duplicate.user.email

    def late_association(sender, instance, created, **kwargs):
        if not created and instance.pk == project.pk and instance.client_id == survivor.user_id:
            CommunicationFolder.objects.create(name='Late association', client=duplicate)

    post_save.connect(late_association, sender=Project, weak=False)
    try:
        with pytest.raises(client_merge.ClientMergeError, match='asociación pendiente'):
            run_client_merge(superuser, survivor, duplicate)
    finally:
        post_save.disconnect(late_association, sender=Project)

    assert Project.objects.get(pk=project.pk).client_id == duplicate.user_id
    assert get_user_model().objects.get(pk=duplicate.user_id).email == original_email
    assert UserProfile.objects.get(pk=duplicate.pk).archived_at is None
    assert not CommunicationFolder.objects.filter(name='Late association').exists()
