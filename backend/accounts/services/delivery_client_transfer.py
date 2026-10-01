"""Keep the previous client's frozen delivery history under its owner."""
from django.db import transaction
from django.db.models import Q

from accounts.models import (
    ContractAmendment, ContractSignatureEvidence, DeliveryMessage, DeliveryPromptContext,
    DeliveryPublication, Project, ProjectContract,
)
from accounts.services.delivery_access import DeliveryConflict, fail, require_admin


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
        frozen = (
            DeliveryPublication.objects.filter(stage__phase__scope__contract__project=current).exists()
            or DeliveryPromptContext.objects.filter(project=current).exists()
            or ContractSignatureEvidence.objects.filter(
                Q(contract__project=current) | Q(amendment__contract__project=current),
            ).exists()
            or ProjectContract.objects.filter(project=current, document__signed_at__isnull=False).exists()
            or ContractAmendment.objects.filter(contract__project=current, document__signed_at__isnull=False).exists()
            or DeliveryMessage.objects.filter(project=current, is_internal=False).exists()
        )
        if frozen:
            fail('Este proyecto conserva entregas, firmas, fuentes o conversaciones del cliente actual. '
                 'No puedes transferirlo a otra persona porque expondría esa historia. '
                 'Crea un proyecto separado para el nuevo cliente.', 'delivery_client_history_frozen')
        return current
