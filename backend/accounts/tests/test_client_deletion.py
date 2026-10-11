"""Client deletion blockers: the one list the delete guard, the orphan cut and CL4 share."""
import pytest
from django.contrib.auth import get_user_model
from django.db.models import CASCADE, PROTECT, RESTRICT
from django.db.models.deletion import get_candidate_relations_to_delete

from accounts.services import client_deletion, proposal_client_service

User = get_user_model()


def _protections_django_enforces():
    """Every PROTECT/RESTRICT relation the deletion Collector meets when a user is deleted.

    Walks Django's own candidate relations, independently of the module under
    test. The cascade into ``Project`` is not followed: the module blocks on
    ``Project.client`` itself, so a client with projects never gets that far.
    """
    found, pending, seen = set(), [User], set()
    while pending:
        model = pending.pop()
        if model in seen:
            continue
        seen.add(model)
        for relation in get_candidate_relations_to_delete(model._meta):
            name = f'{relation.related_model._meta.label_lower}.{relation.field.name}'
            on_delete = relation.field.remote_field.on_delete
            if on_delete in (PROTECT, RESTRICT):
                found.add(name)
            elif on_delete is CASCADE and name not in client_deletion.BUSINESS_CASCADES:
                pending.append(relation.related_model)
    return found


def _client(name, email):
    return proposal_client_service.get_or_create_client_for_proposal(name=name, email=email)


def test_blockers_are_every_protection_the_deletion_collector_enforces():
    """Fails if the guard misses a relation Django enforces when deleting the client's user.

    Reading ``_meta.related_objects`` (which drops hidden ``'+'`` relations) or
    not following CASCADE chains would make the sets differ.
    """
    names = {blocker.name for blocker in client_deletion.deletion_blockers()}

    assert names - client_deletion.BUSINESS_CASCADES == _protections_django_enforces()


def test_blockers_reach_hidden_second_order_and_business_relations():
    """Fails if hidden relations, protections met through a cascade or the client's projects stop blocking."""
    names = {blocker.name for blocker in client_deletion.deletion_blockers()}

    assert 'content.dataintegrityoperation.actor' in names  # related_name='+'
    assert 'content.proposalapprovalfile.deliverable' in names  # User → Deliverable → approval file
    assert 'content.communicationfolder.client' in names  # through the profile
    assert 'content.financingagreement.client' in names
    assert 'accounts.project.client' in names  # cascades, but it is business data


@pytest.mark.django_db
def test_counts_name_each_blocking_relation_with_its_rows():
    """Fails if a blocking row is not reported under its own relation, hidden ones included."""
    from content.models import CommunicationFolder, ProjectRetentionContext

    profile = _client('Con Bloqueos', 'bloqueos@example.com')
    admin = User.objects.create_user(username='admin-bloqueos@example.com', is_staff=True)
    CommunicationFolder.objects.create(client=profile, name='Temporal')
    ProjectRetentionContext.objects.create(
        client=profile.user, original_project_id=9001, project_name='Retenido', created_by=admin,
    )

    assert client_deletion.blocker_counts(profile.user_id) == {
        'content.communicationfolder.client': 1,
        'content.projectretentioncontext.client': 1,
    }
    assert client_deletion.blocker_counts(admin.pk) == {'content.projectretentioncontext.created_by': 1}


@pytest.mark.django_db
def test_unowned_traces_do_not_block_the_delete():
    """Fails if SET_NULL traces such as documents and folders start blocking: they are detached by design."""
    from content.models import Document, DocumentFolder

    profile = _client('Solo Rastros', 'rastros@example.com')
    Document.objects.create(title='Acta', client_user=profile.user)
    DocumentFolder.objects.create(name='Carpeta del cliente', client_user=profile.user)

    assert client_deletion.blocker_counts(profile.user_id) == {}
    assert client_deletion.has_blockers(profile.user_id) is False
