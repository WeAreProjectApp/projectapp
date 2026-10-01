"""Tests for per-section-type content_json schema validation.

Covers the declarative validator (``validate_section_content``) plus its
three wire-in sites: section update serializer, from-JSON serializer, and
default-config serializer.
"""
import pytest

from content.models import BusinessProposal, ProposalSection
from content.serializers.proposal import (
    ProposalDefaultConfigSerializer,
    ProposalFromJSONSerializer,
    ProposalSectionUpdateSerializer,
)
from content.services.section_content_schemas import (
    SECTION_CONTENT_SCHEMAS,
    validate_section_content,
)


class TestGreetingSchema:
    def test_valid_greeting_content_returns_no_errors(self):
        errors = validate_section_content('greeting', {
            'proposalTitle': 'Mi propuesta',
            'clientName': 'María García',
            'inspirationalQuote': 'Design is how it works.',
        })
        assert errors == []

    def test_rejects_non_string_client_name(self):
        errors = validate_section_content('greeting', {'clientName': 123})
        assert errors == ['El campo «greeting.clientName» debe ser texto.']


class TestExecutiveSummarySchema:
    def test_valid_paragraphs_and_highlights(self):
        errors = validate_section_content('executive_summary', {
            'title': 'Resumen',
            'paragraphs': ['Primer párrafo.', 'Segundo párrafo.'],
            'highlightsTitle': 'Incluye',
            'highlights': ['Diseño personalizado'],
        })
        assert errors == []

    def test_rejects_paragraphs_that_is_not_a_list(self):
        errors = validate_section_content(
            'executive_summary', {'paragraphs': 'no soy una lista'},
        )
        assert errors == [
            'El campo «executive_summary.paragraphs» debe ser una lista.'
        ]

    def test_rejects_non_string_paragraph_item_with_index_in_path(self):
        errors = validate_section_content(
            'executive_summary', {'paragraphs': ['ok', 42]},
        )
        assert errors == [
            'El campo «executive_summary.paragraphs[1]» debe ser texto.'
        ]


class TestFunctionalRequirementsSchema:
    def _group(self, **overrides):
        group = {
            'id': 'views',
            'title': 'Vistas',
            'is_always_included': True,
            'is_calculator_module': False,
            'selected': True,
            'is_visible': True,
            'items': [
                {'id': 'item-1', 'name': 'Home', 'price': None, 'is_required': True},
            ],
        }
        group.update(overrides)
        return group

    def test_is_always_included_accepts_boolean_value(self):
        errors = validate_section_content('functional_requirements', {
            'groups': [self._group(is_always_included=True)],
        })
        assert errors == []

    def test_rejects_non_boolean_inclusion_flag_and_item_price(self):
        errors = validate_section_content('functional_requirements', {
            'groups': [self._group(is_always_included='gratis')],
            'additionalModules': [self._group(items=[{'name': 'X', 'price': ['nope']}])],
        })
        assert errors == [
            'El campo «functional_requirements.groups[0].is_always_included» debe ser booleano.',
            'El campo «functional_requirements.additionalModules[0].items[0].price» debe ser numérico.',
        ]

    def test_rejects_non_string_item_name(self):
        errors = validate_section_content('functional_requirements', {
            'groups': [self._group(items=[{'name': 99}])],
        })
        assert errors == [
            'El campo «functional_requirements.groups[0].items[0].name» debe ser texto.'
        ]


class TestInvestmentSchema:
    def test_hosting_percent_numeric_string_passes(self):
        errors = validate_section_content('investment', {
            'totalInvestment': '$3.500.000',
            'hostingPlan': {'hostingPercent': '80'},
        })
        assert errors == []

    def test_free_months_visible_accepts_a_boolean(self):
        errors = validate_section_content('investment', {
            'hostingPlan': {'freeMonths': 2, 'freeMonthsVisible': False},
        })
        assert errors == []

    def test_rejects_non_boolean_free_months_visible(self):
        """A truthy string must not sneak in as a visibility gate."""
        errors = validate_section_content('investment', {
            'hostingPlan': {'freeMonthsVisible': 'si'},
        })
        assert errors == [
            'El campo «investment.hostingPlan.freeMonthsVisible» debe ser booleano.'
        ]

    def test_legacy_hosting_plan_without_the_flag_still_passes(self):
        errors = validate_section_content('investment', {
            'hostingPlan': {'freeMonths': 1, 'freeMonthNote': 'Un mes.'},
        })
        assert errors == []

    def test_rejects_bool_as_numeric_hosting_percent(self):
        errors = validate_section_content('investment', {
            'hostingPlan': {'hostingPercent': True},
        })
        assert errors == [
            'El campo «investment.hostingPlan.hostingPercent» debe ser numérico.'
        ]

    def test_rejects_non_numeric_billing_tier_months(self):
        errors = validate_section_content('investment', {
            'hostingPlan': {
                'billingTiers': [
                    {'months': 12, 'discountPercent': 40},
                    {'months': 'doce', 'discountPercent': {}},
                ],
            },
        })
        assert errors == [
            'El campo «investment.hostingPlan.billingTiers[1].months» debe ser numérico.',
            'El campo «investment.hostingPlan.billingTiers[1].discountPercent» debe ser numérico.',
        ]


class TestTimelineSchema:
    def test_valid_phases(self):
        errors = validate_section_content('timeline', {
            'introText': 'Fases del proyecto.',
            'totalDuration': '1 mes',
            'phases': [{
                'title': '🎨 Diseño',
                'duration': '1 semana',
                'description': 'Diseño visual.',
                'tasks': ['Moodboard', 'Wireframes'],
                'milestone': 'Diseño aprobado',
            }],
        })
        assert errors == []

    def test_rejects_phase_tasks_that_is_not_a_list(self):
        errors = validate_section_content('timeline', {
            'phases': [{'title': 'Diseño', 'tasks': 'Moodboard'}],
        })
        assert errors == ['El campo «timeline.phases[0].tasks» debe ser una lista.']


class TestTechnicalDocumentSchema:
    def test_valid_technical_document_content(self):
        errors = validate_section_content('technical_document', {
            'purpose': 'Doc de arquitectura',
            'stack': [],
            'architecture': {'summary': ''},
            'epics': [{'epicKey': 'core', 'title': 'Núcleo'}],
        })
        assert errors == []

    def test_rejects_wrong_shapes_for_known_keys(self):
        errors = validate_section_content('technical_document', {
            'purpose': ['no', 'texto'],
            'stack': 'Django',
            'architecture': 'monolito',
        })
        assert errors == [
            'El campo «technical_document.purpose» debe ser texto.',
            'El campo «technical_document.stack» debe ser una lista.',
            'El campo «technical_document.architecture» debe ser un objeto.',
        ]


class TestSchemaGrammarRules:
    def test_unknown_keys_always_pass(self):
        errors = validate_section_content('greeting', {
            'clientName': 'Ana',
            '_editMode': 'paste',
            'rawText': 'pasted',
            'weirdFutureKey': {'anything': [1, 2, 3]},
        })
        assert errors == []

    def test_missing_fields_always_pass(self):
        for section_type in SECTION_CONTENT_SCHEMAS:
            assert validate_section_content(section_type, {}) == []

    def test_index_key_is_never_validated(self):
        # The frontend injects ``index``; both str and int must pass.
        assert validate_section_content('executive_summary', {'index': '1'}) == []
        assert validate_section_content('executive_summary', {'index': 1}) == []

    def test_unknown_section_type_returns_empty(self):
        errors = validate_section_content(
            'not_a_real_section', {'anything': object()},
        )
        assert errors == []

    def test_schema_registry_covers_all_model_section_types(self):
        model_types = {choice[0] for choice in ProposalSection.SectionType.choices}
        assert set(SECTION_CONTENT_SCHEMAS) == model_types


@pytest.mark.django_db
class TestSectionUpdateSerializerSchemaIntegration:
    def _section(self, section_type='greeting'):
        proposal = BusinessProposal.objects.create(
            title='Schema Test', client_name='Client',
        )
        return ProposalSection.objects.create(
            proposal=proposal,
            section_type=section_type,
            title='Section',
            order=0,
            content_json={},
        )

    def test_rejects_bad_payload_on_content_json_field(self):
        section = self._section('executive_summary')
        serializer = ProposalSectionUpdateSerializer(
            instance=section,
            data={'content_json': {'paragraphs': 'no soy una lista'}},
            partial=True,
        )
        assert not serializer.is_valid()
        assert 'content_json' in serializer.errors
        assert (
            'El campo «executive_summary.paragraphs» debe ser una lista.'
            in [str(e) for e in serializer.errors['content_json']]
        )

    def test_accepts_valid_payload(self):
        section = self._section('greeting')
        serializer = ProposalSectionUpdateSerializer(
            instance=section,
            data={'content_json': {'clientName': 'María'}},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestFromJSONSerializerSchemaIntegration:
    def _payload(self, sections):
        base = {'general': {'clientName': 'Test Client'}}
        base.update(sections)
        return {
            'title': 'Test Proposal',
            'client_name': 'Test Client',
            'sections': base,
        }

    def test_aggregates_errors_per_camel_case_key(self):
        serializer = ProposalFromJSONSerializer(data=self._payload({
            'executiveSummary': {'paragraphs': 'no lista'},
            'investment': {'hostingPlan': {'hostingPercent': 'mucho'}},
        }))
        assert not serializer.is_valid()
        sections_errors = serializer.errors['sections']
        assert 'executiveSummary' in sections_errors
        assert 'investment' in sections_errors
        assert (
            'El campo «investment.hostingPlan.hostingPercent» debe ser numérico.'
            in [str(e) for e in sections_errors['investment']]
        )

    def test_valid_sections_still_pass(self):
        serializer = ProposalFromJSONSerializer(data=self._payload({
            'executiveSummary': {'title': 'Summary', 'paragraphs': ['P1']},
            'investment': {'totalInvestment': '$5,000,000', 'currency': 'COP'},
        }))
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestDefaultConfigSerializerSchemaIntegration:
    def _config_data(self, content_json, section_type='executive_summary'):
        return {
            'language': 'es',
            'sections_json': [{
                'section_type': section_type,
                'title': 'Section',
                'order': 0,
                'content_json': content_json,
            }],
        }

    def test_rejects_bad_content_json_for_section_type(self):
        serializer = ProposalDefaultConfigSerializer(
            data=self._config_data({'paragraphs': 'no soy una lista'})
        )
        assert not serializer.is_valid()
        assert 'sections_json' in serializer.errors
        assert (
            'El campo «executive_summary.paragraphs» debe ser una lista.'
            in [str(e) for e in serializer.errors['sections_json']]
        )

    def test_accepts_valid_content_json(self):
        serializer = ProposalDefaultConfigSerializer(
            data=self._config_data({'paragraphs': ['P1'], 'title': 'Resumen'})
        )
        assert serializer.is_valid(), serializer.errors
