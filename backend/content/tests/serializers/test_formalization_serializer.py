"""Input boundaries for formalization review requests."""
import pytest

from content.serializers.formalization import FormalizationPrepareSerializer


@pytest.fixture
def formalization_payload():
    return {
        'documents': ['commercial'],
        'additional_doc_ids': [],
        'subject': 'Documentación para formalización',
        'greeting': 'Hola Acme,',
        'body': 'Adjuntamos los documentos revisados.',
        'footer': 'Equipo ProjectApp',
        'sections': [],
        'recipient_emails': ['contact@acme.com'],
        'cc_emails': [],
    }


@pytest.mark.parametrize('subject', ['Asunto\rInyectado', 'Asunto\nInyectado'])
def test_subject_rejects_header_injection(formalization_payload, subject):
    """Fails if a formalization subject permits an injected email header."""
    serializer = FormalizationPrepareSerializer(data={**formalization_payload, 'subject': subject})

    valid = serializer.is_valid()

    assert valid is False
    assert serializer.errors['subject'] == ['El asunto debe ocupar una sola línea.']


@pytest.mark.parametrize(
    ('payload_change', 'error_field', 'error_message'),
    [
        ({'documents': [], 'additional_doc_ids': []}, 'non_field_errors', 'Selecciona al menos un documento.'),
        ({'documents': ['commercial', 'commercial']}, 'documents', 'No repitas documentos.'),
        ({'additional_doc_ids': [12, 12]}, 'additional_doc_ids', 'No repitas documentos.'),
    ],
)
def test_request_rejects_an_invalid_document_selection(
    formalization_payload, payload_change, error_field, error_message,
):
    """Fails if a request has no attachment or repeats one attachment selection."""
    serializer = FormalizationPrepareSerializer(data={**formalization_payload, **payload_change})

    valid = serializer.is_valid()

    assert valid is False
    assert serializer.errors[error_field] == [error_message]


def test_request_normalizes_recipient_addresses(formalization_payload):
    """Fails if recipient address casing reaches the prepared email unchanged."""
    serializer = FormalizationPrepareSerializer(data={
        **formalization_payload,
        'recipient_emails': ['Contact@Acme.COM'],
        'cc_emails': ['Copy@Acme.COM'],
    })

    valid = serializer.is_valid()

    assert valid is True
    assert serializer.validated_data['recipient_emails'] == ['contact@acme.com']
    assert serializer.validated_data['cc_emails'] == ['copy@acme.com']


def test_request_rejects_a_recipient_duplicated_across_to_cc(formalization_payload):
    """Fails if the same logical recipient can receive To and CC copies."""
    serializer = FormalizationPrepareSerializer(data={
        **formalization_payload,
        'recipient_emails': ['Contact@Acme.COM'],
        'cc_emails': ['contact@acme.com'],
    })

    valid = serializer.is_valid()

    assert valid is False
    assert serializer.errors['non_field_errors'] == [
        'El correo contact@acme.com no puede estar en Para y CC al mismo tiempo.',
    ]


def test_documents_field_accepts_the_split_closing_document_keys(formalization_payload):
    """Fails if the split closing's product/service contract keys are rejected by the field."""
    serializer = FormalizationPrepareSerializer(data={
        **formalization_payload,
        'documents': ['contract_product', 'contract_service', 'commercial', 'technical'],
    })

    valid = serializer.is_valid()

    assert valid is True
    assert serializer.validated_data['documents'] == [
        'contract_product', 'contract_service', 'commercial', 'technical',
    ]
