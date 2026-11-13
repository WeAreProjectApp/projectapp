"""Shared setup and payload helpers for requirement package behavior tests."""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from content.models import HourPackage
from content.services import requirement_calculator
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import ChangeRequest, Project, UserProfile
from accounts.models_requirement_packages import (
    PackageMovement,
    PackageOrder,
    PackageRequest,
)
from accounts.services import package_requests

User = get_user_model()


@pytest.fixture
def package_context():
    """Create one client project, a platform admin and an XS package catalog row."""
    client = User.objects.create_user('package-client', email='package-client@example.test')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT)
    admin = User.objects.create_user('package-admin', email='package-admin@example.test')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN)
    project = Project.objects.create(name='Requirement package project', client=client)
    package = HourPackage.objects.create(
        nationality='COL', pricing_model='requirements', name_es='Paquete XS', name_en='XS package',
        xs_count=1, s_count=0, m_count=0, validity_months=12, discount_percent=0,
    )
    return SimpleNamespace(client=client, admin=admin, project=project, package=package)


def paid_order(context, *, expires_at=None):
    """Create a paid XS package with one available allowance for the context client."""
    order = PackageOrder.objects.create(
        project=context.project, client=context.client, package=context.package,
        snapshot={'counts': {'XS': 1, 'S': 0, 'M': 0}, 'validity_months': 12, 'language': 'es'},
        currency='COP', subtotal=Decimal(100), tax_rate=Decimal(0), total=Decimal(100),
        method='external', status='paid', paid_at=timezone.now(),
        expires_at=expires_at or timezone.now() + timedelta(days=30), recorded_by=context.admin,
    )
    PackageMovement.objects.create(order=order, size='XS', quantity=1, kind='credit', actor=context.admin)
    return order


def request_row(context):
    """Create a pending package request attached to an owned change request."""
    ticket = ChangeRequest.objects.create(
        project=context.project, created_by=context.client, title='Actualizar tablero', description='Mostrar una métrica.',
    )
    return PackageRequest.objects.create(project=context.project, client=context.client, ticket=ticket)


def publish_calculator(context):
    """Publish the calculator definition required to record an administrative proposal."""
    definition = requirement_calculator.seed_definition()
    return requirement_calculator.publish(
        definition, note='Definición para probar paquetes', if_match='uninitialized', actor=context.admin,
    )


def offer_xs(context, row, *, request_id=None, size='XS', warranty=False):
    """Publish a deterministic package sizing proposal for one request."""
    state = requirement_calculator.overview()['definition']
    signal = next(item['id'] for item in state['signals'] if item['size'] == size)
    return package_requests.publish_proposal(context.project.pk, context.admin, row.pk, {
        'request_id': request_id or uuid4(), 'expected_version': row.version, 'size': size,
        'scope': 'Agregar una métrica al tablero existente.', 'explanation': 'Aprovecha una vista existente.',
        'assumptions': '', 'delivery_from': '2026-11-12', 'delivery_until': '2026-11-14',
        'schedule_conditions': '', 'signal_ids': [signal], 'warranty': warranty, 'language': 'es',
    })


def decision_data(row, *, order_id, proposal_id=None, version=None):
    """Build a fresh client acceptance payload for the request's current proposal."""
    return {
        'request_id': uuid4(), 'expected_version': row.version if version is None else version,
        'proposal_id': row.current_proposal_id if proposal_id is None else proposal_id,
        'decision': 'accept', 'message': '', 'order_id': order_id,
    }
