"""Impersonation ("Log in as this user") service.

Centralizes the rules and token minting shared by the Django admin button and
the panel DRF endpoint, so both surfaces enforce the exact same policy.

Tokens are never placed on a URL. Instead the backend mints them, stores them
behind a short-lived single-use exchange code, and the frontend callback POSTs
that code to swap it for the real tokens.
"""
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.services.tokens import get_tokens_for_user

EXCHANGE_CODE_TTL_SECONDS = 60
EXCHANGE_CODE_PREFIX = 'impersonation:exchange:'
EXCHANGE_CODE_CLAIM_PREFIX = 'impersonation:exchange-claim:'


class ImpersonationError(Exception):
    """Business rule violation while trying to impersonate a user.

    ``status_code`` lets the DRF endpoint return the right HTTP status; the
    Django admin surfaces ``message`` as a flash error regardless.
    """

    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def impersonate(actor, target):
    """Validate the policy and mint JWT tokens for ``target``.

    Rules (mirror of the fleet base implementation):
    - only active superusers may impersonate,
    - cannot impersonate another superuser (self is allowed),
    - cannot impersonate an inactive user,
    - target must have a platform profile, otherwise the resulting session
      would be unusable on ``/platform/``.

    :returns: ``{'access': ..., 'refresh': ...}``
    :raises ImpersonationError: when any rule is violated.
    """
    if not (actor and actor.is_active and actor.is_superuser):
        raise ImpersonationError(
            'Solo los superusuarios activos pueden iniciar sesión como otro usuario.',
            status_code=403,
        )

    if target.is_superuser and target.pk != actor.pk:
        raise ImpersonationError(
            'No puedes iniciar sesión como otro superusuario.',
            status_code=403,
        )

    if not target.is_active:
        raise ImpersonationError('Este usuario está inactivo.', status_code=400)

    if getattr(target, 'profile', None) is None:
        raise ImpersonationError(
            'Este usuario no tiene un perfil de plataforma.',
            status_code=400,
        )

    refresh = RefreshToken(get_tokens_for_user(target)['refresh'])
    # Keep administrator access distinguishable after token refresh. Viewing
    # the portal as a client must never create the client's signature/review.
    refresh['impersonated_by'] = actor.pk
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


def create_exchange_code(tokens):
    """Store ``tokens`` behind a random opaque code with a short TTL.

    The code is the only thing that travels on the callback URL; it is
    single-use (consumed on exchange) and expires automatically.
    """
    code = secrets.token_urlsafe(32)
    cache.set(f'{EXCHANGE_CODE_PREFIX}{code}', tokens, timeout=EXCHANGE_CODE_TTL_SECONDS)
    return code


def consume_exchange_code(code):
    """Return the tokens bound to ``code`` and invalidate it (single-use).

    :returns: the tokens dict, or ``None`` if the code is missing/expired/used.
    """
    if not code:
        return None
    key = f'{EXCHANGE_CODE_PREFIX}{code}'
    tokens = cache.get(key)
    if tokens is None:
        return None
    # Keep the claim for the code's entire lifetime: overlapping readers may
    # already hold the tokens even after the winning consumer deletes the code.
    claimed = cache.add(
        f'{EXCHANGE_CODE_CLAIM_PREFIX}{code}',
        True,
        timeout=EXCHANGE_CODE_TTL_SECONDS,
    )
    if not claimed:
        return None
    # A reader can resume after the earlier claim expired. Check the live code
    # under this claim so it cannot return a payload read before consumption.
    tokens = cache.get(key)
    if tokens is None:
        return None
    cache.delete(key)
    return tokens


def build_impersonation_redirect_url(code, redirect_path='/platform'):
    """Build the absolute frontend callback URL carrying only the exchange code.

    The i18n strategy is ``prefix``, so the locale segment is always present.
    """
    base = settings.FRONTEND_BASE_URL.rstrip('/')
    locale = getattr(settings, 'FRONTEND_DEFAULT_LOCALE', 'en-us')
    query = urlencode({'code': code, 'redirect': redirect_path})
    return f'{base}/{locale}/platform/admin-login?{query}'
