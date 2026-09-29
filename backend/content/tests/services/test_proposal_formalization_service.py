"""Behavioral tests for the frozen formalization delivery package."""
import hashlib
from io import BytesIO
from pypdf import PdfReader
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from freezegun import freeze_time

from content.models import (
    BusinessProposal,
    EmailTemplateConfig,
    EmailLog,
    ProposalDocument,
    ProposalFormalization,
    ProposalFormalizationFile,
    ProposalSection,
)
from content.services.formalization_content import FormalizationError
from content.services.email_snapshot_service import EmailSnapshotCaptureError
from content.services.proposal_formalization_service import (
    availability,
    document_bytes,
    cleanup_expired,
    load_proposal,
    prepare,
    send_preparation,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def formalization_proposal(proposal):
    sections = {
        'functional_requirements': {
            'groups': [{'id': 'orders', 'title': 'Pedidos', 'items': [{
                'id': 'create-order', 'name': 'Crear pedido', 'description': 'Registra la orden.', 'is_required': True,
            }]}],
        },
        'investment': {'paymentOptions': [{'label': '100% al entregar', 'description': ''}]},
        'technical_document': {
            'purpose': 'Gestionar pedidos.',
            'epics': [{'epicKey': 'ORD', 'title': 'Pedidos', 'requirements': [{
                'flowKey': 'ORD-01', 'title': 'Crear pedido', 'description': 'Registra la orden.',
                'linked_item_ids': ['create-order'],
            }]}],
        },
    }
    for order, (section_type, content_json) in enumerate(sections.items()):
        ProposalSection.objects.create(
            proposal=proposal, section_type=section_type, title=section_type,
            order=order, content_json=content_json,
        )
    return proposal


@pytest.fixture
def formalization_payload():
    return {
        'documents': ['commercial', 'technical'],
        'additional_doc_ids': [],
        'subject': 'Documentación para formalización',
        'greeting': 'Hola Acme,',
        'body': 'Adjuntamos los documentos revisados para la formalización.',
        'footer': 'Equipo ProjectApp',
        'sections': [],
        'recipient_emails': ['contact@acme.com'],
        'cc_emails': [],
    }


@pytest.fixture
def formalization_attachment(formalization_proposal):
    document = ProposalDocument.objects.create(
        proposal=formalization_proposal,
        document_type=ProposalDocument.DOC_TYPE_LEGAL_ANNEX,
        title='Anexo de confidencialidad',
    )
    document.file.save('confidencialidad.pdf', ContentFile(b'confidential formal annex'), save=True)
    return document


def _stored_bytes(item):
    with item.file.open('rb') as stored:
        return stored.read()


def _send(preparation):
    return send_preparation(preparation)


@pytest.fixture
def complete_contract_params():
    return {
        'contractor_full_name': 'ProjectApp S.A.S.',
        'contractor_email': 'legal@projectapp.co',
        'contract_city': 'Medellín',
        'bank_name': 'Banco de Prueba',
        'bank_account_number': '123456789',
        'contractor_nit': '900123456-7',
        'client_full_name': 'Acme Corp',
        'client_cedula': '1234567890',
        'client_email': 'contact@acme.com',
        'contract_date': '2026-09-19',
    }


def test_availability_marks_an_invalid_final_contract_unavailable(
    formalization_proposal, complete_contract_params,
):
    """Fails if the panel enables a final contract whose saved bytes are not a PDF."""
    formalization_proposal.contract_params = complete_contract_params
    formalization_proposal.save(update_fields=['contract_params'])
    contract = ProposalDocument.objects.create(
        proposal=formalization_proposal,
        document_type=ProposalDocument.DOC_TYPE_CONTRACT,
        title='Contrato final',
        is_generated=True,
    )
    contract.file.save('contract.pdf', ContentFile(b'not a PDF'), save=True)

    contract_option = availability(formalization_proposal)[0]

    assert contract_option['key'] == 'contract'
    assert contract_option['available'] is False
    assert 'no es un PDF válido' in contract_option['error']


def test_prepare_freezes_the_requested_manifest(
    formalization_proposal, admin_user, formalization_payload, formalization_attachment,
):
    """Fails if the review manifest differs from the files frozen for delivery."""
    payload = {
        **formalization_payload,
        'additional_doc_ids': [formalization_attachment.pk],
    }

    preparation = prepare(formalization_proposal, admin_user, payload)

    assert list(preparation.files.values_list('key', flat=True)) == [
        'commercial', 'technical', f'additional-{formalization_attachment.pk}',
    ]
    commercial = preparation.files.get(key='commercial')
    technical = preparation.files.get(key='technical')
    annex = preparation.files.get(key=f'additional-{formalization_attachment.pk}')
    assert commercial.sha256 == hashlib.sha256(_stored_bytes(commercial)).hexdigest()
    assert technical.sha256 == hashlib.sha256(_stored_bytes(technical)).hexdigest()
    assert annex.sha256 == hashlib.sha256(_stored_bytes(annex)).hexdigest()
    assert commercial.filename in preparation.text_body
    assert technical.filename in preparation.text_body
    assert annex.filename in preparation.text_body


def test_prepare_rejects_combined_attachments_over_the_limit(
    monkeypatch, formalization_proposal, admin_user, formalization_payload,
):
    """Fails if individually valid attachments exceed the package limit after allocation."""
    first = ProposalDocument.objects.create(
        proposal=formalization_proposal,
        document_type=ProposalDocument.DOC_TYPE_OTHER,
        title='Primer anexo',
    )
    first.file.save('first.pdf', ContentFile(b'12345'), save=True)
    second = ProposalDocument.objects.create(
        proposal=formalization_proposal,
        document_type=ProposalDocument.DOC_TYPE_OTHER,
        title='Segundo anexo',
    )
    second.file.save('second.pdf', ContentFile(b'67890'), save=True)
    payload = {
        **formalization_payload,
        'documents': [],
        'additional_doc_ids': [first.pk, second.pk],
    }
    monkeypatch.setattr(
        'content.services.proposal_formalization_service.MAX_ATTACHMENT_BYTES', 8,
    )

    with pytest.raises(FormalizationError) as error:
        prepare(formalization_proposal, admin_user, payload)

    assert error.value.code == 'attachments_too_large'
    assert ProposalFormalization.objects.count() == 0
    assert ProposalFormalizationFile.objects.count() == 0


def test_prepare_rejects_an_inactive_formalization_template(
    formalization_proposal, admin_user, formalization_payload,
):
    """Fails if a disabled email template still writes a private review package."""
    EmailTemplateConfig.objects.create(
        template_key='proposal_formalization',
        is_active=False,
    )

    with pytest.raises(FormalizationError) as error:
        prepare(formalization_proposal, admin_user, formalization_payload)

    assert error.value.code == 'template_disabled'
    assert ProposalFormalization.objects.count() == 0
    assert ProposalFormalizationFile.objects.count() == 0


def test_send_records_the_frozen_package_in_history(
    mailoutbox, formalization_proposal, admin_user, formalization_payload, formalization_attachment,
):
    """Fails if a formalization email is delivered without its frozen evidence or proposal history."""
    payload = {
        **formalization_payload,
        'documents': ['commercial'],
        'additional_doc_ids': [formalization_attachment.pk],
    }
    preparation = prepare(formalization_proposal, admin_user, payload)
    commercial = preparation.files.get(key='commercial')
    annex = preparation.files.get(key=f'additional-{formalization_attachment.pk}')

    delivered = _send(preparation)
    history = EmailLog.objects.get(template_key='proposal_formalization', recipient='contact@acme.com')

    assert delivered.status == ProposalFormalization.Status.SENT
    assert mailoutbox[0].to == ['contact@acme.com']
    assert [(attachment.filename, attachment.content) for attachment in mailoutbox[0].attachments] == [
        (commercial.filename, _stored_bytes(commercial)),
        (annex.filename, _stored_bytes(annex)),
    ]
    assert history.proposal_id == formalization_proposal.pk
    assert list(history.snapshot.attachments.values_list('filename', flat=True)) == [
        commercial.filename, annex.filename,
    ]


def test_send_marks_snapshot_failure_as_consumed(
    formalization_proposal, admin_user, formalization_payload,
):
    """Fails if an unarchived formalization can be delivered on a later retry."""
    preparation = prepare(formalization_proposal, admin_user, formalization_payload)

    with patch(
        'content.services.proposal_formalization_service.EmailDeliveryGateway.send',
        side_effect=EmailSnapshotCaptureError('snapshot unavailable'),
    ):
        delivery = _send(preparation)
        with pytest.raises(FormalizationError) as error:
            _send(preparation)

    assert delivery.status == ProposalFormalization.Status.FAILED
    assert delivery.error == 'No se pudo guardar la evidencia del envío; el correo no fue enviado.'
    assert error.value.code == 'preparation_consumed'


@pytest.mark.parametrize(
    ('gateway_options', 'expected_status'),
    [
        ({'side_effect': RuntimeError('SMTP unavailable')}, ProposalFormalization.Status.UNKNOWN),
        ({'return_value': 0}, ProposalFormalization.Status.FAILED),
    ],
)
def test_send_consumes_the_preparation_after_gateway_failure(
    gateway_options, expected_status, formalization_proposal, admin_user, formalization_payload,
):
    """Fails if an uncertain or rejected delivery can be retried from the same review."""
    preparation = prepare(formalization_proposal, admin_user, formalization_payload)

    with patch('content.services.proposal_formalization_service.EmailDeliveryGateway.send', **gateway_options) as delivery:
        delivered = _send(preparation)
        with pytest.raises(FormalizationError) as error:
            _send(preparation)

    assert delivered.status == expected_status
    assert error.value.code == 'preparation_consumed'
    assert delivery.call_count == 1


@patch('content.services.proposal_formalization_service.EmailDeliveryGateway.send')
def test_send_rejects_a_preparation_when_its_source_changed(
    delivery, formalization_proposal, admin_user, formalization_payload,
):
    """Fails if a reviewed package can be sent after its proposal source changes."""
    preparation = prepare(formalization_proposal, admin_user, formalization_payload)
    formalization_proposal.title = 'Revised scope title'
    formalization_proposal.save(update_fields=['title'])

    with pytest.raises(FormalizationError) as error:
        _send(preparation)

    assert error.value.code == 'stale_preparation'
    assert error.value.status == 409
    delivery.assert_not_called()


def test_prepare_rejects_a_section_changed_after_the_admin_load(
    formalization_proposal, admin_user, formalization_payload,
):
    """Fails if a package freezes stale sections after the panel loaded the proposal."""
    captured = load_proposal(formalization_proposal.pk)
    ProposalSection.objects.filter(
        proposal=formalization_proposal,
        section_type='technical_document',
    ).update(content_json={
        'purpose': 'Changed after panel load.',
        'epics': [{'epicKey': 'ORD', 'title': 'Pedidos', 'requirements': [{
            'flowKey': 'ORD-02', 'title': 'Cambió el alcance', 'description': 'Nuevo detalle.',
        }]}],
    })

    with pytest.raises(FormalizationError) as error:
        prepare(captured, admin_user, formalization_payload)

    assert error.value.code == 'stale_preparation'
    assert error.value.status == 409


@patch('content.services.proposal_formalization_service.EmailDeliveryGateway.send')
def test_send_rejects_a_missing_private_attachment(
    delivery, formalization_proposal, admin_user, formalization_payload,
):
    """Fails if delivery proceeds after one of the reviewed private files has disappeared."""
    preparation = prepare(formalization_proposal, admin_user, formalization_payload)
    missing = preparation.files.get(key='commercial')
    missing.file.delete(save=True)

    with pytest.raises(FormalizationError) as error:
        _send(preparation)

    assert error.value.code == 'attachment_changed'
    assert error.value.status == 409
    delivery.assert_not_called()


def test_send_rejects_a_preparation_after_its_first_delivery(
    mailoutbox, formalization_proposal, admin_user, formalization_payload,
):
    """Fails if a double-click delivers the same formalization package twice."""
    preparation = prepare(formalization_proposal, admin_user, formalization_payload)

    first_delivery = _send(preparation)
    with pytest.raises(FormalizationError) as error:
        _send(preparation)

    assert first_delivery.status == ProposalFormalization.Status.SENT
    assert error.value.code == 'preparation_consumed'
    assert error.value.status == 409
    assert len(mailoutbox) == 1
    assert EmailLog.objects.filter(template_key='proposal_formalization').count() == 1


@freeze_time('2026-09-19 12:00:00')
def test_prepare_rejects_an_attachment_from_another_proposal(
    formalization_proposal, admin_user, formalization_payload,
):
    """Fails if another proposal's private document can be included in this email."""
    other_proposal = BusinessProposal.objects.create(
        title='Other proposal', client_name='Other client', client_email='other@example.com',
        total_investment='1000.00', currency='COP', expires_at=timezone.now() + timedelta(days=1),
    )
    other_document = ProposalDocument.objects.create(
        proposal=other_proposal, document_type=ProposalDocument.DOC_TYPE_OTHER, title='Private other document',
    )
    other_document.file.save('other-private.pdf', ContentFile(b'other private bytes'), save=True)
    payload = {**formalization_payload, 'additional_doc_ids': [other_document.pk]}

    with pytest.raises(FormalizationError) as error:
        prepare(formalization_proposal, admin_user, payload)

    assert error.value.code == 'invalid_attachment'


@pytest.mark.django_db(transaction=True)
@freeze_time('2026-09-19 12:00:00')
def test_cleanup_expired_deletes_the_private_preparation_file(formalization_proposal, admin_user):
    """Fails if expired preview files remain in private storage after cleanup."""
    preparation = ProposalFormalization.objects.create(
        proposal=formalization_proposal, created_by=admin_user, payload={}, source_hash='a' * 64,
        html_body='preview', text_body='preview', expires_at=timezone.now() - timedelta(seconds=1),
    )
    attachment = ProposalFormalizationFile.objects.create(
        preparation=preparation, key='commercial', filename='formal.pdf', description='Formal PDF',
        mime_type='application/pdf', sha256=hashlib.sha256(b'private formal bytes').hexdigest(), size=20,
    )
    attachment.file.save('formal.pdf', ContentFile(b'private formal bytes'), save=True)
    private_path = attachment.file.name
    storage = attachment.file.storage

    deleted = cleanup_expired()

    assert deleted == 1
    assert not ProposalFormalization.objects.filter(pk=preparation.pk).exists()
    assert storage.exists(private_path) is False


@pytest.mark.parametrize('kind', ['commercial', 'technical'])
def test_prepared_annex_matches_the_downloaded_document(
    formalization_proposal, admin_user, formalization_payload, kind,
):
    """The attachment reviewed for email must have the same content as Download PDF."""
    downloaded = document_bytes(formalization_proposal, kind)

    prepared = prepare(formalization_proposal, admin_user, {
        **formalization_payload, 'documents': [kind],
    })

    raw = _stored_bytes(prepared.files.get(key=kind))
    rendered = [page.extract_text() for page in PdfReader(BytesIO(raw)).pages]
    expected = [page.extract_text() for page in PdfReader(BytesIO(downloaded)).pages]
    assert any('Crear pedido' in page for page in rendered)
    assert rendered == expected
