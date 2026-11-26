"""API tests for the panel collection accounts (Cobros) endpoints."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import HostingSubscription, Payment, Project, UserProfile
from accounts.services.hosting_context import reconcile_hosting

from content.models import (
    Document,
    DocumentCollectionAccount,
    HostingRecord,
    IncomeRecord,
    IssuerProfile,
)
from content.services.document_type_utils import (
    get_collection_account_document_type,
)
from content.services.hosting_billing_service import (
    send_hosting_collection_account,
)
from content.services.hosting_periods import current_summary

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def issuer(settings):
    settings.MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
        },
    }
    profile = IssuerProfile.objects.order_by('pk').first()
    profile.default_payment_methods = [
        {'payment_method_type': 'bank_transfer', 'bank_name': 'Bancolombia'},
    ]
    profile.save()
    return profile


def make_hosting(**overrides):
    defaults = {
        'client_name': 'German - Kore',
        'client_email': 'german@korehealths.com',
        'domain_url': 'https://korehealths.com/',
        'monthly_value': Decimal('91667.00'),
        'payment_modality': 'semiannual',
        'payment_per_cycle': Decimal('550002.00'),
        'valid_to': date(2026, 7, 20),
        'is_active': True,
    }
    defaults.update(overrides)
    return HostingRecord.objects.create(**defaults)


def emission_payload(hosting, actor, *, profile_email=None):
    email = profile_email if profile_email is not None else f'client-{hosting.pk}@example.test'
    user = User.objects.create_user(
        username=f'client-{hosting.pk}@example.test', email=email,
    )
    profile, _ = UserProfile.objects.update_or_create(
        user=user,
        defaults={'role': UserProfile.ROLE_CLIENT, 'company_name': hosting.client_name},
    )
    project = Project.objects.create(
        name=f'Hosting {hosting.pk}', client=user, status=Project.STATUS_ACTIVE,
    )
    hosting.client = profile
    hosting.project = project
    hosting.save(update_fields=['client', 'project'])
    subscription = HostingSubscription.objects.create(
        project=project,
        plan=HostingSubscription.PLAN_SEMIANNUAL,
        base_monthly_amount=hosting.monthly_value,
        effective_monthly_amount=hosting.monthly_value,
        billing_amount=hosting.payment_per_cycle,
        start_date=date(2026, 1, 20),
        status=HostingSubscription.STATUS_ACTIVE,
    )
    payment = Payment.objects.create(
        subscription=subscription,
        amount=hosting.payment_per_cycle,
        status=Payment.STATUS_PENDING,
        billing_period_start=date(2026, 7, 20),
        billing_period_end=date(2027, 1, 19),
        due_date=date(2026, 7, 20),
    )
    reconcile_hosting(project.pk, actor, {
        'expected_version': 0,
        'reason': 'Período pendiente verificado por la fixture.',
        'subscription_id': subscription.pk,
        'hosting_record_ids': [hosting.pk],
        'operational_record_id': hosting.pk,
    })
    summary = current_summary(project.pk)
    return {
        'hosting_payment_id': payment.pk,
        'period_version': summary['version'],
    }


def issue_for(hosting):
    return send_hosting_collection_account(hosting)['document']


class TestSendEndpoint:
    def test_send_creates_and_emails(self, super_client, superuser):
        hosting = make_hosting()
        payload = emission_payload(hosting, superuser)
        response = super_client.post(
            f'/api/accounting/hostings/{hosting.pk}/send-collection-account/',
            payload,
            format='json',
        )
        assert response.status_code == 201, response.data
        assert response.data['email_sent'] is True
        assert response.data['document']['public_number']
        assert response.data['document']['origin'] == 'hosting'
        hosting.refresh_from_db()
        assert hosting.billing_requested_at is not None

    def test_send_without_client_email_returns_400(self, super_client, superuser):
        hosting = make_hosting(client_email='')
        payload = emission_payload(hosting, superuser, profile_email='')
        response = super_client.post(
            f'/api/accounting/hostings/{hosting.pk}/send-collection-account/',
            payload,
            format='json',
        )
        assert response.status_code == 400
        assert 'email' in response.data['error']

    def test_requires_superuser(self, admin_client):
        hosting = make_hosting()
        response = admin_client.post(
            f'/api/accounting/hostings/{hosting.pk}/send-collection-account/',
        )
        assert response.status_code == 403


class TestListAndDetail:
    def test_list_filters_and_meta(self, super_client):
        issue_for(make_hosting())
        other = issue_for(make_hosting(
            client_name='Nestor - Xpandia',
            client_email='nestor@xpandia.global',
            domain_url='https://xpandia.global/',
        ))
        other.commercial_status = Document.CommercialStatus.PAID
        other.save(update_fields=['commercial_status'])

        response = super_client.get('/api/accounting/collection-accounts/')
        assert response.status_code == 200
        assert len(response.data['results']) == 2
        assert response.data['meta']['issued_count'] == 1
        assert response.data['meta']['paid_count'] == 1
        assert response.data['meta']['issued_total'] == '550002.00'

        issued_only = super_client.get(
            '/api/accounting/collection-accounts/?commercial_status=issued',
        )
        assert len(issued_only.data['results']) == 1

        search = super_client.get(
            '/api/accounting/collection-accounts/?q=Xpandia',
        )
        assert len(search.data['results']) == 1

    def test_overdue_flag(self, super_client):
        document = issue_for(make_hosting())
        Document.objects.filter(pk=document.pk).update(
            due_date=date.today() - timedelta(days=2),
        )
        response = super_client.get('/api/accounting/collection-accounts/')
        assert response.data['results'][0]['is_overdue'] is True

    def test_detail_and_pdf(self, super_client):
        document = issue_for(make_hosting())
        detail = super_client.get(
            f'/api/accounting/collection-accounts/{document.pk}/',
        )
        assert detail.status_code == 200
        assert detail.data['items'][0]['unit_price'] == '550002.00'
        assert detail.data['payment_methods'][0]['bank_name'] == 'Bancolombia'

        pdf = super_client.get(
            f'/api/accounting/collection-accounts/{document.pk}/pdf/',
        )
        assert pdf.status_code == 200
        assert pdf['Content-Type'] == 'application/pdf'
        assert pdf.content[:4] == b'%PDF'
        # The detail modal embeds `?inline=1`; the middleware's DENY default
        # would blank that viewer, so the view opts into SAMEORIGIN.
        assert pdf['X-Frame-Options'] == 'SAMEORIGIN'


class TestLifecycleActions:
    def test_resend(self, super_client):
        document = issue_for(make_hosting())
        response = super_client.post(
            f'/api/accounting/collection-accounts/{document.pk}/resend/',
        )
        assert response.status_code == 200
        assert response.data['email_sent'] is True

    def test_mark_paid(self, super_client):
        document = issue_for(make_hosting())
        response = super_client.post(
            f'/api/accounting/collection-accounts/{document.pk}/mark-paid/',
        )
        assert response.status_code == 200
        assert response.data['commercial_status'] == 'paid'

    def test_cancel_resumes_expiry_cadence(self, super_client):
        hosting = make_hosting()
        document = issue_for(hosting)
        hosting.refresh_from_db()
        assert hosting.billing_requested_at is not None

        response = super_client.post(
            f'/api/accounting/collection-accounts/{document.pk}/cancel/',
        )
        assert response.status_code == 200
        assert response.data['commercial_status'] == 'cancelled'
        hosting.refresh_from_db()
        assert hosting.billing_requested_at is None

    def test_paid_cannot_be_cancelled(self, super_client):
        document = issue_for(make_hosting())
        super_client.post(
            f'/api/accounting/collection-accounts/{document.pk}/mark-paid/',
        )
        response = super_client.post(
            f'/api/accounting/collection-accounts/{document.pk}/cancel/',
        )
        assert response.status_code == 400


class TestDeleteEndpoint:
    """Eliminar: only for the cuenta nobody outside can still be holding."""

    def test_delete_refuses_a_cuenta_the_client_received(self, super_client):
        # The hosting flow issues AND emails, so this one did reach the client.
        document = issue_for(make_hosting())
        response = super_client.delete(
            f'/api/accounting/collection-accounts/{document.pk}/delete/',
        )
        assert response.status_code == 400
        assert 'Anúlala' in response.data['error']
        assert Document.objects.filter(pk=document.pk).exists()

    def test_delete_removes_a_cancelled_cuenta_and_updates_the_counters(
        self, super_client,
    ):
        document = issue_for(make_hosting())
        super_client.post(
            f'/api/accounting/collection-accounts/{document.pk}/cancel/',
        )
        listed = super_client.get('/api/accounting/collection-accounts/')
        assert listed.data['meta']['cancelled_count'] == 1

        response = super_client.delete(
            f'/api/accounting/collection-accounts/{document.pk}/delete/',
        )

        assert response.status_code == 204
        assert not Document.objects.filter(pk=document.pk).exists()
        listed = super_client.get('/api/accounting/collection-accounts/')
        assert listed.data['meta']['cancelled_count'] == 0
        assert listed.data['results'] == []

    def test_delete_resumes_the_hosting_expiry_cadence(self, super_client):
        """Same debt anular pays: a cuenta that stops being pending unmutes it."""
        hosting = make_hosting()
        document = issue_for(hosting)
        Document.objects.filter(pk=document.pk).update(
            commercial_status=Document.CommercialStatus.CANCELLED,
        )
        hosting.refresh_from_db()
        hosting.billing_requested_at = timezone.now()
        hosting.save(update_fields=['billing_requested_at'])

        response = super_client.delete(
            f'/api/accounting/collection-accounts/{document.pk}/delete/',
        )

        assert response.status_code == 204
        hosting.refresh_from_db()
        assert hosting.billing_requested_at is None

    def test_delete_requires_superuser(self, admin_client):
        document = issue_for(make_hosting())
        response = admin_client.delete(
            f'/api/accounting/collection-accounts/{document.pk}/delete/',
        )
        assert response.status_code == 403
        assert Document.objects.filter(pk=document.pk).exists()

    def test_list_marks_which_rows_can_be_deleted(self, super_client):
        delivered = issue_for(make_hosting())
        cancelled = issue_for(make_hosting(
            client_name='Nestor - Xpandia',
            client_email='nestor@xpandia.global',
            domain_url='https://xpandia.global/',
        ))
        super_client.post(
            f'/api/accounting/collection-accounts/{cancelled.pk}/cancel/',
        )

        response = super_client.get('/api/accounting/collection-accounts/')

        flags = {row['id']: row['can_delete'] for row in response.data['results']}
        assert flags[delivered.pk] is False
        assert flags[cancelled.pk] is True


def make_income(**overrides):
    fields = {
        'concept': 'Kore - Inicio 40%',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': '2026-07-01',
        'total_amount': Decimal('1000000.00'),
        'gustavo_amount': Decimal('500000.00'),
        'carlos_amount': Decimal('500000.00'),
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


def link_income(document, income):
    Document.objects.filter(pk=document.pk).update(income_record=income)
    document.refresh_from_db()
    return document


class TestIncomeLinkedAccounts:
    def test_origin_income_filter_and_fields(self, super_client):
        issue_for(make_hosting())
        income = make_income()
        document = link_income(issue_for(make_hosting(
            client_name='Nestor - Xpandia',
            client_email='nestor@xpandia.global',
            domain_url='https://xpandia.global/',
        )), income)
        # Only hosting outranks an income link in get_origin, so clear the
        # hosting FK to model a modal-created cuenta.
        Document.objects.filter(pk=document.pk).update(hosting_record=None)

        response = super_client.get(
            '/api/accounting/collection-accounts/?origin=income',
        )
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        row = response.data['results'][0]
        assert row['origin'] == 'income'
        assert row['origin_label'] == 'Ingreso'
        assert row['income_record_id'] == income.pk
        assert row['income_kind'] == 'expected'

    def test_a_project_does_not_relabel_an_income_driven_cuenta(
        self, super_client,
    ):
        """A cuenta inherits its income's project; that must not turn its
        origin into 'project' and drop it out of the income filter."""
        from accounts.models import Project
        from django.contrib.auth import get_user_model

        client_user = get_user_model().objects.create_user(
            username='nestor@xpandia.global', email='nestor@xpandia.global',
            password='pass12345', first_name='Néstor', last_name='Franco',
        )
        income = make_income()
        document = link_income(issue_for(make_hosting()), income)
        project = Project.objects.create(name='Xpandia', client=client_user)
        Document.objects.filter(pk=document.pk).update(
            hosting_record=None, project=project,
        )

        response = super_client.get(
            '/api/accounting/collection-accounts/?origin=income',
        )

        assert [r['id'] for r in response.data['results']] == [document.pk]
        assert response.data['results'][0]['origin'] == 'income'
        # And it must not leak into the project bucket either.
        projects = super_client.get(
            '/api/accounting/collection-accounts/?origin=project',
        )
        assert projects.data['results'] == []

    def test_mark_paid_blocked_while_linked_income_pending(self, super_client):
        income = make_income()
        document = link_income(issue_for(make_hosting()), income)

        response = super_client.post(
            f'/api/accounting/collection-accounts/{document.pk}/mark-paid/',
        )

        assert response.status_code == 409
        assert 'saldo pendiente' in response.data['error']
        document.refresh_from_db()
        assert document.commercial_status == Document.CommercialStatus.ISSUED

    def test_mark_paid_allowed_once_income_fully_paid(self, super_client):
        income = make_income()
        document = link_income(issue_for(make_hosting()), income)
        IncomeRecord.objects.create(
            concept='Kore - Inicio 40% (líquido)',
            kind=IncomeRecord.Kind.LIQUID,
            expected_income=income,
            period_date='2026-07-15',
            total_amount=Decimal('1000000.00'),
            gustavo_amount=Decimal('500000.00'),
            carlos_amount=Decimal('500000.00'),
        )

        response = super_client.post(
            f'/api/accounting/collection-accounts/{document.pk}/mark-paid/',
        )

        assert response.status_code == 200
        assert response.data['commercial_status'] == 'paid'

    def test_mark_paid_direct_when_the_linked_income_is_liquid(self, super_client):
        # A liquid income is money already received: it carries no collection
        # state to settle, so the guard that protects expected incomes must
        # not stand in the way here.
        income = make_income(
            concept='Kore - Inicio 40% (recibido)',
            kind=IncomeRecord.Kind.LIQUID,
        )
        document = link_income(issue_for(make_hosting()), income)

        response = super_client.post(
            f'/api/accounting/collection-accounts/{document.pk}/mark-paid/',
        )

        assert response.status_code == 200
        assert response.data['commercial_status'] == 'paid'


class TestProjectColumnLiveFk:
    """The Proyecto column answers with the live FK; the snapshot is only
    the FK-null fallback (F7). The frozen ``customer_project_name`` keeps
    being what the PDF printed — the column and the PDF may honestly differ.
    """

    def make_cuenta(self, profile, *, project=None, snapshot='',
                    with_extension=True, title='CC F7',
                    status=Document.CommercialStatus.DRAFT):
        document = Document.objects.create(
            title=title,
            document_type=get_collection_account_document_type(),
            commercial_status=status,
            client_user=profile.user,
            project=project,
        )
        if with_extension:
            DocumentCollectionAccount.objects.create(
                document=document,
                customer_name='Ana Cliente',
                customer_project_name=snapshot,
            )
        return document

    def rows_by_id(self, super_client):
        response = super_client.get('/api/accounting/collection-accounts/')
        assert response.status_code == 200
        return {row['id']: row for row in response.data['results']}

    def test_draft_with_fk_shows_the_live_name(
        self, super_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = Project.objects.create(name='Vastago', client=profile.user)
        draft = self.make_cuenta(profile, project=project)

        row = self.rows_by_id(super_client)[draft.pk]

        assert row['project_name'] == 'Vastago'
        assert row['project_id'] == project.pk

    def test_fk_null_row_falls_back_to_the_frozen_snapshot(
        self, super_client, make_client_profile,
    ):
        profile = make_client_profile()
        cuenta = self.make_cuenta(
            profile, snapshot='Kore Web',
            status=Document.CommercialStatus.ISSUED,
        )

        row = self.rows_by_id(super_client)[cuenta.pk]

        assert row['project_name'] == 'Kore Web'
        assert row['project_id'] is None

    def test_mixed_same_client_rows_disagree_honestly(
        self, super_client, make_client_profile,
    ):
        """The reported evidence: two cuentas of one client, one with the
        relation and one with nothing — each cell tells its own truth."""
        profile = make_client_profile()
        project = Project.objects.create(name='Mimittos', client=profile.user)
        linked = self.make_cuenta(profile, project=project)
        blank = self.make_cuenta(profile, title='CC sin proyecto')

        rows = self.rows_by_id(super_client)

        assert rows[linked.pk]['project_name'] == 'Mimittos'
        assert rows[blank.pk]['project_name'] == ''

    def test_rename_shows_live_while_the_snapshot_stays(
        self, super_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = Project.objects.create(name='Vastago', client=profile.user)
        cuenta = self.make_cuenta(
            profile, project=project, snapshot='Vastago',
            status=Document.CommercialStatus.ISSUED,
        )
        project.name = 'Vastago 2.0'
        project.save(update_fields=['name'])

        row = self.rows_by_id(super_client)[cuenta.pk]

        assert row['project_name'] == 'Vastago 2.0'
        extension = DocumentCollectionAccount.objects.get(document=cuenta)
        assert extension.customer_project_name == 'Vastago'

    def test_row_without_extension_answers_empty_not_500(
        self, super_client, make_client_profile,
    ):
        # Platform drafts can exist without the extension until first PATCH.
        profile = make_client_profile()
        cuenta = self.make_cuenta(profile, with_extension=False)

        row = self.rows_by_id(super_client)[cuenta.pk]

        assert row['project_name'] == ''
