from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from procurement.models import Alert, Opportunity


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(
        username='procurement-staff', password='test-password', is_staff=True,
    )


@pytest.fixture
def other_staff_user(db):
    return get_user_model().objects.create_user(
        username='procurement-other-staff', password='test-password', is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    return get_user_model().objects.create_user(
        username='procurement-regular', password='test-password', is_staff=False,
    )


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def regular_client(regular_user):
    client = APIClient()
    client.force_authenticate(user=regular_user)
    return client


@pytest.fixture(params=['anonymous', 'regular', 'csrf_staff'])
def prohibited_procurement_client(request, regular_client, staff_user):
    """Supply each client class that must not mutate procurement tracking."""
    if request.param == 'anonymous':
        return APIClient()
    if request.param == 'regular':
        return regular_client
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(staff_user)
    return client


@pytest.fixture
def opportunity(db):
    def create(source_id, **changes):
        values = {
            'reference': f'REF-{source_id}',
            'title': f'Proceso {source_id}',
            'description': 'Descripción de contratación estatal.',
            'entity_name': 'Entidad Nacional',
            'department': 'Bogotá D.C.',
            'method': 'Licitación pública',
            'contract_type': 'Servicios',
            'source_status': 'Abierto',
            'budget': Decimal('100000.00'),
            'unspsc_code': '80101500',
        }
        values.update(changes)
        return Opportunity.objects.create(source_id=source_id, **values)
    return create


@pytest.fixture
def many_opportunities(db):
    def create(amount, *, description):
        return Opportunity.objects.bulk_create([
            Opportunity(
                source_id=f'BULK-{position}', reference=f'BULK-REF-{position}',
                title=f'Proceso masivo {position}', description=description,
                entity_name='Entidad Nacional', department='Bogotá D.C.',
                method='Licitación pública', contract_type='Servicios',
                source_status='Abierto', budget=Decimal('100000.00'), unspsc_code='80101500',
            )
            for position in range(amount)
        ])
    return create


@pytest.fixture
def alert(staff_user):
    def create(**changes):
        values = {
            'name': 'Alertas jurídicas',
            'filters': {},
            'recipients': ['carlos@example.com'],
            'frequency': 'daily',
            'is_active': True,
            'created_by': staff_user,
        }
        values.update(changes)
        return Alert.objects.create(**values)
    return create
