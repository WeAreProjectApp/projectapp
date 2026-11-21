import secrets

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction


def is_service_actor(actor):
    return actor.first_name == 'MCP' and not actor.has_usable_password()


def service_actor_for_connector(connector):
    """Return a non-interactive Django actor for auditable MCP writes."""
    User = get_user_model()
    linked_actor = (
        User.objects
        .filter(mcp_credentials__connector=connector)
        .distinct()
        .order_by('pk')
        .first()
    )
    if linked_actor is not None and is_service_actor(linked_actor):
        actor = linked_actor
        created = False
    else:
        max_length = User._meta.get_field(User.USERNAME_FIELD).max_length
        base_username = f'mcp_{connector.slug.replace("-", "_")}'
        actor = None
        for attempt in range(5):
            suffix = '' if attempt == 0 else f'_{secrets.token_hex(3)}'
            username = f'{base_username[:max_length - len(suffix)]}{suffix}'
            if User.objects.filter(username=username).exists():
                continue
            candidate = User(
                username=username,
                is_active=True,
                is_staff=True,
                is_superuser=True,
                first_name='MCP',
                last_name=connector.name[:150],
            )
            candidate.set_unusable_password()
            try:
                with transaction.atomic():
                    candidate.save(force_insert=True)
            except IntegrityError:
                continue
            actor = candidate
            break
        if actor is None:
            raise RuntimeError(
                f'No fue posible reservar un principal técnico para {connector.slug}.'
            )
        created = True

    changed = []
    for field, value in (
        ('is_active', True),
        ('is_staff', True),
        ('is_superuser', True),
    ):
        if getattr(actor, field) != value:
            setattr(actor, field, value)
            changed.append(field)
    if created:
        return actor
    if changed:
        actor.save(update_fields=changed)
    return actor
