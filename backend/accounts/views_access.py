"""Anonymous login endpoints explicitly enforce CSRF; management uses staff sessions."""
import secrets

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from accounts.access_models import AccessEvent
from accounts.services import access
from accounts.services.tokens import get_tokens_for_user
from accounts.serializers import UserProfileSerializer
from projectapp.recaptcha import CaptchaError, verify_captcha


class AccessInput(serializers.Serializer):
    email = serializers.EmailField(required=False)
    recaptcha_token = serializers.CharField(required=False, max_length=4096, allow_blank=True)
    challenge_id = serializers.UUIDField(required=False)
    code = serializers.RegexField(r'^[0-9]{6}$', required=False)
    credential = serializers.CharField(required=False, max_length=16384)
    next = serializers.CharField(required=False, max_length=2000, allow_blank=True)


def browser_key(request):
    if 'access_browser' not in request.session:
        request.session['access_browser'] = secrets.token_urlsafe(32)
    return request.session['access_browser']


@never_cache
@ensure_csrf_cookie
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def auth_config(request):
    browser_key(request)
    return Response({'csrf_token': get_token(request), 'google_client_id': getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')})


def session_result(request, user, surface, method, data):
    user = access.complete_access(user, method=method, surface=surface, request=request)
    if surface == 'panel':
        request._request._access_login_recorded = True
        login(request._request, user, backend='django.contrib.auth.backends.ModelBackend')
        request.session['access_version'] = user.profile.access_version
        target = data.get('next', '')
        if not url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure()):
            target = '/panel/'
        return Response({'redirect': target})
    return Response({'requires_verification': False, 'tokens': get_tokens_for_user(user), 'user': UserProfileSerializer(user.profile, context={'request': request}).data})


@never_cache
@csrf_protect
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def authenticate_access(request, surface, operation):
    if surface not in ('panel', 'platform'):
        raise ValidationError('Destino de acceso inválido.')
    serializer = AccessInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    browser = browser_key(request)
    if operation in ('email-request', 'google-challenge'):
        try:
            verify_captcha(data.get('recaptcha_token', ''))
        except CaptchaError as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=exc.status)
    if operation == 'email-request':
        if not data.get('email'):
            raise ValidationError({'email': 'Escribe el correo.'})
        return Response(access.request_code(email=access.normalized_email(data['email']), surface=surface, browser=browser, request=request))
    if operation == 'email-verify':
        if not data.get('challenge_id') or not data.get('code'):
            raise ValidationError({'detail': access.INVALID_CODE})
        user = access.verify_code(challenge_id=data['challenge_id'], code=data['code'], surface=surface, browser=browser)
        return session_result(request, user, surface, 'code', data)
    if operation == 'google-challenge':
        if not access.reserve_request(f'google:{browser}', access.client_ip(request)):
            return Response({'detail': 'Espera unos minutos para volver a intentarlo.'}, status=429)
        nonce = secrets.token_urlsafe(32)
        from django.utils import timezone
        from accounts.access_models import LoginChallenge
        from datetime import timedelta
        challenge = LoginChallenge.objects.create(surface=surface, browser_digest=access.digest(browser), identity_digest='', code_digest=access.digest(nonce), expires_at=timezone.now() + timedelta(minutes=5))
        request.session['google_access'] = {'id': str(challenge.pk), 'digest': access.digest(nonce), 'surface': surface, 'expires': timezone.now().timestamp() + 300}
        return Response({'nonce': nonce})
    if operation == 'google-verify':
        from django.utils import timezone
        from accounts.services.google_access import verify_google
        state = request.session.pop('google_access', {})
        if state.get('surface') != surface or state.get('expires', 0) <= timezone.now().timestamp():
            raise PermissionDenied('Vuelve a iniciar la verificación de Google.')
        from accounts.access_models import LoginChallenge
        consumed = LoginChallenge.objects.filter(pk=state.get('id'), closed=False, expires_at__gt=timezone.now(), browser_digest=access.digest(browser)).update(closed=True, code_digest='')
        if consumed != 1:
            raise PermissionDenied('Vuelve a iniciar la verificación de Google.')
        user = verify_google(data.get('credential', ''), state.get('digest'), surface)
        return session_result(request, user, surface, 'google', data)
    raise ValidationError('Operación de acceso inválida.')


class ClientAccessInput(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=150)
    company = serializers.CharField(max_length=200, required=False, allow_blank=True)


class AccessChangeInput(serializers.Serializer):
    enabled = serializers.BooleanField(required=False)
    unlink_google = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if 'enabled' not in attrs and not attrs.get('unlink_google'):
            raise serializers.ValidationError('Selecciona un cambio de acceso.')
        return attrs


@never_cache
@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def access_list(request):
    if request.method == 'GET':
        return Response(access.list_accesses(request.user, request.query_params))
    serializer = ClientAccessInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(create_access_client(request.user, serializer.validated_data), status=201)


def create_access_client(actor, data):
    access.require_manager(actor)
    from accounts.services.proposal_client_service import get_or_create_client_for_proposal
    email = access.normalized_email(data['email'])
    if get_user_model().objects.filter(email__iexact=email).exists():
        raise ValidationError({'email': ['Este correo ya está registrado. Habilita la cuenta existente.']})
    profile = get_or_create_client_for_proposal(name=data['name'], email=email, company=data.get('company', ''))
    access.record_event(profile.user, 'created', actor=actor)
    return access.access_payload(profile.user)


@never_cache
@api_view(['GET', 'PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def access_detail(request, user_id):
    user = get_object_or_404(get_user_model().objects.select_related('profile', 'google_identity'), pk=user_id, profile__isnull=False)
    access.require_manager(request.user, user)
    if request.method == 'PATCH':
        serializer = AccessChangeInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = access.change_access(user_id, actor=request.user, **serializer.validated_data)
    data = access.access_payload(user)
    events = Paginator(AccessEvent.objects.filter(user=user).select_related('actor'), 20).get_page(request.query_params.get('page', 1))
    data['events'] = [{'id': event.pk, 'action': event.action, 'method': event.method, 'surface': event.surface, 'at': event.created_at, 'ip': event.ip, 'device': event.device, 'actor': event.actor.get_full_name() if event.actor else ''} for event in events]
    data['event_pages'] = events.paginator.num_pages
    data['event_page'] = events.number
    return Response(data)

# DRF endpoints are exempt by default; these anonymous endpoints create sessions.
authenticate_access.csrf_exempt = False
