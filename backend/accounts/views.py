import logging

logger = logging.getLogger(__name__)

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import connection, transaction
from django.db.models import Prefetch, prefetch_related_objects
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from projectapp.recaptcha import CaptchaError, verify_captcha

from accounts.models import UserProfile
from accounts.permissions import IsAdminRole
from accounts.serializers import (
    AdminListSerializer,
    ClientListSerializer,
    CompleteProfileSerializer,
    CreateAdminSerializer,
    CreateClientSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifyCodeSerializer,
    ProjectPhaseSerializer,
    ResendCodeSerializer,
    UpdateClientSerializer,
    UpdateProfileSerializer,
    UserProfileSerializer,
    VerifyOnboardingSerializer,
)
from accounts.services.impersonation import (
    ImpersonationError,
    build_impersonation_redirect_url,
    consume_exchange_code,
    create_exchange_code,
    impersonate,
)
from accounts.services.onboarding import create_admin, create_client, resend_invitation
from accounts.services.password_reset import (
    PasswordResetError,
    confirm_password_reset,
    request_password_reset,
    verify_reset_code,
)
from accounts.services.project_phases import (
    PhaseError,
    add_phase,
    list_phases,
    remove_phase,
    reorder_phases,
)
from accounts.services.proposal_client_service import update_client_profile
from accounts.services.tokens import get_tokens_for_user, get_verification_token_for_user
from accounts.services.verification import create_and_send_otp, validate_otp
from accounts.services.archive import (
    archive_record,
    bug_visible_for_request,
    change_request_visible_for_request,
    deliverable_visible_for_request,
    filter_bug_reports_for_list,
    filter_change_requests_for_list,
    filter_deliverables_for_list,
    filter_subscriptions_for_list,
    unarchive_record,
    wants_include_archived,
)

User = get_user_model()


# ==========================================================================
# Auth endpoints
# ==========================================================================

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    """
    Unified login for admin and client.
    - If user is onboarded → return JWT tokens.
    - If user is NOT onboarded → send OTP, return verification_token.
    """
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        verify_captcha(serializer.validated_data.get('recaptcha_token', ''))
    except CaptchaError as exc:
        return Response({'detail': exc.message, 'code': exc.code}, status=exc.status)

    email = serializer.validated_data['email'].lower().strip()
    password = serializer.validated_data['password']

    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response(
            {'detail': 'Credenciales incorrectas.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response(
            {'detail': 'Tu cuenta ha sido desactivada. Contacta al administrador.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    profile = getattr(user, 'profile', None)
    if profile is None:
        return Response(
            {'detail': 'Tu cuenta no tiene un perfil de plataforma configurado.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not profile.is_onboarded:
        create_and_send_otp(user)
        verification_token = get_verification_token_for_user(user)
        return Response({
            'requires_verification': True,
            'verification_token': verification_token,
            'email': user.email,
        })

    tokens = get_tokens_for_user(user)
    return Response({
        'requires_verification': False,
        'tokens': tokens,
        'user': UserProfileSerializer(profile, context={'request': request}).data,
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_view(request):
    """
    Step 2 of onboarding: verify OTP and set permanent password.
    The user is identified via the verification_token in the Authorization header.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return Response(
            {'detail': 'Token de verificación requerido.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token_str = auth_header.split(' ', 1)[1]

    try:
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token_str)
        user = jwt_auth.get_user(validated_token)
    except Exception:
        return Response(
            {'detail': 'Token de verificación inválido o expirado.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    serializer = VerifyOnboardingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    code = serializer.validated_data['code']
    new_password = serializer.validated_data['new_password']

    success, error_msg = validate_otp(user, code)
    if not success:
        return Response({'detail': error_msg}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save(update_fields=['password'])

    profile = user.profile
    was_onboarded = profile.is_onboarded
    profile.is_onboarded = True
    profile.save(update_fields=['is_onboarded'])

    # First-ever platform login (password just set): notify the team.
    if not was_onboarded:
        from accounts.tasks import notify_team_client_first_login_task

        notify_team_client_first_login_task(user.id)

    tokens = get_tokens_for_user(user)
    return Response({
        'tokens': tokens,
        'user': UserProfileSerializer(profile, context={'request': request}).data,
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def resend_code_view(request):
    """Resend the OTP code. User identified via verification_token."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return Response(
            {'detail': 'Token de verificación requerido.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token_str = auth_header.split(' ', 1)[1]

    try:
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token_str)
        user = jwt_auth.get_user(validated_token)
    except Exception:
        return Response(
            {'detail': 'Token de verificación inválido o expirado.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    create_and_send_otp(user)
    return Response({'detail': 'Código reenviado a tu email.'})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def token_refresh_view(request):
    """Refresh JWT access token."""
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response(
            {'detail': 'Refresh token requerido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        refresh = RefreshToken(refresh_token)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })
    except TokenError:
        return Response(
            {'detail': 'Refresh token inválido o expirado.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )


# ==========================================================================
# Password recovery — 3-step wizard
# ==========================================================================


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def password_reset_request_view(request):
    """Step 1: receives `{email}`, always responds 200 with a request token."""
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    token = request_password_reset(serializer.validated_data['email'])
    return Response({'reset_request_token': token})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def password_reset_verify_view(request):
    """Step 2: receives `{reset_request_token, code}` and returns a verified token."""
    serializer = PasswordResetVerifyCodeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        verified_token = verify_reset_code(
            serializer.validated_data['reset_request_token'],
            serializer.validated_data['code'],
        )
    except PasswordResetError as exc:
        body = {'detail': exc.code, **exc.extra}
        return Response(body, status=exc.http_status)
    return Response({'reset_verified_token': verified_token})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def password_reset_confirm_view(request):
    """Step 3: sets the new password and returns a fresh session."""
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        payload = confirm_password_reset(
            serializer.validated_data['reset_verified_token'],
            serializer.validated_data['new_password'],
        )
    except PasswordResetError as exc:
        body = {'detail': exc.code, **exc.extra}
        return Response(body, status=exc.http_status)
    return Response(payload)


# ==========================================================================
# Profile endpoints
# ==========================================================================

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """Get or update the authenticated user's profile."""
    profile = getattr(request.user, 'profile', None)
    if profile is None:
        return Response(
            {'detail': 'Perfil no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(UserProfileSerializer(profile, context={'request': request}).data)

    serializer = UpdateProfileSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    user = request.user
    if 'first_name' in data:
        user.first_name = data['first_name']
    if 'last_name' in data:
        user.last_name = data['last_name']
    user.save(update_fields=['first_name', 'last_name'])

    profile_fields = ['updated_at']
    for field in ('company_name', 'phone', 'cedula', 'date_of_birth', 'gender', 'education_level', 'theme_color', 'cover_image'):
        if field in data:
            setattr(profile, field, data[field])
            profile_fields.append(field)

    if 'avatar' in data and data['avatar'] is not None:
        profile.avatar = data['avatar']
        profile_fields.append('avatar')

    if 'custom_cover_image' in data and data['custom_cover_image'] is not None:
        profile.custom_cover_image = data['custom_cover_image']
        profile_fields.append('custom_cover_image')

    profile.save(update_fields=profile_fields)

    return Response(UserProfileSerializer(profile, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_profile_view(request):
    """Mandatory profile completion after first onboarding. Accepts multipart/form-data for avatar."""
    profile = getattr(request.user, 'profile', None)
    if profile is None:
        return Response(
            {'detail': 'Perfil no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if profile.profile_completed:
        return Response(
            {'detail': 'El perfil ya fue completado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = CompleteProfileSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    user = request.user
    if data.get('first_name'):
        user.first_name = data['first_name']
    if data.get('last_name'):
        user.last_name = data['last_name']
    user.save(update_fields=['first_name', 'last_name'])

    profile.company_name = data['company_name']
    profile.phone = data['phone']
    profile.cedula = data['cedula']
    profile.date_of_birth = data['date_of_birth']
    profile.gender = data['gender']
    profile.education_level = data['education_level']
    profile.profile_completed = True

    if data.get('avatar'):
        profile.avatar = data['avatar']

    profile.save()

    return Response(UserProfileSerializer(profile, context={'request': request}).data)


# ==========================================================================
# Admin — Client management
# ==========================================================================

def _client_list_profiles(queryset):
    """Prepare table aggregates without loading every client's related rows."""
    from django.db.models import Count, Max, OuterRef, Q, Subquery
    from accounts.models import HostingSubscription, Project

    active_subscription = HostingSubscription.objects.filter(
        project__client_id=OuterRef('user_id'),
        status=HostingSubscription.STATUS_ACTIVE,
    ).order_by('next_billing_date')
    profiles = list(queryset.annotate(
        _list_active_projects_count=Count(
            'user__projects', filter=Q(user__projects__status=Project.STATUS_ACTIVE),
        ),
        _list_total_projects_count=Count(
            'user__projects', filter=~Q(user__projects__status=Project.STATUS_ARCHIVED),
        ),
        _list_latest_project_update=Max('user__projects__updated_at'),
        _list_active_subscription_id=Subquery(active_subscription.values('pk')[:1]),
    ).order_by('-created_at'))
    subscription_ids = {
        profile._list_active_subscription_id for profile in profiles
        if profile._list_active_subscription_id is not None
    }
    subscriptions = {
        subscription.pk: subscription
        for subscription in HostingSubscription.objects.filter(pk__in=subscription_ids).only(
            'id', 'plan', 'next_billing_date', 'billing_amount',
        )
    } if subscription_ids else {}
    for profile in profiles:
        profile._list_active_subscription = subscriptions.get(profile._list_active_subscription_id)
    return profiles


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def client_list_view(request):
    """List all clients or create a new one."""
    if request.method == 'GET':
        filter_param = request.query_params.get('filter', 'all')
        qs = UserProfile.objects.clients()

        if filter_param == 'onboarded':
            qs = qs.filter(is_onboarded=True, user__is_active=True)
        elif filter_param == 'pending':
            qs = qs.filter(is_onboarded=False, user__is_active=True)
        elif filter_param == 'inactive':
            qs = qs.filter(user__is_active=False)

        serializer = ClientListSerializer(
            _client_list_profiles(qs), many=True, context={'request': request},
        )
        return Response(serializer.data)

    serializer = CreateClientSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        user, _ = create_client(
            email=serializer.validated_data['email'],
            first_name=serializer.validated_data['first_name'],
            last_name=serializer.validated_data['last_name'],
            company_name=serializer.validated_data.get('company_name', ''),
            phone=serializer.validated_data.get('phone', ''),
            created_by=request.user,
        )
    except ValueError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        ClientListSerializer(user.profile, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminRole])
def client_detail_view(request, user_id):
    """Get, update, or deactivate a client."""
    try:
        profiles = UserProfile.objects.clients().filter(user_id=user_id)
        if request.method == 'GET':
            loaded_profiles = _client_list_profiles(profiles)
            if not loaded_profiles:
                raise UserProfile.DoesNotExist
            profile = loaded_profiles[0]
        else:
            profile = profiles.get()
    except UserProfile.DoesNotExist:
        return Response(
            {'detail': 'Cliente no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(ClientListSerializer(profile, context={'request': request}).data)

    if request.method == 'DELETE':
        user = profile.user
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response({'detail': 'Cliente desactivado.'})

    serializer = UpdateClientSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    identity_kwargs = {}
    if 'first_name' in data or 'last_name' in data:
        first = data.get('first_name', profile.user.first_name)
        last = data.get('last_name', profile.user.last_name)
        identity_kwargs['name'] = f'{first} {last}'.strip()
    if 'company_name' in data:
        identity_kwargs['company'] = data['company_name']
    if 'phone' in data:
        identity_kwargs['phone'] = data['phone']

    if identity_kwargs:
        update_client_profile(profile, **identity_kwargs)

    billing_fields = []
    if 'nit' in data:
        profile.nit = data['nit'].strip()
        billing_fields.append('nit')
    if 'billing_code' in data:
        # Unique column with NULLs allowed: blank always normalizes to None.
        code = data['billing_code'] or None
        if code and (
            UserProfile.objects.exclude(pk=profile.pk)
            .filter(billing_code=code)
            .exists()
        ):
            return Response(
                {'detail': 'Ese código de facturación ya está en uso.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile.billing_code = code
        billing_fields.append('billing_code')
    if billing_fields:
        profile.save(update_fields=billing_fields)

    if 'is_active' in data:
        user = profile.user
        user.is_active = data['is_active']
        user.save(update_fields=['is_active'])

    profile.refresh_from_db()
    return Response(ClientListSerializer(profile, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def client_resend_invite_view(request, user_id):
    """Resend invitation email with a new temp password."""
    try:
        profile = UserProfile.objects.clients().get(user_id=user_id)
    except UserProfile.DoesNotExist:
        return Response(
            {'detail': 'Cliente no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    resend_invitation(profile.user)
    return Response({'detail': 'Invitación reenviada.'})


# ==========================================================================
# Super admin — Platform admin management (session auth + is_staff)
# ==========================================================================


def _require_staff(request):
    """Check that the request user is a Django staff member (super admin)."""
    if not request.user.is_staff:
        return Response(
            {'detail': 'No autorizado.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def admin_list_view(request):
    """List all platform admins or create a new one. Requires Django staff."""
    denied = _require_staff(request)
    if denied:
        return denied

    if request.method == 'GET':
        qs = UserProfile.objects.admins()

        filter_param = request.query_params.get('filter', 'all')
        if filter_param == 'active':
            qs = qs.filter(is_onboarded=True, user__is_active=True)
        elif filter_param == 'pending':
            qs = qs.filter(is_onboarded=False, user__is_active=True)
        elif filter_param == 'inactive':
            qs = qs.filter(user__is_active=False)

        serializer = AdminListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    serializer = CreateAdminSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        user, _ = create_admin(
            email=serializer.validated_data['email'],
            first_name=serializer.validated_data['first_name'],
            last_name=serializer.validated_data['last_name'],
            created_by=request.user,
        )
    except ValueError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        AdminListSerializer(user.profile, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def admin_detail_view(request, user_id):
    """Get, update, or deactivate a platform admin. Requires Django staff."""
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        profile = (
            UserProfile.objects
            .filter(role=UserProfile.ROLE_ADMIN, user_id=user_id)
            .select_related('user')
            .get()
        )
    except UserProfile.DoesNotExist:
        return Response(
            {'detail': 'Administrador no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(AdminListSerializer(profile, context={'request': request}).data)

    if request.method == 'DELETE':
        active_admin_count = (
            UserProfile.objects
            .filter(role=UserProfile.ROLE_ADMIN, user__is_active=True)
            .count()
        )
        if active_admin_count <= 1:
            return Response(
                {'detail': 'No se puede desactivar al último administrador activo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = profile.user
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response({'detail': 'Administrador desactivado.'})

    # PATCH
    data = request.data
    user = profile.user
    changed_fields = []

    if 'first_name' in data:
        user.first_name = data['first_name']
        changed_fields.append('first_name')
    if 'last_name' in data:
        user.last_name = data['last_name']
        changed_fields.append('last_name')
    if 'is_active' in data:
        if not data['is_active']:
            active_admin_count = (
                UserProfile.objects
                .filter(role=UserProfile.ROLE_ADMIN, user__is_active=True)
                .count()
            )
            if active_admin_count <= 1:
                return Response(
                    {'detail': 'No se puede desactivar al último administrador activo.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        user.is_active = data['is_active']
        changed_fields.append('is_active')

    if changed_fields:
        user.save(update_fields=changed_fields)

    return Response(AdminListSerializer(profile, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_resend_invite_view(request, user_id):
    """Resend admin invitation email with a new temp password. Requires Django staff."""
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        profile = (
            UserProfile.objects
            .filter(role=UserProfile.ROLE_ADMIN, user_id=user_id)
            .select_related('user')
            .get()
        )
    except UserProfile.DoesNotExist:
        return Response(
            {'detail': 'Administrador no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    resend_invitation(profile.user)
    return Response({'detail': 'Invitación reenviada.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_login_as_view(request, user_id):
    """Mint impersonation tokens for ``user_id`` and return the callback URL.

    Superuser-only is enforced by the shared impersonation service. The
    frontend opens ``redirect_url`` to establish the platform session.
    """
    User = get_user_model()
    try:
        target = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response(
            {'detail': 'Usuario no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        tokens = impersonate(request.user, target)
    except ImpersonationError as exc:
        return Response({'detail': exc.message}, status=exc.status_code)

    logger.info('admin %s logged in as user %s', request.user, target)
    code = create_exchange_code(tokens)
    return Response({'redirect_url': build_impersonation_redirect_url(code)})


@api_view(['POST'])
@permission_classes([AllowAny])
def impersonation_exchange_view(request):
    """Swap a single-use impersonation code for the JWT tokens.

    Called by the /platform/admin-login callback. The code itself is the
    bearer of trust (short-lived, single-use), so no prior auth is required.
    """
    tokens = consume_exchange_code(request.data.get('code'))
    if not tokens:
        return Response(
            {'detail': 'Código inválido o expirado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(tokens)


# ==========================================================================
# Projects
# ==========================================================================

from accounts.models import Project  # noqa: E402
from accounts.serializers import (  # noqa: E402
    CreateProjectSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    UpdateProjectSerializer,
)


def _project_list_projects(queryset):
    """Keep each aggregate independent and load only the selected proposals."""
    from django.db.models import Count, DecimalField, OuterRef, Subquery, Sum, Value
    from django.db.models.functions import Coalesce
    from accounts.models import BugReport, ChangeRequest, ProjectPhase
    from content.models import BusinessProposal

    open_bugs = BugReport.objects.filter(
        project_id=OuterRef('pk'),
        status__in=[
            BugReport.STATUS_REPORTED, BugReport.STATUS_CONFIRMED,
            BugReport.STATUS_FIXING, BugReport.STATUS_QA,
        ],
    ).order_by().values('project_id').annotate(total=Count('pk')).values('total')
    pending_changes = ChangeRequest.objects.filter(
        project_id=OuterRef('pk'), status=ChangeRequest.STATUS_PENDING,
    ).order_by().values('project_id').annotate(total=Count('pk')).values('total')
    phases = ProjectPhase.objects.filter(project_id=OuterRef('pk'))
    phase_totals = phases.order_by().values('project_id').annotate(
        total=Sum('business_proposal__total_investment'),
    ).values('total')
    first_phase_proposal = phases.order_by('order').values('business_proposal_id')[:1]
    legacy_proposal = BusinessProposal.objects.filter(
        deliverable__project_id=OuterRef('pk'),
    ).order_by('deliverable_id').values('pk')[:1]
    projects = list(queryset.select_related(
        'client', 'client__profile', 'current_state', 'hosting_subscription',
    ).only(
        'id', 'name', 'description', 'current_state_id', 'state_review_required',
        'progress', 'start_date', 'estimated_end_date', 'client_id',
        'hosting_start_date', 'created_at', 'updated_at',
        'client__id', 'client__first_name', 'client__last_name', 'client__email',
        'client__profile__id', 'client__profile__user_id', 'client__profile__company_name',
        'current_state__id', 'current_state__name', 'current_state__slug',
        'current_state__color', 'current_state__system_key', 'current_state__operational_effect',
        'hosting_subscription__id', 'hosting_subscription__project_id',
        'hosting_subscription__status', 'hosting_subscription__plan',
        'hosting_subscription__next_billing_date', 'hosting_subscription__billing_amount',
    ).annotate(
        _list_bugs_open_count=Coalesce(Subquery(open_bugs), Value(0)),
        _list_changes_pending_count=Coalesce(Subquery(pending_changes), Value(0)),
        _list_phases_total_amount=Coalesce(
            Subquery(phase_totals), Value(0),
            output_field=DecimalField(max_digits=20, decimal_places=2),
        ),
        _list_business_proposal_id=Coalesce(
            Subquery(first_phase_proposal), Subquery(legacy_proposal),
            output_field=BusinessProposal._meta.pk,
        ),
    ).order_by('-updated_at'))
    proposal_ids = {
        project._list_business_proposal_id for project in projects
        if project._list_business_proposal_id is not None
    }
    proposals = {
        proposal.pk: proposal
        for proposal in BusinessProposal.objects.filter(pk__in=proposal_ids).only('id', 'title')
    } if proposal_ids else {}
    for project in projects:
        project._list_business_proposal = proposals.get(project._list_business_proposal_id)
    return projects


def _project_detail_queryset(queryset):
    """Resolve scalar detail fields without multiplying independent relations."""
    from django.db.models import Count, Exists, OuterRef, Subquery, Value
    from django.db.models.functions import Coalesce
    from accounts.models import BugReport, ChangeRequest, ProjectAdminAccess
    from content.models import BusinessProposal

    open_bugs = BugReport.objects.filter(
        project_id=OuterRef('pk'),
        status__in=[
            BugReport.STATUS_REPORTED, BugReport.STATUS_CONFIRMED,
            BugReport.STATUS_FIXING, BugReport.STATUS_QA,
        ],
    ).order_by().values('project_id').annotate(total=Count('pk')).values('total')
    pending_changes = ChangeRequest.objects.filter(
        project_id=OuterRef('pk'), status=ChangeRequest.STATUS_PENDING,
    ).order_by().values('project_id').annotate(total=Count('pk')).values('total')
    legacy_proposals = BusinessProposal.objects.filter(
        deliverable__project_id=OuterRef('pk'),
    ).order_by('deliverable_id')
    admin_accesses = ProjectAdminAccess.objects.filter(
        project_id=OuterRef('pk'),
    ).exclude(admin_password_encrypted='')
    return queryset.select_related('hosting_subscription').annotate(
        _list_bugs_open_count=Coalesce(Subquery(open_bugs), Value(0)),
        _list_changes_pending_count=Coalesce(Subquery(pending_changes), Value(0)),
        _detail_legacy_proposal_id=Subquery(legacy_proposals.values('pk')[:1]),
        _detail_legacy_proposal_title=Subquery(legacy_proposals.values('title')[:1]),
        _detail_has_admin_access=Exists(admin_accesses),
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def project_list_view(request):
    """
    GET  — Admin sees all projects; client sees only their own.
    POST — Admin creates a project for a client.
    """
    profile = getattr(request.user, 'profile', None)

    if request.method == 'GET':
        if profile and profile.is_admin:
            qs = Project.objects.select_related(
                'client', 'client__profile', 'current_state',
            ).all()
            client_filter = request.query_params.get('client')
            if client_filter:
                qs = qs.filter(client_id=client_filter)
            status_filter = request.query_params.get('status')
            if status_filter:
                qs = qs.filter(status=status_filter)
        else:
            qs = Project.objects.select_related(
                'client', 'client__profile', 'current_state',
            ).filter(client=request.user)
        serializer = ProjectListSerializer(
            _project_list_projects(qs), many=True, context={'request': request},
        )
        return Response(serializer.data)

    if not profile or not profile.is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden crear proyectos.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if 'status' in request.data or 'state_id' in request.data:
        from content.api_errors import error_response

        return error_response(
            'Los proyectos nuevos empiezan En desarrollo; cambia el estado '
            'desde el flujo con vista previa del panel.',
            code='project_state_transition_required',
        )

    serializer = CreateProjectSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    proposal = None
    proposal_id = data.get('proposal_id')
    if proposal_id:
        from content.models import BusinessProposal
        proposal = BusinessProposal.objects.filter(id=proposal_id).first()

    # Extract proposal data before creating the project
    payment_milestones = []
    hosting_tiers = []
    if proposal:
        payment_milestones, hosting_tiers = _extract_proposal_financial_data(proposal)

    project = Project.objects.create(
        name=data['name'],
        description=data.get('description', ''),
        client_id=data['client_id'],
        status=data.get('status', Project.STATUS_DEVELOPMENT),
        progress=data.get('progress', 0),
        start_date=data.get('start_date'),
        estimated_end_date=data.get('estimated_end_date'),
        hosting_start_date=data.get('hosting_start_date'),
        payment_milestones=payment_milestones,
        hosting_tiers=hosting_tiers,
    )
    from content.services import project_service
    project_service.log_project_event(
        project, project_service.Action.CREATED, {}, request.user,
    )

    if proposal:
        from accounts.models import Deliverable, ProjectPhase

        d = Deliverable.objects.create(
            project=project,
            category=Deliverable.CATEGORY_DOCUMENTS,
            title=(proposal.title or 'Propuesta comercial')[:300],
            description='',
            file=None,
            uploaded_by=request.user,
        )
        proposal.deliverable = d
        proposal.save(update_fields=['deliverable_id'])
        ProjectPhase.objects.create(
            project=project,
            business_proposal=proposal,
            order=1,
            hosting_start_date=project.hosting_start_date,
        )

    from accounts.models import Notification
    from accounts.services.notifications import notify
    client = User.objects.get(id=data['client_id'])
    notify(
        user=client,
        type=Notification.TYPE_GENERAL,
        title=f'Nuevo proyecto: {project.name}',
        message=f'Se creó el proyecto "{project.name}" para ti. Ya puedes acceder desde tu plataforma.',
        project=project,
        related_object_type='project',
        related_object_id=project.id,
    )

    return Response(
        ProjectDetailSerializer(project, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def project_detail_view(request, project_id):
    """
    GET    — Admin or owning client can view.
    PATCH  — Admin only.
    DELETE — Deprecated: lifecycle transitions replace archive/delete.
    """
    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin

    queryset = Project.objects.select_related('client', 'client__profile', 'current_state')
    if request.method == 'GET':
        queryset = _project_detail_queryset(queryset)
    try:
        project = queryset.get(id=project_id)
    except Project.DoesNotExist:
        return Response({'detail': 'Proyecto no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not is_admin and project.client_id != request.user.id:
        return Response({'detail': 'No tienes acceso a este proyecto.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        return Response(ProjectDetailSerializer(project, context={'request': request}).data)

    if not is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden modificar proyectos.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    from content.api_errors import error_response
    from content.services import project_service

    if request.method == 'DELETE':
        return error_response(
            'Archivado fue reemplazado por el ciclo administrable del proyecto.',
            code='project_archive_replaced',
            hint='Usa Cambiar estado en la ficha comercial del proyecto.',
            status=status.HTTP_410_GONE,
        )

    if 'status' in request.data or 'state_id' in request.data:
        return error_response(
            'El estado requiere una vista previa de sus consecuencias.',
            code='project_state_transition_required',
            hint='Usa el flujo Cambiar estado en el panel.',
        )

    legacy_access_fields = {'admin_url', 'admin_username', 'admin_password'}
    if legacy_access_fields.intersection(request.data):
        return error_response(
            'Las credenciales se administran desde el detalle seguro del proyecto.',
            code='project_access_detail_required',
            hint='Abre Accesos y guarda cada ambiente por separado.',
        )

    serializer = UpdateProjectSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    snapshot = project_service.project_snapshot(project)
    update_fields = ['updated_at']
    simple_fields = (
        'name', 'description', 'progress',
        'start_date', 'estimated_end_date',
        'production_url', 'staging_url', 'repository_url',
    )
    for field in simple_fields:
        if field in data:
            setattr(project, field, data[field])
            update_fields.append(field)

    project.save(update_fields=update_fields)
    project_service.log_project_event(
        project, project_service.Action.UPDATED, snapshot, request.user,
    )

    return Response(ProjectDetailSerializer(project, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def project_access_list_view(request):
    """Deprecated admin summary without plaintext credentials."""
    from django.db.models import BooleanField, Case, Exists, OuterRef, Value, When
    from django.db.models.functions import Length

    from accounts.models import ProjectAdminAccess

    accesses_with_password = (
        ProjectAdminAccess.objects.filter(project_id=OuterRef('pk'))
        .alias(_password_length=Length('admin_password_encrypted'))
        .filter(_password_length__gt=0)
    )

    qs = (
        Project.objects.select_related(
            'client', 'client__profile', 'current_state',
        )
        .alias(_legacy_password_length=Length('admin_password_encrypted'))
        .annotate(_access_has_password=Case(
            When(_legacy_password_length__gt=0, then=Value(True)),
            default=Exists(accesses_with_password),
            output_field=BooleanField(),
        ))
        .only(
            'id', 'name', 'client_id', 'current_state_id',
            'production_url', 'staging_url', 'repository_url',
            'client__id', 'client__first_name', 'client__last_name', 'client__email',
            'client__profile__user_id', 'client__profile__company_name',
            'current_state__id', 'current_state__system_key',
            'current_state__slug', 'current_state__name',
        )
        .exclude(status=Project.STATUS_ARCHIVED)
        .exclude(current_state__operational_effect='decommissioned')
        .order_by('name')
    )

    data = []
    for p in qs:
        client = p.client
        client_name = f'{client.first_name} {client.last_name}'.strip() or client.email
        company = getattr(getattr(client, 'profile', None), 'company_name', '') or ''
        data.append({
            'id': p.id,
            'name': p.name,
            'status': (
                p.current_state.system_key or p.current_state.slug
                if p.current_state else None
            ),
            'status_label': (
                p.current_state.name if p.current_state else 'Sin clasificar'
            ),
            'client_id': client.id,
            'client_name': client_name,
            'client_email': client.email,
            'client_company': company,
            'production_url': p.production_url,
            'staging_url': p.staging_url,
            'repository_url': p.repository_url,
            'has_password': p._access_has_password,
        })

    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def deliverable_sync_technical_resources_view(request, project_id, deliverable_id):
    """Admin: mirror the proposal's resources and data model into the project."""
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    from accounts.models import Deliverable
    from accounts.services.technical_resources_sync import (
        sync_technical_resources_for_deliverable,
    )

    d = Deliverable.objects.filter(pk=deliverable_id, project=proj).first()
    if not d:
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if d.is_archived:
        return Response(
            {'detail': 'El entregable está archivado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = sync_technical_resources_for_deliverable(d, request.user)
    if not result.get('ok'):
        return Response(
            {'detail': result.get('detail', 'No se pudo sincronizar.')},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(result, status=status.HTTP_200_OK)


# ==========================================================================
# Published delivery requirement selectors
# ==========================================================================

from accounts.models import Requirement  # noqa: E402
from accounts.serializers import RequirementListSerializer, published_requirement_rows  # noqa: E402


def _get_project_or_403(request, project_id, *, related_fields=()):
    """Helper: get project checking access for admin or owning client."""
    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin
    projects = Project.objects.all()
    if related_fields:
        projects = projects.select_related(*related_fields)
    try:
        proj = projects.get(id=project_id)
    except Project.DoesNotExist:
        return None, Response({'detail': 'Proyecto no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not is_admin and proj.client_id != request.user.id:
        return None, Response({'detail': 'No tienes acceso a este proyecto.'}, status=status.HTTP_403_FORBIDDEN)
    return proj, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def requirement_list_view(request, project_id):
    """Read requirements visible in the contractual delivery hierarchy."""
    from accounts.services.delivery_workflow import visible_requirements

    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err
    stage_id = request.query_params.get('stage_id')
    phase_id = request.query_params.get('phase_id')
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_admin:
        qs = visible_requirements(proj.pk, request.user).select_related('stage__phase__scope')
        if stage_id:
            qs = qs.filter(stage_id=stage_id)
        if phase_id:
            qs = qs.filter(stage__phase_id=phase_id)
        return Response(RequirementListSerializer(qs.order_by('stage__order', 'order', 'id'), many=True).data)
    rows = published_requirement_rows(proj.pk, request.user)
    if stage_id:
        rows = [row for row in rows if str(row['stage_id']) == stage_id]
    if phase_id:
        rows = [row for row in rows if str(row['phase_id']) == phase_id]
    return Response(rows)


# ==========================================================================
# Change Requests
# ==========================================================================

from accounts.models import ChangeRequest, ChangeRequestComment  # noqa: E402
from accounts.services.notifications import notify_project_admins, notify_project_client  # noqa: E402
from accounts.serializers import (  # noqa: E402
    ChangeRequestCommentSerializer,
    ChangeRequestDetailSerializer,
    ChangeRequestListSerializer,
    CreateChangeRequestCommentSerializer,
    CreateChangeRequestSerializer,
    EvaluateChangeRequestSerializer,
)


_SOURCE_REQUIREMENT_LIST_FIELDS = (
    'source_requirement__id',
    'source_requirement__title',
    'source_requirement__review_status',
    'source_requirement__stage_id',
    'source_requirement__stage__id',
    'source_requirement__stage__title',
    'source_requirement__stage__phase_id',
    'source_requirement__stage__phase__id',
    'source_requirement__stage__phase__title',
    'source_requirement__stage__phase__scope_id',
    'source_requirement__stage__phase__scope__id',
    'source_requirement__stage__phase__scope__contract_id',
    'source_requirement__stage__phase__scope__contract__id',
    'source_requirement__stage__phase__scope__contract__project_id',
)


def _change_request_list_queryset(qs):
    """Load the list payload without per-row counts or proposal content."""
    from django.db.models import Count

    return (
        qs.select_related('created_by', 'project', 'source_requirement__stage__phase__scope')
        .only(
            'id', 'project_id', 'created_by_id', 'source_requirement_id',
            'title', 'description', 'module_or_screen', 'suggested_priority',
            'is_urgent', 'status', 'admin_response', 'estimated_cost', 'estimated_time',
            'linked_requirement_id', 'screenshot', 'is_archived', 'archived_at',
            'created_at', 'updated_at',
            'created_by__id', 'created_by__first_name', 'created_by__last_name',
            'created_by__email', 'project__id', 'project__name',
            *_SOURCE_REQUIREMENT_LIST_FIELDS,
        )
        .annotate(_comments_count=Count('comments'))
        .order_by('-created_at')
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def change_request_all_view(request):
    """
    GET — All change requests across all projects the user has access to.
    Admin sees all; client sees only their projects.
    """
    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin

    if is_admin:
        qs = ChangeRequest.objects.all()
    else:
        qs = ChangeRequest.objects.filter(project__client=request.user)

    qs = _change_request_list_queryset(qs)
    qs = filter_change_requests_for_list(qs, request, is_admin=is_admin)

    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    serializer = ChangeRequestListSerializer(qs, many=True, context={'request': request})

    data = serializer.data
    for item, cr in zip(data, qs):
        item['project_id'] = cr.project_id
        item['project_name'] = cr.project.name

    return Response(data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def change_request_list_view(request, project_id):
    """
    GET  — All change requests for a project (both roles, filtered by status optionally).
    POST — Both roles can create a change request.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin

    if request.method == 'GET':
        qs = _change_request_list_queryset(ChangeRequest.objects.filter(project=proj))
        qs = filter_change_requests_for_list(qs, request, is_admin=is_admin)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        phase_id_filter = request.query_params.get('phase_id')
        if phase_id_filter:
            qs = qs.filter(source_requirement__stage__phase_id=phase_id_filter)
        serializer = ChangeRequestListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    serializer = CreateChangeRequestSerializer(data=request.data, context={'project': proj, 'request': request})
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    cr = ChangeRequest(
        project=proj,
        created_by=request.user,
        title=data['title'],
        description=data.get('description', ''),
        module_or_screen=data.get('module_or_screen', ''),
        suggested_priority=data.get('suggested_priority', ChangeRequest.PRIORITY_MEDIUM),
        is_urgent=data.get('is_urgent', False),
    )
    if data.get('source_requirement_id'):
        cr.source_requirement_id = data['source_requirement_id']
    if data.get('screenshot'):
        cr.screenshot = data['screenshot']
    cr.save()

    if is_admin:
        notify_project_client(
            proj, Notification.TYPE_CR_CREATED, f'Nueva solicitud de cambio: {cr.title}',
            message=f'El equipo creó una solicitud de cambio en {proj.name}.',
            related_object_type='change_request', related_object_id=cr.id,
            exclude_user=request.user,
        )
    else:
        notify_project_admins(
            proj, Notification.TYPE_CR_CREATED, f'Nueva solicitud de cambio: {cr.title}',
            message=f'{request.user.first_name} creó una solicitud en {proj.name}.',
            related_object_type='change_request', related_object_id=cr.id,
            exclude_user=request.user,
        )

    return Response(
        ChangeRequestListSerializer(cr, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def change_request_detail_view(request, project_id, cr_id):
    """
    GET    — Detail with comments (both roles).
    DELETE — Admin only.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    if request.method == 'GET':
        change_requests = ChangeRequest.objects.select_related(
            'created_by', 'source_requirement__stage__phase__scope',
        ).only(
            'id', 'project_id', 'created_by_id', 'source_requirement_id',
            'title', 'description', 'module_or_screen', 'suggested_priority',
            'is_urgent', 'status', 'admin_response', 'estimated_cost', 'estimated_time',
            'linked_requirement_id', 'screenshot', 'is_archived', 'archived_at',
            'created_at', 'updated_at',
            'created_by__id', 'created_by__first_name', 'created_by__last_name',
            'created_by__email', *_SOURCE_REQUIREMENT_LIST_FIELDS,
        ).prefetch_related(
            Prefetch(
                'comments',
                queryset=ChangeRequestComment.objects.select_related('user'),
                to_attr='_detail_comments',
            ),
        )
    else:
        change_requests = ChangeRequest.objects.all()

    try:
        cr = change_requests.get(id=cr_id, project=proj)
    except ChangeRequest.DoesNotExist:
        return Response(
            {'detail': 'Solicitud de cambio no encontrada.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not change_request_visible_for_request(cr, request):
        return Response(
            {'detail': 'Solicitud de cambio no encontrada.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(
            ChangeRequestDetailSerializer(cr, context={'request': request}).data,
        )

    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden eliminar solicitudes de cambio.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    cr.updated_at = timezone.now()
    archive_record(cr, extra_update_fields=('updated_at',))
    return Response({'detail': 'Solicitud de cambio archivada.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_request_evaluate_view(request, project_id, cr_id):
    """
    Admin evaluates a change request: update status, admin_response, estimated_cost/time.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden evaluar solicitudes de cambio.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        cr = (
            ChangeRequest.objects
            .select_related('created_by', 'source_requirement__stage__phase__scope')
            .get(id=cr_id, project=proj)
        )
    except ChangeRequest.DoesNotExist:
        return Response(
            {'detail': 'Solicitud de cambio no encontrada.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = EvaluateChangeRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    upd_fields = ['updated_at']
    for field in ('status', 'admin_response', 'estimated_cost', 'estimated_time'):
        if field in data:
            setattr(cr, field, data[field])
            upd_fields.append(field)
    cr.save(update_fields=upd_fields)

    if 'status' in data:
        status_display = dict(ChangeRequest.STATUS_CHOICES).get(data['status'], data['status'])
        notify_project_client(
            proj, Notification.TYPE_CR_STATUS_CHANGED,
            f'Solicitud actualizada: {cr.title}',
            message=f'Estado cambiado a "{status_display}".',
            related_object_type='change_request', related_object_id=cr.id,
            exclude_user=request.user,
        )

    return Response(
        ChangeRequestDetailSerializer(cr, context={'request': request}).data,
    )


def _bulk_evaluation_ids(items, model):
    """Select possible integer keys without changing each item's dict lookup."""
    minimum, maximum = connection.ops.integer_field_range(model._meta.pk.get_internal_type())
    candidate_ids = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_id = item.get('id')
        # Python dicts match bools and integral floats to integer keys, but
        # never coerce strings or truncate fractional numbers like the ORM can.
        if isinstance(raw_id, int):
            candidate_id = raw_id
        elif isinstance(raw_id, float) and raw_id.is_integer():
            candidate_id = int(raw_id)
        else:
            continue
        if minimum is not None and candidate_id < minimum:
            continue
        if maximum is not None and candidate_id > maximum:
            continue
        candidate_ids.add(candidate_id)
    return candidate_ids


@transaction.non_atomic_requests
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_request_bulk_evaluate_view(request, project_id):
    """
    Admin bulk-evaluates change requests of a project.
    Body: array of {id, status?, admin_response?, estimated_time?, estimated_cost?}.
    Each item is applied independently via the same EvaluateChangeRequestSerializer.
    Items with unknown id or that don't belong to the project are skipped.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden evaluar solicitudes de cambio.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    items = request.data
    if not isinstance(items, list):
        return Response(
            {'detail': 'Se espera un array JSON de evaluaciones.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(items) > 500:
        return Response(
            {'detail': 'Máximo 500 evaluaciones por carga.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    project_crs = {
        cr.id: cr for cr in ChangeRequest.objects.filter(
            project=proj, id__in=_bulk_evaluation_ids(items, ChangeRequest),
        )
    }

    updated_ids = []
    errors = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append({'index': idx, 'detail': 'Item no es un objeto.'})
            continue
        cr_id = item.get('id')
        if cr_id is None:
            errors.append({'index': idx, 'detail': 'Falta el campo id.'})
            continue
        cr = project_crs.get(cr_id)
        if cr is None:
            errors.append({'index': idx, 'id': cr_id, 'detail': 'No encontrada en el proyecto.'})
            continue

        payload = {
            k: v for k, v in item.items()
            if k in ('status', 'admin_response', 'estimated_time', 'estimated_cost')
        }
        if not payload:
            continue

        serializer = EvaluateChangeRequestSerializer(data=payload, partial=True)
        if not serializer.is_valid():
            errors.append({'index': idx, 'id': cr_id, 'detail': serializer.errors})
            continue

        data = serializer.validated_data
        upd_fields = ['updated_at']
        new_status = data.get('status')
        for field in ('status', 'admin_response', 'estimated_cost', 'estimated_time'):
            if field in data:
                setattr(cr, field, data[field])
                upd_fields.append(field)
        cr.save(update_fields=upd_fields)
        updated_ids.append(cr.id)

        if new_status is not None:
            status_display = dict(ChangeRequest.STATUS_CHOICES).get(new_status, new_status)
            notify_project_client(
                proj, Notification.TYPE_CR_STATUS_CHANGED,
                f'Solicitud actualizada: {cr.title}',
                message=f'Estado cambiado a "{status_display}".',
                related_object_type='change_request', related_object_id=cr.id,
                exclude_user=request.user,
            )

    return Response({
        'updated': len(updated_ids),
        'updated_ids': updated_ids,
        'errors': errors,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_request_comment_view(request, project_id, cr_id):
    """Add a comment to a change request. Both roles can comment."""
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        cr = ChangeRequest.objects.get(id=cr_id, project=proj)
    except ChangeRequest.DoesNotExist:
        return Response(
            {'detail': 'Solicitud de cambio no encontrada.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not change_request_visible_for_request(cr, request):
        return Response(
            {'detail': 'Solicitud de cambio no encontrada.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = CreateChangeRequestCommentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin
    is_internal = data.get('is_internal', False) and is_admin

    comment = ChangeRequestComment.objects.create(
        change_request=cr,
        user=request.user,
        content=data['content'],
        is_internal=is_internal,
    )

    return Response(
        ChangeRequestCommentSerializer(comment).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def change_request_convert_view(request, project_id, cr_id):
    """Convert an approved request to a new draft guide in an explicit editable stage."""
    from accounts.services.delivery_workflow import mutate_node
    from rest_framework import serializers as drf_serializers

    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    class ConversionSerializer(drf_serializers.Serializer):
        stage_id = drf_serializers.IntegerField(min_value=1)
        expected_version = drf_serializers.IntegerField(min_value=0)

    serializer = ConversionSerializer(data=request.data)
    with transaction.atomic():
        try:
            cr = ChangeRequest.objects.select_for_update().get(id=cr_id, project=proj)
        except ChangeRequest.DoesNotExist:
            return Response({'detail': 'Solicitud de cambio no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if cr.is_archived or cr.status != ChangeRequest.STATUS_APPROVED:
            return Response({'detail': 'Solo se pueden convertir solicitudes aprobadas y activas.'}, status=status.HTTP_400_BAD_REQUEST)
        if cr.linked_requirement_id is not None:
            return Response({'detail': 'Esta solicitud ya fue convertida en un requerimiento.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer.is_valid(raise_exception=True)
        node = mutate_node(proj.pk, request.user, 'requirements', {
            **serializer.validated_data,
            'key': f'change-request-{cr.pk}',
            'title': cr.title,
            'description': cr.description,
            'guide': {},
        })
        # Authoring a draft never records acceptance of the resulting guide.
        cr.linked_requirement_id = node['result']['id']
        cr.save(update_fields=['linked_requirement', 'updated_at'])
    return Response(ChangeRequestDetailSerializer(cr, context={'request': request}).data, status=status.HTTP_201_CREATED)


# ==========================================================================
# Bug Reports
# ==========================================================================

from accounts.models import BugReport, BugComment  # noqa: E402
from accounts.serializers import (  # noqa: E402
    BugCommentSerializer,
    BugReportDetailSerializer,
    BugReportListSerializer,
    CreateBugCommentSerializer,
    CreateBugReportSerializer,
    EvaluateBugReportSerializer,
)


def _bug_report_list_queryset(qs):
    """Load the list payload while keeping optional source relations nullable."""
    from django.db.models import Count

    return (
        qs.select_related('reported_by', 'project', 'source_requirement__stage__phase__scope')
        .only(
            'id', 'project_id', 'reported_by_id', 'source_requirement_id',
            'title', 'description', 'severity', 'status', 'environment', 'device_browser',
            'is_recurring', 'steps_to_reproduce', 'expected_behavior', 'actual_behavior',
            'admin_response', 'linked_bug_id', 'screenshot', 'is_archived', 'archived_at',
            'created_at', 'updated_at',
            'reported_by__id', 'reported_by__first_name', 'reported_by__last_name',
            'reported_by__email', 'project__id', 'project__name',
            *_SOURCE_REQUIREMENT_LIST_FIELDS,
        )
        .annotate(_comments_count=Count('comments'))
        .order_by('-created_at')
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bug_report_all_view(request):
    """
    GET — All bug reports across all projects the user has access to.
    Admin sees all; client sees only their projects.
    """
    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin

    if is_admin:
        qs = BugReport.objects.all()
    else:
        qs = BugReport.objects.filter(project__client=request.user)

    qs = _bug_report_list_queryset(qs)
    qs = filter_bug_reports_for_list(qs, request, is_admin=is_admin)

    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    severity_filter = request.query_params.get('severity')
    if severity_filter:
        qs = qs.filter(severity=severity_filter)

    serializer = BugReportListSerializer(qs, many=True, context={'request': request})

    data = serializer.data
    for item, bug in zip(data, qs):
        item['project_id'] = bug.project_id
        item['project_name'] = bug.project.name if bug.project else ''

    return Response(data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def bug_report_list_view(request, project_id):
    """
    GET  — All bug reports for a project (both roles, filtered optionally).
    POST — Both roles can report a bug.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin

    if request.method == 'GET':
        qs = _bug_report_list_queryset(BugReport.objects.filter(project=proj))
        qs = filter_bug_reports_for_list(qs, request, is_admin=is_admin)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        severity_filter = request.query_params.get('severity')
        if severity_filter:
            qs = qs.filter(severity=severity_filter)
        phase_id_filter = request.query_params.get('phase_id')
        if phase_id_filter:
            qs = qs.filter(source_requirement__stage__phase_id=phase_id_filter)
        serializer = BugReportListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    serializer = CreateBugReportSerializer(data=request.data, context={'project': proj, 'request': request})
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    bug = BugReport(
        project=proj,
        reported_by=request.user,
        title=data['title'],
        description=data.get('description', ''),
        severity=data.get('severity', BugReport.SEVERITY_MEDIUM),
        steps_to_reproduce=data.get('steps_to_reproduce', []),
        expected_behavior=data.get('expected_behavior', ''),
        actual_behavior=data.get('actual_behavior', ''),
        environment=data.get('environment', BugReport.ENV_PRODUCTION),
        device_browser=data.get('device_browser', ''),
        is_recurring=data.get('is_recurring', False),
    )
    bug.source_requirement_id = data['source_requirement_id']
    if data.get('screenshot'):
        bug.screenshot = data['screenshot']
    bug.save()

    if is_admin:
        notify_project_client(
            proj, Notification.TYPE_BUG_REPORTED, f'Bug reportado: {bug.title}',
            message=f'El equipo reportó un bug en {proj.name}.',
            related_object_type='bug_report', related_object_id=bug.id,
            exclude_user=request.user,
        )
    else:
        notify_project_admins(
            proj, Notification.TYPE_BUG_REPORTED, f'Bug reportado: {bug.title}',
            message=f'{request.user.first_name} reportó un bug en {proj.name}.',
            related_object_type='bug_report', related_object_id=bug.id,
            exclude_user=request.user,
        )

    return Response(
        BugReportListSerializer(bug, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def bug_report_detail_view(request, project_id, bug_id):
    """
    GET    — Detail with comments (both roles).
    DELETE — Admin only.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    if request.method == 'GET':
        bugs = BugReport.objects.select_related(
            'reported_by', 'source_requirement__stage__phase__scope',
        ).only(
            'id', 'project_id', 'reported_by_id', 'source_requirement_id',
            'title', 'description', 'severity', 'status', 'environment',
            'device_browser', 'is_recurring', 'steps_to_reproduce',
            'expected_behavior', 'actual_behavior', 'admin_response',
            'linked_bug_id', 'screenshot', 'is_archived', 'archived_at',
            'created_at', 'updated_at',
            'reported_by__id', 'reported_by__first_name', 'reported_by__last_name',
            'reported_by__email', *_SOURCE_REQUIREMENT_LIST_FIELDS,
        ).prefetch_related(
            Prefetch(
                'comments',
                queryset=BugComment.objects.select_related('user'),
                to_attr='_detail_comments',
            ),
        )
    else:
        bugs = BugReport.objects.all()

    try:
        bug = bugs.get(id=bug_id, project=proj)
    except BugReport.DoesNotExist:
        return Response(
            {'detail': 'Bug no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not bug_visible_for_request(bug, request):
        return Response(
            {'detail': 'Bug no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(
            BugReportDetailSerializer(bug, context={'request': request}).data,
        )

    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden eliminar reportes de bugs.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    bug.updated_at = timezone.now()
    archive_record(bug, extra_update_fields=('updated_at',))
    return Response({'detail': 'Reporte de bug archivado.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bug_report_evaluate_view(request, project_id, bug_id):
    """
    Admin evaluates a bug report: update status, admin_response, linked_bug.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden evaluar reportes de bugs.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        bug = (
            BugReport.objects
            .select_related('reported_by', 'source_requirement__stage__phase__scope')
            .get(id=bug_id, project=proj)
        )
    except BugReport.DoesNotExist:
        return Response(
            {'detail': 'Bug no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = EvaluateBugReportSerializer(data=request.data, context={'bug': bug})
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    upd_fields = ['updated_at']
    for field in ('status', 'admin_response'):
        if field in data:
            setattr(bug, field, data[field])
            upd_fields.append(field)
    if 'linked_bug_id' in data:
        bug.linked_bug_id = data['linked_bug_id']
        upd_fields.append('linked_bug_id')
    bug.save(update_fields=upd_fields)

    if 'status' in data:
        status_display = dict(BugReport.STATUS_CHOICES).get(data['status'], data['status'])
        notify_project_client(
            proj, Notification.TYPE_BUG_STATUS_CHANGED,
            f'Bug actualizado: {bug.title}',
            message=f'Estado cambiado a "{status_display}".',
            related_object_type='bug_report', related_object_id=bug.id,
            exclude_user=request.user,
        )

    return Response(
        BugReportDetailSerializer(bug, context={'request': request}).data,
    )


@transaction.non_atomic_requests
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bug_report_bulk_evaluate_view(request, project_id):
    """
    Admin bulk-evaluates bug reports of a project.
    Body: array of {id, status?, admin_response?, linked_bug_id?}.
    Each item is applied independently via EvaluateBugReportSerializer (partial).
    Items with unknown id or that don't belong to the project are skipped.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden evaluar reportes de bugs.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    items = request.data
    if not isinstance(items, list):
        return Response(
            {'detail': 'Se espera un array JSON de evaluaciones.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(items) > 500:
        return Response(
            {'detail': 'Máximo 500 evaluaciones por carga.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    project_bugs = {
        b.id: b for b in BugReport.objects.filter(
            project=proj, id__in=_bulk_evaluation_ids(items, BugReport),
        )
    }

    updated_ids = []
    errors = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append({'index': idx, 'detail': 'Item no es un objeto.'})
            continue
        bug_id = item.get('id')
        if bug_id is None:
            errors.append({'index': idx, 'detail': 'Falta el campo id.'})
            continue
        bug = project_bugs.get(bug_id)
        if bug is None:
            errors.append({'index': idx, 'id': bug_id, 'detail': 'No encontrado en el proyecto.'})
            continue

        payload = {
            k: v for k, v in item.items()
            if k in ('status', 'admin_response', 'linked_bug_id')
        }
        if not payload:
            continue

        serializer = EvaluateBugReportSerializer(data=payload, context={'bug': bug}, partial=True)
        if not serializer.is_valid():
            errors.append({'index': idx, 'id': bug_id, 'detail': serializer.errors})
            continue

        data = serializer.validated_data
        upd_fields = ['updated_at']
        new_status = data.get('status')
        for field in ('status', 'admin_response'):
            if field in data:
                setattr(bug, field, data[field])
                upd_fields.append(field)
        if 'linked_bug_id' in data:
            bug.linked_bug_id = data['linked_bug_id']
            upd_fields.append('linked_bug_id')
        bug.save(update_fields=upd_fields)
        updated_ids.append(bug.id)

        if new_status is not None:
            status_display = dict(BugReport.STATUS_CHOICES).get(new_status, new_status)
            notify_project_client(
                proj, Notification.TYPE_BUG_STATUS_CHANGED,
                f'Bug actualizado: {bug.title}',
                message=f'Estado cambiado a "{status_display}".',
                related_object_type='bug_report', related_object_id=bug.id,
                exclude_user=request.user,
            )

    return Response({
        'updated': len(updated_ids),
        'updated_ids': updated_ids,
        'errors': errors,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bug_report_comment_view(request, project_id, bug_id):
    """Add a comment to a bug report. Both roles can comment."""
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        bug = BugReport.objects.get(id=bug_id, project=proj)
    except BugReport.DoesNotExist:
        return Response(
            {'detail': 'Bug no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not bug_visible_for_request(bug, request):
        return Response(
            {'detail': 'Bug no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = CreateBugCommentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin
    is_internal = data.get('is_internal', False) and is_admin

    comment = BugComment.objects.create(
        bug_report=bug,
        user=request.user,
        content=data['content'],
        is_internal=is_internal,
    )

    return Response(
        BugCommentSerializer(comment).data,
        status=status.HTTP_201_CREATED,
    )


# ==========================================================================
# Deliverables
# ==========================================================================

from accounts.models import Deliverable, DeliverableVersion  # noqa: E402
from accounts.serializers import (  # noqa: E402
    CreateDeliverableSerializer,
    DeliverableDetailSerializer,
    DeliverableListSerializer,
    UpdateDeliverableSerializer,
    UploadNewVersionSerializer,
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def deliverable_all_view(request):
    """
    GET — All deliverables across all projects the user has access to.
    Admin sees all; client sees only their projects.
    """
    from django.db.models import Count

    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin

    if is_admin:
        qs = Deliverable.objects.select_related('uploaded_by', 'project').all()
    else:
        qs = Deliverable.objects.select_related('uploaded_by', 'project').filter(
            project__client=request.user,
        )

    qs = filter_deliverables_for_list(qs, request, is_admin=is_admin)
    qs = qs.annotate(_versions_count=Count('versions')).order_by('category', '-updated_at')

    category_filter = request.query_params.get('category')
    if category_filter:
        qs = qs.filter(category=category_filter)

    serializer = DeliverableListSerializer(qs, many=True, context={'request': request})

    data = serializer.data
    for item, d in zip(data, qs):
        item['project_id'] = d.project_id
        item['project_name'] = d.project.name

    return Response(data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def deliverable_list_view(request, project_id):
    """
    GET  — All deliverables for a project (both roles, filtered by category optionally).
    POST — Admin uploads a new deliverable.
    """
    from django.db.models import Count

    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin

    if request.method == 'GET':
        qs = (
            Deliverable.objects.filter(project=proj)
            .select_related('uploaded_by')
            .annotate(_versions_count=Count('versions'))
            .order_by('category', '-updated_at')
        )
        qs = filter_deliverables_for_list(qs, request, is_admin=is_admin)
        category_filter = request.query_params.get('category')
        if category_filter:
            qs = qs.filter(category=category_filter)
        serializer = DeliverableListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    serializer = CreateDeliverableSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    category = data.get('category', Deliverable.CATEGORY_OTHER)
    if not is_admin and category in Deliverable.ADMIN_ONLY_CATEGORIES:
        return Response(
            {'detail': 'Esta categoría solo puede ser subida por el administrador.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    upload_file = data.get('file')
    deliverable = Deliverable.objects.create(
        project=proj,
        uploaded_by=request.user,
        title=data['title'],
        description=data.get('description', ''),
        category=category,
        file=upload_file,
        current_version=1 if upload_file else 0,
    )

    if upload_file:
        DeliverableVersion.objects.create(
            deliverable=deliverable,
            file=upload_file,
            version_number=1,
            uploaded_by=request.user,
        )
        notify_project_client(
            proj, Notification.TYPE_DELIVERABLE_UPLOADED,
            f'Nuevo entregable: {deliverable.title}',
            message=f'Se subió un archivo en {proj.name}.',
            related_object_type='deliverable', related_object_id=deliverable.id,
            exclude_user=request.user,
            deliverable=deliverable,
        )

    return Response(
        DeliverableListSerializer(deliverable, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def deliverable_detail_view(request, project_id, deliverable_id):
    """
    GET    — Detail with version history (both roles).
    PATCH  — Admin updates metadata (title, description, category).
    DELETE — Admin only.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    queryset = Deliverable.objects.select_related('business_proposal')
    if request.method == 'GET':
        queryset = queryset.select_related('uploaded_by').only(
            'id', 'project_id', 'category', 'title', 'description',
            'source_epic_key', 'source_epic_title', 'file', 'current_version',
            'uploaded_by_id', 'is_archived', 'archived_at', 'created_at', 'updated_at',
            'uploaded_by__id', 'uploaded_by__first_name', 'uploaded_by__last_name',
            'uploaded_by__email', 'business_proposal__id', 'business_proposal__title',
        )
    try:
        deliverable = queryset.get(id=deliverable_id, project=proj)
    except Deliverable.DoesNotExist:
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        if not deliverable_visible_for_request(deliverable, request):
            return Response(
                {'detail': 'Entregable no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        deliverable._detail_versions = list(
            deliverable.versions.select_related('uploaded_by').all(),
        )
        return Response(
            DeliverableDetailSerializer(deliverable, context={'request': request}).data,
        )

    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden modificar entregables.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'DELETE':
        deliverable.updated_at = timezone.now()
        archive_record(deliverable, extra_update_fields=('updated_at',))
        return Response({'detail': 'Entregable archivado.'})

    serializer = UpdateDeliverableSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)

    if 'is_archived' in data:
        flag = data.pop('is_archived')
        deliverable.updated_at = timezone.now()
        if flag:
            archive_record(deliverable, extra_update_fields=('updated_at',))
        else:
            unarchive_record(deliverable, extra_update_fields=('updated_at',))

    upd_fields = ['updated_at']
    for field in ('title', 'description', 'category'):
        if field in data:
            setattr(deliverable, field, data[field])
            upd_fields.append(field)
    if len(upd_fields) > 1:
        deliverable.save(update_fields=upd_fields)

    deliverable._detail_versions = list(
        deliverable.versions.select_related('uploaded_by').all(),
    )
    return Response(
        DeliverableDetailSerializer(deliverable, context={'request': request}).data,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deliverable_upload_version_view(request, project_id, deliverable_id):
    """
    Admin uploads a new version of an existing deliverable.
    The old file is kept in DeliverableVersion history.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden subir nuevas versiones.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        deliverable = Deliverable.objects.get(id=deliverable_id, project=proj)
    except Deliverable.DoesNotExist:
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if deliverable.is_archived:
        return Response(
            {'detail': 'El entregable está archivado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = UploadNewVersionSerializer(data=request.data, context={'deliverable': deliverable})
    serializer.is_valid(raise_exception=True)

    new_version = deliverable.current_version + 1

    DeliverableVersion.objects.create(
        deliverable=deliverable,
        file=serializer.validated_data['file'],
        version_number=new_version,
        uploaded_by=request.user,
    )

    deliverable.file = serializer.validated_data['file']
    deliverable.current_version = new_version
    deliverable.save(update_fields=['file', 'current_version', 'updated_at'])

    notify_project_client(
        proj, Notification.TYPE_DELIVERABLE_NEW_VERSION,
        f'Nueva versión: {deliverable.title} v{new_version}',
        message=f'Se actualizó un entregable en {proj.name}.',
        related_object_type='deliverable', related_object_id=deliverable.id,
        exclude_user=request.user,
        deliverable=deliverable,
    )

    deliverable._detail_versions = list(
        deliverable.versions.select_related('uploaded_by').all(),
    )
    return Response(
        DeliverableDetailSerializer(deliverable, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


def _build_proposal_pdf_http_response(proposal, doc_variant: str):
    """Shared PDF bytes + filename for platform-authenticated downloads."""
    from django.http import HttpResponse
    from django.utils import timezone as _tz
    import re as _re

    if proposal.is_expired:
        return None, Response(
            {'detail': 'La propuesta ha expirado.'},
            status=status.HTTP_410_GONE,
        )

    doc_variant = (doc_variant or '').strip().lower()
    if doc_variant == 'technical':
        from content.services.technical_document_pdf import generate_technical_document_pdf

        sel = proposal.selected_modules if proposal.has_confirmed_module_selection else None
        pdf_bytes = generate_technical_document_pdf(
            proposal, selected_modules=sel,
        )
        if not pdf_bytes:
            return None, Response(
                {'detail': 'El detalle técnico no está disponible.'},
                status=status.HTTP_404_NOT_FOUND,
            )
    else:
        from content.services.proposal_pdf_service import ProposalPdfService

        selected_modules = (
            proposal.selected_modules if proposal.has_confirmed_module_selection else None
        )
        pdf_bytes = ProposalPdfService.generate(
            proposal, selected_modules=selected_modules,
        )
        if not pdf_bytes:
            return None, Response(
                {'detail': 'No se pudo generar el PDF.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    _created = proposal.created_at or _tz.now()
    date_suffix = _created.strftime('%Y-%m-%d')
    safe_title = _re.sub(r'[^\w\s-]', '', proposal.title or proposal.client_name).strip()
    safe_title = _re.sub(r'\s+', '_', safe_title)[:100]
    filename = (
        f'{safe_title}_technical_{date_suffix}.pdf'
        if doc_variant == 'technical'
        else f'{safe_title}_{date_suffix}.pdf'
    )
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def deliverable_commercial_proposal_pdf_view(request, project_id, deliverable_id):
    """JWT client/admin: download commercial PDF for the BusinessProposal on this deliverable."""
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        deliverable = Deliverable.objects.select_related('business_proposal').get(
            id=deliverable_id, project=proj,
        )
    except Deliverable.DoesNotExist:
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not deliverable_visible_for_request(deliverable, request):
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    bp = getattr(deliverable, 'business_proposal', None)
    if not bp:
        return Response(
            {'detail': 'Este entregable no tiene propuesta comercial vinculada.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    http_resp, err_resp = _build_proposal_pdf_http_response(bp, '')
    if err_resp:
        return err_resp
    return http_resp


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def deliverable_technical_document_pdf_view(request, project_id, deliverable_id):
    """JWT client/admin: download technical-document PDF for the proposal on this deliverable."""
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        deliverable = Deliverable.objects.select_related('business_proposal').get(
            id=deliverable_id, project=proj,
        )
    except Deliverable.DoesNotExist:
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not deliverable_visible_for_request(deliverable, request):
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    bp = getattr(deliverable, 'business_proposal', None)
    if not bp:
        return Response(
            {'detail': 'Este entregable no tiene propuesta comercial vinculada.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    http_resp, err_resp = _build_proposal_pdf_http_response(bp, 'technical')
    if err_resp:
        return err_resp
    return http_resp


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def deliverable_attachment_files_view(request, project_id, deliverable_id):
    """List extra files on a deliverable (GET) or upload (POST, admin)."""
    from accounts.models import Deliverable, DeliverableFile
    from accounts.serializers import DeliverableFileSerializer, CreateDeliverableFileSerializer

    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        deliverable = Deliverable.objects.get(id=deliverable_id, project=proj)
    except Deliverable.DoesNotExist:
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        if not deliverable_visible_for_request(deliverable, request):
            return Response(
                {'detail': 'Entregable no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        qs = deliverable.attachment_files.select_related('uploaded_by').all()
        return Response(DeliverableFileSerializer(qs, many=True, context={'request': request}).data)

    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden subir archivos adicionales.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if deliverable.is_archived:
        return Response(
            {'detail': 'El entregable está archivado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = CreateDeliverableFileSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    row = DeliverableFile.objects.create(
        deliverable=deliverable,
        file=data['file'],
        title=data.get('title', ''),
        category=data.get('category', Deliverable.CATEGORY_OTHER),
        uploaded_by=request.user,
    )
    return Response(
        DeliverableFileSerializer(row, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


def _client_or_admin_for_project_docs(request, proj):
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_admin:
        return True
    return proj.client_id == request.user.id


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def deliverable_client_folders_view(request, project_id, deliverable_id):
    from accounts.models import Deliverable, DeliverableClientFolder
    from accounts.serializers import (
        CreateDeliverableClientFolderSerializer,
        DeliverableClientFolderSerializer,
    )

    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err
    try:
        deliverable = Deliverable.objects.get(id=deliverable_id, project=proj)
    except Deliverable.DoesNotExist:
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not _client_or_admin_for_project_docs(request, proj):
        return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        if not deliverable_visible_for_request(deliverable, request):
            return Response(
                {'detail': 'Entregable no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        qs = deliverable.client_folders.all()
        return Response(DeliverableClientFolderSerializer(qs, many=True).data)

    if deliverable.is_archived:
        return Response(
            {'detail': 'El entregable está archivado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = CreateDeliverableClientFolderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    row = DeliverableClientFolder.objects.create(
        deliverable=deliverable,
        name=data['name'],
        order=data.get('order', 0),
        created_by=request.user,
    )
    return Response(
        DeliverableClientFolderSerializer(row).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def deliverable_client_folder_detail_view(request, project_id, deliverable_id, folder_id):
    from accounts.models import Deliverable, DeliverableClientFolder
    from accounts.serializers import DeliverableClientFolderSerializer

    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err
    try:
        deliverable = Deliverable.objects.get(id=deliverable_id, project=proj)
    except Deliverable.DoesNotExist:
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not _client_or_admin_for_project_docs(request, proj):
        return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)

    if not deliverable_visible_for_request(deliverable, request):
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        folder = DeliverableClientFolder.objects.get(
            id=folder_id, deliverable=deliverable,
        )
    except DeliverableClientFolder.DoesNotExist:
        return Response({'detail': 'Carpeta no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        folder.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    name = request.data.get('name')
    order = request.data.get('order')
    upd = []
    if name is not None:
        folder.name = str(name)[:200]
        upd.append('name')
    if order is not None:
        folder.order = int(order)
        upd.append('order')
    if upd:
        folder.save(update_fields=upd)
    return Response(DeliverableClientFolderSerializer(folder).data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def deliverable_client_uploads_view(request, project_id, deliverable_id):
    from accounts.models import Deliverable, DeliverableClientUpload
    from accounts.serializers import (
        CreateDeliverableClientUploadSerializer,
        DeliverableClientUploadSerializer,
    )

    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err
    try:
        deliverable = Deliverable.objects.get(id=deliverable_id, project=proj)
    except Deliverable.DoesNotExist:
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not _client_or_admin_for_project_docs(request, proj):
        return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        if not deliverable_visible_for_request(deliverable, request):
            return Response(
                {'detail': 'Entregable no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        qs = deliverable.client_uploads.select_related('uploaded_by', 'folder').all()
        return Response(
            DeliverableClientUploadSerializer(qs, many=True, context={'request': request}).data,
        )

    if deliverable.is_archived:
        return Response(
            {'detail': 'El entregable está archivado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = CreateDeliverableClientUploadSerializer(
        data=request.data,
        context={'deliverable': deliverable},
    )
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    row = DeliverableClientUpload.objects.create(
        deliverable=deliverable,
        folder_id=data.get('folder_id'),
        file=data['file'],
        title=data.get('title', ''),
        uploaded_by=request.user,
    )
    return Response(
        DeliverableClientUploadSerializer(row, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


# ==========================================================================
# Data Model Entities
# ==========================================================================

from accounts.models import DataModelEntity, ProjectDataModelEntity  # noqa: E402
from accounts.serializers import (  # noqa: E402
    DataModelEntitySerializer,
    ProjectDataModelEntitySerializer,
    ProjectDataModelUploadSerializer,
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def deliverable_data_model_entities_view(request, project_id, deliverable_id):
    """GET — List data model entities linked to a deliverable."""
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        deliverable = Deliverable.objects.get(id=deliverable_id, project=proj)
    except Deliverable.DoesNotExist:
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not deliverable_visible_for_request(deliverable, request):
        return Response(
            {'detail': 'Entregable no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    qs = deliverable.data_model_entities.filter(is_archived=False)
    return Response(DataModelEntitySerializer(qs, many=True).data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def project_data_model_entities_view(request, project_id):
    """
    GET  — List project-level data model entities (admin or owning client).
    POST — Admin uploads JSON to create/replace entities for the project.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    if request.method == 'GET':
        qs = ProjectDataModelEntity.objects.filter(project=proj)
        return Response(ProjectDataModelEntitySerializer(qs, many=True).data)

    profile = getattr(request.user, 'profile', None)
    if not (profile and profile.is_admin):
        return Response(
            {'detail': 'Solo administradores pueden subir el modelo de datos.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = ProjectDataModelUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    entities_data = serializer.validated_data['entities']

    with transaction.atomic():
        ProjectDataModelEntity.objects.filter(project=proj).delete()
        objs = [
            ProjectDataModelEntity(
                project=proj,
                name=item['name'][:300],
                description=item.get('description', ''),
                key_fields=item.get('keyFields', ''),
                relationship=item.get('relationship', ''),
            )
            for item in entities_data
        ]
        ProjectDataModelEntity.objects.bulk_create(objs)

    qs = ProjectDataModelEntity.objects.filter(project=proj)
    return Response(
        ProjectDataModelEntitySerializer(qs, many=True).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_data_model_template_view(request, project_id):
    """GET — Return the JSON template for project data model upload."""
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    template = {
        'entities': [
            {
                'name': 'ExampleEntity',
                'description': 'Brief description of the entity',
                'keyFields': 'id, name, created_at',
                'relationship': '1:N with OtherEntity',
            },
        ],
    }
    return Response(template)


# ==========================================================================
# Notifications
# ==========================================================================

from accounts.models import Notification  # noqa: E402
from accounts.serializers import NotificationSerializer  # noqa: E402


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list_view(request):
    """
    GET — List notifications for the authenticated user.
    Supports ?is_read=true/false filter and ?limit=N.
    """
    qs = Notification.objects.filter(user=request.user).select_related('project', 'deliverable')

    is_read_param = request.query_params.get('is_read')
    if is_read_param == 'true':
        qs = qs.filter(is_read=True)
    elif is_read_param == 'false':
        qs = qs.filter(is_read=False)

    limit = request.query_params.get('limit')
    if limit:
        try:
            qs = qs[:int(limit)]
        except (ValueError, TypeError):
            pass

    serializer = NotificationSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_unread_count_view(request):
    """GET — Return count of unread notifications for badge display."""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return Response({'count': count})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notification_mark_read_view(request, notification_id):
    """Mark a single notification as read."""
    try:
        notif = Notification.objects.get(id=notification_id, user=request.user)
    except Notification.DoesNotExist:
        return Response(
            {'detail': 'Notificación no encontrada.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return Response(NotificationSerializer(notif).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notification_mark_all_read_view(request):
    """Mark all unread notifications as read for the authenticated user."""
    updated = Notification.objects.filter(
        user=request.user, is_read=False,
    ).update(is_read=True)
    return Response({'marked_read': updated})


# ==========================================================================
# Payments & Subscriptions
# ==========================================================================

from accounts.models import HostingSubscription, Payment, PaymentHistory  # noqa: E402
from accounts.serializers import (  # noqa: E402
    HostingSubscriptionListSerializer,
    HostingSubscriptionSerializer,
    PaymentSerializer,
    ProposalSummarySerializer,
    UpdateSubscriptionSerializer,
)


def _extract_proposal_financial_data(proposal):
    """
    Extract payment milestones and hosting tiers from the proposal's
    investment section (section_type='investment') content_json.
    Returns (payment_milestones, hosting_tiers) as plain lists.
    """
    from content.models import ProposalSection
    from content.services.proposal_service import normalize_hosting_plan
    from decimal import Decimal

    payment_milestones = []
    hosting_tiers = []

    try:
        section = ProposalSection.objects.get(
            proposal=proposal, section_type='investment',
        )
    except ProposalSection.DoesNotExist:
        return payment_milestones, hosting_tiers

    cj = section.content_json or {}

    # --- Payment milestones (admin-visible only) ---
    for opt in cj.get('paymentOptions', []):
        payment_milestones.append({
            'label': opt.get('label', ''),
            'description': opt.get('description', ''),
        })

    # --- Hosting tiers (pricing for client plan selection) ---
    normalized = normalize_hosting_plan(
        proposal, cj.get('hostingPlan', {}), force_current_terms=True,
    )
    base_percent = normalized['hostingPercent']
    hosting_twelve_month_reference = (
        float(proposal.total_investment) * base_percent / 100
    )
    base_monthly = round(hosting_twelve_month_reference / 12, 2)
    currency = str(cj.get('currency', proposal.currency))

    billing_tiers = normalized['billingTiers']
    if not billing_tiers:
        billing_tiers = [
            {'frequency': 'nine_month', 'months': 9, 'label': 'Cada 9 meses',
             'badge': 'Máximo descuento',
             'discountPercent': proposal.hosting_discount_nine_month},
            {'frequency': 'semiannual', 'months': 6, 'label': 'Semestral',
             'badge': '20% dcto',
             'discountPercent': proposal.hosting_discount_semiannual},
            {'frequency': 'quarterly', 'months': 3, 'label': 'Trimestral',
             'badge': (f'{proposal.hosting_discount_quarterly}% dcto'
                       if proposal.hosting_discount_quarterly else ''),
             'discountPercent': proposal.hosting_discount_quarterly},
        ]

    for tier in billing_tiers:
        discount = tier.get('discountPercent', 0)
        months = tier.get('months', 1)
        effective_monthly = round(base_monthly * (100 - discount) / 100, 2)
        hosting_tiers.append({
            'frequency': tier.get('frequency', ''),
            'months': months,
            'label': tier.get('label', ''),
            'badge': tier.get('badge', ''),
            'discount_percent': discount,
            'base_monthly': base_monthly,
            'effective_monthly': effective_monthly,
            'billing_amount': round(effective_monthly * months, 2),
            'currency': currency,
        })

    return payment_milestones, hosting_tiers


def _create_subscription_multi_phase(project, plan):
    """
    Create a HostingSubscription billing the sum of the project's started
    phases at the given plan. A phase counts as started when its
    hosting_start_date is unset or already reached; future-dated phases are
    left for the billing cron to onboard (prorated) when their date arrives.
    Returns None when no phase has started yet.
    """
    from datetime import date
    from decimal import Decimal

    from dateutil.relativedelta import relativedelta

    from accounts.services.hosting_billing import (
        first_billing_date, phase_monthly_base, project_billing_amount,
    )

    today = date.today()
    phases = list(project.phases.select_related('business_proposal').all())
    started = [p for p in phases if p.hosting_start_date is None or p.hosting_start_date <= today]
    if not started:
        return None

    start_dates = [p.hosting_start_date for p in started if p.hosting_start_date]
    start_date = min(start_dates) if start_dates else today

    # Free month: hosting is gifted from delivery (start_date) until the first
    # billing date, which always lands on the 1st of a month and is at least one
    # full month away. No charge is generated for that free period.
    billing_start = first_billing_date(start_date)

    for p in started:
        p.hosting_activated_at = p.hosting_start_date or today
        p.save(update_fields=['hosting_activated_at'])

    # All amounts/dates are pure Python (no DB dependency), so compute them up
    # front and persist the subscription in a single write.
    months = HostingSubscription.PLAN_MONTHS[plan]
    billing_amount = project_billing_amount(project, plan)
    billing_end = billing_start + relativedelta(months=months) - relativedelta(days=1)

    sub = HostingSubscription(
        project=project,
        plan=plan,
        base_monthly_amount=sum((phase_monthly_base(p) for p in started), Decimal('0')),
        discount_percent=0,
        effective_monthly_amount=round(billing_amount / Decimal(months), 2),
        billing_amount=billing_amount,
        status=HostingSubscription.STATUS_PENDING,
        start_date=start_date,
        next_billing_date=billing_end + relativedelta(days=1),
    )
    sub.save()

    Payment.objects.create(
        subscription=sub,
        amount=billing_amount,
        description=f'Hosting {sub.plan_label} — {billing_start} a {billing_end}',
        billing_period_start=billing_start,
        billing_period_end=billing_end,
        due_date=billing_start,
        status=Payment.STATUS_PENDING,
    )

    return sub


def _generate_next_payment(subscription):
    """
    Generate the next Payment record for a subscription's billing cycle.
    Called after a payment is completed (auto-renewal) or when a subscription
    is first created.
    Skips if a pending/processing payment already exists for the next period.
    """
    from dateutil.relativedelta import relativedelta

    # Check if there's already a pending/processing payment
    existing = Payment.objects.filter(
        subscription=subscription,
        status__in=[Payment.STATUS_PENDING, Payment.STATUS_PROCESSING],
    ).exists()
    if existing:
        return None

    billing_start = subscription.next_billing_date
    if not billing_start:
        return None

    months = subscription.billing_months
    billing_end = billing_start + relativedelta(months=months) - relativedelta(days=1)

    payment = Payment.objects.create(
        subscription=subscription,
        amount=subscription.billing_amount,
        description=f'Hosting {subscription.plan_label} — {billing_start} a {billing_end}',
        billing_period_start=billing_start,
        billing_period_end=billing_end,
        due_date=billing_start,
        status=Payment.STATUS_PENDING,
    )
    return payment


def _handle_payment_approved(payment, payment_history_source=''):
    """
    Common logic when a payment is approved (card-pay, verify, webhook).
    Marks payment as paid, updates subscription, and generates next payment (auto-renewal).
    """
    from django.utils import timezone as tz
    from dateutil.relativedelta import relativedelta

    from accounts.models import PaymentHistory
    from accounts.services.payment_history import record_payment_status_change

    old_status = payment.status
    payment.status = Payment.STATUS_PAID
    payment.paid_at = tz.now()
    payment.save(update_fields=['wompi_transaction_id', 'status', 'paid_at'])
    record_payment_status_change(
        payment,
        old_status,
        Payment.STATUS_PAID,
        source=payment_history_source or PaymentHistory.SOURCE_SYSTEM,
    )

    sub = payment.subscription
    sub.next_billing_date = payment.billing_period_end + relativedelta(days=1)
    if sub.status == HostingSubscription.STATUS_PENDING:
        sub.status = HostingSubscription.STATUS_ACTIVE
    sub.save(update_fields=['next_billing_date', 'status', 'updated_at'])

    # Auto-renewal: generate the next billing cycle payment
    _generate_next_payment(sub)

    # Notify about payment
    try:
        from accounts.models import Notification
        from accounts.services.notifications import notify, notify_project_admins
        from content.utils import format_bogota_date, format_cop_email
        project = sub.project
        notify(
            user=project.client,
            type=Notification.TYPE_GENERAL,
            title='Pago confirmado',
            message=f'Tu pago de ${format_cop_email(payment.amount)} COP para "{project.name}" fue procesado exitosamente. Próxima renovación: {format_bogota_date(sub.next_billing_date)}.',
            project=project,
            related_object_type='payment',
            related_object_id=payment.id,
        )
        notify_project_admins(
            project, Notification.TYPE_GENERAL,
            f'Pago recibido: {project.name}',
            message=f'{project.client.first_name} pagó ${format_cop_email(payment.amount)} COP del hosting de "{project.name}".',
            related_object_type='payment', related_object_id=payment.id,
        )
    except Exception:
        logger.warning('Failed to create payment notifications for payment %s', payment.id)


def _poll_transaction_status(transaction_id, attempts=5, delay=2):
    """
    Card transactions settle asynchronously — Wompi returns PENDING and
    resolves seconds later. Poll the transaction a few times so an approved
    charge resolves now instead of waiting on the webhook (which can't reach
    localhost in development). Returns the settled transaction data, or None
    if it is still pending after the polling window.
    """
    import time

    from accounts.services.wompi import verify_transaction

    for _ in range(attempts):
        time.sleep(delay)
        try:
            data = verify_transaction(transaction_id)
        except Exception as e:
            logger.warning('Transaction poll error for %s: %s', transaction_id, e)
            continue
        if data.get('status') and data.get('status') != 'PENDING':
            return data
    return None


def _charge_payment_with_source(payment, history_source=''):
    """
    Charge a Payment using its subscription's stored Wompi payment source.
    Updates the Payment status from the transaction result and returns the
    Wompi transaction data dict. Raises ValueError if no stored card exists.
    """
    import hashlib
    import time

    from django.conf import settings as dj_settings

    from accounts.models import PaymentHistory
    from accounts.services.payment_history import record_payment_status_change
    from accounts.services.wompi import charge_with_payment_source

    sub = payment.subscription
    if not sub.wompi_payment_source_id:
        raise ValueError('La suscripción no tiene una tarjeta guardada.')

    ts = int(time.time())
    reference = f'PA{payment.id}P{sub.project_id}T{ts}'
    amount_in_cents = int(payment.amount * 100)
    integrity_str = f'{reference}{amount_in_cents}COP{dj_settings.WOMPI_INTEGRITY_SECRET}'
    signature = hashlib.sha256(integrity_str.encode()).hexdigest()

    txn_data = charge_with_payment_source(
        payment, sub.wompi_payment_source_id, reference, signature,
    )
    txn_id = txn_data.get('id', '')
    txn_status = txn_data.get('status', '')

    # The charge settles asynchronously — give Wompi a moment to resolve a
    # PENDING transaction before falling back to the webhook.
    if txn_status == 'PENDING' and txn_id:
        settled = _poll_transaction_status(str(txn_id))
        if settled:
            txn_data = settled
            txn_status = settled.get('status', txn_status)

    payment.wompi_transaction_id = str(txn_id)
    src = history_source or PaymentHistory.SOURCE_API

    if txn_status == 'APPROVED':
        _handle_payment_approved(payment, src)
    elif txn_status == 'PENDING':
        old_status = payment.status
        payment.status = Payment.STATUS_PROCESSING
        payment.save(update_fields=['wompi_transaction_id', 'status'])
        record_payment_status_change(payment, old_status, Payment.STATUS_PROCESSING, src)
    else:  # DECLINED, ERROR, VOIDED
        old_status = payment.status
        payment.status = Payment.STATUS_FAILED
        payment.last_charge_error = (
            txn_data.get('status_message') or txn_status or 'Pago rechazado'
        )[:300]
        payment.save(update_fields=['wompi_transaction_id', 'status', 'last_charge_error'])
        record_payment_status_change(payment, old_status, Payment.STATUS_FAILED, src)

    return txn_data


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def proposal_list_for_selector_view(request):
    """Admin-only: list proposals for the project creation selector."""
    from content.models import BusinessProposal

    qs = BusinessProposal.objects.filter(
        status__in=['accepted', 'finished', 'sent', 'viewed', 'negotiating'],
        deliverable__isnull=True,
    ).only(
        'id', 'title', 'client_name', 'client_email', 'total_investment',
        'currency', 'hosting_percent', 'hosting_discount_nine_month',
        'hosting_discount_semiannual', 'hosting_discount_quarterly', 'status',
    ).order_by('-created_at')

    serializer = ProposalSummarySerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_list_view(request):
    """
    Admin sees all subscriptions. Client sees only their projects' subscriptions.
    """
    from datetime import timedelta

    from django.db.models import Count, Q

    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin

    if is_admin:
        qs = HostingSubscription.objects.select_related('project').all()
    else:
        qs = HostingSubscription.objects.select_related('project').filter(
            project__client=request.user,
        )

    qs = filter_subscriptions_for_list(qs, request, is_admin=is_admin)
    cutoff = timezone.now().date() + timedelta(days=7)
    qs = qs.annotate(
        _pending_payments_count=Count(
            'payments',
            filter=Q(
                payments__is_archived=False,
                payments__status__in=[
                    Payment.STATUS_PENDING, Payment.STATUS_OVERDUE, Payment.STATUS_FAILED,
                ],
                payments__due_date__lte=cutoff,
            ),
        ),
    ).order_by('-created_at')

    serializer = HostingSubscriptionListSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAuthenticated])
def project_subscription_view(request, project_id):
    """
    GET  — Subscription detail with payments (admin or owning client).
           Returns 404 if no subscription exists yet.
    POST — Client (or admin) creates subscription by choosing a hosting plan.
           Required: { plan: 'quarterly'|'semiannual'|'nine_month' }
           Only works if no subscription exists yet and the project has phases
           with at least one already started.
    PATCH — Change hosting plan (admin or client) or status (admin only).
    """
    related_fields = ('hosting_subscription',) if request.method == 'PATCH' else ()
    proj, err = _get_project_or_403(request, project_id, related_fields=related_fields)
    if err:
        return err

    # --- POST: create subscription ---
    if request.method == 'POST':
        if HostingSubscription.objects.filter(project=proj).exists():
            return Response(
                {'detail': 'Ya existe una suscripción de hosting para este proyecto.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not proj.phases.exists():
            return Response(
                {'detail': 'El proyecto no tiene fases para calcular el hosting.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan = request.data.get('plan')
        if plan not in dict(HostingSubscription.PLAN_CHOICES):
            return Response(
                {'detail': 'Plan inválido. Opciones: quarterly, semiannual, nine_month.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sub = _create_subscription_multi_phase(proj, plan)
        if sub is None:
            return Response(
                {'detail': 'Ninguna fase tiene su hosting iniciado todavía.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sub = HostingSubscription.objects.prefetch_related(_subscription_payment_prefetch()).get(pk=sub.pk)
        return Response(
            HostingSubscriptionSerializer(sub).data,
            status=status.HTTP_201_CREATED,
        )

    # --- GET / PATCH: existing subscription ---
    try:
        if request.method == 'PATCH':
            # The access check already loaded this one-to-one relation. Delay
            # payment collections until permissions and input have passed.
            sub = proj.hosting_subscription
        else:
            sub = HostingSubscription.objects.prefetch_related(
                _subscription_payment_prefetch(),
            ).get(project=proj)
    except HostingSubscription.DoesNotExist:
        return Response(
            {'detail': 'No hay suscripción de hosting para este proyecto.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin

    if request.method == 'GET':
        if sub.is_archived and not is_admin:
            return Response(
                {'detail': 'No hay suscripción de hosting para este proyecto.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(HostingSubscriptionSerializer(sub).data)

    serializer = UpdateSubscriptionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)

    # Client can only change plan, not status
    if 'status' in data and not is_admin:
        return Response(
            {'detail': 'Solo los administradores pueden cambiar el estado de la suscripción.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if 'is_archived' in data:
        if not is_admin:
            return Response(
                {'detail': 'Solo los administradores pueden archivar la suscripción.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        flag = data.pop('is_archived')
        sub.updated_at = timezone.now()
        if flag:
            archive_record(sub, extra_update_fields=('updated_at',))
        else:
            unarchive_record(sub, extra_update_fields=('updated_at',))

    if 'plan' in data and data['plan'] != sub.plan:
        # The frequency is locked once the first payment is settled; until
        # then (status pending) the client may still change it.
        if not is_admin and sub.status != HostingSubscription.STATUS_PENDING:
            return Response(
                {'detail': 'La frecuencia ya no se puede cambiar. Escríbenos para ajustarla.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        from decimal import Decimal

        from dateutil.relativedelta import relativedelta

        from accounts.services.hosting_billing import project_billing_amount

        sub.plan = data['plan']
        sub.billing_amount = project_billing_amount(proj, data['plan'])
        months = sub.billing_months
        sub.effective_monthly_amount = round(sub.billing_amount / Decimal(months), 2)

        # While still pending, realign the unpaid first payment + cycle.
        if sub.status == HostingSubscription.STATUS_PENDING:
            first = (
                sub.payments.filter(status=Payment.STATUS_PENDING, is_archived=False)
                .order_by('billing_period_start').first()
            )
            if first:
                billing_end = (
                    first.billing_period_start
                    + relativedelta(months=months) - relativedelta(days=1)
                )
                first.amount = sub.billing_amount
                first.billing_period_end = billing_end
                first.description = (
                    f'Hosting {sub.plan_label} — '
                    f'{first.billing_period_start} a {billing_end}'
                )
                first.save(update_fields=['amount', 'billing_period_end', 'description'])
                sub.next_billing_date = billing_end + relativedelta(days=1)
    if 'status' in data:
        sub.status = data['status']
    sub.save()

    prefetch_related_objects([sub], _subscription_payment_prefetch())
    return Response(HostingSubscriptionSerializer(sub).data)


def _subscription_payment_prefetch():
    from django.db.models import Prefetch

    from accounts.models import Payment

    return Prefetch(
        'payments',
        queryset=Payment.objects.filter(is_archived=False).prefetch_related('history'),
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_payments_view(request, project_id):
    """List payments for a project's subscription."""
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        sub = HostingSubscription.objects.get(project=proj)
    except HostingSubscription.DoesNotExist:
        return Response([])

    profile = getattr(request.user, 'profile', None)
    is_admin = profile and profile.is_admin

    payments = Payment.objects.filter(subscription=sub)
    if not (is_admin and wants_include_archived(request)):
        payments = payments.filter(is_archived=False)
    payments = payments.select_related('subscription__project').prefetch_related('history')
    serializer = PaymentSerializer(payments, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def register_manual_payment_view(request, project_id):
    """Admin registers a manual (off-platform) hosting payment for a project."""
    from decimal import Decimal

    from dateutil.relativedelta import relativedelta
    from django.utils import timezone

    from accounts.serializers import ManualPaymentSerializer as _ManualSer

    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    ser = _ManualSer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    data = ser.validated_data
    frequency = data['frequency']
    amount = data['amount']
    billing_period_start = data['billing_period_start']
    description = data.get('description') or 'Pago manual registrado por administrador'

    billing_months = HostingSubscription.PLAN_MONTHS[frequency]
    billing_period_end = billing_period_start + relativedelta(months=billing_months) - relativedelta(days=1)
    next_billing = billing_period_end + relativedelta(days=1)

    try:
        sub = HostingSubscription.objects.get(project=proj)
        if not sub.next_billing_date or next_billing > sub.next_billing_date:
            sub.next_billing_date = next_billing
            sub.status = HostingSubscription.STATUS_ACTIVE
            sub.save(update_fields=['next_billing_date', 'status'])
    except HostingSubscription.DoesNotExist:
        base_monthly = round(Decimal(str(amount)) / billing_months, 2)
        sub = HostingSubscription.objects.create(
            project=proj,
            plan=frequency,
            base_monthly_amount=base_monthly,
            discount_percent=0,
            effective_monthly_amount=base_monthly,
            billing_amount=amount,
            status=HostingSubscription.STATUS_ACTIVE,
            start_date=billing_period_start,
            next_billing_date=next_billing,
        )

    payment = Payment.objects.create(
        subscription=sub,
        amount=amount,
        description=description,
        billing_period_start=billing_period_start,
        billing_period_end=billing_period_end,
        due_date=billing_period_start,
        status=Payment.STATUS_PAID,
        paid_at=timezone.now(),
    )

    PaymentHistory.objects.create(
        payment=payment,
        from_status=Payment.STATUS_PENDING,
        to_status=Payment.STATUS_PAID,
        source=PaymentHistory.SOURCE_MANUAL,
        metadata={'registered_by': request.user.email},
    )

    return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def payment_generate_link_view(request, project_id, payment_id):
    """Admin generates a Wompi payment link for a pending payment."""
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        payment = Payment.objects.select_related('subscription__project').get(
            id=payment_id, subscription__project=proj,
        )
    except Payment.DoesNotExist:
        return Response(
            {'detail': 'Pago no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if payment.status not in (Payment.STATUS_PENDING, Payment.STATUS_OVERDUE, Payment.STATUS_FAILED):
        return Response(
            {'detail': 'Solo se pueden generar links para pagos pendientes, vencidos o fallidos.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        from accounts.services.wompi import create_payment_link
        link_id, link_url = create_payment_link(payment)
        return Response({
            'payment_id': payment.id,
            'wompi_payment_link_id': link_id,
            'wompi_payment_link_url': link_url,
        })
    except Exception as e:
        return Response(
            {'detail': f'Error al generar el link de pago: {str(e)}'},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_widget_data_view(request, project_id, payment_id):
    """
    Generate Wompi widget checkout data (integrity signature, reference, etc.)
    for the frontend to open the Wompi widget with a custom branded button.
    """
    import hashlib
    import time

    from django.conf import settings as django_settings

    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        payment = Payment.objects.select_related('subscription__project').get(
            id=payment_id, subscription__project=proj,
        )
    except Payment.DoesNotExist:
        return Response(
            {'detail': 'Pago no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if payment.status not in (Payment.STATUS_PENDING, Payment.STATUS_OVERDUE, Payment.STATUS_PROCESSING, Payment.STATUS_FAILED):
        return Response(
            {'detail': 'Este pago no está disponible para cobro.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    amount_in_cents = int(payment.amount * 100)
    ts = int(time.time())
    reference = f'PA{payment.id}P{proj.id}T{ts}'

    integrity_secret = django_settings.WOMPI_INTEGRITY_SECRET
    integrity_str = f'{reference}{amount_in_cents}COP{integrity_secret}'
    integrity_signature = hashlib.sha256(integrity_str.encode()).hexdigest()

    base_url = django_settings.FRONTEND_BASE_URL
    redirect_url = ''
    if base_url.startswith('https'):
        redirect_url = f'{base_url}/platform/projects/{proj.id}/payments?payment={payment.id}'

    logger.info(
        'Wompi widget data — ref=%s amount=%s redirect=%s',
        reference, amount_in_cents, redirect_url or '(omitted for dev)',
    )

    data = {
        'public_key': django_settings.WOMPI_PUBLIC_KEY,
        'currency': 'COP',
        'amount_in_cents': amount_in_cents,
        'reference': reference,
        'integrity_signature': integrity_signature,
        'customer_email': proj.client.email,
        'customer_full_name': f'{proj.client.first_name} {proj.client.last_name}'.strip(),
    }
    if redirect_url:
        data['redirect_url'] = redirect_url

    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def payment_card_pay_view(request, project_id, payment_id):
    """
    Process a card payment: tokenize card → create Wompi transaction with installments=1.
    Card data is tokenized server-side to guarantee installments=1 (subscription, no multi-cuota).
    """
    import hashlib
    import time

    from django.conf import settings as django_settings

    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        payment = Payment.objects.select_related('subscription__project__client').get(
            id=payment_id, subscription__project=proj,
        )
    except Payment.DoesNotExist:
        return Response({'detail': 'Pago no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if payment.status not in (Payment.STATUS_PENDING, Payment.STATUS_OVERDUE, Payment.STATUS_FAILED):
        return Response({'detail': 'Este pago no está disponible para cobro.'}, status=status.HTTP_400_BAD_REQUEST)

    card_number = request.data.get('card_number', '')
    exp_month = request.data.get('exp_month', '')
    exp_year = request.data.get('exp_year', '')
    cvc = request.data.get('cvc', '')
    card_holder = request.data.get('card_holder', '')

    if not all([card_number, exp_month, exp_year, cvc, card_holder]):
        return Response({'detail': 'Todos los campos de la tarjeta son requeridos.'}, status=status.HTTP_400_BAD_REQUEST)

    from django.utils import timezone as tz

    try:
        from accounts.services.wompi import tokenize_card, get_acceptance_token, create_card_transaction

        card_token = tokenize_card(card_number, exp_month, exp_year, cvc, card_holder)['id']
        acceptance_token = get_acceptance_token()

        ts = int(time.time())
        reference = f'PA{payment.id}P{proj.id}T{ts}'
        amount_in_cents = int(payment.amount * 100)
        integrity_str = f'{reference}{amount_in_cents}COP{django_settings.WOMPI_INTEGRITY_SECRET}'
        signature = hashlib.sha256(integrity_str.encode()).hexdigest()

        txn_data = create_card_transaction(payment, card_token, acceptance_token, reference, signature)

        txn_id = txn_data.get('id', '')
        txn_status = txn_data.get('status', '')

        payment.wompi_transaction_id = str(txn_id)

        from accounts.models import PaymentHistory
        from accounts.services.payment_history import record_payment_status_change

        if txn_status == 'APPROVED':
            _handle_payment_approved(payment, PaymentHistory.SOURCE_API)
        elif txn_status == 'PENDING':
            old_status = payment.status
            payment.status = Payment.STATUS_PROCESSING
            payment.save(update_fields=['wompi_transaction_id', 'status'])
            record_payment_status_change(
                payment, old_status, Payment.STATUS_PROCESSING, PaymentHistory.SOURCE_API,
            )
        elif txn_status in ('DECLINED', 'ERROR', 'VOIDED'):
            old_status = payment.status
            payment.status = Payment.STATUS_FAILED
            payment.save(update_fields=['wompi_transaction_id', 'status'])
            record_payment_status_change(
                payment, old_status, Payment.STATUS_FAILED, PaymentHistory.SOURCE_API,
            )

        return Response({
            'payment_id': payment.id,
            'payment_status': payment.status,
            'transaction_id': txn_id,
            'transaction_status': txn_status,
        })

    except Exception as e:
        logger.error('Card payment error for payment %s: %s', payment.id, e)
        return Response(
            {'detail': f'Error procesando el pago: {str(e)}'},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def payment_verify_transaction_view(request, project_id, payment_id):
    """
    After the Wompi widget completes, the frontend calls this endpoint
    with the transaction_id to verify the payment status directly with Wompi
    (needed because webhooks can't reach localhost in dev).
    """
    from django.utils import timezone as tz

    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        payment = Payment.objects.select_related('subscription').get(
            id=payment_id, subscription__project=proj,
        )
    except Payment.DoesNotExist:
        return Response(
            {'detail': 'Pago no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Falls back to the transaction id already stored on the payment, so the
    # client can re-verify a PROCESSING payment without re-supplying it.
    transaction_id = request.data.get('transaction_id') or payment.wompi_transaction_id
    if not transaction_id:
        return Response(
            {'detail': 'No hay una transacción asociada a este pago.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        from accounts.services.wompi import verify_transaction
        txn_data = verify_transaction(str(transaction_id))
    except Exception as e:
        logger.error('Wompi verify error: %s', e)
        return Response(
            {'detail': 'No se pudo verificar la transacción con Wompi.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    from accounts.models import PaymentHistory
    from accounts.services.payment_history import record_payment_status_change

    txn_status = txn_data.get('status', '')
    payment.wompi_transaction_id = str(transaction_id)

    if txn_status == 'APPROVED':
        _handle_payment_approved(payment, PaymentHistory.SOURCE_WOMPI_VERIFY)
    elif txn_status in ('DECLINED', 'ERROR', 'VOIDED'):
        old_status = payment.status
        payment.status = Payment.STATUS_FAILED
        payment.save(update_fields=['wompi_transaction_id', 'status'])
        record_payment_status_change(
            payment, old_status, Payment.STATUS_FAILED, PaymentHistory.SOURCE_WOMPI_VERIFY,
        )
    else:
        payment.save(update_fields=['wompi_transaction_id'])

    logger.info('Payment %s verified — Wompi status: %s', payment.id, txn_status)

    return Response({
        'payment_id': payment.id,
        'payment_status': payment.status,
        'transaction_status': txn_status,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def card_setup_start_view(request, project_id):
    """
    Start stored-card setup for a subscription: tokenize the card and create
    a Wompi payment source. When the merchant has 3DS enabled, the response
    carries the three_ds_auth flow the frontend completes by polling
    card_setup_status_view until the source becomes AVAILABLE.
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        sub = HostingSubscription.objects.select_related('project__client').get(project=proj)
    except HostingSubscription.DoesNotExist:
        return Response(
            {'detail': 'Este proyecto no tiene una suscripción de hosting.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    card_number = request.data.get('card_number', '')
    exp_month = request.data.get('exp_month', '')
    exp_year = request.data.get('exp_year', '')
    cvc = request.data.get('cvc', '')
    card_holder = request.data.get('card_holder', '')
    if not all([card_number, exp_month, exp_year, cvc, card_holder]):
        return Response(
            {'detail': 'Todos los campos de la tarjeta son requeridos.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        from accounts.services.wompi import (
            create_payment_source, get_acceptance_tokens, tokenize_card,
        )
        token_data = tokenize_card(card_number, exp_month, exp_year, cvc, card_holder)
        tokens = get_acceptance_tokens()
        source = create_payment_source(
            token_data['id'], sub.project.client.email,
            tokens['acceptance_token'], tokens['accept_personal_auth'],
        )
    except Exception as e:
        logger.error('Card setup start error for project %s: %s', proj.id, e)
        return Response(
            {'detail': f'No se pudo registrar la tarjeta: {str(e)}'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    extra = source.get('extra', {}) or {}
    return Response({
        'payment_source_id': source.get('id'),
        'status': source.get('status'),
        'is_three_ds': bool(extra.get('is_three_ds')),
        'three_ds_auth': extra.get('three_ds_auth', {}),
        'card_brand': token_data.get('brand', ''),
        'card_last_four': token_data.get('last_four', ''),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def card_setup_status_view(request, project_id, payment_source_id):
    """Poll a payment source's state while the 3DS auth flow runs."""
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        from accounts.services.wompi import get_payment_source
        source = get_payment_source(payment_source_id)
    except Exception as e:
        logger.error('Card setup status error (source %s): %s', payment_source_id, e)
        return Response(
            {'detail': 'No se pudo consultar el estado de la tarjeta.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if (source.get('customer_email') or '').lower() != (proj.client.email or '').lower():
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

    extra = source.get('extra', {}) or {}
    return Response({
        'payment_source_id': source.get('id'),
        'status': source.get('status'),
        'is_three_ds': bool(extra.get('is_three_ds')),
        'three_ds_auth': extra.get('three_ds_auth', {}),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def card_setup_confirm_view(request, project_id, payment_source_id):
    """
    Finalize stored-card setup: verify the payment source is AVAILABLE,
    persist it on the subscription, and charge the oldest open payment
    (the initial billing cycle).
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        sub = HostingSubscription.objects.select_related('project__client').get(project=proj)
    except HostingSubscription.DoesNotExist:
        return Response(
            {'detail': 'Este proyecto no tiene una suscripción de hosting.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        from accounts.services.wompi import get_payment_source
        source = get_payment_source(payment_source_id)
    except Exception as e:
        logger.error('Card setup confirm error (source %s): %s', payment_source_id, e)
        return Response(
            {'detail': 'No se pudo verificar la tarjeta con Wompi.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if (source.get('customer_email') or '').lower() != (sub.project.client.email or '').lower():
        return Response(
            {'detail': 'La tarjeta no corresponde a esta cuenta.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if source.get('status') != 'AVAILABLE':
        return Response(
            {
                'detail': 'La tarjeta no quedó autorizada. Intenta de nuevo o usa otra tarjeta.',
                'status': source.get('status'),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    public_data = source.get('public_data', {}) or {}
    sub.wompi_payment_source_id = str(source.get('id'))
    sub.card_brand = (request.data.get('card_brand') or public_data.get('brand') or '')[:20]
    sub.card_last_four = (request.data.get('card_last_four') or public_data.get('last_four') or '')[:4]
    sub.card_exp_month = str(request.data.get('exp_month') or public_data.get('exp_month') or '')[:2]
    sub.card_exp_year = str(request.data.get('exp_year') or public_data.get('exp_year') or '')[:4]
    sub.save(update_fields=[
        'wompi_payment_source_id', 'card_brand', 'card_last_four',
        'card_exp_month', 'card_exp_year', 'updated_at',
    ])

    # Only charge a payment that is actually due. With the free-month gift the
    # first payment is dated to the 1st of a future month; it must NOT be charged
    # at card registration — the billing cron charges it once its due date arrives.
    from datetime import date as _date
    payment = Payment.objects.filter(
        subscription=sub,
        status__in=[Payment.STATUS_PENDING, Payment.STATUS_OVERDUE, Payment.STATUS_FAILED],
        is_archived=False,
        due_date__lte=_date.today(),
    ).order_by('due_date').first()

    charge_result = None
    if payment is not None:
        try:
            txn_data = _charge_payment_with_source(payment)
            charge_result = {
                'payment_id': payment.id,
                'payment_status': payment.status,
                'transaction_status': txn_data.get('status', ''),
            }
        except Exception as e:
            logger.error('Initial charge error for payment %s: %s', payment.id, e)
            charge_result = {'payment_id': payment.id, 'error': str(e)}

    sub = HostingSubscription.objects.prefetch_related(
        _subscription_payment_prefetch(),
    ).get(pk=sub.pk)
    return Response({
        'subscription': HostingSubscriptionSerializer(sub).data,
        'charge': charge_result,
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def card_delete_view(request, project_id):
    """
    Remove the stored card from a subscription. Attempts to delete the payment
    source at Wompi (best-effort) and clears the local card reference, which
    also disables automatic recurring billing (the cron skips subscriptions
    with an empty wompi_payment_source_id).
    """
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        sub = HostingSubscription.objects.get(project=proj)
    except HostingSubscription.DoesNotExist:
        return Response(
            {'detail': 'Este proyecto no tiene una suscripción de hosting.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not sub.wompi_payment_source_id:
        return Response(
            {'detail': 'No hay una tarjeta registrada para eliminar.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from accounts.services.wompi import delete_payment_source
    delete_payment_source(sub.wompi_payment_source_id)

    sub.wompi_payment_source_id = ''
    sub.card_brand = ''
    sub.card_last_four = ''
    sub.card_exp_month = ''
    sub.card_exp_year = ''
    sub.save(update_fields=[
        'wompi_payment_source_id', 'card_brand', 'card_last_four',
        'card_exp_month', 'card_exp_year', 'updated_at',
    ])

    sub = HostingSubscription.objects.prefetch_related(
        _subscription_payment_prefetch(),
    ).get(pk=sub.pk)
    return Response({'subscription': HostingSubscriptionSerializer(sub).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def payment_charge_stored_view(request, project_id, payment_id):
    """Charge a single open payment using the subscription's stored card."""
    proj, err = _get_project_or_403(request, project_id)
    if err:
        return err

    try:
        payment = Payment.objects.select_related('subscription__project__client').get(
            id=payment_id, subscription__project=proj,
        )
    except Payment.DoesNotExist:
        return Response({'detail': 'Pago no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if payment.status not in (Payment.STATUS_PENDING, Payment.STATUS_OVERDUE, Payment.STATUS_FAILED):
        return Response(
            {'detail': 'Este pago no está disponible para cobro.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not payment.subscription.wompi_payment_source_id:
        return Response(
            {'detail': 'No hay una tarjeta guardada. Registra una tarjeta primero.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        txn_data = _charge_payment_with_source(payment)
    except Exception as e:
        logger.error('Stored-card charge error for payment %s: %s', payment.id, e)
        return Response(
            {'detail': f'Error procesando el pago: {str(e)}'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response({
        'payment_id': payment.id,
        'payment_status': payment.status,
        'transaction_id': txn_data.get('id', ''),
        'transaction_status': txn_data.get('status', ''),
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def wompi_webhook_view(request):
    """
    Public webhook endpoint for Wompi transaction events.
    Validates signature and updates payment status.
    """
    import json
    from django.utils import timezone as tz

    event = request.data

    from accounts.services.wompi import validate_event_signature
    if not validate_event_signature(event):
        logger.warning('Wompi webhook rejected — invalid or missing event signature')
        return Response(
            {'status': 'invalid signature'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    event_type = event.get('event')
    data = event.get('data', {})
    transaction = data.get('transaction', {})

    if event_type != 'transaction.updated':
        return Response({'status': 'ignored'})

    transaction_id = transaction.get('id', '')
    transaction_status = transaction.get('status', '')
    reference = transaction.get('reference', '')

    if not transaction_id or not reference:
        return Response({'status': 'missing data'}, status=status.HTTP_400_BAD_REQUEST)

    import re

    payment = None

    try:
        payment = Payment.objects.select_related('subscription').get(
            wompi_payment_link_id=reference,
        )
    except Payment.DoesNotExist:
        pass

    if payment is None:
        match = re.match(r'^PA(\d+)P\d+T\d+$', reference)
        if match:
            try:
                payment = Payment.objects.select_related('subscription').get(id=int(match.group(1)))
            except Payment.DoesNotExist:
                pass

    if payment is None:
        try:
            payment = Payment.objects.select_related('subscription').get(id=int(reference))
        except (ValueError, Payment.DoesNotExist):
            pass

    if payment is None:
        logger.warning('Wompi webhook — payment not found for reference=%s', reference)
        return Response({'status': 'payment not found'}, status=status.HTTP_404_NOT_FOUND)

    from accounts.models import PaymentHistory
    from accounts.services.payment_history import record_payment_status_change

    payment.wompi_transaction_id = str(transaction_id)

    if transaction_status == 'APPROVED':
        _handle_payment_approved(payment, PaymentHistory.SOURCE_WEBHOOK)
    elif transaction_status in ('DECLINED', 'ERROR', 'VOIDED'):
        old_status = payment.status
        payment.status = Payment.STATUS_FAILED
        payment.save(update_fields=['wompi_transaction_id', 'status'])
        record_payment_status_change(
            payment, old_status, Payment.STATUS_FAILED, PaymentHistory.SOURCE_WEBHOOK,
        )
    else:
        payment.save(update_fields=['wompi_transaction_id'])

    return Response({'status': 'ok'})


# ==========================================================================
# Cover Gallery
# ==========================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cover_gallery_view(request):
    """List cover gallery categories and images."""
    import os
    from django.conf import settings

    gallery_dir = os.path.join(settings.STATICFILES_DIRS[0], 'cover_gallery')
    if not os.path.isdir(gallery_dir):
        return Response([])

    categories = []
    for category_name in sorted(os.listdir(gallery_dir)):
        category_path = os.path.join(gallery_dir, category_name)
        if not os.path.isdir(category_path):
            continue

        images = []
        for filename in sorted(os.listdir(category_path)):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                continue
            # Build human-readable name from filename
            name_part = filename.rsplit('.', 1)[0]
            # Remove imgi_XX_ prefix
            parts = name_part.split('_', 2)
            display_name = parts[2] if len(parts) > 2 else name_part
            display_name = display_name.replace('_', ' ').title()

            images.append({
                'filename': filename,
                'path': f'{category_name}/{filename}',
                'name': display_name,
                'url': f'{settings.STATIC_URL}cover_gallery/{category_name}/{filename}',
            })

        if images:
            categories.append({
                'name': category_name,
                'images': images,
            })

    return Response(categories)


# ==========================================================================
# Project phases (platform IA refactor)
# ==========================================================================


def _get_project_or_404(project_id, user):
    from accounts.models import Project
    qs = Project.objects.filter(id=project_id)
    profile = getattr(user, 'profile', None)
    if profile and profile.role != 'admin':
        qs = qs.filter(client=user)
    return qs.first()


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def project_phases_view(request, project_id):
    project = _get_project_or_404(project_id, request.user)
    if project is None:
        return Response({'detail': 'project_not_found'}, status=404)
    if request.method == 'GET':
        return Response(ProjectPhaseSerializer(list_phases(project), many=True).data)
    profile = getattr(request.user, 'profile', None)
    if not (profile and profile.is_admin):
        return Response({'detail': 'forbidden'}, status=403)
    proposal_id = request.data.get('proposal_id')
    if not proposal_id:
        return Response({'detail': 'proposal_id required'}, status=400)
    from content.models import BusinessProposal
    proposal = BusinessProposal.objects.filter(id=proposal_id).first()
    if proposal is None:
        return Response({'detail': 'proposal_not_found'}, status=404)
    try:
        phase = add_phase(project, proposal, order=request.data.get('order'))
    except PhaseError as exc:
        return Response({'detail': exc.code, **exc.extra}, status=exc.http_status)
    return Response(ProjectPhaseSerializer(phase).data, status=201)


@api_view(['DELETE', 'PATCH'])
@permission_classes([IsAuthenticated, IsAdminRole])
def project_phase_detail_view(request, project_id, phase_id):
    project = _get_project_or_404(project_id, request.user)
    if project is None:
        return Response({'detail': 'project_not_found'}, status=404)

    if request.method == 'DELETE':
        try:
            remove_phase(project, phase_id)
        except PhaseError as exc:
            return Response({'detail': exc.code, **exc.extra}, status=exc.http_status)
        return Response(status=204)

    # PATCH — update hosting_start_date
    from accounts.models import ProjectPhase
    from accounts.serializers import UpdateProjectPhaseSerializer
    phase = ProjectPhase.objects.filter(pk=phase_id, project=project).first()
    if phase is None:
        return Response({'detail': 'phase_not_found'}, status=404)
    serializer = UpdateProjectPhaseSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    phase.hosting_start_date = serializer.validated_data['hosting_start_date']
    phase.save(update_fields=['hosting_start_date'])

    # Keep Project.hosting_start_date in sync with Phase 1 (used by subscription creation)
    if phase.order == 1:
        project.hosting_start_date = phase.hosting_start_date
        project.save(update_fields=['hosting_start_date'])

    from accounts.serializers import ProjectPhaseSerializer as PhaseSerializer
    return Response(PhaseSerializer(phase).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminRole])
def project_phases_reorder_view(request, project_id):
    project = _get_project_or_404(project_id, request.user)
    if project is None:
        return Response({'detail': 'project_not_found'}, status=404)
    items = request.data
    if not isinstance(items, list):
        return Response({'detail': 'expected_list'}, status=400)
    try:
        reorder_phases(project, items)
    except PhaseError as exc:
        return Response({'detail': exc.code, **exc.extra}, status=exc.http_status)
    return Response(ProjectPhaseSerializer(list_phases(project), many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def client_eligible_proposals_view(request, user_id):
    """Returns 'signed' BusinessProposals (status accepted/finished) for the
    client that are not already attached to any project as a phase."""
    user = User.objects.only('id', 'email').filter(id=user_id).first()
    if user is None:
        return Response({'detail': 'client_not_found'}, status=404)

    from content.models import BusinessProposal
    proposals = BusinessProposal.objects.filter(
        client_email__iexact=user.email,
        status__in=['accepted', 'finished'],
    ).exclude(
        project_phases__isnull=False,
    ).only('id', 'title', 'status', 'total_investment').order_by('-id')

    data = [
        {
            'id': p.id, 'title': p.title, 'status': p.status,
            'total_amount': getattr(p, 'total_investment', None) or 0,
        }
        for p in proposals
    ]
    return Response(data)
