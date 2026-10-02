"""Admin total display after public calculator retirement."""
from decimal import Decimal

import pytest
from django.urls import reverse

from content.models import BusinessProposal, ProposalSection

pytestmark = pytest.mark.django_db


def test_list_uses_manual_total_despite_legacy_module_selection(admin_client):
    """Falla si el listado administrativo vuelve a sumar un porcentaje histórico."""
    proposal = BusinessProposal.objects.create(
        title='Alcance legado',
        client_name='Cliente',
        status='sent',
        total_investment=Decimal('1000.00'),
        selected_modules=['module-extra'],
    )
    functional_requirements = ProposalSection.objects.create(
        proposal=proposal,
        section_type=ProposalSection.SectionType.FUNCTIONAL_REQUIREMENTS,
        title='Alcance',
        order=0,
        content_json={'groups': [], 'additionalModules': []},
    )
    ProposalSection.objects.filter(pk=functional_requirements.pk).update(
        content_json={
            'groups': [],
            'additionalModules': [{
                'id': 'extra',
                'is_calculator_module': True,
                'price_percent': 40,
            }],
        },
    )

    response = admin_client.get(reverse('list-proposals'))

    item = next(row for row in response.data if row['id'] == proposal.id)
    assert response.status_code == 200
    assert item['total_investment'] == '1000.00'
    assert item['effective_total_investment'] == '1000.00'
