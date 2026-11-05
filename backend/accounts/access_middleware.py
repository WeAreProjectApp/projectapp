"""Django sessions share the account revocation version with platform JWTs."""
import re

from django.contrib.auth import logout

from accounts.models import UserProfile


class AccessVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_profile = UserProfile.objects.filter(
                user_id=request.user.pk,
            ).first()
            session_version = request.session.get('access_version', 0)
            if current_profile is None or session_version != current_profile.access_version:
                logout(request)
            else:
                request.user.profile = current_profile
        response = self.get_response(request)
        path = re.sub(r'^/[a-z]{2}(?:-[a-z]{2})?(?=/)', '', request.path).rstrip('/')
        if path in ('/panel/login', '/platform/login', '/admin/login'):
            response['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'
        return response
