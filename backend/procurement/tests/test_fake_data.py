"""Safety and useful-output coverage for procurement example-data generation."""

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings
from procurement.models import Alert, Opportunity

pytestmark = pytest.mark.django_db


@override_settings(FAKE_DATA_ALLOWED=False)
def test_fake_procurement_command_refuses_before_creating_examples(staff_user):
    """Falla si la semilla de demostración escribe oportunidades cuando el guard de fake data está apagado."""
    with pytest.raises(CommandError, match='FAKE_DATA_ALLOWED=True'):
        call_command('create_fake_procurement', '--count', '4', verbosity=0)

    assert Opportunity.objects.count() == 0


@override_settings(FAKE_DATA_ALLOWED=True)
def test_fake_procurement_command_creates_inactive_alerts_without_real_delivery(staff_user):
    """Falla si los ejemplos no son utilizables o dejan una alerta activa que pueda enviar correo."""
    call_command('create_fake_procurement', '--count', '4', verbosity=0)

    assert Opportunity.objects.filter(source_id__startswith='DEMO.SECOP.').count() == 4
    assert Alert.objects.get(name='Oportunidades software · ejemplo').is_active is False
