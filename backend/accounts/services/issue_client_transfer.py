"""Preserve ticket history when a project's client relationship is changed."""
from accounts.models import BugReport, ChangeRequest, Project
from accounts.services.delivery_access import DeliveryConflict


def assert_issue_client_transfer_safe(project, new_client):
    """Allow an unchanged owner or a project without any ticket history.

    ``new_client`` is the target User (not a UserProfile), or None. The stored
    owner is read from the database because a form may already have replaced
    ``project.client`` in memory. Apply callers must hold the project row lock
    until save; ticket creation uses the same lock. Archived reports and staff
    authors count as history too: neither changes its historical recipient.

    Raise DeliveryConflict (409), code ``issue_client_transfer_history``, when
    reassignment would let another client read the previous owner's tickets.
    This guard does not rewrite, detach, archive or delete anything.
    """
    if project.pk is None:
        return
    owner_id = Project.objects.values_list('client_id', flat=True).get(pk=project.pk)
    if owner_id == (new_client.pk if new_client is not None else None):
        return
    if (BugReport.objects.filter(project_id=project.pk).exists()
            or ChangeRequest.objects.filter(project_id=project.pk).exists()):
        raise DeliveryConflict({
            'detail': 'El proyecto conserva bugs o solicitudes del cliente actual. '
                      'Cambiar de cliente expondría esa historia.',
            'code': 'issue_client_transfer_history',
        })
