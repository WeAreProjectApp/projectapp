"""Tests for platform serializer validation and observable output contracts."""

from datetime import date, datetime
from datetime import timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from content.models.business_proposal import BusinessProposal
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from accounts.models import (
    BugComment,
    BugReport,
    ChangeRequest,
    ChangeRequestComment,
    Deliverable,
    DeliverableVersion,
    HostingSubscription,
    Payment,
    Project,
    ProjectPhase,
    UserProfile,
)
from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement


def _make_phase(project):
    bp = BusinessProposal.objects.create(title='P', client_name='c')
    return ProjectPhase.objects.create(project=project, business_proposal=bp, order=1)
from accounts.serializers import (
    BugReportDetailSerializer,
    BugReportListSerializer,
    ChangeRequestDetailSerializer,
    ChangeRequestListSerializer,
    ClientListSerializer,
    CompleteProfileSerializer,
    CreateAdminSerializer,
    CreateBugReportSerializer,
    CreateClientSerializer,
    CreateProjectSerializer,
    DeliverableClientUploadSerializer,
    DeliverableFileSerializer,
    DeliverableListSerializer,
    DeliverableVersionSerializer,
    EvaluateBugReportSerializer,
    HostingSubscriptionListSerializer,
    LoginSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    UpdateClientSerializer,
    UpdateProfileSerializer,
    UpdateProjectSerializer,
    UserProfileSerializer,
    VerifyOnboardingSerializer,
)

User = get_user_model()
factory = APIRequestFactory()


# =========================================================================
# LoginSerializer
# =========================================================================

class TestLoginSerializer:
    """Validate platform login credentials."""

    def test_valid_data_passes_validation(self):
        """Accept a valid input payload."""
        serializer = LoginSerializer(data={'email': 'a@b.com', 'password': 'secret'})

        assert serializer.is_valid() is True

    def test_missing_email_fails_validation(self):
        """Reject login data without an email address."""
        serializer = LoginSerializer(data={'password': 'secret'})

        assert serializer.is_valid() is False
        assert 'email' in serializer.errors

    def test_missing_password_fails_validation(self):
        """Reject login data without a password."""
        serializer = LoginSerializer(data={'email': 'a@b.com'})

        assert serializer.is_valid() is False
        assert 'password' in serializer.errors

    def test_invalid_email_format_fails_validation(self):
        """Reject a malformed login email address."""
        serializer = LoginSerializer(data={'email': 'not-an-email', 'password': 'x'})

        assert serializer.is_valid() is False
        assert 'email' in serializer.errors


# =========================================================================
# VerifyOnboardingSerializer
# =========================================================================

class TestVerifyOnboardingSerializer:
    """Validate onboarding verification codes and passwords."""

    def test_valid_data_passes_validation(self):
        """Accept a valid input payload."""
        serializer = VerifyOnboardingSerializer(
            data={'code': '123456', 'new_password': 'MySecure1!'},
        )

        assert serializer.is_valid() is True

    def test_code_too_short_fails_validation(self):
        """Reject an onboarding verification code below the required length."""
        serializer = VerifyOnboardingSerializer(
            data={'code': '123', 'new_password': 'MySecure1!'},
        )

        assert serializer.is_valid() is False
        assert 'code' in serializer.errors

    def test_password_too_short_fails_validation(self):
        """Reject an onboarding password below the required length."""
        serializer = VerifyOnboardingSerializer(
            data={'code': '123456', 'new_password': 'short'},
        )

        assert serializer.is_valid() is False
        assert 'new_password' in serializer.errors


# =========================================================================
# CompleteProfileSerializer
# =========================================================================

class TestCompleteProfileSerializer:
    """Validate required client profile details."""

    VALID_DATA = {
        'company_name': 'ACME Corp',
        'phone': '+57 300 111 2222',
        'cedula': '1234567890',
        'date_of_birth': '1990-05-15',
        'gender': 'male',
        'education_level': 'universitario',
    }

    def test_valid_data_passes_validation(self):
        """Accept a valid input payload."""
        serializer = CompleteProfileSerializer(data=self.VALID_DATA)

        assert serializer.is_valid() is True

    def test_missing_cedula_fails_validation(self):
        """Reject profile completion without an identity-document number."""
        data = {**self.VALID_DATA}
        del data['cedula']
        serializer = CompleteProfileSerializer(data=data)

        assert serializer.is_valid() is False
        assert 'cedula' in serializer.errors

    def test_blank_cedula_fails_custom_validation(self):
        """Reject a blank identity-document number."""
        data = {**self.VALID_DATA, 'cedula': '   '}
        serializer = CompleteProfileSerializer(data=data)

        assert serializer.is_valid() is False
        assert 'cedula' in serializer.errors

    def test_blank_phone_fails_custom_validation(self):
        """Reject a blank phone number."""
        data = {**self.VALID_DATA, 'phone': '   '}
        serializer = CompleteProfileSerializer(data=data)

        assert serializer.is_valid() is False
        assert 'phone' in serializer.errors

    def test_invalid_gender_choice_fails_validation(self):
        """Reject a gender value outside the supported choices."""
        data = {**self.VALID_DATA, 'gender': 'invalid_choice'}
        serializer = CompleteProfileSerializer(data=data)

        assert serializer.is_valid() is False
        assert 'gender' in serializer.errors

    def test_invalid_education_level_fails_validation(self):
        """Reject an education level outside the supported choices."""
        data = {**self.VALID_DATA, 'education_level': 'phd'}
        serializer = CompleteProfileSerializer(data=data)

        assert serializer.is_valid() is False
        assert 'education_level' in serializer.errors

    def test_avatar_is_optional(self):
        """Accept profile completion without an avatar."""
        serializer = CompleteProfileSerializer(data=self.VALID_DATA)

        assert serializer.is_valid() is True
        assert serializer.validated_data.get('avatar') is None


# =========================================================================
# CreateClientSerializer
# =========================================================================

@pytest.mark.django_db
class TestCreateClientSerializer:
    """Validate new client inputs and email normalization."""

    def test_valid_data_passes_validation(self):
        """Accept a valid input payload."""
        serializer = CreateClientSerializer(data={
            'email': 'new@client.com',
            'first_name': 'New',
            'last_name': 'Client',
        })

        assert serializer.is_valid() is True

    def test_duplicate_email_fails_validation(self):
        """Reject an email address already registered to an account."""
        User.objects.create_user(
            username='exist@test.com', email='exist@test.com', password='pass',
        )
        serializer = CreateClientSerializer(data={
            'email': 'exist@test.com',
            'first_name': 'A',
            'last_name': 'B',
        })

        assert serializer.is_valid() is False
        assert 'email' in serializer.errors

    def test_email_normalized_to_lowercase(self):
        """Normalize an account email address to lowercase."""
        serializer = CreateClientSerializer(data={
            'email': '  UPPER@Example.COM  ',
            'first_name': 'A',
            'last_name': 'B',
        })

        assert serializer.is_valid() is True
        assert serializer.validated_data['email'] == 'upper@example.com'


# =========================================================================
# UpdateClientSerializer
# =========================================================================

class TestUpdateClientSerializer:
    """Validate editable fields on existing client accounts."""

    def test_partial_update_with_single_field(self):
        """Accept a partial client update containing one supported field."""
        serializer = UpdateClientSerializer(data={'first_name': 'Updated'})

        assert serializer.is_valid() is True
        assert serializer.validated_data == {'first_name': 'Updated'}

    def test_is_active_boolean_field(self):
        """Accept the client activation flag as a boolean."""
        serializer = UpdateClientSerializer(data={'is_active': False})

        assert serializer.is_valid() is True
        assert serializer.validated_data['is_active'] is False


# =========================================================================
# UpdateProfileSerializer
# =========================================================================

class TestUpdateProfileSerializer:
    """Validate partial self-profile updates."""

    def test_valid_partial_update(self):
        """Accept a partial profile update."""
        serializer = UpdateProfileSerializer(data={
            'first_name': 'Updated',
            'gender': 'female',
        })

        assert serializer.is_valid() is True

    def test_invalid_gender_choice_fails(self):
        """Reject a gender value outside the supported choices."""
        serializer = UpdateProfileSerializer(data={'gender': 'xyz'})

        assert serializer.is_valid() is False
        assert 'gender' in serializer.errors

    def test_empty_payload_is_valid(self):
        """Accept an empty partial profile update."""
        serializer = UpdateProfileSerializer(data={})

        assert serializer.is_valid() is True


# =========================================================================
# CreateProjectSerializer
# =========================================================================

@pytest.mark.django_db
class TestCreateProjectSerializer:
    """Validate project creation inputs and tenant references."""

    @pytest.fixture
    def client_user(self):
        """Create the client profile used for project input validation."""
        user = User.objects.create_user(
            username='cli@test.com', email='cli@test.com', password='pass',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        return user

    def test_valid_data_passes_validation(self, client_user):
        """Accept a valid input payload."""
        serializer = CreateProjectSerializer(data={
            'name': 'Test Project',
            'client_id': client_user.id,
        })

        assert serializer.is_valid() is True

    def test_nonexistent_client_id_fails_validation(self):
        """Reject a project whose client account does not exist."""
        serializer = CreateProjectSerializer(data={
            'name': 'Test',
            'client_id': 99999,
        })

        assert serializer.is_valid() is False
        assert 'client_id' in serializer.errors

    def test_admin_as_client_fails_validation(self):
        """Reject an administrator account as a project client."""
        admin = User.objects.create_user(
            username='adm@test.com', email='adm@test.com', password='pass',
        )
        UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN)

        serializer = CreateProjectSerializer(data={
            'name': 'Test',
            'client_id': admin.id,
        })

        assert serializer.is_valid() is False
        assert 'client_id' in serializer.errors

    def test_status_is_not_a_writable_field(self, client_user):
        """Exclude project status from the writable serializer fields."""
        serializer = CreateProjectSerializer(data={
            'name': 'Test',
            'client_id': client_user.id,
        })

        assert 'status' not in serializer.fields

    def test_progress_out_of_range_fails_validation(self, client_user):
        """Reject project progress outside its allowed range."""
        serializer = CreateProjectSerializer(data={
            'name': 'Test',
            'client_id': client_user.id,
            'progress': 150,
        })

        assert serializer.is_valid() is False
        assert 'progress' in serializer.errors


# =========================================================================
# UpdateProjectSerializer
# =========================================================================

class TestUpdateProjectSerializer:
    """Validate the editable project fields."""

    def test_partial_update_valid(self):
        """Accept a partial project update."""
        serializer = UpdateProjectSerializer(data={'name': 'New Name'})

        assert serializer.is_valid() is True

    def test_status_is_not_a_writable_field(self):
        """Exclude project status from the writable serializer fields."""
        serializer = UpdateProjectSerializer(data={'name': 'New Name'})

        assert 'status' not in serializer.fields


# =========================================================================
# ClientListSerializer (ModelSerializer output)
# =========================================================================

@pytest.mark.django_db
class TestClientListSerializer:
    """Serialize client profile summaries and live aggregates."""

    def test_serializes_client_profile_correctly(self):
        """Expose the persisted client profile fields."""
        user = User.objects.create_user(
            username='cl@test.com', email='cl@test.com', password='pass',
            first_name='Carlos', last_name='López',
        )
        profile = UserProfile.objects.create(
            user=user, role=UserProfile.ROLE_CLIENT,
            company_name='Tech Corp', phone='+57 300',
            is_onboarded=True,
        )

        data = ClientListSerializer(profile).data

        assert data['email'] == 'cl@test.com'
        assert data['first_name'] == 'Carlos'
        assert data['last_name'] == 'López'
        assert data['company_name'] == 'Tech Corp'
        assert data['is_onboarded'] is True
        assert data['user_id'] == user.id

    def test_calculates_unprepared_aggregate_values(self):
        """Fails if detail serializers lose aggregate fallbacks outside prepared list queries."""
        user = User.objects.create_user(
            username='fallback-client@test.com', email='fallback-client@test.com', password='pass',
        )
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        active_project = Project.objects.create(
            name='Active', client=user, status=Project.STATUS_ACTIVE,
        )
        Project.objects.create(name='Archived', client=user, status=Project.STATUS_ARCHIVED)
        HostingSubscription.objects.create(
            project=active_project,
            plan=HostingSubscription.PLAN_QUARTERLY,
            base_monthly_amount=Decimal('100'),
            effective_monthly_amount=Decimal('100'),
            billing_amount=Decimal('300'),
            start_date=date(2026, 1, 1),
            next_billing_date=date(2026, 4, 1),
            status=HostingSubscription.STATUS_ACTIVE,
        )

        data = ClientListSerializer(profile).data

        assert data['hosting_plan'] == 'quarterly'
        assert data['active_projects_count'] == 1
        assert data['total_projects_count'] == 1


# =========================================================================
# ProjectListSerializer (ModelSerializer output)
# =========================================================================

@pytest.mark.django_db
class TestProjectListSerializer:
    """Serialize project summaries, client labels and detail aggregates."""

    def test_serializes_project_with_client_info(self):
        """Expose the project details with the associated client information."""
        user = User.objects.create_user(
            username='pj@test.com', email='pj@test.com', password='pass',
            first_name='Maria', last_name='García',
        )
        UserProfile.objects.create(
            user=user, role=UserProfile.ROLE_CLIENT, company_name='ACME',
        )
        project = Project.objects.create(
            name='Website Redesign', client=user, status=Project.STATUS_ACTIVE,
        )

        data = ProjectListSerializer(project).data

        assert data['name'] == 'Website Redesign'
        assert data['client_name'] == 'Maria García'
        assert data['client_email'] == 'pj@test.com'
        assert data['client_company'] == 'ACME'

    def test_client_name_falls_back_to_email(self):
        """Use the client email when the client has no display name."""
        user = User.objects.create_user(
            username='fb@test.com', email='fb@test.com', password='pass',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        project = Project.objects.create(name='P', client=user)

        data = ProjectListSerializer(project).data

        assert data['client_name'] == 'fb@test.com'

    def test_detail_calculates_unprepared_aggregate_values(self):
        """Fails if project detail serialization requires list-only annotations to return aggregates."""
        user = User.objects.create_user(
            username='fallback-project@test.com', email='fallback-project@test.com', password='pass',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        project = Project.objects.create(name='Fallback project', client=user)
        proposal = BusinessProposal.objects.create(
            title='Fallback proposal', client_name='Client', total_investment=Decimal('125.00'),
        )
        ProjectPhase.objects.create(project=project, business_proposal=proposal, order=1)
        BugReport.objects.create(
            project=project,
            reported_by=user,
            title='Open bug',
            description='x',
            status=BugReport.STATUS_REPORTED,
        )
        ChangeRequest.objects.create(
            project=project,
            created_by=user,
            title='Pending change',
            description='x',
            status=ChangeRequest.STATUS_PENDING,
        )
        HostingSubscription.objects.create(
            project=project,
            plan=HostingSubscription.PLAN_SEMIANNUAL,
            base_monthly_amount=Decimal('100'),
            effective_monthly_amount=Decimal('100'),
            billing_amount=Decimal('600'),
            start_date=date(2026, 1, 1),
            next_billing_date=date(2026, 7, 1),
            status=HostingSubscription.STATUS_ACTIVE,
        )

        data = ProjectDetailSerializer(project).data

        assert data['proposal_title'] == 'Fallback proposal'
        assert data['bugs_open_count'] == 1
        assert data['changes_pending_count'] == 1
        assert data['phases_total_amount'] == Decimal('125.00')
        assert data['next_hosting_payment'] == {
            'date': date(2026, 7, 1),
            'amount': Decimal('600.00'),
            'plan': 'semiannual',
        }


# =========================================================================
# UserProfileSerializer (output)
# =========================================================================

@pytest.mark.django_db
class TestUserProfileSerializer:
    """Serialize profile details and avatar links."""

    def test_serializes_full_profile_fields(self):
        """Expose the persisted account and profile details."""
        user = User.objects.create_user(
            username='ups@test.com', email='ups@test.com', password='pass',
            first_name='Laura', last_name='Ríos',
        )
        profile = UserProfile.objects.create(
            user=user, role=UserProfile.ROLE_CLIENT,
            company_name='LauraInc', phone='+57 300',
            is_onboarded=True, profile_completed=True,
            cedula='1234567890', gender='female',
            education_level='universitario',
        )
        request = factory.get('/')

        data = UserProfileSerializer(profile, context={'request': request}).data

        assert data['email'] == 'ups@test.com'
        assert data['first_name'] == 'Laura'
        assert data['last_name'] == 'Ríos'
        assert data['user_id'] == user.id
        assert data['role'] == 'client'
        assert data['company_name'] == 'LauraInc'
        assert data['is_onboarded'] is True
        assert data['profile_completed'] is True
        assert data['cedula'] == '1234567890'
        assert data['gender'] == 'female'
        assert data['education_level'] == 'universitario'

    def test_avatar_display_url_returns_empty_when_no_avatar(self):
        """Return an empty avatar link when the profile has no avatar."""
        user = User.objects.create_user(
            username='noav2@test.com', email='noav2@test.com', password='pass',
        )
        profile = UserProfile.objects.create(user=user)
        request = factory.get('/')

        data = UserProfileSerializer(profile, context={'request': request}).data

        assert data['avatar_display_url'] == ''

    def test_avatar_display_url_returns_absolute_url_for_avatar_url_field(self):
        """Keep the configured absolute avatar link unchanged."""
        user = User.objects.create_user(
            username='avurl@test.com', email='avurl@test.com', password='pass',
        )
        profile = UserProfile.objects.create(
            user=user, avatar_url='https://cdn.example.com/pic.jpg',
        )
        request = factory.get('/')

        data = UserProfileSerializer(profile, context={'request': request}).data

        assert data['avatar_display_url'] == 'https://cdn.example.com/pic.jpg'


# =========================================================================
# List serializer unannotated count fallbacks
# =========================================================================

@pytest.mark.django_db
class TestListSerializerAnnotatedCounts:
    """Preserve list counts when queryset annotations are absent."""

    def test_deliverable_list_serializer_falls_back_to_versions_count(self):
        """Fails if an unannotated deliverable loses its real version count."""
        user = User.objects.create_user(
            username='deliverable-count@test.com', email='deliverable-count@test.com', password='pass',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        project = Project.objects.create(name='Deliverable count project', client=user)
        deliverable = Deliverable.objects.create(
            project=project, uploaded_by=user, title='Versioned deliverable', category=Deliverable.CATEGORY_OTHER,
        )
        DeliverableVersion.objects.create(
            deliverable=deliverable, file='deliverables/versions/fallback.pdf', version_number=1, uploaded_by=user,
        )

        data = DeliverableListSerializer(deliverable).data

        assert data['versions_count'] == 1

    def test_change_request_list_serializer_falls_back_to_comments_count(self):
        """Fails if an unannotated change request omits internal comments from its count."""
        user = User.objects.create_user(
            username='change-count@test.com', email='change-count@test.com', password='pass',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        project = Project.objects.create(name='Change count project', client=user)
        change_request = ChangeRequest.objects.create(project=project, created_by=user, title='Count comments')
        ChangeRequestComment.objects.bulk_create([
            ChangeRequestComment(change_request=change_request, user=user, content='Public'),
            ChangeRequestComment(change_request=change_request, user=user, content='Internal', is_internal=True),
        ])

        data = ChangeRequestListSerializer(change_request).data

        assert data['comments_count'] == 2

    def test_bug_report_list_serializer_falls_back_to_comments_count(self):
        """Fails if an unannotated bug report omits internal comments from its count."""
        user = User.objects.create_user(
            username='bug-count@test.com', email='bug-count@test.com', password='pass',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        project = Project.objects.create(name='Bug count project', client=user)
        bug = BugReport.objects.create(project=project, reported_by=user, title='Count comments')
        BugComment.objects.bulk_create([
            BugComment(bug_report=bug, user=user, content='Public'),
            BugComment(bug_report=bug, user=user, content='Internal', is_internal=True),
        ])

        data = BugReportListSerializer(bug).data

        assert data['comments_count'] == 2


# =========================================================================
# HostingSubscriptionListSerializer.get_pending_payments
# =========================================================================

@pytest.mark.django_db
class TestHostingSubscriptionListSerializerPendingPayments:
    """Calculate pending payments for unannotated subscriptions."""

    def test_unannotated_subscription_serializer_uses_fallback(self):
        """Fails if direct subscription serialization loses the payment count fallback."""
        client = User.objects.create_user(
            username='subscription-serializer@test.com',
            email='subscription-serializer@test.com',
            password='pass',
        )
        UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT)
        project = Project.objects.create(name='Subscription serializer project', client=client)
        subscription = HostingSubscription(
            project=project,
            plan=HostingSubscription.PLAN_QUARTERLY,
            base_monthly_amount=Decimal('100000'),
            discount_percent=0,
            start_date=date(2026, 1, 1),
            next_billing_date=date(2026, 4, 1),
            status=HostingSubscription.STATUS_ACTIVE,
        )
        subscription.calculate_amounts()
        subscription.save()
        Payment.objects.create(
            subscription=subscription,
            amount=subscription.billing_amount,
            billing_period_start=date(2026, 1, 1),
            billing_period_end=date(2026, 1, 31),
            due_date=date(2026, 1, 22),
            status=Payment.STATUS_PENDING,
        )

        with patch(
            'django.utils.timezone.now',
            return_value=datetime(2026, 1, 15, tzinfo=datetime_timezone.utc),
        ):
            data = HostingSubscriptionListSerializer(subscription).data

        assert data['pending_payments'] == 1


# =========================================================================
# CreateAdminSerializer — duplicate email validation (line 127)
# =========================================================================

@pytest.mark.django_db
class TestCreateAdminSerializer:
    """Validate administrator email uniqueness and normalization."""

    def test_duplicate_email_fails_validation(self):
        """Reject an email address already registered to an account."""
        User.objects.create_user(
            username='addup@test.com', email='addup@test.com', password='pass',
        )
        serializer = CreateAdminSerializer(data={
            'email': 'addup@test.com',
            'first_name': 'A',
            'last_name': 'B',
        })

        assert serializer.is_valid() is False
        assert 'email' in serializer.errors

    def test_email_normalized_to_lowercase(self):
        """Normalize an account email address to lowercase."""
        serializer = CreateAdminSerializer(data={
            'email': '  NEWADMIN@TEST.COM  ',
            'first_name': 'A',
            'last_name': 'B',
        })

        assert serializer.is_valid() is True
        assert serializer.validated_data['email'] == 'newadmin@test.com'


# =========================================================================
# ClientListSerializer.get_avatar_display_url — relative URL with request (line 173)
# =========================================================================

@pytest.mark.django_db
class TestClientListSerializerAvatarUrl:
    """Resolve public avatar links in client summaries."""

    def test_avatar_display_url_builds_absolute_for_relative_url(self):
        """Expand a relative public avatar link against the request origin."""
        user = User.objects.create_user(
            username='avtest@test.com', email='avtest@test.com', password='pass',
        )
        profile = UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)

        with patch.object(
            type(profile), 'avatar_display_url',
            new_callable=PropertyMock,
            return_value='/media/avatars/pic.jpg',
        ):
            request = factory.get('/')
            data = ClientListSerializer(profile, context={'request': request}).data

        assert data['avatar_display_url'].startswith('http')


# =========================================================================
# CreateProjectSerializer.validate_proposal_id — already linked (line 272)
# =========================================================================

@pytest.mark.django_db
class TestCreateProjectSerializerProposalValidation:
    """Reject proposals already linked to delivery packages."""

    def test_proposal_already_linked_to_deliverable_fails(self):
        """Reject a proposal that is already attached to a delivery package."""
        from content.models import BusinessProposal

        client = User.objects.create_user(
            username='pvcli@test.com', email='pvcli@test.com', password='pass',
        )
        UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT)
        project = Project.objects.create(name='Linked', client=client)
        deliverable = Deliverable.objects.create(
            project=project, title='D',
            category=Deliverable.CATEGORY_OTHER,
            file=None, uploaded_by=client,
        )
        proposal = BusinessProposal.objects.create(
            title='Linked Proposal', client_name='Client',
            client_email='c@t.com', status='accepted',
            deliverable=deliverable,
        )

        serializer = CreateProjectSerializer(data={
            'name': 'New Project',
            'client_id': client.id,
            'proposal_id': proposal.id,
        })

        assert serializer.is_valid() is False
        assert 'proposal_id' in serializer.errors


# =========================================================================
# ChangeRequestListSerializer.get_screenshot_url (lines 441-443)
# ChangeRequestDetailSerializer.get_screenshot_url (lines 479-483)
# =========================================================================

class TestChangeRequestSerializerScreenshotUrl:
    """Serialize public screenshot links for change requests."""

    def test_list_serializer_returns_http_url_directly(self):
        """Keep an absolute public list screenshot link unchanged."""
        mock_obj = MagicMock()
        mock_obj.screenshot = MagicMock()
        mock_obj.screenshot.url = 'https://cdn.example.com/shot.png'

        s = ChangeRequestListSerializer()
        result = s.get_screenshot_url(mock_obj)

        assert result == 'https://cdn.example.com/shot.png'

    def test_list_serializer_returns_none_when_no_screenshot(self):
        """Return no list screenshot link when the screenshot is absent."""
        mock_obj = MagicMock()
        mock_obj.screenshot = None

        s = ChangeRequestListSerializer()
        result = s.get_screenshot_url(mock_obj)

        assert result is None

    def test_list_serializer_builds_absolute_with_request(self):
        """Expand a relative public list screenshot link against the request origin."""
        mock_obj = MagicMock()
        mock_obj.screenshot = MagicMock()
        mock_obj.screenshot.url = '/media/shot.png'

        request = factory.get('/')
        s = ChangeRequestListSerializer(context={'request': request})
        result = s.get_screenshot_url(mock_obj)

        assert result.startswith('http')

    def test_detail_serializer_returns_http_url_directly(self):
        """Keep an absolute public detail screenshot link unchanged."""
        mock_obj = MagicMock()
        mock_obj.screenshot = MagicMock()
        mock_obj.screenshot.url = 'https://cdn.example.com/shot.png'

        s = ChangeRequestDetailSerializer()
        result = s.get_screenshot_url(mock_obj)

        assert result == 'https://cdn.example.com/shot.png'

    def test_detail_serializer_returns_none_when_no_screenshot(self):
        """Return no detail screenshot link when the screenshot is absent."""
        mock_obj = MagicMock()
        mock_obj.screenshot = None

        s = ChangeRequestDetailSerializer()
        result = s.get_screenshot_url(mock_obj)

        assert result is None

    def test_detail_serializer_builds_absolute_with_request(self):
        """Expand a relative public detail screenshot link against the request origin."""
        mock_obj = MagicMock()
        mock_obj.screenshot = MagicMock()
        mock_obj.screenshot.url = '/media/shot.png'

        request = factory.get('/')
        s = ChangeRequestDetailSerializer(context={'request': request})
        result = s.get_screenshot_url(mock_obj)

        assert result.startswith('http')


# =========================================================================
# BugReportListSerializer.get_screenshot_url (lines 562-566)
# BugReportDetailSerializer.get_screenshot_url (lines 603-609)
# =========================================================================

class TestBugReportSerializerScreenshotUrl:
    """Serialize public screenshot links for issue reports."""

    def test_list_serializer_returns_http_url_directly(self):
        """Keep an absolute public list screenshot link unchanged."""
        mock_obj = MagicMock()
        mock_obj.screenshot = MagicMock()
        mock_obj.screenshot.url = 'https://cdn.example.com/bug.png'

        s = BugReportListSerializer()
        result = s.get_screenshot_url(mock_obj)

        assert result == 'https://cdn.example.com/bug.png'

    def test_list_serializer_returns_none_when_no_screenshot(self):
        """Return no list screenshot link when the screenshot is absent."""
        mock_obj = MagicMock()
        mock_obj.screenshot = None

        s = BugReportListSerializer()
        result = s.get_screenshot_url(mock_obj)

        assert result is None

    def test_list_serializer_builds_absolute_with_request(self):
        """Expand a relative public list screenshot link against the request origin."""
        mock_obj = MagicMock()
        mock_obj.screenshot = MagicMock()
        mock_obj.screenshot.url = '/media/bug.png'

        request = factory.get('/')
        s = BugReportListSerializer(context={'request': request})
        result = s.get_screenshot_url(mock_obj)

        assert result.startswith('http')

    def test_detail_serializer_returns_http_url_directly(self):
        """Keep an absolute public detail screenshot link unchanged."""
        mock_obj = MagicMock()
        mock_obj.screenshot = MagicMock()
        mock_obj.screenshot.url = 'https://cdn.example.com/bug.png'

        s = BugReportDetailSerializer()
        result = s.get_screenshot_url(mock_obj)

        assert result == 'https://cdn.example.com/bug.png'

    def test_detail_serializer_returns_none_when_no_screenshot(self):
        """Return no detail screenshot link when the screenshot is absent."""
        mock_obj = MagicMock()
        mock_obj.screenshot = None

        s = BugReportDetailSerializer()
        result = s.get_screenshot_url(mock_obj)

        assert result is None

    def test_detail_serializer_builds_absolute_with_request(self):
        """Expand a relative public detail screenshot link against the request origin."""
        mock_obj = MagicMock()
        mock_obj.screenshot = MagicMock()
        mock_obj.screenshot.url = '/media/bug.png'

        request = factory.get('/')
        s = BugReportDetailSerializer(context={'request': request})
        result = s.get_screenshot_url(mock_obj)

        assert result.startswith('http')


# =========================================================================
# CreateBugReportSerializer.validate_source_requirement_id
# =========================================================================

@pytest.mark.django_db
class TestCreateBugReportSerializerValidation:
    """Require a project-owned source for new issue reports."""

    def test_no_project_context_raises_validation_error(self):
        """Reject issue creation without its required project context."""
        serializer = CreateBugReportSerializer(
            data={'source_requirement_id': 1, 'title': 'Bug'},
            context={},  # no 'project' key
        )

        assert serializer.is_valid() is False
        assert 'source_requirement_id' in serializer.errors

    def test_source_requirement_not_in_project_fails(self):
        """Reject an issue source requirement belonging to another project."""
        client = User.objects.create_user(
            username='bugcli@test.com', email='bugcli@test.com', password='pass',
        )
        UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT)
        project = Project.objects.create(name='P', client=client)
        other_project = Project.objects.create(name='Other', client=client)
        other_phase = _make_phase(other_project)
        foreign_req = make_requirement(make_delivery_stage(other_phase.project), title='Foreign')

        serializer = CreateBugReportSerializer(
            data={'source_requirement_id': foreign_req.id, 'title': 'Bug'},
            context={'project': project, 'request': type('RequestContext', (), {'user': client})()},
        )

        assert serializer.is_valid() is False
        assert 'source_requirement_id' in serializer.errors


# =========================================================================
# EvaluateBugReportSerializer.validate — linked_bug not found (line 653),
# linked_bug archived (line 655)
# =========================================================================

@pytest.mark.django_db
class TestEvaluateBugReportSerializerValidation:
    """Validate links to existing, active project issue reports."""

    @pytest.fixture
    def project_with_bug(self):
        """Create a project and issue for linked-issue validation."""
        client = User.objects.create_user(
            username='evbug@test.com', email='evbug@test.com', password='pass',
        )
        UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT)
        project = Project.objects.create(name='P', client=client)
        bug = BugReport.objects.create(
            project=project, reported_by=client,
            title='Main bug', severity=BugReport.SEVERITY_MEDIUM,
        )
        return project, bug

    def test_nonexistent_linked_bug_fails(self, project_with_bug):
        """Reject a linked issue identifier that does not exist."""
        _, bug = project_with_bug
        serializer = EvaluateBugReportSerializer(
            data={'status': BugReport.STATUS_REPORTED, 'linked_bug_id': 99999},
            context={'bug': bug},
        )

        assert serializer.is_valid() is False
        assert 'linked_bug_id' in serializer.errors

    def test_archived_linked_bug_fails(self, project_with_bug):
        """Reject an archived issue as the linked issue."""
        project, bug = project_with_bug
        archived_bug = BugReport.objects.create(
            project=project, reported_by=bug.reported_by,
            title='Archived bug', severity=BugReport.SEVERITY_MEDIUM,
            is_archived=True,
        )
        serializer = EvaluateBugReportSerializer(
            data={'status': BugReport.STATUS_REPORTED, 'linked_bug_id': archived_bug.id},
            context={'bug': bug},
        )

        assert serializer.is_valid() is False
        assert 'linked_bug_id' in serializer.errors

    def test_valid_linked_bug_passes(self, project_with_bug):
        """Accept an active linked issue belonging to the same project."""
        project, bug = project_with_bug
        other_bug = BugReport.objects.create(
            project=project, reported_by=bug.reported_by,
            title='Other bug', severity=BugReport.SEVERITY_MEDIUM,
        )
        serializer = EvaluateBugReportSerializer(
            data={'status': BugReport.STATUS_REPORTED, 'linked_bug_id': other_bug.id},
            context={'bug': bug},
        )

        assert serializer.is_valid() is True


# =========================================================================
# DeliverableVersionSerializer.get_file_url (lines 701, 706)
# DeliverableListSerializer.get_file_url (lines 733, 738)
# DeliverableFileSerializer (lines 753-763)
# DeliverableClientUploadSerializer.get_file_url (lines 784-786)
# =========================================================================

class TestDeliverableSerializerFileUrls:
    """Serialize missing resource files and resource author labels."""

    def test_version_serializer_returns_none_when_no_file(self):
        """Return no version download link when the version file is absent."""
        mock_version = MagicMock()
        mock_version.file = None

        s = DeliverableVersionSerializer()
        result = s.get_file_url(mock_version)

        assert result is None



    def test_file_serializer_returns_none_when_no_file(self):
        """Return no attachment download link when the attachment file is absent."""
        mock_file = MagicMock()
        mock_file.file = None

        s = DeliverableFileSerializer()
        result = s.get_file_url(mock_file)

        assert result is None


    def test_file_serializer_get_uploaded_by_name(self):
        """Expose the resource author full name."""
        mock_file = MagicMock()
        mock_file.uploaded_by.first_name = 'Ana'
        mock_file.uploaded_by.last_name = 'García'
        mock_file.uploaded_by.email = 'ana@test.com'

        s = DeliverableFileSerializer()
        result = s.get_uploaded_by_name(mock_file)

        assert result == 'Ana García'

    def test_client_upload_serializer_returns_none_when_no_file(self):
        """Return no client-upload download link when its file is absent."""
        mock_upload = MagicMock()
        mock_upload.file = None

        s = DeliverableClientUploadSerializer()
        result = s.get_file_url(mock_upload)

        assert result is None
