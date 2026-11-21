"""MCP confirmation and document-boundary tests for the requirement calculator."""

import pytest
from accounts.models import Project, UserProfile

from content.models import CalculatorRevision, Document, DocumentType, McpConnector
from content.services import requirement_calculator as calculator
from content.tests.mcp_confirmation_helpers import call_confirmed

pytestmark = pytest.mark.django_db


@pytest.fixture
def calculator_admin(django_user_model):
    admin = django_user_model.objects.create_user(username="calculator-mcp-admin", is_staff=True)
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN)
    return admin


@pytest.fixture
def calculator_definition():
    DocumentType.objects.get_or_create(code="markdown", defaults={"name": "Markdown"})
    definition = calculator.seed_definition()
    definition["signals"] = [
        next(row for row in definition["signals"] if row["size"] == size)
        for size in ("XS", "S", "M", "L", "XL", "PROJECT")
    ]
    definition["families"] = definition["families"][:1]
    definition["modifiers"] = definition["modifiers"][:2]
    return definition


@pytest.fixture
def commercial_token():
    connector, _ = McpConnector.objects.get_or_create(
        slug="commercial", defaults={"name": "Commercial"}
    )
    connector.is_active = True
    connector.save(update_fields=["is_active"])
    return connector.generate_token()


@pytest.fixture
def projects_token():
    connector, _ = McpConnector.objects.get_or_create(
        slug="projects", defaults={"name": "Projects"}
    )
    connector.is_active = True
    connector.save(update_fields=["is_active"])
    return connector.generate_token()


@pytest.fixture
def documents_token():
    connector, _ = McpConnector.objects.get_or_create(
        slug="documents", defaults={"name": "Documents"}
    )
    connector.is_active = True
    connector.save(update_fields=["is_active"])
    return connector.generate_token()


@pytest.fixture
def calculator_state(calculator_admin, calculator_definition):
    DocumentType.objects.get_or_create(code="markdown", defaults={"name": "Markdown"})
    return calculator.publish(
        calculator_definition,
        note="Initial definition",
        if_match="uninitialized",
        actor=calculator_admin,
    )


@pytest.fixture
def calculator_project(django_user_model):
    owner = django_user_model.objects.create_user(username="calculator-mcp-owner")
    UserProfile.objects.get_or_create(user=owner, defaults={"role": "client"})
    return Project.objects.create(name="Calculator MCP project", client=owner)


def _url(slug, token):
    return f"/api/mcp/{slug}/{token}/"


def _rpc(method, params=None, msg_id=1):
    payload = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def _call(api_client, slug, token, name, arguments):
    return api_client.post(
        _url(slug, token),
        _rpc("tools/call", {"name": name, "arguments": arguments}),
        format="json",
    )


def _confirmed(api_client, slug, token, name, arguments):
    return call_confirmed(api_client, _url(slug, token), _rpc, name, arguments)


def test_capabilities_mark_calculator_publications_as_confirmed(
    api_client, commercial_token, projects_token
):
    """Fails if MCP advertises publishing or approval without a confirmation boundary."""
    commercial = _call(
        api_client, "commercial", commercial_token, "describe_capabilities", {}
    )
    projects = _call(
        api_client, "projects", projects_token, "describe_capabilities", {}
    )
    commercial_tools = {
        row["name"]: row
        for row in commercial.data["result"]["structuredContent"]["tools"]
    }
    project_tools = {
        row["name"]: row
        for row in projects.data["result"]["structuredContent"]["tools"]
    }

    assert (
        commercial_tools["publish_requirement_calculator"]["requires_confirmation"]
        is True
    )
    assert (
        project_tools["approve_project_requirement_calculator"]["requires_confirmation"]
        is True
    )


def test_mcp_publication_waits_for_confirmation(
    api_client, commercial_token, calculator_definition
):
    """Fails if an MCP publish call creates a revision before explicit confirmation."""
    arguments = {
        "definition": calculator_definition,
        "note": "MCP initial definition",
        "if_match": "uninitialized",
    }

    preview = _call(
        api_client,
        "commercial",
        commercial_token,
        "publish_requirement_calculator",
        arguments,
    )

    assert preview.data["result"]["isError"] is False
    assert "confirmation_id" in preview.data["result"]["structuredContent"]
    assert CalculatorRevision.objects.count() == 0
    confirmed = _confirmed(
        api_client,
        "commercial",
        commercial_token,
        "publish_requirement_calculator",
        arguments,
    )
    assert confirmed.data["result"]["isError"] is False
    assert CalculatorRevision.objects.count() == 1


def test_mcp_approval_waits_for_confirmation(
    api_client, projects_token, calculator_state, calculator_project, calculator_admin
):
    """Fails if an MCP approval assigns a document before explicit confirmation."""
    draft = calculator.create_project_draft(
        calculator_project.pk,
        base_revision_id=calculator_state["revision_id"],
        note="Negotiated version",
        if_match=calculator.project_overview(calculator_project.pk)["if_match"],
        actor=calculator_admin,
    )
    arguments = {
        "version_id": draft["id"],
        "note": "Approved from MCP",
        "if_match": draft["if_match"],
    }

    preview = _call(
        api_client,
        "projects",
        projects_token,
        "approve_project_requirement_calculator",
        arguments,
    )

    calculator_project.refresh_from_db()
    assert preview.data["result"]["isError"] is False
    assert calculator_project.calculator_document_id is None
    confirmed = _confirmed(
        api_client,
        "projects",
        projects_token,
        "approve_project_requirement_calculator",
        arguments,
    )
    calculator_project.refresh_from_db()
    assert confirmed.data["result"]["isError"] is False
    assert calculator_project.calculator_document_id == draft["document_id"]


def test_mcp_document_update_rejects_managed_calculator_body(
    api_client,
    documents_token,
    calculator_state,
):
    """Fails if the document MCP can overwrite calculator content outside its version flow."""
    document = Document.objects.get(pk=calculator_state["document_id"])

    response = _call(
        api_client,
        "documents",
        documents_token,
        "update_document",
        {
            "document_id": document.pk,
            "content_markdown": "Unauthorized rewrite",
        },
    )

    document.refresh_from_db()
    result = response.data["result"]
    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "calculator_document_managed"
    assert document.content_markdown.startswith("# Calculadora de requerimientos")


@pytest.fixture
def measured_xs(calculator_state, calculator_admin):
    """Real Django rows for a synthetic five-hour delivery, with traceable participation."""
    from uuid import uuid4

    from content.services import calculator_calibration as calibration

    definition = calculator_state['definition']
    signal = next(item['id'] for item in definition['signals'] if item['size'] == 'XS')

    def close(*, rate=14000, hours='5.00', supported=True):
        estimate = calibration.record_estimate({
            'request_id': uuid4(), 'revision_id': calculator_state['revision_id'],
            'definition_digest': calculator.digest(definition), 'requirement': 'Cambiar un título ficticio',
            'size': 'XS', 'signal_ids': [signal], 'explanation': 'Título ya disponible',
        }, actor=calculator_admin)
        data = {'estimate_id': estimate['id'], 'actual_hours': hours, 'hourly_cost_cop': rate,
                'evidence': 'Parte de trabajo ficticio 21', 'cause': 'Entrega de prueba'}
        if supported:
            data['cost_breakdown'] = [{'participant': 'Diseño', 'period': '2026-10', 'hours': hours,
                                       'hourly_cost_cop': rate, 'evidence': 'Costo imputado ficticio 21'}]
        return data, calibration.record_actual(data, actor=calculator_admin)
    return close


@pytest.mark.parametrize(('rate', 'combined'), [(11000, False), (14000, True)])
def test_panel_and_mcp_keep_cost_warning_independent_of_hours(
    api_client, commercial_token, calculator_admin, measured_xs, rate, combined,
):
    """Even a deficit below the legacy threshold is visible with hours inside the band."""
    from decimal import Decimal

    from django.urls import reverse

    from content.models import CalculatorCostReview

    for _ in range(3):
        measured_xs(rate=rate)
    api_client.force_login(calculator_admin)
    panel = api_client.get(reverse('calculator-calibration'))
    api_client.logout()
    rpc = _call(api_client, 'commercial', commercial_token, 'get_requirement_calibration', {})

    assert panel.status_code == 200
    assert rpc.data['result']['isError'] is False
    for report in (panel.data, rpc.data['result']['structuredContent']):
        cohort, = report['cohorts']
        assert (cohort['covers_median_cost'], cohort['propose_hours_review'], cohort['propose_review']) == (
            False, False, combined,
        )
        xs, small, medium = report['package_coverage']
        assert xs['covers_verified_median_cost'] is False
        assert Decimal(xs['median_verified_cost_cop']) == rate * 5
        assert (xs['verified_cost_samples'], xs['economic_status']) == (3, 'provisional')
        assert [(row['size'], row['samples'], row['economic_status']) for row in (small, medium)] == [
            ('S', 0, 'provisional'), ('M', 0, 'provisional'),
        ]
    assert CalculatorCostReview.objects.count() == 0


@pytest.mark.parametrize(('count', 'hours', 'alerts'), [(2, '9.11', False), (3, '9.10', False), (3, '9.11', True)])
def test_hours_review_requires_measured_deviation_beyond_boundary(measured_xs, count, hours, alerts):
    from content.services import calculator_calibration as calibration

    for _ in range(count):
        measured_xs(hours=hours, supported=False)
    report = calibration.report()

    assert report['cohorts'][0]['propose_hours_review'] is alerts
    xs = report['package_coverage'][0]
    assert (xs['verified_cost_samples'], xs['median_verified_cost_cop'], xs['economic_status']) == (0, None, 'provisional')


def test_replacing_a_closure_reopens_only_its_reviewed_corpus(api_client, calculator_admin, measured_xs):
    from decimal import Decimal

    from django.urls import reverse

    from content.models import CalculatorCostReview, HourPackageSettings

    data, first = measured_xs()
    api_client.force_login(calculator_admin)
    report_url = reverse('calculator-calibration')
    decision_url = reverse('calculator-cost-review')
    xs = api_client.get(report_url).data['package_coverage'][0]
    decision = {key: xs[key] for key in ('size', 'definition_digest', 'corpus_digest')}
    decision['note'] = 'Costos contrastados con el parte y su tarifa. Revisar valor por separado.'
    result = api_client.post(decision_url, decision, format='json')
    assert result.status_code == 200
    assert result.data['economic_status'] == 'accepted'
    assert api_client.post(decision_url, decision, format='json').status_code == 200

    data['supersedes_id'] = first['id']
    data.pop('hourly_cost_cop')
    data['cost_breakdown'] = [
        {'participant': 'Diseño', 'period': '2026-10', 'hours': '2', 'hourly_cost_cop': 10000, 'evidence': 'Parte A'},
        {'participant': 'Desarrollo', 'period': '2026-10', 'hours': '3', 'hourly_cost_cop': 20000, 'evidence': 'Parte B'},
    ]
    corrected = api_client.post(reverse('calculator-actuals'), data, format='json')
    assert corrected.status_code == 201
    current = api_client.get(report_url).data['package_coverage'][0]
    assert (current['samples'], current['verified_cost_samples'], current['economic_status']) == (1, 1, 'provisional')
    assert Decimal(current['median_verified_cost_cop']) == 80000
    assert current['corpus_digest'] != xs['corpus_digest']
    assert api_client.post(decision_url, decision, format='json').status_code == 409
    review = CalculatorCostReview.objects.get()
    assert (review.corpus['verified_actual_ids'], review.author_id) == ([first['id']], calculator_admin.pk)
    assert HourPackageSettings.load().xs_price_cop == 50000


def test_incomplete_participation_cannot_replace_a_closure(api_client, calculator_admin, measured_xs):
    from django.urls import reverse

    from content.models import CalculatorActual

    data, original = measured_xs()
    data['supersedes_id'] = original['id']
    data['cost_breakdown'][0]['hours'] = '4'
    api_client.force_login(calculator_admin)
    result = api_client.post(reverse('calculator-actuals'), data, format='json')

    assert result.status_code == 400
    assert 'cost_breakdown' in result.data
    assert list(CalculatorActual.objects.values_list('id', flat=True)) == [original['id']]


def test_reference_rate_cannot_authorize_economic_acceptance(api_client, calculator_admin, measured_xs):
    from django.urls import reverse

    measured_xs(supported=False)
    api_client.force_login(calculator_admin)
    xs = api_client.get(reverse('calculator-calibration')).data['package_coverage'][0]
    decision = {key: xs[key] for key in ('size', 'definition_digest', 'corpus_digest')}

    result = api_client.post(reverse('calculator-cost-review'), {**decision, 'note': 'Sólo referencia'}, format='json')

    assert result.status_code == 400
    assert xs['covers_verified_median_cost'] is None


def test_mcp_cost_review_requires_confirmed_personal_admin(api_client, calculator_admin, commercial_token, measured_xs):
    from content.models import CalculatorCostReview, McpCredential
    from content.tests.mcp_parity import call_tool_inprocess

    measured_xs()
    report = _call(api_client, 'commercial', commercial_token, 'get_requirement_calibration', {})
    xs = report.data['result']['structuredContent']['package_coverage'][0]
    decision = {key: xs[key] for key in ('size', 'definition_digest', 'corpus_digest')}
    decision['note'] = 'Parte y costo imputado cotejados por el responsable.'
    denied = _confirmed(api_client, 'commercial', commercial_token, 'accept_requirement_cost_review', decision)
    assert denied.data['result']['isError'] is True
    assert not CalculatorCostReview.objects.exists()

    connector = McpConnector.objects.get(slug='commercial')
    personal = McpCredential.objects.create(connector=connector, actor=calculator_admin, label='Administrador de prueba')
    preview = call_tool_inprocess('commercial', 'accept_requirement_cost_review', decision, credential=personal)
    assert preview['confirmation_required'] is True
    assert not CalculatorCostReview.objects.exists()
    confirmed = call_tool_inprocess('commercial', 'confirm_action', {'confirmation_id': preview['confirmation_id']},
                                    credential=personal)
    assert confirmed['confirmed'] is True
    assert CalculatorCostReview.objects.get().author_id == calculator_admin.pk
