"""Tests for proposal section update API with realistic content_json payloads.

Covers: PATCH /api/proposals/sections/:id/update/ with form-equivalent
and paste-processed data for each section type. Verifies content_json
is stored and returned correctly.
"""
import copy

import pytest
from django.urls import reverse

from content.models import BusinessProposal, ProposalSection

pytestmark = pytest.mark.django_db


@pytest.fixture
def prop(db):
    """A proposal with no sections yet."""
    return BusinessProposal.objects.create(
        title='Section Update Test',
        client_name='Test Client',
    )


def _investment_content_json():
    return {
        'index': '9',
        'title': 'Inversión',
        'introText': 'La inversión total es:',
        'totalInvestment': '$3.500.000',
        'currency': 'COP',
        'whatsIncluded': [
            {'icon': '🎨', 'title': 'Diseño', 'description': 'UX/UI'},
        ],
        'paymentOptions': [
            {'label': '40% al firmar', 'description': '$1.400.000'},
            {'label': '30% al aprobar', 'description': '$1.050.000'},
            {'label': '30% al desplegar', 'description': '$1.050.000'},
        ],
        'hostingPlan': {
            'title': 'Hosting, Mantenimiento y Soporte',
            'description': 'Infraestructura optimizada.',
            'specs': [
                {'icon': '🧠', 'label': 'vCPU', 'value': '1 núcleo'},
            ],
            'monthlyPrice': '$49.999 COP',
            'monthlyLabel': 'por mes',
            'annualPrice': '$680.000 COP',
            'annualLabel': 'Hosting anual — Año 1',
            'renewalNote': 'Renovación con SMLMV.',
            'coverageNote': 'Cubre mantenimiento y soporte.',
        },
        'paymentMethods': ['Transferencia', 'Nequi'],
        'valueReasons': ['Diseño a medida'],
    }


def _next_steps_content_json():
    return {
        'index': '11',
        'title': 'Próximos pasos',
        'introMessage': 'Estamos listos.',
        'steps': [
            {'title': 'Revisión', 'description': 'Revisa la propuesta.'},
            {'title': '¡Comenzamos!', 'description': 'Kickoff meeting.'},
        ],
        'ctaMessage': 'Contáctanos hoy.',
        'primaryCTA': {'text': 'WhatsApp', 'link': 'https://wa.me/123'},
        'secondaryCTA': {'text': 'Agendar', 'link': 'https://calendly.com/x'},
        'contactMethods': [
            {'icon': '📧', 'title': 'Email', 'value': 'hi@test.co', 'link': 'mailto:hi@test.co'},
        ],
        'validityMessage': 'Válida 30 días.',
        'thankYouMessage': 'Gracias.',
    }


def _create_section(prop, section_type, order=0):
    return ProposalSection.objects.create(
        proposal=prop,
        section_type=section_type,
        title=f'{section_type} title',
        order=order,
        content_json={},
    )


class TestUpdateGreetingSection:
    def test_saves_greeting_content_json(self, admin_client, prop):
        """PATCH greeting section and verify content_json is persisted."""
        section = _create_section(prop, 'greeting')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'title': 'Greeting',
            'content_json': {
                'clientName': 'María García',
                'inspirationalQuote': 'Design is how it works.',
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert section.content_json['clientName'] == 'María García'
        assert section.content_json['inspirationalQuote'] == 'Design is how it works.'


class TestUpdateExecutiveSummarySection:
    def test_saves_paragraphs_and_highlights(self, admin_client, prop):
        """PATCH executive summary with paragraphs and highlights arrays."""
        section = _create_section(prop, 'executive_summary')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'index': '1',
                'title': 'Resumen ejecutivo',
                'paragraphs': ['Primer párrafo.', 'Segundo párrafo.'],
                'highlightsTitle': 'Incluye',
                'highlights': ['Diseño personalizado', 'Desarrollo responsivo'],
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['paragraphs']) == 2
        assert len(section.content_json['highlights']) == 2

    def test_saves_paste_processed_data(self, admin_client, prop):
        """Simulates content that was pasted and processed by the frontend."""
        section = _create_section(prop, 'executive_summary')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'index': '1',
                'title': 'Executive Summary',
                'paragraphs': [
                    'Our proposal covers the design and development of a professional website that will serve as the primary digital presence for the business.',
                    'The solution includes responsive design, SEO optimization, and a modern technology stack.',
                ],
                'highlightsTitle': 'Includes',
                'highlights': [
                    'Custom visual design with brand alignment',
                    'Responsive web development (mobile, tablet, desktop)',
                    'Basic SEO optimization and meta tags',
                    'Contact form with email notifications',
                    'Social media integration',
                ],
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['paragraphs']) == 2
        assert len(section.content_json['highlights']) == 5


class TestUpdateConversionStrategySection:
    def test_saves_steps_with_nested_bullets(self, admin_client, prop):
        """PATCH conversion strategy with nested steps containing bullet arrays."""
        section = _create_section(prop, 'conversion_strategy')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'index': '3',
                'title': 'Estrategia de conversión',
                'intro': 'La página se construirá como herramienta de conversión.',
                'steps': [
                    {
                        'title': '👀 Captar atención',
                        'bullets': ['Mensaje claro', 'Beneficio visible', 'CTA principal'],
                    },
                    {
                        'title': '🤝 Construir confianza',
                        'bullets': ['Testimonios', 'Credenciales'],
                    },
                ],
                'resultTitle': '🎯 Resultado',
                'result': 'Una página que genere contactos reales.',
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['steps']) == 2
        assert len(section.content_json['steps'][0]['bullets']) == 3


class TestUpdateFunctionalRequirementsSection:
    def test_saves_groups_with_items_via_form(self, admin_client, prop):
        """PATCH functional requirements with groups and items via form submission."""
        section = _create_section(prop, 'functional_requirements')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'index': '7',
                'title': 'Requerimientos Funcionales',
                'intro': 'Detalle de requerimientos.',
                'groups': [
                    {
                        'id': 'views',
                        'icon': '🖥️',
                        'title': 'Vistas',
                        'description': 'Pantallas del sitio.',
                        'items': [
                            {'icon': '🏠', 'name': 'Página Principal', 'description': 'Landing con CTAs.'},
                            {'icon': '📧', 'name': 'Contacto', 'description': 'Formulario.'},
                            {'icon': '📜', 'name': 'Legales', 'description': 'Términos y privacidad.'},
                        ],
                    },
                    {
                        'id': 'components',
                        'icon': '🧩',
                        'title': 'Componentes',
                        'description': 'Elementos reutilizables.',
                        'items': [
                            {'icon': '🔝', 'name': 'Header', 'description': 'Logo y menú.'},
                            {'icon': '🔚', 'name': 'Footer', 'description': 'Derechos y enlaces.'},
                        ],
                    },
                ],
                'additionalModules': [],
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['groups']) == 2
        assert len(section.content_json['groups'][0]['items']) == 3
        assert section.content_json['groups'][0]['items'][0]['name'] == 'Página Principal'

    def test_saves_groups_with_paste_processed_items(self, admin_client, prop):
        """Simulates items parsed from pasted text by processGroupPaste()."""
        section = _create_section(prop, 'functional_requirements')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'index': '7',
                'title': 'Functional Requirements',
                'intro': 'Below are the project requirements.',
                'groups': [
                    {
                        'id': 'views',
                        'icon': '🖥️',
                        'title': 'Views',
                        'description': 'Each view is a screen of the website.',
                        'items': [
                            {'icon': '🏠', 'name': 'Home Page', 'description': 'Main landing page with CTAs.'},
                            {'icon': '📧', 'name': 'Contact', 'description': 'Contact form and details.'},
                            {'icon': '📜', 'name': 'Legal', 'description': 'Terms and privacy.'},
                            {'icon': '🛒', 'name': 'Products', 'description': 'Product catalog with filters.'},
                        ],
                    },
                ],
                'additionalModules': [
                    {
                        'icon': '📊',
                        'title': 'Analytics Module',
                        'description': 'Dashboard with metrics.',
                        'items': [
                            {'icon': '📈', 'name': 'Traffic Reports', 'description': 'Automatic traffic reports.'},
                            {'icon': '🎯', 'name': 'Conversion Tracking', 'description': 'Track form submissions.'},
                        ],
                    },
                ],
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['groups'][0]['items']) == 4
        assert len(section.content_json['additionalModules']) == 1
        assert len(section.content_json['additionalModules'][0]['items']) == 2

    def test_saves_with_empty_items_array(self, admin_client, prop):
        """PATCH functional requirements with empty items to verify edge case."""
        section = _create_section(prop, 'functional_requirements')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'index': '7',
                'title': 'Reqs',
                'intro': '',
                'groups': [
                    {'id': 'views', 'icon': '🖥️', 'title': 'Views', 'description': '', 'items': []},
                ],
                'additionalModules': [],
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert section.content_json['groups'][0]['items'] == []


class TestUpdateTimelineSection:
    def test_saves_phases_with_tasks_array(self, admin_client, prop):
        """PATCH timeline section with phases containing task arrays."""
        section = _create_section(prop, 'timeline')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'index': '8',
                'title': 'Cronograma',
                'introText': 'Fases del proyecto.',
                'totalDuration': '1 mes',
                'phases': [
                    {
                        'title': '🎨 Diseño',
                        'duration': '1 semana',
                        'description': 'Diseño visual.',
                        'tasks': ['Moodboard', 'Wireframes', 'Diseño UI'],
                        'milestone': 'Diseño aprobado',
                    },
                ],
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['phases'][0]['tasks']) == 3


class TestUpdateInvestmentSection:
    def test_saves_investment_with_payment_options(self, admin_client, prop):
        """PATCH investment section with payment options, methods, and value reasons."""
        section = _create_section(prop, 'investment')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {'content_json': _investment_content_json()}
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['paymentOptions']) == 3
        assert section.content_json['totalInvestment'] == '$3.500.000'


class TestUpdateNextStepsSection:
    def test_saves_next_steps_with_ctas_and_contacts(self, admin_client, prop):
        """PATCH next steps section with CTAs, contact methods, and validity."""
        section = _create_section(prop, 'next_steps')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {'content_json': _next_steps_content_json()}
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['steps']) == 2
        assert section.content_json['primaryCTA']['text'] == 'WhatsApp'
        assert len(section.content_json['contactMethods']) == 1


def _context_diagnostic_content_json():
    """Fixture: realistic context_diagnostic content_json."""
    return {
        'index': '2',
        'title': 'Contexto y Diagnóstico',
        'paragraphs': [
            'El cliente busca fortalecer su presencia digital.',
            'Actualmente no tiene una web profesional.',
        ],
        'issuesTitle': 'Desafíos',
        'issues': ['Falta de presencia digital', 'Difícil captar clientes'],
        'opportunityTitle': 'Oportunidad',
        'opportunity': 'Crear una plataforma que genere confianza.',
    }


def _design_ux_content_json():
    """Fixture: realistic design_ux content_json."""
    return {
        'index': '4',
        'title': 'Diseño UX',
        'paragraphs': ['El desarrollo será una experiencia digital.'],
        'focusTitle': 'Estructura',
        'focusItems': ['Presentación clara', 'Integración redes sociales'],
        'objectiveTitle': 'Objetivo',
        'objective': 'Inspirar confianza desde el primer momento.',
    }


def _creative_support_content_json():
    """Fixture: realistic creative_support content_json."""
    return {
        'index': '5',
        'title': 'Acompañamiento Creativo',
        'paragraphs': ['El cliente contará con acompañamiento cercano.'],
        'includesTitle': 'Incluye',
        'includes': ['Sesiones de revisión', 'Apoyo en selección visual'],
        'closing': 'Cada decisión será una co-creación.',
    }


def _development_stages_content_json():
    """Fixture: realistic development_stages content_json."""
    return {
        'stages': [
            {
                'icon': '✉️',
                'title': 'Propuesta',
                'description': 'Etapa actual.',
                'current': True,
            },
            {
                'icon': '🎨',
                'title': 'Diseño',
                'description': 'Prototipo en Figma.',
            },
            {
                'icon': '💻',
                'title': 'Desarrollo',
                'description': 'Implementación.',
            },
        ],
    }


def _final_note_content_json():
    """Fixture: realistic final_note content_json."""
    return {
        'index': '10',
        'title': 'Nota Final',
        'message': 'Creemos firmemente en esta propuesta.',
        'personalNote': 'Estamos emocionados.',
        'teamName': 'Project App',
        'teamRole': 'Socio digital',
        'contactEmail': 'team@projectapp.co',
        'commitmentBadges': [
            {
                'icon': '🤝',
                'title': 'Compromiso',
                'description': 'Dedicación completa.',
            },
            {
                'icon': '💯',
                'title': 'Calidad',
                'description': 'Revisiones ilimitadas.',
            },
        ],
        'validityMessage': 'Válida por 30 días.',
        'thankYouMessage': 'Gracias por la oportunidad.',
    }


class TestUpdateContextDiagnosticSection:
    """PATCH context_diagnostic section with paragraphs, issues, and opportunity."""

    def test_saves_paragraphs_issues_and_opportunity(self, admin_client, prop):
        """Verify context_diagnostic stores paragraphs, issues list, and opportunity."""
        section = _create_section(prop, 'context_diagnostic')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {'content_json': _context_diagnostic_content_json()}
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['paragraphs']) == 2
        assert len(section.content_json['issues']) == 2
        assert section.content_json['opportunity'] == 'Crear una plataforma que genere confianza.'
        assert section.content_json['issuesTitle'] == 'Desafíos'


class TestUpdateDesignUxSection:
    """PATCH design_ux section with focus items and objective."""

    def test_saves_focus_items_and_objective(self, admin_client, prop):
        """Verify design_ux stores focusItems array and objective string."""
        section = _create_section(prop, 'design_ux')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {'content_json': _design_ux_content_json()}
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['focusItems']) == 2
        assert section.content_json['objective'] == 'Inspirar confianza desde el primer momento.'


class TestUpdateCreativeSupportSection:
    """PATCH creative_support section with includes and closing."""

    def test_saves_includes_and_closing(self, admin_client, prop):
        """Verify creative_support stores includes list and closing text."""
        section = _create_section(prop, 'creative_support')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {'content_json': _creative_support_content_json()}
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['includes']) == 2
        assert section.content_json['closing'] == 'Cada decisión será una co-creación.'


class TestUpdateDevelopmentStagesSection:
    """PATCH development_stages section with stages and current flag."""

    def test_saves_stages_with_current_flag(self, admin_client, prop):
        """Verify development_stages stores stages with current boolean."""
        section = _create_section(prop, 'development_stages')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {'content_json': _development_stages_content_json()}
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['stages']) == 3
        assert section.content_json['stages'][0]['current'] is True
        assert 'current' not in section.content_json['stages'][1]


class TestUpdateFinalNoteSection:
    """PATCH final_note section with badges, contact info, and messages."""

    def test_saves_badges_and_messages(self, admin_client, prop):
        """Verify final_note stores commitment badges, validity, and thank you."""
        section = _create_section(prop, 'final_note')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {'content_json': _final_note_content_json()}
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert len(section.content_json['commitmentBadges']) == 2
        assert section.content_json['contactEmail'] == 'team@projectapp.co'
        assert section.content_json['validityMessage'] == 'Válida por 30 días.'
        assert section.content_json['thankYouMessage'] == 'Gracias por la oportunidad.'


_FORM_MODE_PAYLOAD = {
    'content_json': {
        'index': '2', 'title': 'Contexto',
        'paragraphs': ['P1'], 'issuesTitle': 'Desafíos',
        'issues': [], 'opportunityTitle': '', 'opportunity': '',
        '_editMode': 'form',
    },
}

_PASTE_MODE_PAYLOAD = {
    'content_json': {
        'index': '4', 'title': 'Diseño',
        'paragraphs': [], 'focusTitle': '', 'focusItems': [],
        'objectiveTitle': '', 'objective': '',
        '_editMode': 'paste', 'rawText': 'First paste version.',
    },
}


class TestUpdateSectionPasteMode:
    """Tests for _editMode and rawText metadata persisted via PATCH."""

    def test_saves_paste_mode_metadata(self, admin_client, prop):
        """Verify _editMode='paste' and rawText are stored in content_json."""
        section = _create_section(prop, 'executive_summary')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'index': '1',
                'title': 'Summary',
                'paragraphs': ['P1'],
                'highlightsTitle': 'Includes',
                'highlights': ['H1'],
                '_editMode': 'paste',
                'rawText': 'Custom pasted content for the summary section.',
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert section.content_json['_editMode'] == 'paste'
        assert section.content_json['rawText'] == 'Custom pasted content for the summary section.'
        assert section.content_json['paragraphs'] == ['P1']

    def test_saves_form_mode_without_rawtext(self, admin_client, prop):
        """Verify _editMode='form' is stored and rawText is absent."""
        section = _create_section(prop, 'context_diagnostic')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        response = admin_client.patch(url, _FORM_MODE_PAYLOAD, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert section.content_json['_editMode'] == 'form'
        assert 'rawText' not in section.content_json


class TestUpdateCommercialConditionsSection:
    """hourPackagesMode persists through the section PATCH like _editMode."""

    def test_persists_hour_packages_mode_and_omitted_pkg_rates(self, admin_client, prop):
        section = _create_section(prop, 'commercial_conditions')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'index': '17',
                'title': 'Condiciones comerciales',
                'pricingModel': 'hours',
                'hourlyRate': 90000,
                'currency': 'COP',
                'hourPackagesMode': 'manual',
                'packages': [
                    {'name': 'Ágil', 'hours': 20, 'discountPercent': 10, 'note': ''},
                ],
                '_editMode': 'form',
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert section.content_json['hourPackagesMode'] == 'manual'
        assert 'hourlyRate' not in section.content_json['packages'][0]

    def test_persists_manual_rate_keys(self, admin_client, prop):
        """The «Tarifa por hora» tab writes its rate keys through this PATCH."""
        section = _create_section(prop, 'commercial_conditions')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'index': '17',
                'title': 'Condiciones comerciales',
                'pricingModel': 'hours',
                'hourPackagesMode': 'manual',
                'manualHourlyRate': 45000,
                'manualCurrency': 'COP',
                'manualPackageRates': [{'packageId': 7, 'hourlyRate': 52000}],
                'packages': [
                    {'id': 7, 'name': 'Ágil', 'hours': 20,
                     'discountPercent': 10, 'note': ''},
                ],
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert section.content_json['manualHourlyRate'] == 45000
        assert section.content_json['manualCurrency'] == 'COP'
        assert section.content_json['manualPackageRates'] == [
            {'packageId': 7, 'hourlyRate': 52000},
        ]
        assert section.content_json['packages'][0]['id'] == 7

    def test_rejects_non_numeric_manual_rate(self, admin_client, prop):
        section = _create_section(prop, 'commercial_conditions')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'index': '17',
                'title': 'Condiciones comerciales',
                'manualHourlyRate': 'gratis',
            },
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 400

    def test_roundtrips_paste_data_across_updates(self, admin_client, prop):
        """Save paste data, then update again and verify persistence."""
        section = _create_section(prop, 'design_ux')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        paste_payload = copy.deepcopy(_PASTE_MODE_PAYLOAD)
        admin_client.patch(url, paste_payload, format='json')
        section.refresh_from_db()
        assert section.content_json['rawText'] == 'First paste version.'

        paste_payload['content_json']['rawText'] = 'Updated paste version.'
        admin_client.patch(url, paste_payload, format='json')
        section.refresh_from_db()
        assert section.content_json['rawText'] == 'Updated paste version.'


_GROUP_PASTE_PAYLOAD = {
    'content_json': {
        'index': '7',
        'title': 'Requerimientos',
        'intro': '',
        'groups': [
            {
                'id': 'views', 'icon': '🖥️', 'title': 'Vistas',
                'description': '', 'items': [],
                '_editMode': 'paste', 'rawText': 'Pasted views content here.',
            },
            {
                'id': 'components', 'icon': '🧩', 'title': 'Componentes',
                'description': '',
                'items': [{'icon': '🔝', 'name': 'Header', 'description': 'Logo.'}],
                '_editMode': 'form',
            },
        ],
        'additionalModules': [
            {
                'icon': '📊', 'title': 'Analytics',
                'description': '', 'items': [],
                '_editMode': 'paste', 'rawText': 'Analytics pasted content.',
            },
        ],
    },
}


class TestUpdateFunctionalRequirementsGroupPaste:
    """Tests for per-group _editMode/rawText in functional_requirements."""

    def test_saves_group_paste_metadata(self, admin_client, prop):
        """Verify group-level _editMode='paste' and rawText persist."""
        section = _create_section(prop, 'functional_requirements')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        response = admin_client.patch(url, _GROUP_PASTE_PAYLOAD, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        groups = section.content_json['groups']
        assert groups[0]['_editMode'] == 'paste'
        assert groups[0]['rawText'] == 'Pasted views content here.'
        assert groups[1]['_editMode'] == 'form'
        assert 'rawText' not in groups[1]

    def test_saves_additional_module_paste_metadata(self, admin_client, prop):
        """Verify additionalModules _editMode='paste' and rawText persist."""
        section = _create_section(prop, 'functional_requirements')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        response = admin_client.patch(url, _GROUP_PASTE_PAYLOAD, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        modules = section.content_json['additionalModules']
        assert modules[0]['_editMode'] == 'paste'
        assert modules[0]['rawText'] == 'Analytics pasted content.'


class TestUpdateSectionEdgeCases:
    def test_saves_empty_content_json(self, admin_client, prop):
        section = _create_section(prop, 'greeting')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {'content_json': {}}
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert section.content_json == {}

    def test_updates_title_and_content_json_together(self, admin_client, prop):
        section = _create_section(prop, 'greeting')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'title': 'New Title',
            'content_json': {'clientName': 'Updated Client'},
        }
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert section.title == 'New Title'
        assert section.content_json['clientName'] == 'Updated Client'

    def test_preserves_existing_content_when_only_title_updated(self, admin_client, prop):
        """PATCH only title and verify existing content_json is preserved."""
        section = _create_section(prop, 'greeting')
        section.content_json = {'clientName': 'Keep Me'}
        section.save()
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {'title': 'Only Title Changed'}
        response = admin_client.patch(url, payload, format='json')
        assert response.status_code == 200
        section.refresh_from_db()
        assert section.title == 'Only Title Changed'
        assert section.content_json['clientName'] == 'Keep Me'

    def _setup_fr_save_scenario(self, prop):
        prop.total_investment = 1000000
        prop.currency = 'COP'
        prop.save(update_fields=['total_investment', 'currency'])
        fr = _create_section(prop, 'functional_requirements', order=0)
        fr.content_json = {'groups': [{'id': 'views', 'title': 'Vistas', 'is_calculator_module': True, 'price_percent': 25, 'selected': True, 'items': []}], 'additionalModules': []}
        fr.save(update_fields=['content_json'])
        inv = _create_section(prop, 'investment', order=1)
        inv.content_json = {'totalInvestment': '$1.000.000', 'currency': 'COP', 'paymentOptions': [{'label': '40% al firmar', 'description': '$500.000 COP'}, {'label': '60% al desplegar', 'description': '$750.000 COP'}]}
        inv.save(update_fields=['content_json'])
        payload = {'content_json': {'groups': [{'id': 'views', 'title': 'Vistas', 'is_calculator_module': True, 'price_percent': 25, 'selected': False, 'items': []}], 'additionalModules': []}}
        return fr, inv, payload

    def test_response_returns_section_with_updated_selection(self, admin_client, prop):
        """PATCH response includes the updated section with the new selection state."""
        fr, inv, payload = self._setup_fr_save_scenario(prop)
        response = admin_client.patch(reverse('update-proposal-section', kwargs={'section_id': fr.id}), payload, format='json')
        assert response.status_code == 200
        body = response.json()
        assert 'section' in body
        assert body['section']['id'] == fr.id
        assert body['section']['content_json']['groups'][0]['selected'] is False

    def test_response_returns_proposal_totals_and_investment_section_for_fr_save(
        self, admin_client, prop,
    ):
        """Saving a functional_requirements section recomputes proposal totals and returns the auto-resynced investment section."""
        fr, inv, payload = self._setup_fr_save_scenario(prop)
        response = admin_client.patch(reverse('update-proposal-section', kwargs={'section_id': fr.id}), payload, format='json')
        body = response.json()
        totals = body['proposal_totals']
        assert totals['total_investment'] == '1000000.00'
        assert totals['effective_total_investment'] == '1000000.00'
        assert 'investment_section' in body
        assert body['investment_section']['id'] == inv.id
        opts = body['investment_section']['content_json']['paymentOptions']
        assert opts[0]['description'] == '$400.000 COP'
        assert opts[1]['description'] == '$600.000 COP'

    def test_response_returns_proposal_totals_for_non_fr_save_without_investment(
        self, admin_client, prop,
    ):
        """Non-FR saves skip _resync, so investment_section is omitted; totals are still included so the General tab can stay current."""
        prop.total_investment = 500000
        prop.save(update_fields=['total_investment'])
        section = _create_section(prop, 'greeting')
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {'content_json': {'clientName': 'María'}}

        response = admin_client.patch(url, payload, format='json')

        assert response.status_code == 200
        body = response.json()
        assert body['section']['id'] == section.id
        assert 'proposal_totals' in body
        assert 'investment_section' not in body

    def test_canonicalizes_technical_document_linked_module_ids(self, admin_client, prop):
        fr = _create_section(prop, 'functional_requirements')
        fr.content_json = {
            'groups': [
                {'id': 'views', 'title': 'Vistas', 'items': [{'name': 'Home'}]},
            ],
            'additionalModules': [
                {'id': 'pwa_module', 'title': 'PWA', 'is_calculator_module': True, 'price_percent': 40},
            ],
        }
        fr.save(update_fields=['content_json'])
        section = _create_section(prop, 'technical_document', order=1)
        url = reverse('update-proposal-section', kwargs={'section_id': section.id})
        payload = {
            'content_json': {
                'purpose': 'Doc',
                'epics': [
                    {
                        'title': 'Mobile',
                        'linked_module_ids': ['views'],
                        'requirements': [
                            {'title': 'Installable', 'linked_module_ids': ['pwa_module']},
                        ],
                    },
                ],
            },
        }

        response = admin_client.patch(url, payload, format='json')

        assert response.status_code == 200
        section.refresh_from_db()
        epic = section.content_json['epics'][0]
        assert epic['linked_module_ids'] == ['group-views']
        assert epic['requirements'][0]['linked_module_ids'] == ['module-pwa_module']
