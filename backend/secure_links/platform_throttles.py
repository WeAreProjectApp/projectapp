from rest_framework.throttling import UserRateThrottle


class PlatformSecureLinkCreateThrottle(UserRateThrottle):
    scope = 'platform_secure_link_create'
    rate = '10/hour'

    def allow_request(self, request, view):
        return request.method != 'POST' or super().allow_request(request, view)


class PlatformSecureLinkURLThrottle(UserRateThrottle):
    scope = 'platform_secure_link_url'
    rate = '30/minute'
