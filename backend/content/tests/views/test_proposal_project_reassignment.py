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
