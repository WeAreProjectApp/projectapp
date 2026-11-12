from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

from .models import RuntimeCredential


class RuntimeAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if len(parts) != 2 or parts[0].lower() != b'bearer':
            raise AuthenticationFailed('Credencial de recepción requerida.')
        try:
            digest = RuntimeCredential.hash_token(parts[1].decode('ascii'))
        except UnicodeDecodeError:
            raise AuthenticationFailed('Credencial inválida.') from None
        credential = RuntimeCredential.objects.filter(token_hash=digest, revoked_at__isnull=True).first()
        if credential is None:
            raise AuthenticationFailed('Credencial inválida o revocada.')
        return None, credential

    def authenticate_header(self, request):
        return 'Bearer'


class HasRuntimeCredential(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, RuntimeCredential) and request.auth.revoked_at is None
