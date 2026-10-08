"""Verified Platform JWT sessions use their current profile authority."""
import pytest
from rest_framework.test import APIClient

from accounts.models import (
    BugComment,
    BugReport,
    ChangeRequest,
    ChangeRequestComment,
    ProjectContract,
    RequirementReview,
    UserProfile,
)
from accounts.services import delivery_workflow as delivery
from accounts.services.tokens import get_tokens_for_user
from accounts.tests.delivery_authoring_helpers import build_authoring_context
from accounts.tests.delivery_helpers import decisions, publish, version

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    """Build a draft hierarchy with a real signed source owned by its client."""
    return build_authoring_context()


def _downgrade(user, *, superuser=False):
    user.is_staff = True
    user.is_superuser = superuser
    user.save(update_fields=['is_staff', 'is_superuser'])
    profile = user.profile
    profile.role = UserProfile.ROLE_ADMIN
    profile.save(update_fields=['role'])
    profile.role = UserProfile.ROLE_CLIENT
    profile.save(update_fields=['role'])
    user.refresh_from_db()
    return user


def _jwt(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(user)["access"]}')
    return api


def _prefix(context):
    return f'/api/accounts/projects/{context.project.pk}/'


@pytest.mark.parametrize('superuser', [False, True])
def test_staff_client_cannot_read_a_foreign_delivery(context, superuser):
    """Fails if a retained Django flag overrides JWT project ownership."""
    actor = _downgrade(context.admin, superuser=superuser)

    response = _jwt(actor).get(_prefix(context) + 'delivery/')

    assert response.status_code == 404


@pytest.mark.parametrize('superuser', [False, True])
def test_staff_client_cannot_edit_a_foreign_delivery_guide(context, superuser):
    """Fails if a client can persist an administrator edit through Django flags."""
    actor = _downgrade(context.admin, superuser=superuser)
    original_title = context.first.title
    expected = version(context)

    response = _jwt(actor).patch(_prefix(context) + f'delivery/requirements/{context.first.pk}/', {
        'expected_version': expected, 'title': 'Forbidden guide edit',
    }, format='json')

    context.first.refresh_from_db()
    assert response.status_code == 403
    assert context.first.title == original_title
    assert version(context) == expected


@pytest.mark.parametrize('superuser', [False, True])
def test_staff_client_owner_can_review_its_published_guide(context, superuser):
    """Fails if the real client owner is denied its ordinary JWT decision."""
    actor = _downgrade(context.client, superuser=superuser)
    publish(context)

    response = _jwt(actor).post(_prefix(context) + f'delivery/stages/{context.stage.pk}/review/',
        decisions(context, (context.first, 'approved')), format='json')

    context.first.refresh_from_db()
    assert response.status_code == 200
    review = RequirementReview.objects.get(requirement=context.first)
    assert review.actor_id == actor.pk
    assert review.is_external is False
    assert context.first.review_status == 'approved'


def test_admin_profile_without_staff_can_edit_a_delivery_guide(context):
    """Fails if Platform administration starts requiring a Django staff grant."""
    api = _jwt(context.admin)

    response = api.patch(_prefix(context) + f'delivery/requirements/{context.first.pk}/', {
        'expected_version': version(context), 'title': 'Platform administrator edit',
    }, format='json')

    context.first.refresh_from_db()
    assert response.status_code == 200
    assert context.first.title == 'Platform administrator edit'
    context.admin.refresh_from_db()
    assert context.admin.is_staff is False
    assert context.admin.is_superuser is False


def test_profile_downgrade_revokes_delivery_authority_for_an_existing_jwt(context):
    """Fails if the role claim in an older JWT overrides the current profile."""
    api = _jwt(context.admin)
    profile = context.admin.profile
    profile.role = UserProfile.ROLE_CLIENT
    profile.save(update_fields=['role'])

    response = api.get(_prefix(context) + 'delivery/')

    assert response.status_code == 404


def test_jwt_validation_exception_restores_the_previous_authority(context):
    """Fails if the JWT authority leaks into a subsequent non-JWT service call."""
    actor = _downgrade(context.admin)
    original_title = context.first.title

    response = _jwt(actor).post(_prefix(context) + f'delivery/requirements/{context.first.pk}/', {}, format='json')

    context.first.refresh_from_db()
    assert response.status_code == 400
    assert context.first.title == original_title
    delivery.mutate_node(context.project.pk, actor, 'requirements', {
        'expected_version': version(context), 'title': 'Restored trusted service edit',
    }, context.first.pk)
    context.first.refresh_from_db()
    assert context.first.title == 'Restored trusted service edit'
    actor.refresh_from_db()
    assert actor.is_staff is True
    assert actor.profile.role == UserProfile.ROLE_CLIENT


def test_jwt_payload_cannot_select_the_mcp_authority_channel(context):
    """Fails if request data can opt a client into the MCP authority boundary."""
    actor = _downgrade(context.admin)
    original_title = context.first.title

    response = _jwt(actor).patch(_prefix(context) + f'delivery/requirements/{context.first.pk}/', {
        'expected_version': version(context), 'title': 'Forged channel edit',
        'authority_channel': 'mcp', 'is_staff': True,
    }, format='json')

    context.first.refresh_from_db()
    assert response.status_code == 403
    assert context.first.title == original_title


def test_staff_client_cannot_read_foreign_issue_context_options(context):
    """Fails if the sibling issue adapter leaves the same ownership bypass."""
    publish(context)
    actor = _downgrade(context.admin)

    response = _jwt(actor).get(_prefix(context) + 'issue-reports/context-options/')

    assert response.status_code == 404


def test_staff_client_owner_can_acknowledge_its_signed_document(context):
    """Fails if the document signing adapter misclassifies the current client."""
    actor = _downgrade(context.client)
    signed_at = context.document.signed_at

    response = _jwt(actor).post(f'/api/accounts/documents/{context.document.uuid}/sign/',
        {'accept': True, 'signature_name': 'Cliente'}, format='json')

    context.document.refresh_from_db()
    assert response.status_code == 200
    assert context.document.signed_by_id == actor.pk
    assert context.document.signed_at == signed_at


def test_staff_client_requirement_selector_hides_unpublished_guides(context):
    """Fails if the client selector reads live drafts through the shared overview."""
    actor = _downgrade(context.client)

    response = _jwt(actor).get(_prefix(context) + 'requirements/')

    assert response.status_code == 200
    assert response.data == []


def test_nested_issue_options_preserve_the_current_client_authority(context):
    """Fails if a nested overview restores administrator authority too early."""
    actor = _downgrade(context.client)
    ProjectContract.objects.create(project=context.project, key='private-contract', title='Private contract',
        document=context.document, client_visible=False)

    response = _jwt(actor).get(_prefix(context) + 'issue-reports/context-options/')

    assert response.status_code == 200
    assert response.data['scope_review_available'] is False
    assert [row['id'] for row in response.data['contracts']] == [context.contract.pk]
    assert response.data['requirements'] == []


def _bug_issue(context):
    ticket = BugReport.objects.create(project=context.project, reported_by=context.client,
        title='Bug with retained notes', description='Original report')
    BugComment.objects.create(bug_report=ticket, user=context.admin, content='Private note', is_internal=True)
    public = BugComment.objects.create(bug_report=ticket, user=context.client, content='Public note')
    return f'bug-reports/{ticket.pk}/', public.pk


def _change_issue(context):
    ticket = ChangeRequest.objects.create(project=context.project, created_by=context.client,
        title='Request with retained notes', description='Original report')
    ChangeRequestComment.objects.create(change_request=ticket, user=context.admin, content='Private note', is_internal=True)
    public = ChangeRequestComment.objects.create(change_request=ticket, user=context.client, content='Public note')
    return f'change-requests/{ticket.pk}/', public.pk


@pytest.mark.parametrize('build_issue', [_bug_issue, _change_issue])
def test_staff_client_ticket_detail_hides_internal_comments(context, build_issue):
    """Fails if the shared issue serializer reveals internal comments to a client."""
    actor = _downgrade(context.client)
    suffix, public_comment_id = build_issue(context)

    response = _jwt(actor).get(_prefix(context) + suffix)

    assert response.status_code == 200
    assert [comment['id'] for comment in response.data['comments']] == [public_comment_id]
