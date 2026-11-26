"""Panel create/preview/next-number endpoints for cuentas de cobro."""
import io
from decimal import Decimal
from unittest.mock import patch

import pytest
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from pypdf import PdfReader
from freezegun import freeze_time

from content.models import (
    ClientDocumentNumberSequence,
    Document,
    EmailLog,
    IncomeRecord,
    IssuerProfile,
)
from content.services import collection_account_email_service
from content.services.document_type_utils import (
    get_collection_account_document_type,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def issuer(settings):
    settings.MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
        },
    }
    profile = IssuerProfile.objects.order_by('pk').first()
    profile.city = 'Bogotá'
    profile.default_payment_methods = [
        {'payment_method_type': 'bank_transfer', 'bank_name': 'Bancolombia'},
    ]
    profile.save()
    return profile


def make_client(email='ana@acme.co', company='Acme Soluciones', **profile_kwargs):
    user = User.objects.create_user(
        username=email, email=email, password='pass12345',
        first_name='Ana', last_name='Pérez',
    )
    UserProfile.objects.create(user=user, company_name=company, **profile_kwargs)
    return user


def make_income(**overrides):
    fields = {
        'concept': 'Desarrollo módulo de reportes',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': '2026-08-01',
        'total_amount': Decimal('1490000.00'),
        'gustavo_amount': Decimal('745000.00'),
        'carlos_amount': Decimal('745000.00'),
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


def payload(client_user, income, **overrides):
    data = {
        'client_profile_id': client_user.profile.pk,
        'income_record_id': income.pk,
        'items': [{
            'description': 'Desarrollo módulo de reportes',
            'quantity': '1',
            'unit_price': '1490000.00',
        }],
    }
    data.update(overrides)
    return data


VAT_CASES = [
    ('0', 'before_vat', '100000.00', '100000.00', '0.00', '100000.00'),
    ('0', 'vat_included', '100000.00', '100000.00', '0.00', '100000.00'),
    ('19', 'before_vat', '100000.00', '100000.00', '19000.00', '119000.00'),
    ('19', 'vat_included', '119000.00', '100000.00', '19000.00', '119000.00'),
]


@pytest.fixture
def vat_payload_factory():
    """Build separate income-backed payloads for preview and issue tests."""
    def build(*, vat_rate='19', amount_mode='vat_included', amount='119000.00', show_vat=True):
        return payload(
            make_client(), make_income(), vat_rate=vat_rate, show_vat=show_vat,
            items=[{
                'description': 'Servicio fiscal de prueba',
                'amount': amount,
                'amount_mode': amount_mode,
            }],
        )
    return build


def pdf_text(pdf_bytes):
    return ''.join(
        page.extract_text() for page in PdfReader(io.BytesIO(pdf_bytes)).pages
    )


class TestCreateEndpoint:
    def test_create_issues_and_emails(self, super_client, mailoutbox):
        client = make_client(nit='901234567')
        income = make_income()

        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(client, income),
            format='json',
        )

        assert response.status_code == 201, response.data
        assert response.data['email_sent'] is True
        doc = response.data['document']
        assert doc['public_number'] == 'PA-ACMESOLU-001'
        assert doc['origin'] == 'income'
        assert doc['income_record_id'] == income.pk
        assert len(mailoutbox) == 1
        assert 'PA-ACMESOLU-001' in mailoutbox[0].subject
        assert mailoutbox[0].attachments[0][0] == 'PA-ACMESOLU-001.pdf'

    def test_an_ampersand_code_survives_the_whole_document_chain(
        self, super_client, mailoutbox, settings, tmp_path,
    ):
        """G&M is a real trade name; the code has to reach every consumer.

        One test rather than four because the point is the chain: consecutivo,
        PDF attachment name, email subject and the served URL all derive from
        the same string and each escapes it differently.
        """
        settings.MEDIA_ROOT = tmp_path
        client = make_client(
            email='gym@example.co', company='G&M', nit='901234567',
            billing_code='G&M',
        )
        income = make_income()

        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(client, income),
            format='json',
        )

        assert response.status_code == 201, response.data
        assert response.data['document']['public_number'] == 'PA-G&M-001'
        # Subject and attachment keep the code verbatim...
        assert 'PA-G&M-001' in mailoutbox[0].subject
        assert mailoutbox[0].attachments[0][0] == 'PA-G&M-001.pdf'

        doc_id = response.data['document']['id']
        document = Document.objects.get(pk=doc_id)
        with document.generated_file.open('rb') as stored_file:
            stored_pdf = stored_file.read()
        with patch(
            'content.services.collection_account_pdf_service'
            '.CollectionAccountPdfService.generate',
            side_effect=AssertionError('served PDF must not be regenerated'),
        ) as generate:
            pdf = super_client.get(
                f'/api/accounting/collection-accounts/{doc_id}/pdf/',
            )
        assert pdf.status_code == 200
        assert pdf.content == stored_pdf
        assert mailoutbox[0].attachments[0][1] == stored_pdf
        generate.assert_not_called()
        # ...and so does the download name, via Django's header builder.
        assert pdf['Content-Disposition'] == (
            'attachment; filename="PA-G&M-001.pdf"'
        )

    def test_email_failure_keeps_document_issued(self, super_client):
        client = make_client()
        income = make_income()

        with patch.object(
            collection_account_email_service.EmailMultiAlternatives,
            'send',
            side_effect=OSError('smtp down'),
        ):
            response = super_client.post(
                '/api/accounting/collection-accounts/create/',
                payload(client, income),
                format='json',
            )

        assert response.status_code == 201
        assert response.data['email_sent'] is False
        assert response.data['document']['commercial_status'] == 'issued'
        assert EmailLog.objects.filter(status=EmailLog.Status.FAILED).exists()

    def test_duplicate_income_rejected(self, super_client):
        client = make_client()
        income = make_income()
        super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(client, income),
            format='json',
        )

        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(client, income),
            format='json',
        )

        assert response.status_code == 400
        assert 'ya tiene una cuenta de cobro' in response.data['error']

    def test_items_required(self, super_client):
        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(make_client(), make_income(), items=[]),
            format='json',
        )
        assert response.status_code == 400

    def test_a_zero_day_term_survives_the_round_trip(self, super_client):
        """Immediate payment has to reach the document as a real 0: the
        serializer used to reject it and the service then read it as "unset"
        and quietly billed the 8-day default instead."""
        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(make_client(), make_income(), payment_term_days=0),
            format='json',
        )

        assert response.status_code == 201, response.data
        doc = Document.objects.get(pk=response.data['document']['id'])
        assert doc.collection_account.payment_term_days == 0
        assert doc.collection_account.due_date_mode == 'legacy'
        assert doc.due_date is None
        assert response.data['document']['due_date'] is None
        assert response.data['document']['is_overdue'] is False

    @pytest.mark.parametrize(
        ('vat_rate', 'amount_mode', 'amount', 'subtotal', 'tax_total', 'total'), VAT_CASES,
    )
    @pytest.mark.parametrize('show_vat', [True, False])
    def test_issued_vat_choices_preserve_the_exact_money(
        self, super_client, vat_payload_factory, vat_rate, amount_mode, amount,
        subtotal, tax_total, total, show_vat,
    ):
        """Hiding IVA changes presentation only, never the tax calculation."""
        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            vat_payload_factory(
                vat_rate=vat_rate, amount_mode=amount_mode, amount=amount,
                show_vat=show_vat,
            ),
            format='json',
        )

        assert response.status_code == 201, response.data
        document = Document.objects.get(pk=response.data['document']['id'])
        detail = super_client.get(
            f'/api/accounting/collection-accounts/{document.pk}/',
        )
        assert document.collection_account.show_vat is show_vat
        assert detail.data['show_vat'] is show_vat
        assert tuple(map(Decimal, (
            detail.data['subtotal'], detail.data['tax_total'], detail.data['total'],
        ))) == tuple(map(Decimal, (subtotal, tax_total, total)))

    @pytest.mark.parametrize('show_vat', [True, False])
    def test_preview_controls_its_html_and_pdf_tax_breakdown(
        self, super_client, vat_payload_factory, show_vat,
    ):
        """Preview must match the chosen presentation without creating a row."""
        before = Document.objects.count()
        response = super_client.post(
            '/api/accounting/collection-accounts/preview/',
            vat_payload_factory(show_vat=show_vat),
            format='json',
        )

        assert response.status_code == 200, response.data
        assert Document.objects.count() == before
        assert ('Valor antes de IVA' in response.data['html_body']) is show_vat
        preview = super_client.get(response.data['pdf_url'])
        assert ('Valor antes de IVA' in pdf_text(preview.content)) is show_vat

    @pytest.mark.parametrize('show_vat', [True, False])
    def test_issue_and_resend_reuse_the_archived_vat_pdf(
        self, super_client, mailoutbox, settings, tmp_path, vat_payload_factory,
        show_vat,
    ):
        """Client delivery uses the same archived bytes on its initial send and resend."""
        settings.MEDIA_ROOT = tmp_path
        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            vat_payload_factory(show_vat=show_vat), format='json',
        )
        document = Document.objects.get(pk=response.data['document']['id'])
        with document.generated_file.open('rb') as archived:
            archived_pdf = archived.read()
        initial = mailoutbox[0]
        resent = super_client.post(
            f'/api/accounting/collection-accounts/{document.pk}/resend/', format='json',
        )

        assert resent.status_code == 200, resent.data
        assert ('Valor antes de IVA' in initial.body) is show_vat
        assert ('Valor antes de IVA' in initial.alternatives[0][0]) is show_vat
        assert initial.attachments[0][1] == archived_pdf
        assert mailoutbox[1].attachments[0][1] == archived_pdf

    @freeze_time('2026-04-01 12:00:00-05:00')
    def test_explicit_dated_zero_day_term_is_due_on_its_bogota_issue_date(
        self, super_client,
    ):
        """An explicit dated zero is a same-day deadline, not legacy payment
        on delivery, and must survive the panel response."""
        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(
                make_client(), make_income(), payment_term_days=0,
                due_date_mode='dated',
            ),
            format='json',
        )

        assert response.status_code == 201, response.data
        document = Document.objects.get(pk=response.data['document']['id'])
        assert document.issue_date.isoformat() == '2026-04-01'
        assert document.due_date.isoformat() == '2026-04-01'
        assert response.data['document']['due_date'] == '2026-04-01'
        assert response.data['document']['due_date_mode'] == 'dated'
        assert response.data['document']['is_overdue'] is False

    @freeze_time('2026-04-01 12:00:00-05:00')
    def test_default_term_is_due_eight_days_after_the_bogota_issue_date(
        self, super_client,
    ):
        """The omitted term remains the agreed eight-day default."""
        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(make_client(), make_income()),
            format='json',
        )

        assert response.status_code == 201, response.data
        document = Document.objects.get(pk=response.data['document']['id'])
        assert document.collection_account.payment_term_days == 8
        assert document.due_date.isoformat() == '2026-04-09'

    def test_no_deadline_mode_persists_no_due_date(self, super_client):
        """A deliberate no-date selection cannot acquire a silent deadline."""
        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(make_client(), make_income(), due_date_mode='none'),
            format='json',
        )

        assert response.status_code == 201, response.data
        document = Document.objects.get(pk=response.data['document']['id'])
        assert document.collection_account.due_date_mode == 'none'
        assert document.collection_account.payment_term_days is None
        assert document.due_date is None

    def test_resending_a_paid_dated_account_preserves_its_deadline_everywhere(
        self, super_client, mailoutbox, settings, tmp_path,
    ):
        """The paid resend is a historical record: its HTML, text and archived
        PDF must keep the explicit deadline rather than reverting to legacy."""
        settings.MEDIA_ROOT = tmp_path
        created = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(
                make_client(), make_income(), due_date_mode='dated',
                due_date='2026-08-21',
            ),
            format='json',
        )
        document = Document.objects.get(pk=created.data['document']['id'])
        document.commercial_status = Document.CommercialStatus.PAID
        document.save(update_fields=['commercial_status'])

        resent = super_client.post(
            f'/api/accounting/collection-accounts/{document.pk}/resend/',
            format='json',
        )

        assert resent.status_code == 200, resent.data
        resent_message = mailoutbox[1]
        assert 'Fecha límite de pago' in resent_message.body
        assert 'Fecha límite de pago' in resent_message.alternatives[0][0]
        resent_pdf_text = ''.join(
            page.extract_text()
            for page in PdfReader(io.BytesIO(resent_message.attachments[0][1])).pages
        )
        assert 'Fecha de vencimiento' in resent_pdf_text
        assert '21 de agosto de 2026' in resent_pdf_text

    @pytest.mark.parametrize(
        ('overrides', 'field'),
        [
            ({'due_date_mode': 'none', 'payment_term_days': 8}, 'due_date_mode'),
            ({'due_date_mode': 'none', 'due_date': '2026-04-20'}, 'due_date_mode'),
            ({'due_date_mode': 'dated', 'due_date': '2026-04-20', 'payment_term_days': 8}, 'due_date'),
        ],
    )
    def test_rejects_contradictory_due_date_requests(
        self, super_client, overrides, field,
    ):
        """The API must not quietly choose between mutually exclusive terms."""
        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(make_client(), make_income(), **overrides),
            format='json',
        )

        assert response.status_code == 400
        assert field in response.data

    def test_a_negative_term_is_rejected(self, super_client):
        response = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(make_client(), make_income(), payment_term_days=-5),
            format='json',
        )

        assert response.status_code == 400

    def test_requires_superuser(self, admin_client):
        response = admin_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(make_client(), make_income()),
            format='json',
        )
        assert response.status_code == 403


class TestNextNumberEndpoint:
    def test_suggests_without_consuming(self, super_client):
        client = make_client()

        first = super_client.get(
            f'/api/accounting/collection-accounts/next-number/?client_profile_id={client.profile.pk}',
        )
        second = super_client.get(
            f'/api/accounting/collection-accounts/next-number/?client_profile_id={client.profile.pk}',
        )

        assert first.status_code == 200
        # No NIT on this client, so the series belongs to the person. The
        # sibling tests above pass nit=... and still get PA-ACMESOLU-001:
        # the code follows the identification, it does not just prefer people.
        assert first.data['suggested_number'] == 'PA-ANAPEREZ-001'
        assert first.data['billing_code'] == 'ANAPEREZ'
        assert first.data['issuer_city'] == 'Bogotá'
        assert second.data['suggested_number'] == 'PA-ANAPEREZ-001'

    def test_missing_param_is_400(self, super_client):
        response = super_client.get(
            '/api/accounting/collection-accounts/next-number/',
        )
        assert response.status_code == 400


class TestPreviewEndpoint:
    def test_preview_renders_without_persisting(self, super_client, mailoutbox):
        client = make_client(nit='901234567')
        income = make_income()
        docs_before = Document.objects.count()

        response = super_client.post(
            '/api/accounting/collection-accounts/preview/',
            payload(client, income),
            format='json',
        )

        assert response.status_code == 200, response.data
        assert response.data['public_number'] == 'PA-ACMESOLU-001'
        assert 'PA-ACMESOLU-001' in response.data['subject']
        assert 'Valor a pagar' in response.data['html_body']
        # A served URL, not base64 for a blob: the viewer names its download
        # after the URL and the header, and a blob: URL carries neither.
        assert response.data['pdf_url'].endswith('/PA-ACMESOLU-001.pdf')
        # Nothing persisted: no document, no email, no consecutivo consumed.
        assert Document.objects.count() == docs_before
        assert not EmailLog.objects.exists()
        assert len(mailoutbox) == 0
        seq = ClientDocumentNumberSequence.objects.filter(
            client_profile=client.profile,
        ).first()
        assert seq is None or seq.last_value == 0

    def test_preview_names_what_the_last_notice_shows(self, super_client):
        """The panel's last notice reads these from the rolled-back issue."""
        from freezegun import freeze_time

        client = make_client()
        with freeze_time('2026-08-10 15:00:00'):
            response = super_client.post(
                '/api/accounting/collection-accounts/preview/',
                payload(
                    client, make_income(),
                    billing_concept='Desarrollo módulo de reportes',
                ),
                format='json',
            )

        assert response.status_code == 200, response.data
        assert response.data['issue_date'] == '2026-08-10'
        assert response.data['customer_name'] == 'Ana Pérez'
        assert response.data['project_name'] == ''
        assert response.data['billing_concept'] == 'Desarrollo módulo de reportes'

    def test_preview_surfaces_manual_number_collision(self, super_client):
        Document.objects.create(
            document_type=get_collection_account_document_type(),
            title='Legacy',
            public_number='PA-2026-0001',
            total=Decimal('1'),
        )
        response = super_client.post(
            '/api/accounting/collection-accounts/preview/',
            payload(
                make_client(), make_income(), public_number='PA-2026-0001',
            ),
            format='json',
        )
        assert response.status_code == 400
        assert 'ya está en uso' in response.data['error']

    def test_preview_number_matches_created_number(self, super_client):
        client = make_client()
        income = make_income()

        preview = super_client.post(
            '/api/accounting/collection-accounts/preview/',
            payload(client, income),
            format='json',
        )
        created = super_client.post(
            '/api/accounting/collection-accounts/create/',
            payload(client, income),
            format='json',
        )

        assert (
            preview.data['public_number']
            == created.data['document']['public_number']
        )


class TestPreviewPdfEndpoint:
    """The URL the preview modal embeds. It exists so Chrome's viewer has a
    filename to propose: from a blob: URL it fell back to the blob's own UUID
    in its download button and in 'Save to Drive'."""

    def _preview_pdf_url(self, super_client):
        response = super_client.post(
            '/api/accounting/collection-accounts/preview/',
            payload(make_client(nit='901234567'), make_income()),
            format='json',
        )
        assert response.status_code == 200, response.data
        return response.data['pdf_url']

    def test_serves_the_pdf_named_after_the_consecutivo(self, super_client):
        response = super_client.get(self._preview_pdf_url(super_client))

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        # `inline`, not `attachment`: this URL is what the modal embeds.
        assert response['Content-Disposition'] == (
            'inline; filename="PA-ACMESOLU-001.pdf"'
        )
        assert response.content[:4] == b'%PDF'

    def test_allows_same_origin_embedding(self, super_client):
        """The middleware default is DENY, which browsers honour for <embed>
        too — the modal's viewer rendered a connection-refused page instead of
        the document until the view opted into SAMEORIGIN."""
        response = super_client.get(self._preview_pdf_url(super_client))

        assert response['X-Frame-Options'] == 'SAMEORIGIN'

    def test_url_ends_in_the_consecutivo(self, super_client):
        """Belt and braces for a viewer that ignores the header and names the
        download after the last path segment."""
        assert self._preview_pdf_url(super_client).endswith(
            '/PA-ACMESOLU-001.pdf',
        )

    def test_a_hand_typed_consecutivo_cannot_break_the_url_or_the_header(
        self, super_client,
    ):
        """The consecutivo is a free-text field. A '/' fits in no path segment
        and a '"' would end the header's quoted filename early."""
        response = super_client.post(
            '/api/accounting/collection-accounts/preview/',
            payload(
                make_client(nit='901234567'), make_income(),
                public_number='PA/ACME "01"',
            ),
            format='json',
        )
        assert response.status_code == 200, response.data

        pdf = super_client.get(response.data['pdf_url'])

        assert pdf.status_code == 200
        # The path segment carries a sanitised name...
        assert response.data['pdf_url'].endswith('/PA-ACME-01-.pdf')
        # ...while the header keeps the real one, escaped rather than truncated.
        assert pdf['Content-Disposition'] == (
            'inline; filename="PA/ACME \\"01\\".pdf"'
        )

    def test_expired_token_is_a_404_the_operator_can_act_on(self, super_client):
        response = super_client.get(
            '/api/accounting/collection-accounts/preview/'
            'not-a-live-token/PA-ACMESOLU-001.pdf',
        )

        assert response.status_code == 404
        assert 'expiró' in response.data['error']

    def test_requires_superuser(self, admin_client):
        response = admin_client.get(
            '/api/accounting/collection-accounts/preview/'
            'any-token/PA-ACMESOLU-001.pdf',
        )

        assert response.status_code == 403
