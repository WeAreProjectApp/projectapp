from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement
import io
from datetime import datetime, timezone as datetime_timezone

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import (
    ChangeRequest,
    ChangeRequestComment,
    Deliverable,
    Project,
    Requirement,
    UserProfile,
)
from content.models.business_proposal import BusinessProposal

User = get_user_model()
MAX_CHANGE_REQUEST_LIST_QUERIES = 6


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    user = User.objects.create_user(
        username='admin@cr.com', email='admin@cr.com', password='adminpass1',
        first_name='Admin', last_name='User',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_ADMIN,
        is_onboarded=True, profile_completed=True,
    )
    return user


@pytest.fixture
def admin_headers(api_client, admin_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'admin@cr.com', 'password': 'adminpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user(admin_user):
    user = User.objects.create_user(
        username='client@cr.com', email='client@cr.com', password='clientpass1',
        first_name='Carlos', last_name='López',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT,
        is_onboarded=True, profile_completed=True,
        company_name='CRCorp', created_by=admin_user,
    )
    return user


@pytest.fixture
def client_headers(api_client, client_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'client@cr.com', 'password': 'clientpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def project(client_user):
    return Project.objects.create(
        name='CR Project', client=client_user,
        status=Project.STATUS_ACTIVE, progress=0,
    )


@pytest.fixture
def default_deliverable(project, client_user):
    return Deliverable.objects.create(
        project=project,
        title='CR default deliverable',
        category=Deliverable.CATEGORY_OTHER,
        file=None,
        uploaded_by=client_user,
    )


@pytest.fixture
def default_phase(project):
    from content.models.business_proposal import BusinessProposal
    bp = BusinessProposal.objects.create(title='CR proposal', client_name='Carlos')
    return make_delivery_stage(project, phase_title=bp.title)


@pytest.fixture
def source_requirement(default_phase):
    return make_requirement(default_phase, title='Source req')


@pytest.fixture
def sample_change_requests(project, client_user, admin_user):
    crs = []
    crs.append(ChangeRequest.objects.create(
        project=project, created_by=client_user,
        title='Add dark mode', description='Support dark theme.',
        module_or_screen='UI', suggested_priority='medium',
        status=ChangeRequest.STATUS_PENDING,
    ))
    crs.append(ChangeRequest.objects.create(
        project=project, created_by=client_user,
        title='Change button color', suggested_priority='low',
        status=ChangeRequest.STATUS_APPROVED,
        admin_response='Approved, 1 day effort.', estimated_time='1 día',
    ))
    crs.append(ChangeRequest.objects.create(
        project=project, created_by=client_user,
        title='Add export PDF', suggested_priority='high',
        is_urgent=True, status=ChangeRequest.STATUS_EVALUATING,
    ))
    return crs


def _make_test_image(width=200, height=200):
    """Create a small in-memory PNG image for upload tests."""
    img = Image.new('RGB', (width, height), color='red')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return SimpleUploadedFile('test.png', buf.read(), content_type='image/png')


def _url(project_id, suffix=''):
    return f'/api/accounts/projects/{project_id}/change-requests/{suffix}'


def _detail_url(project_id, cr_id, suffix=''):
    return f'/api/accounts/projects/{project_id}/change-requests/{cr_id}/{suffix}'


def _create_change_request_rows(project, user, count, *, start=0, add_comments=False):
    requirements = [
        make_requirement(
            make_delivery_stage(project, phase_title=f'Change budget proposal {index}'),
            title=f'Change budget source {index}', key=f'change-budget-source-{index}',
        )
        for index in range(start, start + count)
    ]
    items = ChangeRequest.objects.bulk_create([
        ChangeRequest(project=project, created_by=user, source_requirement=requirement,
            title=f'Change budget request {requirement.id}', )
        for requirement in requirements
    ])
    if add_comments:
        ChangeRequestComment.objects.bulk_create([
            ChangeRequestComment(change_request=item, user=user, content=f'Change budget comment {item.id}', is_internal=True)
            for item in items
        ])
    return items


# =========================================================================
# List & Filter
# =========================================================================


@pytest.mark.django_db
class TestChangeRequestList:
    def test_admin_lists_all_change_requests_for_project(
        self, api_client, admin_headers, project, sample_change_requests,
    ):
        resp = api_client.get(_url(project.id), **admin_headers)

        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_client_lists_change_requests_for_own_project(
        self, api_client, client_headers, project, sample_change_requests,
    ):
        resp = api_client.get(_url(project.id), **client_headers)

        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_filter_by_status_returns_matching_only(
        self, api_client, admin_headers, project, sample_change_requests,
    ):
        resp = api_client.get(f'{_url(project.id)}?status=pending', **admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['status'] == 'pending'

    def test_unauthenticated_request_rejected(self, api_client, project):
        resp = api_client.get(_url(project.id))

        assert resp.status_code == 401

    def test_other_client_cannot_list_change_requests(self, api_client, project):
        other = User.objects.create_user(
            username='other@cr.com', email='other@cr.com', password='pass1234',
        )
        UserProfile.objects.create(
            user=other, role=UserProfile.ROLE_CLIENT,
            is_onboarded=True, profile_completed=True,
        )
        client = APIClient()
        resp = client.post('/api/accounts/login/', {
            'email': 'other@cr.com', 'password': 'pass1234',
        })
        token = resp.json()['tokens']['access']

        resp = client.get(_url(project.id), HTTP_AUTHORIZATION=f'Bearer {token}')

        assert resp.status_code == 403

    def test_change_request_project_list_query_budget(self, api_client, admin_headers, project, client_user):
        """Fails if listing change requests restores per-row relation queries."""
        _create_change_request_rows(project, client_user, 1)

        with CaptureQueriesContext(connection) as one_request_queries:
            one_request_response = api_client.get(_url(project.id), **admin_headers)

        _create_change_request_rows(project, client_user, 49, start=1, add_comments=True)

        with CaptureQueriesContext(connection) as fifty_request_queries:
            fifty_request_response = api_client.get(_url(project.id), **admin_headers)

        assert (one_request_response.status_code, fifty_request_response.status_code) == (200, 200)
        assert (len(one_request_response.json()), len(fifty_request_response.json())) == (1, 50)
        assert [item['comments_count'] for item in one_request_response.json()] == [0]
        assert sorted(item['comments_count'] for item in fifty_request_response.json()) == [0] + [1] * 49
        assert len(one_request_queries) == len(fifty_request_queries)
        assert len(fifty_request_queries) <= MAX_CHANGE_REQUEST_LIST_QUERIES

    def test_change_request_project_list_sorts_by_created_at(
        self, api_client, admin_headers, project, client_user,
    ):
        """Fails if a comment aggregate drops newest-first request ordering."""
        older = ChangeRequest.objects.create(project=project, created_by=client_user, title='Older')
        newer = ChangeRequest.objects.create(project=project, created_by=client_user, title='Newer')
        ChangeRequest.objects.filter(pk=older.pk).update(
            created_at=datetime(2026, 1, 1, tzinfo=datetime_timezone.utc),
        )
        ChangeRequest.objects.filter(pk=newer.pk).update(
            created_at=datetime(2026, 1, 2, tzinfo=datetime_timezone.utc),
        )

        response = api_client.get(_url(project.id), **admin_headers)

        assert response.status_code == 200
        assert [item['id'] for item in response.json()] == [newer.id, older.id]

    def test_change_request_list_filters_phase_id(self, api_client, admin_headers, project, client_user):
        """Fails if the phase filter returns requests from another project phase."""
        target, _ = _create_change_request_rows(project, client_user, 2)

        response = api_client.get(f'{_url(project.id)}?phase_id={target.source_requirement.stage.phase_id}', **admin_headers)

        assert response.status_code == 200
        assert [item['id'] for item in response.json()] == [target.id]

    def test_change_request_list_excludes_archived(self, api_client, admin_headers, project, client_user):
        """Fails if archived requests are visible without the admin archive flag."""
        visible = ChangeRequest.objects.create(project=project, created_by=client_user, title='Visible')
        archived = ChangeRequest.objects.create(
            project=project, created_by=client_user, title='Archived', is_archived=True,
        )

        default_response = api_client.get(_url(project.id), **admin_headers)
        archived_response = api_client.get(f'{_url(project.id)}?include_archived=1', **admin_headers)

        assert [item['id'] for item in default_response.json()] == [visible.id]
        assert {item['id'] for item in archived_response.json()} == {visible.id, archived.id}

    def test_change_request_list_serializes_source_requirement(
        self, api_client, admin_headers, project, client_user,
    ):
        """Fails if the optimized list loses source requirement fields or nulls."""
        source_request = _create_change_request_rows(project, client_user, 1)[0]
        source = source_request.source_requirement
        no_source = ChangeRequest.objects.create(project=project, created_by=client_user, title='No source')

        response = api_client.get(_url(project.id), **admin_headers)

        by_id = {item['id']: item for item in response.json()}
        assert by_id[source_request.id]['source_requirement'] == {
            'id': source.id,
            'title': source.title,
            'review_status': source.review_status,
            'stage_id': source.stage_id,
            'stage_title': source.stage.title,
            'phase_id': source.stage.phase_id,
            'phase_title': 'Change budget proposal 0',
        }
        assert by_id[no_source.id]['source_requirement'] is None


# =========================================================================
# Create
# =========================================================================


@pytest.mark.django_db
class TestChangeRequestCreate:
    def test_client_creates_change_request(
        self, api_client, client_headers, project, source_requirement,
    ):
        resp = api_client.post(_url(project.id), {
            'title': 'New feature request',
            'description': 'I need this feature.',
            'module_or_screen': 'Dashboard',
            'suggested_priority': 'high',
            'is_urgent': True,
            'source_requirement_id': source_requirement.id,
        }, format='json', **client_headers)

        assert resp.status_code == 201
        data = resp.json()
        assert data['title'] == 'New feature request'
        assert data['suggested_priority'] == 'high'
        assert data['is_urgent'] is True
        assert data['status'] == 'pending'
        assert data['created_by_name'] == 'Carlos López'

    def test_admin_creates_change_request(
        self, api_client, admin_headers, project, source_requirement,
    ):
        resp = api_client.post(_url(project.id), {
            'title': 'Admin-initiated change',
            'source_requirement_id': source_requirement.id,
        }, format='json', **admin_headers)

        assert resp.status_code == 201
        assert resp.json()['title'] == 'Admin-initiated change'

    def test_create_without_title_fails(
        self, api_client, client_headers, project, source_requirement,
    ):
        resp = api_client.post(_url(project.id), {
            'description': 'No title provided.',
            'source_requirement_id': source_requirement.id,
        }, format='json', **client_headers)

        assert resp.status_code == 400

    def test_create_with_screenshot_saves_optimized_image(
        self, api_client, client_headers, project, source_requirement,
    ):
        image = _make_test_image(2000, 1500)

        resp = api_client.post(
            _url(project.id),
            {
                'title': 'With screenshot',
                'description': 'See attached.',
                'suggested_priority': 'medium',
                'is_urgent': 'false',
                'screenshot': image,
                'source_requirement_id': source_requirement.id,
            },
            format='multipart', **client_headers,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data['screenshot_url'] is not None
        assert data['screenshot_url'].endswith('.jpg')

        cr = ChangeRequest.objects.get(id=data['id'])
        assert cr.screenshot is not None

    def test_create_with_large_screenshot_resizes_below_max_dimension(
        self, api_client, client_headers, project, source_requirement,
    ):
        image = _make_test_image(3000, 2000)

        resp = api_client.post(
            _url(project.id),
            {
                'title': 'Large screenshot',
                'suggested_priority': 'medium',
                'is_urgent': 'false',
                'screenshot': image,
                'source_requirement_id': source_requirement.id,
            },
            format='multipart', **client_headers,
        )

        assert resp.status_code == 201
        cr = ChangeRequest.objects.get(id=resp.json()['id'])
        img = Image.open(cr.screenshot.path)
        assert max(img.width, img.height) <= 1200


# =========================================================================
# Detail
# =========================================================================


@pytest.mark.django_db
class TestChangeRequestDetail:
    def test_admin_gets_detail_with_comments(
        self, api_client, admin_headers, project, sample_change_requests, admin_user,
    ):
        cr = sample_change_requests[0]
        ChangeRequestComment.objects.create(
            change_request=cr, user=admin_user, content='Noted.',
        )

        resp = api_client.get(_detail_url(project.id, cr.id), **admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data['title'] == 'Add dark mode'
        assert 'comments' in data
        assert len(data['comments']) == 1

    def test_client_gets_detail_for_own_project(
        self, api_client, client_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        resp = api_client.get(_detail_url(project.id, cr.id), **client_headers)

        assert resp.status_code == 200
        assert resp.json()['title'] == 'Add dark mode'

    def test_nonexistent_change_request_returns_404(
        self, api_client, admin_headers, project,
    ):
        resp = api_client.get(_detail_url(project.id, 99999), **admin_headers)

        assert resp.status_code == 404

    def test_client_does_not_see_internal_comments(
        self, api_client, admin_headers, client_headers, project,
        sample_change_requests, admin_user,
    ):
        cr = sample_change_requests[0]
        ChangeRequestComment.objects.create(
            change_request=cr, user=admin_user, content='Internal note',
            is_internal=True,
        )
        ChangeRequestComment.objects.create(
            change_request=cr, user=admin_user, content='Public note',
            is_internal=False,
        )

        resp = api_client.get(_detail_url(project.id, cr.id), **client_headers)

        comments = resp.json()['comments']
        assert len(comments) == 1
        assert comments[0]['content'] == 'Public note'

    def test_admin_sees_all_comments_including_internal(
        self, api_client, admin_headers, project, sample_change_requests, admin_user,
    ):
        cr = sample_change_requests[0]
        ChangeRequestComment.objects.create(
            change_request=cr, user=admin_user, content='Internal', is_internal=True,
        )
        ChangeRequestComment.objects.create(
            change_request=cr, user=admin_user, content='Public', is_internal=False,
        )

        resp = api_client.get(_detail_url(project.id, cr.id), **admin_headers)

        assert len(resp.json()['comments']) == 2


# =========================================================================
# Delete
# =========================================================================


@pytest.mark.django_db
class TestChangeRequestDelete:
    def test_admin_deletes_change_request(
        self, api_client, admin_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        resp = api_client.delete(_detail_url(project.id, cr.id), **admin_headers)

        assert resp.status_code == 200
        assert resp.json()['detail'] == 'Solicitud de cambio archivada.'
        cr.refresh_from_db()
        assert cr.is_archived is True

    def test_client_cannot_delete_change_request(
        self, api_client, client_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        resp = api_client.delete(_detail_url(project.id, cr.id), **client_headers)

        assert resp.status_code == 403
        assert ChangeRequest.objects.filter(id=cr.id).exists()


# =========================================================================
# Evaluate (admin only)
# =========================================================================


@pytest.mark.django_db
class TestChangeRequestEvaluate:
    def test_admin_evaluates_change_request(
        self, api_client, admin_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        resp = api_client.post(
            _detail_url(project.id, cr.id, 'evaluate/'),
            {
                'status': 'approved',
                'admin_response': 'Looks good, we will implement.',
                'estimated_time': '3 días',
                'estimated_cost': 500000,
            },
            format='json', **admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'approved'
        assert data['admin_response'] == 'Looks good, we will implement.'
        assert data['estimated_time'] == '3 días'
        assert float(data['estimated_cost']) == 500000.0

    def test_admin_rejects_change_request_with_response(
        self, api_client, admin_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        resp = api_client.post(
            _detail_url(project.id, cr.id, 'evaluate/'),
            {
                'status': 'rejected',
                'admin_response': 'Out of scope for this phase.',
            },
            format='json', **admin_headers,
        )

        assert resp.status_code == 200
        assert resp.json()['status'] == 'rejected'

    def test_admin_marks_needs_clarification(
        self, api_client, admin_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        resp = api_client.post(
            _detail_url(project.id, cr.id, 'evaluate/'),
            {'status': 'needs_clarification', 'admin_response': 'Could you elaborate?'},
            format='json', **admin_headers,
        )

        assert resp.status_code == 200
        assert resp.json()['status'] == 'needs_clarification'

    def test_client_cannot_evaluate_change_request(
        self, api_client, client_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        resp = api_client.post(
            _detail_url(project.id, cr.id, 'evaluate/'),
            {'status': 'approved'},
            format='json', **client_headers,
        )

        assert resp.status_code == 403

    def test_evaluate_nonexistent_cr_returns_404(
        self, api_client, admin_headers, project,
    ):
        resp = api_client.post(
            _detail_url(project.id, 99999, 'evaluate/'),
            {'status': 'approved'},
            format='json', **admin_headers,
        )

        assert resp.status_code == 404

    def test_evaluate_persists_changes_in_database(
        self, api_client, admin_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        api_client.post(
            _detail_url(project.id, cr.id, 'evaluate/'),
            {'status': 'out_of_scope', 'admin_response': 'Not in scope.'},
            format='json', **admin_headers,
        )

        cr.refresh_from_db()
        assert cr.status == ChangeRequest.STATUS_OUT_OF_SCOPE
        assert cr.admin_response == 'Not in scope.'


# =========================================================================
# Comments
# =========================================================================


@pytest.mark.django_db
class TestChangeRequestComments:
    def test_admin_adds_public_comment(
        self, api_client, admin_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        resp = api_client.post(
            _detail_url(project.id, cr.id, 'comments/'),
            {'content': 'Thanks for the request.', 'is_internal': False},
            format='json', **admin_headers,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data['content'] == 'Thanks for the request.'
        assert data['is_internal'] is False

    def test_admin_adds_internal_comment(
        self, api_client, admin_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        resp = api_client.post(
            _detail_url(project.id, cr.id, 'comments/'),
            {'content': 'Internal: check with designer', 'is_internal': True},
            format='json', **admin_headers,
        )

        assert resp.status_code == 201
        assert resp.json()['is_internal'] is True

    def test_client_adds_comment(
        self, api_client, client_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        resp = api_client.post(
            _detail_url(project.id, cr.id, 'comments/'),
            {'content': 'Please prioritize this.'},
            format='json', **client_headers,
        )

        assert resp.status_code == 201
        assert resp.json()['content'] == 'Please prioritize this.'

    def test_client_cannot_create_internal_comment(
        self, api_client, client_headers, project, sample_change_requests,
    ):
        cr = sample_change_requests[0]

        api_client.post(
            _detail_url(project.id, cr.id, 'comments/'),
            {'content': 'Trying internal', 'is_internal': True},
            format='json', **client_headers,
        )

        comment = ChangeRequestComment.objects.last()
        assert comment.is_internal is False

    def test_comment_on_nonexistent_cr_returns_404(
        self, api_client, admin_headers, project,
    ):
        resp = api_client.post(
            _detail_url(project.id, 99999, 'comments/'),
            {'content': 'Ghost comment'},
            format='json', **admin_headers,
        )

        assert resp.status_code == 404


# =========================================================================
# Convert to Requirement
# =========================================================================


@pytest.mark.django_db
class TestChangeRequestConvert:
    def test_admin_converts_approved_request_to_draft_guide(self, api_client, admin_headers, project, sample_change_requests):
        stage = make_delivery_stage(project, published=False)
        approved = sample_change_requests[1]

        response = api_client.post(_detail_url(project.id, approved.id, 'convert/'), {
            'stage_id': stage.id, 'expected_version': 0,
        }, format='json', **admin_headers)

        assert response.status_code == 201
        requirement = Requirement.objects.get(id=response.json()['linked_requirement_id'])
        assert (requirement.title, requirement.stage_id, requirement.review_status) == (approved.title, stage.id, 'pending')

    def test_conversion_preserves_project_commercial_progress(self, api_client, admin_headers, project, sample_change_requests):
        stage = make_delivery_stage(project, published=False)
        project.progress = 72
        project.save(update_fields=['progress'])

        response = api_client.post(_detail_url(project.id, sample_change_requests[1].id, 'convert/'), {
            'stage_id': stage.id, 'expected_version': 0,
        }, format='json', **admin_headers)

        project.refresh_from_db()
        assert response.status_code == 201
        assert project.progress == 72

    def test_conversion_requires_approved_change_request(self, api_client, admin_headers, project, sample_change_requests):
        response = api_client.post(_detail_url(project.id, sample_change_requests[0].id, 'convert/'), format='json', **admin_headers)

        assert response.status_code == 400

    def test_conversion_does_not_duplicate_linked_requirement(self, api_client, admin_headers, project, sample_change_requests):
        stage = make_delivery_stage(project, published=False)
        approved = sample_change_requests[1]
        api_client.post(_detail_url(project.id, approved.id, 'convert/'), {'stage_id': stage.id, 'expected_version': 0}, format='json', **admin_headers)

        response = api_client.post(_detail_url(project.id, approved.id, 'convert/'), {'stage_id': stage.id, 'expected_version': 1}, format='json', **admin_headers)

        assert response.status_code == 400
        assert Requirement.objects.filter(key=f'change-request-{approved.id}').count() == 1

    def test_client_cannot_convert_change_request(self, api_client, client_headers, project, sample_change_requests):
        response = api_client.post(_detail_url(project.id, sample_change_requests[1].id, 'convert/'), format='json', **client_headers)

        assert response.status_code == 403

    def test_conversion_cannot_add_a_guide_to_an_approved_stage(self, api_client, admin_headers, project, sample_change_requests):
        stage = make_delivery_stage(project)
        existing = make_requirement(stage)
        existing.review_status = 'approved'
        existing.save(update_fields=['review_status'])
        request = sample_change_requests[1]

        response = api_client.post(_detail_url(project.id, request.id, 'convert/'), {
            'stage_id': stage.id, 'expected_version': 0,
        }, format='json', **admin_headers)

        request.refresh_from_db()
        assert response.status_code == 400
        assert request.linked_requirement_id is None
        assert list(stage.requirements.values_list('pk', flat=True)) == [existing.pk]

    def test_conversion_rejects_a_stage_from_another_project(self, api_client, admin_headers, project, client_user, sample_change_requests):
        other = Project.objects.create(name='Other delivery', client=client_user)
        stage = make_delivery_stage(other, published=False)
        request = sample_change_requests[1]

        response = api_client.post(_detail_url(project.id, request.id, 'convert/'), {
            'stage_id': stage.id, 'expected_version': 0,
        }, format='json', **admin_headers)

        request.refresh_from_db()
        assert response.status_code == 404
        assert request.linked_requirement_id is None
        assert not stage.requirements.exists()

    def test_conversion_rejects_a_stale_followup_version(self, api_client, admin_headers, project, sample_change_requests):
        from accounts.models import DeliveryWorkspace
        stage = make_delivery_stage(project, published=False)
        DeliveryWorkspace.objects.create(project=project, version=2)
        request = sample_change_requests[1]

        response = api_client.post(_detail_url(project.id, request.id, 'convert/'), {
            'stage_id': stage.id, 'expected_version': 0,
        }, format='json', **admin_headers)

        request.refresh_from_db()
        assert response.status_code == 409
        assert request.linked_requirement_id is None
        assert not stage.requirements.exists()


# =========================================================================
# General endpoint (all projects)
# =========================================================================


@pytest.mark.django_db
class TestChangeRequestAllView:
    def test_admin_sees_change_requests_across_all_projects(
        self, api_client, admin_headers, project, sample_change_requests, client_user,
    ):
        other_project = Project.objects.create(
            name='Other Project', client=client_user, status=Project.STATUS_ACTIVE,
        )
        ChangeRequest.objects.create(
            project=other_project, created_by=client_user,
            title='Other project CR', suggested_priority='low',
        )

        resp = api_client.get('/api/accounts/change-requests/', **admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        project_names = {item['project_name'] for item in data}
        assert 'CR Project' in project_names
        assert 'Other Project' in project_names

    def test_client_sees_only_own_project_change_requests(
        self, api_client, client_headers, project, sample_change_requests, admin_user,
    ):
        other_client = User.objects.create_user(
            username='other2@cr.com', email='other2@cr.com', password='pass1234',
        )
        UserProfile.objects.create(
            user=other_client, role=UserProfile.ROLE_CLIENT,
            is_onboarded=True, profile_completed=True,
        )
        other_project = Project.objects.create(
            name='Secret Project', client=other_client, status=Project.STATUS_ACTIVE,
        )
        ChangeRequest.objects.create(
            project=other_project, created_by=other_client,
            title='Should not see', suggested_priority='low',
        )

        resp = api_client.get('/api/accounts/change-requests/', **client_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert all(item['project_name'] == 'CR Project' for item in data)

    def test_general_endpoint_includes_project_id_and_name(
        self, api_client, admin_headers, project, sample_change_requests,
    ):
        resp = api_client.get('/api/accounts/change-requests/', **admin_headers)

        data = resp.json()
        for item in data:
            assert 'project_id' in item
            assert 'project_name' in item
            assert item['project_id'] == project.id

    def test_general_endpoint_filters_by_status(
        self, api_client, admin_headers, project, sample_change_requests,
    ):
        resp = api_client.get(
            '/api/accounts/change-requests/?status=evaluating', **admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['status'] == 'evaluating'

    def test_unauthenticated_request_rejected(self, api_client):
        resp = api_client.get('/api/accounts/change-requests/')

        assert resp.status_code == 401

    def test_change_request_global_list_query_budget(self, api_client, admin_headers, project, client_user):
        """Fails if the global change request list restores relation queries per row."""
        _create_change_request_rows(project, client_user, 1)

        with CaptureQueriesContext(connection) as one_request_queries:
            one_request_response = api_client.get('/api/accounts/change-requests/', **admin_headers)

        _create_change_request_rows(project, client_user, 49, start=1, add_comments=True)

        with CaptureQueriesContext(connection) as fifty_request_queries:
            fifty_request_response = api_client.get('/api/accounts/change-requests/', **admin_headers)

        assert (one_request_response.status_code, fifty_request_response.status_code) == (200, 200)
        assert (len(one_request_response.json()), len(fifty_request_response.json())) == (1, 50)
        assert [item['comments_count'] for item in one_request_response.json()] == [0]
        assert sorted(item['comments_count'] for item in fifty_request_response.json()) == [0] + [1] * 49
        assert len(one_request_queries) == len(fifty_request_queries)
        assert len(fifty_request_queries) <= MAX_CHANGE_REQUEST_LIST_QUERIES


# =========================================================================
# Screenshot optimization (model-level)
# =========================================================================


@pytest.mark.django_db
class TestScreenshotOptimization:
    def test_screenshot_saved_as_jpeg(self, project, client_user):
        image = _make_test_image(800, 600)

        cr = ChangeRequest(
            project=project, created_by=client_user,
            title='Screenshot test', suggested_priority='medium',
        )
        cr.screenshot = image
        cr.save()

        assert cr.screenshot.name.endswith('.jpg')

    def test_large_screenshot_resized_to_max_1200px(self, project, client_user):
        image = _make_test_image(2400, 1800)

        cr = ChangeRequest(
            project=project, created_by=client_user,
            title='Large image test', suggested_priority='medium',
        )
        cr.screenshot = image
        cr.save()

        saved_img = Image.open(cr.screenshot.path)
        assert max(saved_img.width, saved_img.height) <= 1200

    def test_small_screenshot_not_upscaled(self, project, client_user):
        image = _make_test_image(400, 300)

        cr = ChangeRequest(
            project=project, created_by=client_user,
            title='Small image test', suggested_priority='medium',
        )
        cr.screenshot = image
        cr.save()

        saved_img = Image.open(cr.screenshot.path)
        assert saved_img.width == 400
        assert saved_img.height == 300

    def test_change_request_without_screenshot_saves_normally(self, project, client_user):
        cr = ChangeRequest.objects.create(
            project=project, created_by=client_user,
            title='No screenshot', suggested_priority='medium',
        )

        assert not cr.screenshot
        assert cr.id is not None
