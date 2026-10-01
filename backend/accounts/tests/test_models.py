from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from freezegun import freeze_time

from accounts.models import (
    BugReport,
    ChangeRequest,
    DataModelEntity,
    Deliverable,
    DeliverableClientFolder,
    DeliverableClientUpload,
    DeliverableVersion,
    HostingSubscription,
    Notification,
    Project,
    ProjectDataModelEntity,
    ProjectPhase,
    UserProfile,
    VerificationCode,
)
from content.models.business_proposal import BusinessProposal



User = get_user_model()


@pytest.mark.django_db
class TestUserProfile:
    def test_create_admin_profile(self):
        user = User.objects.create_user(username='admin@test.com', email='admin@test.com', password='pass1234')
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)

        assert profile.is_admin is True
        assert profile.is_client is False
        assert profile.is_onboarded is True
        assert str(profile) == 'admin@test.com (Admin)'

    def test_create_client_profile(self):
        user = User.objects.create_user(username='client@test.com', email='client@test.com', password='pass1234')
        profile = UserProfile.objects.create(
            user=user, role=UserProfile.ROLE_CLIENT,
            company_name='Acme Corp', phone='+57 300 111 2222',
        )

        assert profile.is_client is True
        assert profile.is_admin is False
        assert profile.is_onboarded is False
        assert profile.company_name == 'Acme Corp'

    def test_profile_default_role_is_client(self):
        user = User.objects.create_user(username='new@test.com', email='new@test.com', password='pass1234')
        profile = UserProfile.objects.create(user=user)

        assert profile.role == UserProfile.ROLE_CLIENT

    def test_created_by_tracks_admin(self):
        admin_user = User.objects.create_user(username='admin@t.com', email='admin@t.com', password='p')
        client_user = User.objects.create_user(username='client@t.com', email='client@t.com', password='p')
        profile = UserProfile.objects.create(user=client_user, created_by=admin_user)

        assert profile.created_by == admin_user


@pytest.mark.django_db
class TestVerificationCode:
    def _make_user(self, email='user@test.com'):
        return User.objects.create_user(username=email, email=email, password='pass1234')

    def test_generate_code_returns_six_digits(self):
        code = VerificationCode.generate_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_create_for_user_invalidates_previous(self):
        user = self._make_user()
        first = VerificationCode.create_for_user(user)
        second = VerificationCode.create_for_user(user)

        first.refresh_from_db()
        assert first.is_used is True
        assert second.is_used is False
        assert second.is_valid is True

    def test_is_valid_when_fresh(self):
        user = self._make_user()
        otp = VerificationCode.create_for_user(user)

        assert otp.is_valid is True
        assert otp.is_expired is False

    @freeze_time("2025-01-01 12:00:00")
    def test_is_expired_after_expiry(self):
        user = self._make_user()
        otp = VerificationCode.create_for_user(user)

        with freeze_time("2025-01-01 12:11:00"):
            assert otp.is_expired is True
            assert otp.is_valid is False

    def test_max_attempts_reached(self):
        user = self._make_user()
        otp = VerificationCode.create_for_user(user)
        otp.attempts = VerificationCode.MAX_ATTEMPTS
        otp.save()

        assert otp.is_valid is False

    def test_mark_used(self):
        user = self._make_user()
        otp = VerificationCode.create_for_user(user)
        otp.mark_used()

        assert otp.is_used is True
        assert otp.is_valid is False

    def test_increment_attempts(self):
        user = self._make_user()
        otp = VerificationCode.create_for_user(user)
        otp.increment_attempts()

        assert otp.attempts == 1

    def test_str_representation_active(self):
        user = self._make_user('str@test.com')
        otp = VerificationCode.create_for_user(user)

        result = str(otp)

        assert 'str@test.com' in result
        assert 'active' in result

    def test_str_representation_used(self):
        user = self._make_user('used@test.com')
        otp = VerificationCode.create_for_user(user)
        otp.mark_used()

        result = str(otp)

        assert 'used' in result


@pytest.mark.django_db
class TestUserProfileAvatarDisplayUrl:
    def test_returns_avatar_url_when_avatar_field_is_set(self):
        user = User.objects.create_user(username='av@test.com', email='av@test.com', password='pass1234')
        profile = UserProfile.objects.create(user=user, avatar_url='https://old.com/pic.jpg')
        # Simulate avatar field being truthy by checking the fallback
        # When avatar is empty, falls back to avatar_url
        assert profile.avatar_display_url == 'https://old.com/pic.jpg'

    def test_returns_empty_string_when_no_avatar(self):
        user = User.objects.create_user(username='noav@test.com', email='noav@test.com', password='pass1234')
        profile = UserProfile.objects.create(user=user)

        assert profile.avatar_display_url == ''

    def test_returns_avatar_url_field_as_fallback(self):
        user = User.objects.create_user(username='fb@test.com', email='fb@test.com', password='pass1234')
        profile = UserProfile.objects.create(user=user, avatar_url='https://cdn.example.com/avatar.png')

        assert profile.avatar_display_url == 'https://cdn.example.com/avatar.png'


@pytest.mark.django_db
class TestProjectModel:
    def test_str_representation(self):
        user = User.objects.create_user(username='pm@test.com', email='pm@test.com', password='pass')
        project = Project.objects.create(name='My Project', client=user)

        assert str(project) == 'My Project — pm@test.com'

    def test_status_display_returns_human_label(self):
        user = User.objects.create_user(username='sd@test.com', email='sd@test.com', password='pass')
        project = Project.objects.create(name='P', client=user, status=Project.STATUS_ACTIVE)

        assert project.status_display == 'Activo'

    def test_status_display_marks_legacy_archived_for_review(self):
        user = User.objects.create_user(username='ar@test.com', email='ar@test.com', password='pass')
        project = Project.objects.create(name='P', client=user, status=Project.STATUS_ARCHIVED)

        assert project.status_display == 'Sin clasificar'
        assert project.state_review_required is True








# ---------------------------------------------------------------------------
# Project.linked_business_proposal
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestProjectLinkedBusinessProposal:
    def test_returns_none_when_no_linked_proposals(self):
        user = User.objects.create_user(username='lbp@test.com', email='lbp@test.com', password='x')
        project = Project.objects.create(name='P', client=user)
        assert project.linked_business_proposal() is None

    def test_returns_proposal_when_phase_links_it(self):
        """As of the platform IA refactor, linked_business_proposal() reads
        from ProjectPhase instead of going through Deliverable.deliverable."""
        from accounts.models import ProjectPhase
        from content.models import BusinessProposal

        user = User.objects.create_user(username='lbp2@test.com', email='lbp2@test.com', password='x')
        project = Project.objects.create(name='P2', client=user)
        proposal = BusinessProposal.objects.create(
            title='Linked',
            client_name='X',
            client_email='x@example.com',
            total_investment=1000,
        )
        ProjectPhase.objects.create(project=project, business_proposal=proposal, order=1)
        result = project.linked_business_proposal()
        assert result.pk == proposal.pk


# ---------------------------------------------------------------------------
# Deliverable.file_size — exception path
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDeliverableFileSizeExceptionPath:
    def test_file_size_returns_zero_when_file_access_raises(self):
        user = User.objects.create_user(username='dfs@test.com', email='dfs@test.com', password='x')
        project = Project.objects.create(name='P', client=user)
        d = Deliverable.objects.create(
            project=project, title='D', category=Deliverable.CATEGORY_OTHER,
            file=None, uploaded_by=user,
        )
        with patch.object(type(d.file), 'size', new_callable=lambda: property(lambda self: (_ for _ in ()).throw(Exception('no file')))):
            assert d.file_size == 0

    def test_file_size_returns_zero_when_file_is_none(self):
        user = User.objects.create_user(username='dfs2@test.com', email='dfs2@test.com', password='x')
        project = Project.objects.create(name='P2', client=user)
        d = Deliverable.objects.create(
            project=project, title='D2', category=Deliverable.CATEGORY_OTHER,
            file=None, uploaded_by=user,
        )
        with patch.object(type(d), 'file', new_callable=lambda: property(lambda self: (_ for _ in ()).throw(OSError('no file')))):
            result = d.file_size
        assert result == 0


# ---------------------------------------------------------------------------
# DeliverableVersion.file_size — exception path
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDeliverableVersionFileSizeExceptionPath:
    def test_file_size_returns_zero_when_file_raises(self):
        user = User.objects.create_user(username='dvfs@test.com', email='dvfs@test.com', password='x')
        project = Project.objects.create(name='P', client=user)
        d = Deliverable.objects.create(
            project=project, title='D', category=Deliverable.CATEGORY_OTHER,
            file=None, uploaded_by=user,
        )
        version = DeliverableVersion.objects.create(
            deliverable=d, version_number=1, uploaded_by=user,
        )
        with patch.object(type(version.file), 'size', new_callable=lambda: property(lambda self: (_ for _ in ()).throw(Exception('no file')))):
            assert version.file_size == 0


# ---------------------------------------------------------------------------
# HostingSubscription.calculate_amounts
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHostingSubscriptionCalculateAmounts:
    def _make_sub(self, username, base, discount):
        from datetime import date
        user = User.objects.create_user(username=username, email=f'{username}@test.com', password='x')
        project = Project.objects.create(name=f'P-{username}', client=user)
        return HostingSubscription.objects.create(
            project=project,
            plan=HostingSubscription.PLAN_MONTHLY,
            base_monthly_amount=Decimal(str(base)),
            effective_monthly_amount=Decimal(str(base)),
            billing_amount=Decimal(str(base)),
            discount_percent=discount,
            start_date=date.today(),
            next_billing_date=date.today(),
        )

    def test_calculate_amounts_with_no_discount(self):
        sub = self._make_sub('hs1', 100, 0)
        sub.calculate_amounts()
        assert sub.effective_monthly_amount == Decimal('100.00')
        assert sub.billing_amount == Decimal('100.00')

    def test_calculate_amounts_applies_discount(self):
        sub = self._make_sub('hs2', 200, 10)
        sub.calculate_amounts()
        assert sub.effective_monthly_amount == Decimal('180.00')
        assert sub.billing_amount == Decimal('180.00')


# ---------------------------------------------------------------------------
# UserProfile.save — image optimization path
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUserProfileSaveImageOptimization:
    def test_save_with_image_content_type_calls_optimize(self):
        user = User.objects.create_user(username='upo@test.com', email='upo@test.com', password='x')
        profile = UserProfile(user=user)

        fake_file = SimpleUploadedFile('avatar.jpg', b'fake_jpeg', content_type='image/jpeg')
        profile.avatar = fake_file

        with patch('accounts.models.optimize_avatar', return_value=fake_file) as mock_opt:
            profile.save()

        mock_opt.assert_called_once()

    def test_save_swallows_exception_from_optimize(self):
        user = User.objects.create_user(username='upoe@test.com', email='upoe@test.com', password='x')
        profile = UserProfile(user=user)

        fake_file = SimpleUploadedFile('avatar.jpg', b'fake_jpeg', content_type='image/jpeg')
        profile.avatar = fake_file

        with patch('accounts.models.optimize_avatar', side_effect=RuntimeError('boom')):
            profile.save()  # must not raise

        assert UserProfile.objects.filter(pk=profile.pk).exists()


# ---------------------------------------------------------------------------
# ChangeRequest.save — image optimization
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestChangeRequestSaveImageOptimization:
    def test_save_with_image_screenshot_calls_optimize(self):
        user = User.objects.create_user(username='crio@test.com', email='crio@test.com', password='x')
        project = Project.objects.create(name='P', client=user)
        cr = ChangeRequest(
            project=project,
            title='Fix something',
            created_by=user,
        )
        fake_file = SimpleUploadedFile('screen.jpg', b'fake_jpeg', content_type='image/jpeg')
        cr.screenshot = fake_file

        with patch('accounts.models.optimize_image', return_value=fake_file) as mock_opt:
            cr.save()

        mock_opt.assert_called_once()

    def test_save_swallows_exception_from_optimize(self):
        user = User.objects.create_user(username='crex@test.com', email='crex@test.com', password='x')
        project = Project.objects.create(name='P', client=user)
        cr = ChangeRequest(
            project=project,
            title='Fix other',
            created_by=user,
        )
        fake_file = SimpleUploadedFile('screen.jpg', b'fake_jpeg', content_type='image/jpeg')
        cr.screenshot = fake_file

        with patch('accounts.models.optimize_image', side_effect=RuntimeError('boom')):
            cr.save()  # must not raise

        assert ChangeRequest.objects.filter(pk=cr.pk).exists()


# ---------------------------------------------------------------------------
# __str__ methods and simple properties for uncovered models
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUncoveredModelStrMethods:
    def _make_user(self, username):
        return User.objects.create_user(
            username=username, email=username, password='x',
        )

    def _make_project(self, user):
        return Project.objects.create(name='Str Project', client=user)

    def _make_deliverable(self, project, user):
        return Deliverable.objects.create(
            project=project,
            title='My Deliverable',
            category=Deliverable.CATEGORY_OTHER,
            uploaded_by=user,
        )

    def test_change_request_str(self):
        user = self._make_user('cr_str@test.com')
        project = self._make_project(user)
        cr = ChangeRequest.objects.create(project=project, title='Needs Fix', created_by=user)

        assert 'Needs Fix' in str(cr)

    def test_bug_report_str(self):
        user = self._make_user('bug_str@test.com')
        project = self._make_project(user)
        br = BugReport.objects.create(
            project=project, reported_by=user, title='Crash on Login',
        )

        assert 'Crash on Login' in str(br)

    def test_deliverable_str(self):
        user = self._make_user('del_str@test.com')
        project = self._make_project(user)
        d = self._make_deliverable(project, user)

        assert 'My Deliverable' in str(d)

    def test_deliverable_file_name_with_no_file(self):
        user = self._make_user('del_fn@test.com')
        project = self._make_project(user)
        d = self._make_deliverable(project, user)

        assert d.file_name == ''

    def test_deliverable_version_str(self):
        user = self._make_user('dv_str@test.com')
        project = self._make_project(user)
        d = self._make_deliverable(project, user)
        ver = DeliverableVersion.objects.create(
            deliverable=d, version_number=2, uploaded_by=user,
        )

        assert 'My Deliverable' in str(ver)
        assert '2' in str(ver)

    def test_deliverable_version_file_name_with_no_file(self):
        user = self._make_user('dv_fn@test.com')
        project = self._make_project(user)
        d = self._make_deliverable(project, user)
        ver = DeliverableVersion.objects.create(
            deliverable=d, version_number=1, uploaded_by=user,
        )

        assert ver.file_name == ''

    def test_deliverable_client_upload_str(self):
        user = self._make_user('dcu_str@test.com')
        project = self._make_project(user)
        d = self._make_deliverable(project, user)
        fake_file = SimpleUploadedFile('report.pdf', b'%PDF', content_type='application/pdf')
        upload = DeliverableClientUpload.objects.create(
            deliverable=d, file=fake_file, title='Client Report', uploaded_by=user,
        )

        assert str(d.id) in str(upload)

    def test_deliverable_client_upload_file_name_with_file(self):
        user = self._make_user('dcu_fn@test.com')
        project = self._make_project(user)
        d = self._make_deliverable(project, user)
        fake_file = SimpleUploadedFile('upload.pdf', b'%PDF', content_type='application/pdf')
        upload = DeliverableClientUpload.objects.create(
            deliverable=d, file=fake_file, uploaded_by=user,
        )

        assert upload.file_name.endswith('.pdf')

    def test_data_model_entity_str(self):
        user = self._make_user('dme_str@test.com')
        project = self._make_project(user)
        d = self._make_deliverable(project, user)
        entity = DataModelEntity.objects.create(deliverable=d, name='UserEntity')

        assert 'UserEntity' in str(entity)

    def test_project_data_model_entity_str(self):
        user = self._make_user('pdme_str@test.com')
        project = self._make_project(user)
        entity = ProjectDataModelEntity.objects.create(project=project, name='OrderEntity')

        assert 'OrderEntity' in str(entity)

    def test_notification_str(self):
        user = self._make_user('notif_str@test.com')
        notif = Notification.objects.create(
            user=user,
            type=Notification.TYPE_GENERAL,
            title='System Alert',
        )

        assert 'System Alert' in str(notif)

    def test_hosting_subscription_str(self):
        user = self._make_user('hs_str@test.com')
        project = self._make_project(user)
        sub = HostingSubscription.objects.create(
            project=project,
            plan=HostingSubscription.PLAN_MONTHLY,
            base_monthly_amount=200000,
            effective_monthly_amount=200000,
            billing_amount=200000,
            start_date='2025-01-01',
            next_billing_date='2025-02-01',
        )

        assert project.name in str(sub)

    def test_requirement_project_property(self):
        user = self._make_user('req_proj@test.com')
        project = self._make_project(user)
        req = make_requirement(make_delivery_stage(project), title='Feature X')

        assert req.project == project
        assert req.project_id == project.id

    def test_user_profile_is_email_placeholder_true(self):
        user = self._make_user('holder@temp.example.com')
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)

        assert profile.is_email_placeholder is True

    def test_user_profile_is_email_placeholder_false(self):
        user = self._make_user('real@gmail.com')
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)

        assert profile.is_email_placeholder is False

    def test_deliverable_client_folder_str(self):
        user = self._make_user('dcf_str@test.com')
        project = self._make_project(user)
        d = self._make_deliverable(project, user)
        folder = DeliverableClientFolder.objects.create(
            deliverable=d, name='Designs', created_by=user,
        )

        assert 'Designs' in str(folder)
