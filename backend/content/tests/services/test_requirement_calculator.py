"""Calculator rules and client agreements retain their effective definitions."""
import uuid
from copy import deepcopy
from decimal import Decimal

import pytest
from accounts.models import Project, UserProfile
from rest_framework.exceptions import ValidationError

from content.models import (
    CalculatorRevision,
    Document,
    DocumentType,
    HourPackageSettings,
    ProjectCalculatorVersion,
)
from content.services import calculator_calibration as calibration
from content.services import requirement_calculator as calculator
from content.services.document_pdf_service import DocumentPdfService

pytestmark = pytest.mark.django_db


@pytest.fixture
def calculator_admin(django_user_model):
    return django_user_model.objects.create_user(username='calculator-admin', is_staff=True)


@pytest.fixture
def calculator_state(calculator_admin):
    DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown'})
    config = calculator.seed_definition()
    config['signals'] = [next(row for row in config['signals'] if row['size'] == size) for size in ('XS', 'S', 'M', 'L', 'XL', 'PROJECT')]
    config['families'] = config['families'][:1]
    config['modifiers'] = config['modifiers'][:2]
    return calculator.publish(config, note='Initial definition',
                              if_match='uninitialized', actor=calculator_admin)


@pytest.fixture
def calculator_project(django_user_model):
    owner = django_user_model.objects.create_user(username='calculator-owner')
    UserProfile.objects.get_or_create(user=owner, defaults={'role': 'client'})
    return Project.objects.create(name='Calculator project', client=owner)


@pytest.fixture
def project_draft(calculator_state, calculator_project, calculator_admin):
    return calculator.create_project_draft(calculator_project.pk,
        base_revision_id=calculator_state['revision_id'], note='Negotiated version',
        if_match=calculator.project_overview(calculator_project.pk)['if_match'], actor=calculator_admin)


def test_publishing_updates_shared_size_price(calculator_state, calculator_admin):
    config = deepcopy(calculator_state['definition'])
    config['sizes'][0]['standard_value_cop'] = '62000'

    calculator.publish(config, note='Adjust XS', if_match=calculator_state['if_match'], actor=calculator_admin)

    assert HourPackageSettings.load().xs_price_cop == Decimal(62000)


def test_publishing_rejects_stale_definition(calculator_state, calculator_admin):
    calculator.publish(calculator_state['definition'], note='New revision',
                       if_match=calculator_state['if_match'], actor=calculator_admin)

    with pytest.raises(calculator.CalculatorConflict):
        calculator.publish(calculator_state['definition'], note='Stale edit',
                           if_match=calculator_state['if_match'], actor=calculator_admin)

    assert CalculatorRevision.objects.count() == 2


def test_project_draft_rejects_body_changes(project_draft, calculator_admin):
    config = deepcopy(project_draft['definition'])
    config['methodology'] = 'Replace the agreed methodology'

    with pytest.raises(ValidationError, match='parámetros'):
        calculator.update_project_draft(project_draft['id'], definition=config, note='Attempt body edit',
                                        if_match=project_draft['if_match'], actor=calculator_admin)

    assert ProjectCalculatorVersion.objects.get(pk=project_draft['id']).digest == project_draft['digest']


def test_project_draft_preserves_original_base(calculator_state, project_draft, calculator_admin):
    config = deepcopy(calculator_state['definition'])
    config['sizes'][0]['definition'] = 'A new general definition'

    calculator.publish(config, note='New explanation', if_match=calculator_state['if_match'], actor=calculator_admin)

    version = ProjectCalculatorVersion.objects.get(pk=project_draft['id'])
    assert version.definition['sizes'][0]['definition'] == project_draft['definition']['sizes'][0]['definition']


def test_approval_preserves_pdf_after_general_change(calculator_state, project_draft, calculator_admin):
    """The real renderer must retain the exact client PDF across global changes."""
    approved = calculator.approve_project_version(project_draft['id'], note='Agreed',
                if_match=project_draft['if_match'], actor=calculator_admin)
    document = Document.objects.get(pk=approved['document_id'])
    original = DocumentPdfService.generate(document)
    config = deepcopy(calculator_state['definition'])
    config['sizes'][0]['points'] = '1.5'

    calculator.publish(config, note='New points', if_match=calculator_state['if_match'], actor=calculator_admin)

    document.refresh_from_db()
    assert DocumentPdfService.generate(document) == original
    assert original.startswith(b'%PDF-')
    assert 'Horas' not in document.content_markdown


def test_generic_document_save_rejects_calculator_body(calculator_state):
    document = Document.objects.get(pk=calculator_state['document_id'])
    document.content_markdown = 'Changed outside calculator'

    with pytest.raises(ValidationError, match='Calculadora'):
        document.save()

    document.refresh_from_db()
    assert document.content_markdown.startswith('# Calculadora de requerimientos')


def test_unassigned_project_context_warns(calculator_state, calculator_project):
    context = calculator.calculator_context(project_id=calculator_project.pk)

    assert context['revision_id'] == calculator_state['revision_id']
    assert 'no tiene calculadora aprobada' in context['warning']


def test_recorded_closure_uses_actual_cost(calculator_state, calculator_admin):
    config = calculator_state['definition']
    signal = next(row for row in config['signals'] if row['size'] == 'XS')
    estimate = calibration.record_estimate({
        'request_id': uuid.UUID('ae391ea0-b14f-43fb-9aa6-5dc533b57181'), 'revision_id': calculator_state['revision_id'],
        'definition_digest': calculator.digest(config), 'requirement': 'Adjust an existing field',
        'size': 'XS', 'signal_ids': [signal['id']], 'explanation': 'Existing field adjustment.',
    }, actor=calculator_admin)

    calibration.record_actual({'estimate_id': estimate['id'], 'actual_hours': Decimal(2),
        'hourly_cost_cop': Decimal(30000), 'evidence': 'Confirmed execution log', 'cause': 'Delivered scope'}, actor=calculator_admin)

    cohort = calibration.report()['cohorts'][0]
    assert cohort['median_cost_cop'] == '60000.0000'
    assert cohort['covers_median_cost'] is False
    assert cohort['status'] == 'insufficient_data'
