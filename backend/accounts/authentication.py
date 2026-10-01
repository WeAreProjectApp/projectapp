"""JWT authentication for complete platform sessions."""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class SessionJWTAuthentication(JWTAuthentication):
    """Keep challenge tokens confined to their explicit verification endpoints."""

    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        if 'purpose' in token.payload:
            raise InvalidToken('Este token no permite acceder a una sesión.')
        return token
