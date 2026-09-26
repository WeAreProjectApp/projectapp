"""Per-IP limits for the anonymous secure-link endpoints.

Rates are hardcoded like ``content/throttles.py`` so no settings edit is
needed. Authenticated staff are exempt (AnonRateThrottle only counts
anonymous requests).
"""

from rest_framework.throttling import AnonRateThrottle


class SecureLinkCreateThrottle(AnonRateThrottle):
    """Public creation writes encrypted rows and emails the team."""

    scope = 'secure-link-create'

    def get_rate(self):
        return '10/hour'


class SecureLinkAccessThrottle(AnonRateThrottle):
    """Status and reveal lookups; tokens are unguessable, this caps noise."""

    scope = 'secure-link-access'

    def get_rate(self):
        return '30/min'
