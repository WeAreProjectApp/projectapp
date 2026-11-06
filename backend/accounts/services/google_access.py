"""Verify Google identity, then match an already authorized local account."""
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import PermissionDenied

from accounts.access_models import GoogleIdentity
from accounts.services.access import digest, resolve_user


def verify_google(credential, nonce, surface):
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token
    client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
    if not client_id:
        raise PermissionDenied('El acceso con Google no está disponible.')
    try:
        from functools import partial
        payload = id_token.verify_oauth2_token(credential, partial(Request(), timeout=5), client_id)
    except Exception:
        raise PermissionDenied('No pudimos verificar la cuenta de Google.') from None
    email = payload.get('email', '').strip().lower()
    if (
        payload.get('iss') not in ('accounts.google.com', 'https://accounts.google.com')
        or payload.get('email_verified') is not True or not payload.get('sub')
        or not nonce or not constant_time_compare(digest(payload.get('nonce', '')), nonce)
        or not (email.endswith('@gmail.com') or payload.get('hd'))
    ):
        raise PermissionDenied('No pudimos iniciar sesión con esta cuenta.')
    with transaction.atomic():
        user = resolve_user(email, surface)
        if user is None:
            raise PermissionDenied('No pudimos iniciar sesión con esta cuenta.')
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.select_for_update().select_related('profile').get(pk=user.pk)
        from accounts.services.access import eligible
        if not eligible(user, surface) or user.email.strip().lower() != email:
            raise PermissionDenied('No pudimos iniciar sesión con esta cuenta.')
        identity = GoogleIdentity.objects.filter(user=user).first()
        other = GoogleIdentity.objects.filter(subject=payload['sub']).exclude(user=user).exists()
        if other or (identity and identity.subject != payload['sub']):
            raise PermissionDenied('La vinculación de Google necesita revisión del equipo.')
        if identity is None:
            try:
                with transaction.atomic():
                    GoogleIdentity.objects.create(user=user, subject=payload['sub'])
            except IntegrityError:
                raise PermissionDenied('La vinculación de Google necesita revisión del equipo.') from None
    return user
