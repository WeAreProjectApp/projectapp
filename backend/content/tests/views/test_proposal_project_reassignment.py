"""HTTP validation for administrative proposal project corrections."""
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_reassignment_rejects_a_non_object_json_payload(admin_client, proposal):
    """Fails if a JSON array reaches the reassignment service as though it were a correction object."""
    response = admin_client.post(
        reverse('proposal-project-reassignment', kwargs={'proposal_id': proposal.pk}),
        ['not', 'a', 'reassignment', 'object'],
        format='json',
    )

    assert response.status_code == 400
    assert 'non_field_errors' in response.data


@pytest.mark.django_db
@pytest.mark.parametrize(
    'params', ({}, {'target_project_id': 0}, {'target_project_id': 'not-an-integer'}),
    ids=('missing', 'zero', 'text'),
)
def test_reassignment_preview_requires_a_positive_target_project_id(admin_client, proposal, params):
    """Fails if an invalid target project identifier reaches reassignment preview work."""
    response = admin_client.get(
        reverse('proposal-project-reassignment', kwargs={'proposal_id': proposal.pk}), params,
    )

    assert response.status_code == 400
    assert 'target_project_id' in response.data
