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

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        from accounts.services.platform_features import profile_queryset, values_from_profile
        profile = profile_queryset().filter(user_id=user.pk).first()
        if profile is None or validated_token.get('access_version', 0) != profile.access_version:
            raise InvalidToken('El acceso fue revocado. Inicia sesión de nuevo.')
        user._state.fields_cache['profile'] = profile
        user._platform_feature_values = values_from_profile(profile)
        return user
