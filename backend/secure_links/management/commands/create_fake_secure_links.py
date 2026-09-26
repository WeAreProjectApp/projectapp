from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from secure_links import services
from secure_links.models import SecureLink

SAMPLES = [
    ('credentials', 'Admin Django producción — demo', {'service': 'Django admin', 'url': 'https://demo.projectapp.co/admin/', 'username': 'admin', 'password': 'demo-Pa55-no-real'}),
    ('api_key', 'Llaves Wompi sandbox — demo', {'service': 'Wompi', 'environment': 'sandbox', 'public_key': 'pub_test_demo', 'secret_key': 'prv_test_demo'}),
    ('server_access', 'SSH staging — demo', {'host': '203.0.113.10', 'port': '22', 'username': 'deploy', 'credential': 'demo-no-real'}),
    ('database', 'MySQL staging — demo', {'engine': 'MySQL', 'host': 'localhost', 'port': '3306', 'name': 'demo', 'username': 'demo', 'password': 'demo-no-real'}),
    ('env_vars', 'Variables .env — demo', {'content': 'DEBUG=False\nSECRET_KEY=demo-no-real'}),
    ('bank_account', 'Cuenta para pagos — demo', {'bank': 'Banco Demo', 'account_type': 'Ahorros', 'account_number': '000-000000-00', 'holder': 'Project App SAS'}),
    ('recovery_codes', 'Códigos 2FA GoDaddy — demo', {'service': 'GoDaddy', 'codes': 'AAAA-1111\nBBBB-2222'}),
    ('confidential_message', 'Comunicado confidencial — demo', {'subject': 'Cambio de dominio', 'message': 'Texto de ejemplo sin información real.'}),
]


class Command(BaseCommand):
    help = 'Crear enlaces seguros de ejemplo exclusivamente en desarrollo.'

    def handle(self, *args, **options):
        if not getattr(settings, 'FAKE_DATA_ALLOWED', False) or getattr(settings, 'IS_PRODUCTION', False):
            raise CommandError('Los datos ficticios no están permitidos en este entorno.')
        now = timezone.now()
        states = ['active', 'consumed', 'expired', 'revoked']
        for index, (secret_type, title, fields) in enumerate(SAMPLES * 3):
            origin = [SecureLink.Origin.PANEL, SecureLink.Origin.MCP, SecureLink.Origin.PUBLIC][index % 3]
            link, _url = services.create_link(
                secret_type=secret_type, title=f'{title} #{index + 1}', fields=fields, origin=origin,
                validity_days=7, creator_name='Cliente demo' if origin == SecureLink.Origin.PUBLIC else '',
            )
            state = states[index % len(states)]
            if state == 'consumed':
                link.consumed_at = now - timedelta(hours=index)
            elif state == 'expired':
                link.expires_at = now - timedelta(days=1)
            elif state == 'revoked':
                link.revoked_at = now - timedelta(hours=index)
            link.save()
        self.stdout.write('Enlaces seguros de ejemplo disponibles.')
