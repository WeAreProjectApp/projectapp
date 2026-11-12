"""Shared authority for panel, platform and administrative MCP access."""
import ipaddress
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.access_models import AccessEvent, AccessRateBucket, GoogleIdentity, LoginChallenge
from accounts.models import UserProfile

User = get_user_model()
GENERIC_NOTICE = 'Si el correo está registrado y habilitado, recibirás un código.'
INVALID_CODE = 'El código no es válido o ha vencido. Solicita uno nuevo.'


def digest(value):
    return salted_hmac('accounts.access.v1', str(value), algorithm='sha256').hexdigest()


def normalized_email(value):
    return (value or '').strip().lower()


def client_ip(request):
    """Only the last hop added by an explicitly trusted proxy may supply IP."""
    remote = request.META.get('REMOTE_ADDR', '')
    if remote in getattr(settings, 'ACCESS_TRUSTED_PROXY_IPS', ()):
        remote = request.META.get('HTTP_X_FORWARDED_FOR', remote).split(',')[-1].strip()
    try:
        return str(ipaddress.ip_address(remote))
    except ValueError:
        return None


def request_device(request):
    return request.META.get('HTTP_USER_AGENT', '')[:200]


def eligible(user, surface):
    return bool(user and user.is_active and hasattr(user, 'profile') and (
        surface == 'platform' or user.is_staff
    ))


def resolve_user(email, surface):
    users = list(User.objects.filter(email__iexact=email).select_related('profile')[:2])
    if len(users) != 1 or not eligible(users[0], surface):
        return None
    return users[0]


def identity_digest(user):
    return digest(f'{user.pk}:{normalized_email(user.email)}:{user.password}:{user.profile.access_version}')


def record_event(user, action, *, actor=None, method='', surface='', request=None):
    return AccessEvent.objects.create(
        user=user, actor=actor, action=action, method=method, surface=surface,
        ip=client_ip(request) if request else None,
        device=request_device(request) if request else '',
    )


@transaction.atomic
def reserve_request(email, ip):
    """Portable shared rolling windows; row locks serialize all application workers."""
    now = timezone.now().timestamp()
    rules = [(f'ip:{digest(ip)}', 30, 0), (f'email:{digest(email)}', 5, 60)]
    buckets = []
    for key, maximum, cooldown in rules:
        bucket, _ = AccessRateBucket.objects.select_for_update().get_or_create(key=key)
        times = [value for value in bucket.requests if value > now - 900]
        if len(times) >= maximum or (times and now - times[-1] < cooldown):
            return False
        buckets.append((bucket, times))
    for bucket, times in buckets:
        bucket.requests = [*times, now]
        bucket.save(update_fields=['requests', 'updated_at'])
    return True


def request_code(*, email, surface, browser, request):
    allowed = reserve_request(email, client_ip(request))
    if not allowed:
        import uuid
        return {'detail': GENERIC_NOTICE, 'challenge_id': str(uuid.uuid4()), 'expires_in': 600, 'retry_after': 60}
    user = resolve_user(email, surface)
    with transaction.atomic():
        if user:
            # User is the mutex, including when no previous challenge exists.
            user = User.objects.select_for_update().select_related('profile').get(pk=user.pk)
            if not eligible(user, surface):
                user = None
        if user:
            LoginChallenge.objects.filter(user=user, closed=False).update(closed=True, code_digest='')
        challenge = LoginChallenge.objects.create(
            user=user, surface=surface, browser_digest=digest(browser),
            identity_digest=identity_digest(user) if user else digest(secrets.token_urlsafe(32)),
            access_version=user.profile.access_version if user else 0,
            expires_at=timezone.now() + timedelta(minutes=10), device=request_device(request),
        )
        from accounts.tasks_access import enqueue_login_code
        transaction.on_commit(lambda: enqueue_login_code(str(challenge.pk)))
    return {'detail': GENERIC_NOTICE, 'challenge_id': str(challenge.pk), 'expires_in': 600, 'retry_after': 60}


def verify_code(*, challenge_id, code, surface, browser):
    # Determine the locking order (User -> challenge) without trusting the caller.
    candidate = LoginChallenge.objects.filter(pk=challenge_id).first()
    if candidate is None:
        raise ValidationError({'detail': INVALID_CODE})
    user = None
    with transaction.atomic():
        if candidate.user_id:
            user = User.objects.select_for_update().select_related('profile').filter(pk=candidate.user_id).first()
        challenge = LoginChallenge.objects.select_for_update().get(pk=challenge_id)
        valid_context = (
            not challenge.closed and challenge.expires_at > timezone.now()
            and challenge.attempts < 5 and challenge.surface == surface
            and constant_time_compare(challenge.browser_digest, digest(browser))
        )
        valid_user = eligible(user, surface) and constant_time_compare(challenge.identity_digest, identity_digest(user))
        accepted = valid_context and valid_user and bool(challenge.code_digest) and constant_time_compare(
            challenge.code_digest, digest(f'{challenge.pk}:{code}'),
        )
        if valid_context:
            challenge.attempts += 1
            if accepted or challenge.attempts >= 5 or not valid_user:
                challenge.closed = True
                challenge.code_digest = ''
            challenge.save(update_fields=['attempts', 'closed', 'code_digest'])
    # Raise outside atomic: failed attempts must commit.
    if not accepted:
        raise ValidationError({'detail': INVALID_CODE})
    return user


@transaction.atomic
def complete_access(user, *, method, surface, request):
    user = User.objects.select_for_update().select_related('profile').get(pk=user.pk)
    if not eligible(user, surface):
        raise PermissionDenied('No pudimos iniciar sesión con esta cuenta.')
    profile = user.profile
    first_access = not profile.is_onboarded
    if first_access:
        user.set_unusable_password()
        user.save(update_fields=['password'])
        profile.refresh_from_db()
    profile.is_onboarded = True
    was_verified = profile.email_verified
    profile.email_verified = True
    profile.email_verified_at = profile.email_verified_at or timezone.now()
    profile.save(update_fields=['is_onboarded', 'email_verified', 'email_verified_at'])
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])
    record_event(user, 'login', method=method, surface=surface, request=request)
    if first_access and profile.is_client:
        from accounts.tasks import notify_team_client_first_login_task
        transaction.on_commit(lambda: notify_team_client_first_login_task(user.pk), robust=True)
    if not was_verified and profile.is_client:
        from accounts.tasks import notify_team_email_validated_task
        transaction.on_commit(lambda: notify_team_email_validated_task(user.pk), robust=True)
    return user


def require_manager(actor, user=None):
    profile = getattr(actor, 'profile', None) if actor else None
    if not actor or not actor.is_active or not (actor.is_staff or (profile and profile.is_admin)):
        raise PermissionDenied('Solo el equipo autorizado puede administrar accesos.')
    if user and (user.is_staff or user.is_superuser or user.profile.role == UserProfile.ROLE_ADMIN) and not actor.is_superuser:
        raise PermissionDenied('Solo un superusuario administra los accesos del equipo.')


@transaction.atomic
def change_access(user_id, *, actor, enabled=None, unlink_google=False):
    require_manager(actor)
    # A stable common mutex protects concurrent attempts to disable the last owner.
    list(User.objects.select_for_update().filter(is_superuser=True).order_by('pk'))
    user = User.objects.select_for_update().select_related('profile').get(pk=user_id)
    require_manager(actor, user)
    if enabled is False:
        if user.pk == actor.pk:
            raise ValidationError('No puedes deshabilitar tu propio acceso.')
        if user.is_superuser and not User.objects.filter(is_superuser=True, is_active=True).exclude(pk=user.pk).exclude(first_name='MCP', email='').exists():
            raise ValidationError('Debe conservarse al menos un superusuario habilitado.')
    if enabled is True:
        email = normalized_email(user.email)
        if not email or email.endswith(UserProfile.PLACEHOLDER_EMAIL_DOMAIN) or User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            raise ValidationError('Registra primero un correo válido y único para esta cuenta.')
    if enabled is not None and user.is_active != enabled:
        user.is_active = enabled
        user.save(update_fields=['is_active'])
        record_event(user, 'enabled' if enabled else 'disabled', actor=actor)
    if unlink_google:
        GoogleIdentity.objects.filter(user=user).delete()
        revoke(user)
        record_event(user, 'google_unlinked', actor=actor)
    user.refresh_from_db()
    return user


def revoke(user):
    from django.db.models import F
    UserProfile.objects.filter(user=user).update(access_version=F('access_version') + 1)
    LoginChallenge.objects.filter(user=user, closed=False).update(closed=True, code_digest='')


def access_payload(user):
    profile = user.profile
    last_method = getattr(user, '_last_method', '')
    if not hasattr(user, '_last_method'):
        last = AccessEvent.objects.filter(user=user, action='login').first()
        last_method = last.method if last else ''
    return {
        'id': user.pk, 'name': user.get_full_name() or user.email, 'email': user.email,
        'company': profile.company_name, 'enabled': user.is_active,
        'team': user.is_staff or user.is_superuser or profile.role == UserProfile.ROLE_ADMIN,
        'onboarded': profile.is_onboarded, 'email_verified': profile.email_verified,
        'google_linked': hasattr(user, 'google_identity'), 'last_login': user.last_login.isoformat() if user.last_login else None,
        'last_method': last_method or '', 'profile_id': profile.pk,
    }


def list_accesses(actor, params):
    require_manager(actor)
    from django.core.paginator import Paginator
    users = User.objects.select_related('profile', 'google_identity').filter(profile__isnull=False).exclude(first_name='MCP', email='')
    team = Q(is_staff=True) | Q(is_superuser=True) | Q(profile__role=UserProfile.ROLE_ADMIN)
    if params.get('group') == 'team':
        if not actor.is_superuser:
            raise PermissionDenied('Solo un superusuario puede consultar el equipo.')
        users = users.filter(team)
    else:
        users = users.exclude(team)
    search = str(params.get('search', ''))[:200].strip()
    if search:
        users = users.filter(Q(email__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(profile__company_name__icontains=search))
    totals = users.aggregate(total=Count('pk'), enabled=Count('pk', filter=Q(is_active=True)), disabled=Count('pk', filter=Q(is_active=False)), pending=Count('pk', filter=Q(profile__is_onboarded=False)))
    counts = {'all': totals['total'], 'enabled': totals['enabled'], 'disabled': totals['disabled'], 'pending': totals['pending']}
    for key, lookup in [('enabled', 'is_active'), ('onboarded', 'profile__is_onboarded'), ('verified', 'profile__email_verified'), ('google', 'google_identity__isnull')]:
        values = str(params.get(key, '')).split(',')
        if values in (['true'], ['false']):
            value = values[0] == 'true'
            users = users.filter(**{lookup: not value if key == 'google' else value})
    if params.get('last_access') == 'never':
        users = users.filter(last_login__isnull=True)
    elif params.get('last_access') in ('7', '30'):
        users = users.filter(last_login__gte=timezone.now() - timedelta(days=int(params['last_access'])))
    order = {'name': 'first_name', 'email': 'email', 'recent': '-last_login'}.get(params.get('order'), 'email')
    page = Paginator(users.order_by(order, 'pk'), 20).get_page(params.get('page', 1))
    from django.db.models import OuterRef, Subquery
    last_method = AccessEvent.objects.filter(user_id=OuterRef('pk'), action='login').values('method')[:1]
    page.object_list = page.object_list.annotate(_last_method=Subquery(last_method))
    data = [access_payload(user) for user in page]
    return {'results': data, 'count': page.paginator.count, 'page': page.number, 'pages': page.paginator.num_pages, 'counts': counts, 'can_manage_team': actor.is_superuser}
