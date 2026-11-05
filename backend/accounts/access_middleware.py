"""Django sessions share the account revocation version with platform JWTs."""
import re
from django.contrib.auth import logout


class AccessVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            if profile:
                version = request.session.get('access_version')
                if version is None:
                    # Native password login rotates CSRF; user_logged_in stamps version.
                    version = 0
                if version != profile.access_version:
                    logout(request)
        response = self.get_response(request)
        path = re.sub(r'^/[a-z]{2}(?:-[a-z]{2})?(?=/)', '', request.path).rstrip('/')
        if path in ('/panel/login', '/platform/login', '/admin/login'):
            response['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'
        return response
