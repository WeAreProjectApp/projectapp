"""Local example identity and reproducible business timestamps.

Tokens and ciphertext intentionally remain cryptographically random. They are
never part of the reproducibility contract or printed by the seeder.
"""
from datetime import timedelta

from django.db.models import Q

from content.fake_data import ensure_fake_data_allowed
from secure_links.models import SecureLink, SecureLinkEvent, SecureLinkFolder

PANEL_PREFIX = '[Demo] Enlace QA '
PLATFORM_TITLES = Q(title__startswith='Demo 1 — ') | Q(title__startswith='Demo 2 — ')


def stamp_link(link, context, state):
    now = context.anchor_now
    values = {
        'created_at': now - timedelta(days=2), 'updated_at': now,
        'expires_at': now + timedelta(days=link.validity_days),
        'sent_at': now - timedelta(days=1) if state == 'sent' and not link.team_only else None,
        'consumed_at': now if state in {'opened', 'consumed'} else None,
        'revoked_at': now if state == 'revoked' else None,
    }
    if state == 'expired':
        values['expires_at'] = now - timedelta(days=1)
    SecureLink.objects.filter(pk=link.pk).update(**values)
    SecureLinkEvent.objects.filter(link=link).update(created_at=now)


def clear_fake_secure_links():
    ensure_fake_data_allowed('clear_fake_secure_links')
    SecureLink.objects.filter(title__startswith=PANEL_PREFIX).delete()
    SecureLink.objects.filter(PLATFORM_TITLES, project__name__startswith='Secure links demo ').delete()
    # Only the four manual folders owned by this seeder are retired here.
    # Independent links are returned to root, not deleted with a demo folder.
    folders = SecureLinkFolder.objects.filter(
        name__in=('[Demo] Enlaces propios', '[Demo] Proveedores',
                  '[Demo] Archivo de enlaces', '[Demo] Historial'),
        project__isnull=True, managed_project__isnull=True,
    )
    ids = list(folders.values_list('pk', flat=True))
    SecureLink.objects.filter(folder_id__in=ids).update(folder=None, archived_via_folder=None)
    SecureLinkFolder.objects.filter(parent_id__in=ids).exclude(pk__in=ids).update(parent=None)
    while folders.filter(children__isnull=True).exists():
        folders.filter(children__isnull=True).delete()
