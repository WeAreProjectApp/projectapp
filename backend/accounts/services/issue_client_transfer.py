"""Preserve ticket history when a project's client relationship is changed."""
from accounts.services.delivery_access import DeliveryConflict
from accounts.services.project_client_transfer import (
    ISSUE_CODE,
    ISSUE_MESSAGE,
    client_transfer_blockers,
)


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
    evaluation = client_transfer_blockers(project, new_client, lock=True)
    if any(row['code'] == ISSUE_CODE for row in evaluation['blockers']):
        error = DeliveryConflict({'detail': ISSUE_MESSAGE, 'code': ISSUE_CODE})
        error.detail.update(evaluation)
        raise error
