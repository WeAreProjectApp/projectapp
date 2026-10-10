"""Keep the previous client's frozen delivery history under its owner."""
from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.models import Project
from accounts.services.delivery_access import DeliveryConflict, require_admin
from accounts.services.project_client_transfer import (
    DELIVERY_CODE,
    DELIVERY_MESSAGE,
    client_transfer_blockers,
)


def assert_delivery_client_transfer_safe(project, new_client, *, actor=None):
    """Return the locked current project or reject before any transfer writes.

    Both service and Django Admin callers must hold their surrounding write
    transaction. This nested transaction retains its lock until that ends.
    The optional actor lets an authenticated service enforce its admin boundary.
    """
    if actor is not None:
        require_admin(actor)
    with transaction.atomic():
        current = Project.objects.select_for_update().select_related('client').get(pk=project.pk)
        if current.client_id != project.client_id:
            raise DeliveryConflict('El cliente del proyecto cambió. Revisa el propietario actual antes de continuar.')
        if current.client_id == new_client.pk:
            return current
        evaluation = client_transfer_blockers(current, new_client, lock=True)
        if any(row['code'] == DELIVERY_CODE for row in evaluation['blockers']):
            error = ValidationError({'detail': DELIVERY_MESSAGE, 'code': DELIVERY_CODE})
            error.detail.update(evaluation)
            raise error
        return current
