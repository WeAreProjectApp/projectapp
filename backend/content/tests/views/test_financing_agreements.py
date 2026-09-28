from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from freezegun import freeze_time
from pypdf import PdfReader
from rest_framework.test import APIClient

from accounts.models import Project
from content.models import (
    FinancingAgreement,
    FinancingAgreementTemplate,
    HourPackage,
    Nationality,
)
from content.services.financing_agreement_service import (
    DEFAULT_FINANCING_TEMPLATE_MARKDOWN,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def pro_package():
    return HourPackage.objects.create(
        nationality=Nationality.COL,
        name_es='Paquete Pro',
        name_en='Pro Pack',
        hours=60,
        hourly_rate=Decimal('32000.00'),
        discount_percent=20,
        order=99,
        is_active=True,
    )


@pytest.fixture
def agreement_template():
    return FinancingAgreementTemplate.objects.create(
        name='Otrosí API',
        version=1,
        is_default=True,
        content_markdown=DEFAULT_FINANCING_TEMPLATE_MARKDOWN,
    )


@pytest.fixture
def financing_client(make_client_profile):
    return make_client_profile(
        company='Semilla SAS',
        nit='901234567-8',
        email='ana@semilla.co',
        first_name='Ana',
        last_name='Semilla',
    )


def _payload(client, **overrides):
    payload = {
        'client_id': client.id,
        'original_contract_reference': 'Contrato de desarrollo 014',
        'original_contract_date': '2026-01-10',
        'project_name': 'Vástago',
        'financed_scope': 'Implementación de la fase de analítica.',
        'modality': 'five_year',
        'partnership_start_date': '2026-02-01',
        'currency': 'COP',
        'total_value': '25000000.00',
        'initial_payment': '5000000.00',
        'hosting_value': '500000.00',
        'hosting_period': 'monthly',
        'first_installment_date': '2026-03-05',
    }
    payload.update(overrides)
    return payload


def _create_draft(admin_client, client, **overrides):
    return admin_client.post(
        '/api/financing/agreements/',
        _payload(client, **overrides),
        format='json',
    )


def _settings_payload(**overrides):
    payload = {
        'minimum_project_value_cop': '20000000.00',
        'maximum_project_value_cop': '140000000.00',
        'financing_months': 12,
        'maximum_financed_percent': '80.00',
        'late_hosting_increase_percent': '2.00',
        'installment_due_day_start': 1,
        'installment_due_day_end': 5,
    }
    payload.update(overrides)
    return payload


def test_admin_reads_current_financing_settings(admin_client):
    response = admin_client.get('/api/financing/settings/')

    assert response.status_code == 200
    assert response.data['current']['version'] == 2
    assert response.data['current']['minimum_project_value_cop'] == '20000000.00'
    assert response.data['current']['minimum_initial_payment_percent'] == '20.00'


def test_non_admin_cannot_read_financing_settings():
    response = APIClient().get('/api/financing/settings/')

    assert response.status_code in (401, 403)


def test_admin_publishes_financing_settings_revision(admin_client):
    response = admin_client.post(
        '/api/financing/settings/',
        _settings_payload(financing_months=18),
        format='json',
    )

    assert response.status_code == 201
    assert response.data['current']['version'] == 3
    assert response.data['current']['financing_months'] == 18


def test_admin_rejects_invalid_financing_value_range(admin_client):
    response = admin_client.post(
        '/api/financing/settings/',
        _settings_payload(maximum_project_value_cop='10000000.00'),
        format='json',
    )

    assert response.status_code == 400
    assert 'maximum_project_value_cop' in response.data


@pytest.fixture
def rebuild_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(
        'content.views.financing_agreements.schedule_rebuild_after_publish',
        lambda **kwargs: calls.append(kwargs),
    )
    return calls


def test_published_policy_requests_program_rebuild(admin_client, rebuild_calls):
    """Fails if a new policy leaves the prerendered Partnership Program with old terms."""
    response = admin_client.post(
        '/api/financing/settings/',
        _settings_payload(financing_months=18),
        format='json',
    )

    assert response.status_code == 201
    assert response.data['current']['financing_months'] == 18
    assert rebuild_calls == [{'reason': 'partnership-program'}]


def test_rejected_policy_skips_program_rebuild(admin_client, rebuild_calls):
    response = admin_client.post(
        '/api/financing/settings/',
        _settings_payload(maximum_project_value_cop='10000000.00'),
        format='json',
    )

    assert response.status_code == 400
    assert 'maximum_project_value_cop' in response.data
    assert rebuild_calls == []


def test_reading_financing_settings_skips_program_rebuild(admin_client, rebuild_calls):
    response = admin_client.get('/api/financing/settings/')

    assert response.status_code == 200
    assert response.data['current']['version'] == 2
    assert rebuild_calls == []


@freeze_time('2026-02-01 12:00:00')
def test_draft_action_applies_published_financing_policy(
    admin_client,
    financing_client,
    agreement_template,
):
    created = _create_draft(admin_client, financing_client)
    admin_client.post(
        '/api/financing/settings/',
        _settings_payload(financing_months=10),
        format='json',
    )

    response = admin_client.post(
        f'/api/financing/agreements/{created.data["id"]}/apply-current-policy/',
        {},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['policy_version'] == 3
    assert len(response.data['installment_schedule']) == 10


def test_admin_creates_populated_agreement_with_twelve_installments(
    admin_client,
    financing_client,
    agreement_template,
):
    """Fails if an admin-created draft loses its legal client or payment data."""
    response = admin_client.post(
        '/api/financing/agreements/',
        _payload(financing_client),
        format='json',
    )

    assert response.status_code == 201
    assert response.data['client_full_name'] == 'Ana Semilla'
    assert response.data['client_id_number'] == '901234567-8'
    assert len(response.data['installment_schedule']) == 12
    assert response.data['financed_balance'] == '20000000.00'


def test_draft_pdf_contains_populated_legal_identity(
    admin_client,
    financing_client,
    agreement_template,
    company_settings,
):
    """Fails if the admin draft PDF omits the selected client's legal identity."""
    created = admin_client.post(
        '/api/financing/agreements/',
        _payload(financing_client),
        format='json',
    )

    response = admin_client.get(
        f'/api/financing/agreements/{created.data["id"]}/draft-pdf/',
    )
    text = '\n'.join(
        page.extract_text() or ''
        for page in PdfReader(BytesIO(response.content)).pages
    )

    assert response.status_code == 200
    assert 'Ana Semilla' in text
    assert 'BORRADOR' in text
    assert 'XXX-XXX-XXX' not in text


def test_ready_rejects_schedule_outside_first_five_days(
    admin_client,
    financing_client,
    agreement_template,
    company_settings,
):
    """Fails if an admin can mark ready a schedule with a late due date."""
    created = admin_client.post(
        '/api/financing/agreements/',
        _payload(financing_client),
        format='json',
    )
    schedule = created.data['installment_schedule']
    schedule[0]['due_date'] = '2026-03-06'
    patched = admin_client.patch(
        f'/api/financing/agreements/{created.data["id"]}/',
        {'installment_schedule': schedule},
        format='json',
    )

    assert patched.status_code == 400
    assert 'installment_schedule' in patched.data


def test_completed_five_year_agreement_allows_second_cycle(
    admin_client,
    financing_client,
    agreement_template,
    company_settings,
    tmp_path,
    monkeypatch,
):
    """Fails if the admin lifecycle cannot create an approved second five-year cycle."""
    field = FinancingAgreement._meta.get_field('signed_document')
    monkeypatch.setattr(
        field,
        'storage',
        FileSystemStorage(location=tmp_path, base_url=None),
    )
    created = admin_client.post(
        '/api/financing/agreements/',
        _payload(financing_client),
        format='json',
    )
    agreement_id = created.data['id']
    ready = admin_client.post(
        f'/api/financing/agreements/{agreement_id}/mark-ready/',
        {},
        format='json',
    )
    upload = BytesIO(b'%PDF-1.4\n%%EOF')
    upload.name = 'firmado.pdf'
    active = admin_client.post(
        f'/api/financing/agreements/{agreement_id}/upload-signed/',
        {'signed_document': upload},
        format='multipart',
    )
    completed = admin_client.post(
        f'/api/financing/agreements/{agreement_id}/complete/',
        {'completion_note': 'Pago íntegro verificado contra soportes.'},
        format='json',
    )
    second = admin_client.post(
        f'/api/financing/agreements/{agreement_id}/create-second-cycle/',
        {},
        format='json',
    )

    assert ready.status_code == 200
    assert active.data['status'] == 'active'
    assert completed.data['status'] == 'completed'
    assert second.status_code == 201
    assert second.data['cycle_number'] == 2
    assert second.data['previous_agreement'] == agreement_id
    assert second.data['total_value'] == '0.00'


def test_non_admin_cannot_list_financing_agreements(
    financing_client,
    agreement_template,
):
    """Fails if the administrative agreement list becomes publicly accessible."""
    response = APIClient().get('/api/financing/agreements/')

    assert response.status_code in (401, 403)


def test_admin_list_applies_financing_filters(
    admin_client,
    financing_client,
    agreement_template,
):
    expected = _create_draft(admin_client, financing_client)
    _create_draft(
        admin_client,
        financing_client,
        project_name='Producto alterno',
        modality='three_year',
    )

    response = admin_client.get(
        '/api/financing/agreements/'
        '?archived=all&q=V%C3%A1stago&status=draft&modality=five_year'
        '&cycle=1&limit=1&offset=0',
    )

    assert response.status_code == 200
    assert [row['id'] for row in response.data['results']] == [expected.data['id']]


def test_admin_list_returns_archived_financing_agreements(
    admin_client,
    financing_client,
    agreement_template,
):
    created = _create_draft(admin_client, financing_client)
    FinancingAgreement.objects.filter(pk=created.data['id']).update(is_archived=True)

    response = admin_client.get(
        '/api/financing/agreements/?archived=true&limit=invalid&offset=-1',
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['limit'] == 25
    assert response.data['offset'] == 0


@pytest.mark.parametrize(
    ('query', 'field'),
    (
        ('status=unknown', 'status'),
        ('modality=unknown', 'modality'),
        ('cycle=3', 'cycle'),
    ),
)
def test_admin_list_rejects_invalid_financing_filter(admin_client, query, field):
    response = admin_client.get(f'/api/financing/agreements/?{query}')

    assert response.status_code == 400
    assert field in response.data


def test_admin_updates_draft_client_snapshot(
    admin_client,
    financing_client,
    agreement_template,
    make_client_profile,
):
    created = _create_draft(admin_client, financing_client)
    replacement = make_client_profile(
        company='Renuevo SAS',
        nit='900888777-1',
        first_name='Lucia',
        last_name='Renuevo',
    )
    replacement_template = FinancingAgreementTemplate.objects.create(
        name='Otrosí alterno',
        version=2,
        content_markdown=agreement_template.content_markdown,
    )

    response = admin_client.patch(
        f'/api/financing/agreements/{created.data["id"]}/',
        {
            'client_id': replacement.id,
            'template_id': replacement_template.id,
            'modality': 'three_year',
            'partnership_start_date': '2026-04-01',
        },
        format='json',
    )

    assert response.status_code == 200
    assert response.data['client_full_name'] == 'Lucia Renuevo'
    assert response.data['client_id_number'] == '900888777-1'
    assert response.data['template']['id'] == replacement_template.id
    assert response.data['partnership_end_date'] == '2029-04-01'


def test_ready_agreement_can_reopen_as_draft(
    admin_client,
    financing_client,
    agreement_template,
    company_settings,
):
    created = _create_draft(admin_client, financing_client)
    admin_client.post(
        f'/api/financing/agreements/{created.data["id"]}/mark-ready/',
        {},
        format='json',
    )

    response = admin_client.post(
        f'/api/financing/agreements/{created.data["id"]}/reopen/',
        {},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['status'] == 'draft'
    assert response.data['resolved_contract_sha256'] == ''


def test_admin_cancels_financing_agreement(
    admin_client,
    financing_client,
    agreement_template,
):
    created = _create_draft(admin_client, financing_client)

    response = admin_client.post(
        f'/api/financing/agreements/{created.data["id"]}/cancel/',
        {'cancellation_reason': 'El cliente cambió la estrategia del producto.'},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['status'] == 'cancelled'
    assert response.data['cancellation_reason'].startswith('El cliente')


def test_cancelled_financing_agreement_can_be_archived(
    admin_client,
    financing_client,
    agreement_template,
):
    created = _create_draft(admin_client, financing_client)
    admin_client.post(
        f'/api/financing/agreements/{created.data["id"]}/cancel/',
        {'cancellation_reason': 'Financiación descartada por el cliente.'},
        format='json',
    )

    response = admin_client.post(
        f'/api/financing/agreements/{created.data["id"]}/archive/',
        {},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['is_archived'] is True


def test_archived_financing_agreement_can_be_restored(
    admin_client,
    financing_client,
    agreement_template,
):
    created = _create_draft(admin_client, financing_client)
    agreement_id = created.data['id']
    FinancingAgreement.objects.filter(pk=agreement_id).update(
        status=FinancingAgreement.Status.CANCELLED,
        is_archived=True,
    )

    response = admin_client.post(
        f'/api/financing/agreements/{agreement_id}/restore/',
        {},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['is_archived'] is False


def test_invalid_financing_transition_returns_conflict(
    admin_client,
    financing_client,
    agreement_template,
):
    created = _create_draft(admin_client, financing_client)

    response = admin_client.post(
        f'/api/financing/agreements/{created.data["id"]}/archive/',
        {},
        format='json',
    )

    assert response.status_code == 409
    assert response.data['code'] == 'invalid_transition'


def test_unknown_financing_action_returns_not_found(
    admin_client,
    financing_client,
    agreement_template,
):
    created = _create_draft(admin_client, financing_client)

    response = admin_client.post(
        f'/api/financing/agreements/{created.data["id"]}/unknown/',
        {},
        format='json',
    )

    assert response.status_code == 404


def test_draft_pdf_rejects_empty_contract_template(
    admin_client,
    financing_client,
    agreement_template,
):
    created = _create_draft(admin_client, financing_client)
    FinancingAgreement.objects.filter(pk=created.data['id']).update(
        contract_markdown='',
    )

    response = admin_client.get(
        f'/api/financing/agreements/{created.data["id"]}/draft-pdf/',
    )

    assert response.status_code == 400
    assert response.data['code'] == 'invalid_financing_agreement'


def test_signed_pdf_returns_not_found_before_activation(
    admin_client,
    financing_client,
    agreement_template,
):
    created = _create_draft(admin_client, financing_client)

    response = admin_client.get(
        f'/api/financing/agreements/{created.data["id"]}/signed-pdf/',
    )

    assert response.status_code == 404


def test_admin_downloads_registered_signed_pdf(
    admin_client,
    financing_client,
    agreement_template,
    company_settings,
    tmp_path,
    monkeypatch,
):
    field = FinancingAgreement._meta.get_field('signed_document')
    monkeypatch.setattr(
        field,
        'storage',
        FileSystemStorage(location=tmp_path, base_url=None),
    )
    created = _create_draft(admin_client, financing_client)
    agreement_id = created.data['id']
    admin_client.post(
        f'/api/financing/agreements/{agreement_id}/mark-ready/',
        {},
        format='json',
    )
    upload = BytesIO(b'%PDF-1.4\n%%EOF')
    upload.name = 'firmado.pdf'
    admin_client.post(
        f'/api/financing/agreements/{agreement_id}/upload-signed/',
        {'signed_document': upload},
        format='multipart',
    )

    response = admin_client.get(
        f'/api/financing/agreements/{agreement_id}/signed-pdf/',
    )

    assert response.status_code == 200
    assert response['Cache-Control'] == 'private, no-store'
    assert response['Content-Type'] == 'application/pdf'


def test_financing_templates_expose_known_placeholders(
    admin_client,
    agreement_template,
):
    response = admin_client.get('/api/financing/agreements/templates/')

    assert response.status_code == 200
    assert response.data['results'][0]['id'] == agreement_template.id
    assert 'installment_schedule' in response.data['known_placeholders']


def test_financing_client_context_lists_commercial_sources(
    admin_client,
    financing_client,
    proposal,
):
    proposal.client = financing_client
    proposal.save(update_fields=['client'])
    project = Project.objects.create(
        client=financing_client.user,
        name='Vástago operativo',
        status=Project.STATUS_ACTIVE,
    )

    response = admin_client.get(
        f'/api/financing/agreements/client-context/?client_id={financing_client.id}',
    )

    assert response.status_code == 200
    assert response.data['client']['id'] == financing_client.id
    assert response.data['proposals'][0]['id'] == proposal.id
    assert response.data['projects'][0]['id'] == project.id


def test_admin_create_rejects_incomplete_financing_payload(admin_client):
    response = admin_client.post(
        '/api/financing/agreements/',
        {},
        format='json',
    )

    assert response.status_code == 400
    assert 'client_id' in response.data


def test_admin_create_requires_active_financing_template(
    admin_client,
    financing_client,
):
    FinancingAgreementTemplate.objects.update(is_active=False)

    response = _create_draft(admin_client, financing_client)

    assert response.status_code == 400
    assert response.data['code'] == 'invalid_financing_agreement'
    assert 'template_id' in response.data


def test_admin_create_rejects_foreign_commercial_sources(
    admin_client,
    financing_client,
    agreement_template,
    make_client_profile,
    proposal,
):
    other_client = make_client_profile(company='Otro cliente SAS')
    proposal.client = other_client
    proposal.save(update_fields=['client'])
    project = Project.objects.create(
        client=other_client.user,
        name='Proyecto de otro cliente',
    )

    response = _create_draft(
        admin_client,
        financing_client,
        source_proposal_id=proposal.id,
        source_project_id=project.id,
    )

    assert response.status_code == 400
    assert {'source_proposal_id', 'source_project_id'} <= set(response.data)


def test_mark_ready_reports_incomplete_legal_snapshot(
    admin_client,
    financing_client,
    agreement_template,
    company_settings,
):
    created = _create_draft(admin_client, financing_client)
    company_settings.contractor_full_name = ''
    company_settings.contractor_nit = ''
    company_settings.contractor_cedula = ''
    company_settings.save()
    FinancingAgreement.objects.filter(pk=created.data['id']).update(
        client_full_name='',
        client_id_type='',
        client_id_number='',
        client_email='',
        financed_balance=Decimal('0.00'),
        hosting_value=Decimal('0.00'),
        partnership_end_date=date(2026, 2, 1),
    )

    response = admin_client.post(
        f'/api/financing/agreements/{created.data["id"]}/mark-ready/',
        {},
        format='json',
    )

    assert response.status_code == 400
    assert {
        'client_full_name',
        'client_id_type',
        'client_id_number',
        'client_email',
        'company_settings',
        'financed_balance',
        'hosting_value',
        'partnership_start_date',
    } <= set(response.data)


def test_upload_signed_rejects_non_pdf_payload(
    admin_client,
    financing_client,
    agreement_template,
    company_settings,
):
    created = _create_draft(admin_client, financing_client)
    agreement_id = created.data['id']
    admin_client.post(
        f'/api/financing/agreements/{agreement_id}/mark-ready/',
        {},
        format='json',
    )
    invalid_file = SimpleUploadedFile(
        'signed.txt',
        b'not a pdf',
        content_type='text/plain',
    )

    response = admin_client.post(
        f'/api/financing/agreements/{agreement_id}/upload-signed/',
        {'signed_document': invalid_file},
        format='multipart',
    )

    assert response.status_code == 400
    assert response.data['code'] == 'invalid_signed_pdf'


def test_cancel_requires_financing_reason(
    admin_client,
    financing_client,
    agreement_template,
):
    created = _create_draft(admin_client, financing_client)

    response = admin_client.post(
        f'/api/financing/agreements/{created.data["id"]}/cancel/',
        {'cancellation_reason': '   '},
        format='json',
    )

    assert response.status_code == 400
    assert 'cancellation_reason' in response.data
