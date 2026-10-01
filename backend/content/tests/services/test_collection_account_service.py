"""Tests for collection_account_service business rules."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from accounts.models import CollectionAccountContext, Project, ProjectContract, UserProfile
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from freezegun import freeze_time

from content.models import (
    AccountingChangeLog,
    CompanySettings,
    Document,
    DocumentCollectionAccount,
    DocumentItem,
    DocumentPaymentMethod,
    EmailLog,
    EmailLogTarget,
    IncomeRecord,
    IssuerProfile,
)
from content.services.collection_account_service import (
    CollectionAccountError,
    allocate_public_number,
    assert_draft_for_mutation,
    collection_account_was_delivered,
    commercial_is_overdue,
    default_payment_methods_config,
    delete_collection_account,
    is_collection_account,
    issue_collection_account,
    mark_collection_account_cancelled,
    mark_collection_account_paid,
    recalculate_document_totals,
)
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.services.document_type_utils import (
    get_collection_account_document_type,
    get_markdown_document_type,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def issuer():
    return IssuerProfile.objects.create(
        name='Issuer Co',
        legal_name='Issuer LLC',
        identification_number='900',
        email='issuer@example.com',
        phone='+5700',
        address='Addr',
        public_number_prefix='ZZ',
    )


@pytest.fixture
def admin_actor():
    user = User.objects.create_user(
        username='svc-admin@test.com',
        email='svc-admin@test.com',
        password='pass12345',
    )
    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
        profile_completed=True,
    )
    return user


@pytest.fixture
def client_user(admin_actor):
    user = User.objects.create_user(
        username='svc-client@test.com',
        email='svc-client@test.com',
        password='pass12345',
        first_name='Pat',
        last_name='Lee',
    )
    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=True,
        profile_completed=True,
        company_name='ClientCo',
        cedula='123',
        created_by=admin_actor,
    )
    return user


@pytest.fixture
def project(client_user):
    return Project.objects.create(
        name='Svc Project',
        client=client_user,
        status=Project.STATUS_ACTIVE,
        progress=0,
    )


def _ca_document(**kwargs):
    dt = get_collection_account_document_type()
    defaults = {
        'title': 'CA',
        'document_type': dt,
        'commercial_status': Document.CommercialStatus.DRAFT,
        'total': Decimal('0'),
    }
    defaults.update(kwargs)
    document = Document.objects.create(**defaults)
    project = defaults.get('project')
    if project:
        source = Document.objects.create(title='Contrato de prueba', project=project, client_user=project.client)
        contract = ProjectContract.objects.create(
            project=project, key=f'account-service-{document.pk}', title='Contrato de prueba', document=source,
        )
        CollectionAccountContext.objects.create(document=document, nature='contract', contract=contract)
    return document


def test_commercial_is_overdue_returns_false_for_non_collection_account_document():
    md = get_markdown_document_type()
    doc = Document.objects.create(
        title='Md',
        document_type=md,
        commercial_status=Document.CommercialStatus.ISSUED,
        due_date=date(2026, 6, 15),
    )

    assert commercial_is_overdue(doc) is False


def test_commercial_is_overdue_returns_false_when_status_is_draft():
    doc = _ca_document(commercial_status=Document.CommercialStatus.DRAFT)
    DocumentCollectionAccount.objects.create(document=doc)
    doc.due_date = date(2026, 6, 15)
    doc.save(update_fields=['due_date'])

    assert commercial_is_overdue(doc) is False


def test_commercial_is_overdue_returns_false_when_due_date_is_missing():
    doc = _ca_document(commercial_status=Document.CommercialStatus.ISSUED)
    DocumentCollectionAccount.objects.create(document=doc)

    assert commercial_is_overdue(doc) is False


def test_commercial_is_overdue_returns_false_when_due_date_string_is_unparseable():
    stub = SimpleNamespace(
        document_type=SimpleNamespace(code=COLLECTION_ACCOUNT),
        commercial_status=Document.CommercialStatus.ISSUED,
        due_date='not-a-real-date',
    )

    assert commercial_is_overdue(stub) is False


def test_commercial_is_overdue_returns_false_when_parse_date_returns_none():
    stub = SimpleNamespace(
        document_type=SimpleNamespace(code=COLLECTION_ACCOUNT),
        commercial_status=Document.CommercialStatus.ISSUED,
        due_date='99-99-99',
    )

    assert commercial_is_overdue(stub) is False


def test_commercial_is_overdue_returns_false_when_due_date_string_is_in_future():
    stub = SimpleNamespace(
        document_type=SimpleNamespace(code=COLLECTION_ACCOUNT),
        commercial_status=Document.CommercialStatus.ISSUED,
        due_date='2099-01-01',
    )

    assert commercial_is_overdue(stub) is False


def test_recalculate_document_totals_sets_zero_totals_when_no_line_items():
    doc = _ca_document(discount_total=Decimal('5'))

    recalculate_document_totals(doc)

    assert doc.subtotal == Decimal('0')
    assert doc.tax_total == Decimal('0')
    assert doc.total == Decimal('-5')


def test_recalculate_document_totals_aggregates_line_items():
    """recalculate_document_totals sums line items into subtotal, tax, and total."""
    doc = _ca_document(discount_total=Decimal('0'))
    DocumentItem.objects.create(
        document=doc,
        position=0,
        description='A',
        quantity=Decimal('2'),
        unit_price=Decimal('50'),
        discount_amount=Decimal('10'),
        tax_amount=Decimal('5'),
        line_total=Decimal('95'),
    )

    recalculate_document_totals(doc)

    assert doc.subtotal == Decimal('90')
    assert doc.tax_total == Decimal('5')
    assert doc.total == Decimal('95')


def test_allocate_public_number_increments_per_issuer_and_year(issuer):
    n1 = allocate_public_number(issuer)
    n2 = allocate_public_number(issuer)

    assert n1.startswith('ZZ-')
    assert n2.startswith('ZZ-')
    assert n1 != n2


def test_allocate_public_number_uses_pa_prefix_when_prefix_is_blank():
    bare = IssuerProfile.objects.create(name='Bare Issuer', public_number_prefix='')

    num = allocate_public_number(bare)

    assert num.split('-')[0] == 'PA'


def test_issue_collection_account_raises_when_document_is_not_collection_type(issuer, project, client_user):
    md = get_markdown_document_type()
    doc = Document.objects.create(
        title='Wrong',
        document_type=md,
        commercial_status=Document.CommercialStatus.DRAFT,
        project=project,
        client_user=client_user,
    )

    with pytest.raises(CollectionAccountError, match='not a collection account') as exc_info:
        issue_collection_account(doc, issuer=issuer)
    assert isinstance(exc_info.value, CollectionAccountError)


def test_issue_collection_account_raises_when_status_is_not_draft(issuer, project, client_user):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.ISSUED,
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)

    with pytest.raises(CollectionAccountError, match='Only draft') as exc_info:
        issue_collection_account(doc, issuer=issuer)
    assert isinstance(exc_info.value, CollectionAccountError)


def test_issue_collection_account_raises_when_no_client_can_be_resolved(issuer):
    doc = _ca_document()
    DocumentCollectionAccount.objects.create(document=doc)

    with pytest.raises(CollectionAccountError, match='client_user or project') as exc_info:
        issue_collection_account(doc, issuer=issuer)
    assert isinstance(exc_info.value, CollectionAccountError)


def test_issue_collection_account_raises_for_fixed_date_without_due_date(issuer, project, client_user):
    doc = _ca_document(project=project, client_user=client_user)
    DocumentCollectionAccount.objects.create(
        document=doc,
        payment_term_type=DocumentCollectionAccount.PaymentTermType.FIXED_DATE,
    )

    with pytest.raises(CollectionAccountError, match='due_date is required') as exc_info:
        issue_collection_account(doc, issuer=issuer)
    assert isinstance(exc_info.value, CollectionAccountError)


def test_issue_collection_account_preserves_due_date_for_fixed_date_term(issuer, project, client_user):
    """issue_collection_account keeps an existing due_date when payment term is fixed date."""
    doc = _ca_document(
        project=project,
        client_user=client_user,
        due_date=date(2026, 12, 31),
    )
    DocumentCollectionAccount.objects.create(
        document=doc,
        payment_term_type=DocumentCollectionAccount.PaymentTermType.FIXED_DATE,
    )

    issue_collection_account(doc, issuer=issuer)
    doc.refresh_from_db()

    assert doc.due_date.isoformat() == '2026-12-31'


@freeze_time('2026-04-01 12:00:00')
def test_issue_collection_account_sets_due_from_payment_term_days_after_issue(issuer, project, client_user):
    doc = _ca_document(project=project, client_user=client_user)
    DocumentCollectionAccount.objects.create(
        document=doc,
        payment_term_type=DocumentCollectionAccount.PaymentTermType.DAYS_AFTER_ISSUE,
        payment_term_days=7,
    )

    issue_collection_account(doc, issuer=issuer)
    doc.refresh_from_db()

    assert doc.due_date.isoformat() == '2026-04-08'


@freeze_time('2026-04-01 12:00:00')
def test_issue_collection_account_leaves_no_due_date_for_zero_day_term(
    issuer, project, client_user,
):
    """Zero days is immediate payment, so there is no deadline to state."""
    doc = _ca_document(project=project, client_user=client_user)
    DocumentCollectionAccount.objects.create(
        document=doc,
        payment_term_type=DocumentCollectionAccount.PaymentTermType.DAYS_AFTER_ISSUE,
        payment_term_days=0,
    )

    issue_collection_account(doc, issuer=issuer)
    doc.refresh_from_db()

    assert doc.issue_date.isoformat() == '2026-04-01'
    assert doc.due_date is None


@freeze_time('2026-04-01 12:00:00')
def test_zero_day_collection_account_never_turns_overdue(
    issuer, project, client_user,
):
    """The defect the omission removes: a due date equal to the issue date
    made an immediate-payment cuenta overdue the day after it was sent."""
    doc = _ca_document(project=project, client_user=client_user)
    DocumentCollectionAccount.objects.create(
        document=doc,
        payment_term_type=DocumentCollectionAccount.PaymentTermType.DAYS_AFTER_ISSUE,
        payment_term_days=0,
    )
    issue_collection_account(doc, issuer=issuer)
    doc.refresh_from_db()

    with freeze_time('2026-06-01'):
        assert commercial_is_overdue(doc) is False


@freeze_time('2026-05-10 12:00:00')
def test_issue_collection_account_leaves_no_due_date_for_against_delivery_term(
    issuer, project, client_user,
):
    """against_delivery is that same immediate payment reached through the
    term type, so it stopped stamping the issue date as a fake deadline."""
    doc = _ca_document(project=project, client_user=client_user)
    DocumentCollectionAccount.objects.create(
        document=doc,
        payment_term_type=DocumentCollectionAccount.PaymentTermType.AGAINST_DELIVERY,
    )

    issue_collection_account(doc, issuer=issuer)
    doc.refresh_from_db()

    assert doc.due_date is None


def test_mark_collection_account_paid_returns_document_when_already_paid(issuer, project, client_user):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.PAID,
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)

    out = mark_collection_account_paid(doc)

    assert out.pk == doc.pk


def test_mark_collection_account_paid_raises_when_document_is_not_issued(project, client_user):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.DRAFT,
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)

    with pytest.raises(CollectionAccountError, match='Only issued') as exc_info:
        mark_collection_account_paid(doc)
    assert isinstance(exc_info.value, CollectionAccountError)


def test_mark_collection_account_paid_raises_when_document_is_not_collection_type(project, client_user):
    md = get_markdown_document_type()
    doc = Document.objects.create(
        title='X',
        document_type=md,
        commercial_status=Document.CommercialStatus.ISSUED,
        project=project,
        client_user=client_user,
    )

    with pytest.raises(CollectionAccountError, match='not a collection account') as exc_info:
        mark_collection_account_paid(doc)
    assert isinstance(exc_info.value, CollectionAccountError)


def test_mark_collection_account_paid_sets_paid_when_document_is_issued(admin_actor, project, client_user):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.ISSUED,
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)

    mark_collection_account_paid(doc, acting_user=admin_actor)
    doc.refresh_from_db()

    assert doc.commercial_status == Document.CommercialStatus.PAID


def test_mark_collection_account_cancelled_returns_document_when_already_cancelled(
    issuer, project, client_user,
):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.CANCELLED,
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)

    out = mark_collection_account_cancelled(doc)

    assert out.pk == doc.pk


def test_mark_collection_account_cancelled_raises_when_document_is_paid(issuer, project, client_user):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.PAID,
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)

    with pytest.raises(CollectionAccountError, match='Paid documents cannot') as exc_info:
        mark_collection_account_cancelled(doc)
    assert isinstance(exc_info.value, CollectionAccountError)


def test_mark_collection_account_cancelled_raises_when_document_is_not_collection_type(project, client_user):
    md = get_markdown_document_type()
    doc = Document.objects.create(
        title='X',
        document_type=md,
        commercial_status=Document.CommercialStatus.DRAFT,
        project=project,
        client_user=client_user,
    )

    with pytest.raises(CollectionAccountError, match='not a collection account') as exc_info:
        mark_collection_account_cancelled(doc)
    assert isinstance(exc_info.value, CollectionAccountError)


def test_mark_collection_account_cancelled_sets_cancelled_when_document_is_issued(
    admin_actor, project, client_user,
):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.ISSUED,
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)

    mark_collection_account_cancelled(doc, acting_user=admin_actor)
    doc.refresh_from_db()

    assert doc.commercial_status == Document.CommercialStatus.CANCELLED


def test_mark_collection_account_cancelled_raises_for_unsupported_commercial_status(
    issuer, project, client_user,
):
    doc = _ca_document(
        commercial_status=None,
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)

    with pytest.raises(CollectionAccountError, match='Only draft or issued') as exc_info:
        mark_collection_account_cancelled(doc)
    assert isinstance(exc_info.value, CollectionAccountError)


# ── Eliminar (delete_collection_account) ──
#
# Eliminar is not anular: it is for the cuenta created by mistake, and only
# when nobody outside can still be treating it as live.

def _delivered_email(doc, status=EmailLog.Status.SENT):
    """An EmailLog target row for this cuenta, the way the send service writes it."""
    log = EmailLog.objects.create(
        template_key='collection_account',
        recipient='client@example.com',
        status=status,
    )
    EmailLogTarget.objects.create(
        email_log=log,
        entity_type=AccountingChangeLog.EntityType.COLLECTION_ACCOUNT,
        object_id=doc.pk,
        object_repr=doc.public_number or '',
    )
    return log


def test_delete_removes_a_draft_that_never_reached_anyone(admin_actor, project, client_user):
    doc = _ca_document(project=project, client_user=client_user)
    DocumentCollectionAccount.objects.create(document=doc)

    delete_collection_account(doc, acting_user=admin_actor)

    assert not Document.objects.filter(pk=doc.pk).exists()


def test_delete_removes_an_issued_cuenta_whose_email_failed(admin_actor, project, client_user):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.ISSUED,
        public_number='ZZ-2026-0001',
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)
    _delivered_email(doc, status=EmailLog.Status.FAILED)

    delete_collection_account(doc, acting_user=admin_actor)

    assert not Document.objects.filter(pk=doc.pk).exists()


def test_delete_refuses_an_issued_cuenta_the_client_already_received(
    admin_actor, project, client_user,
):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.ISSUED,
        public_number='ZZ-2026-0002',
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)
    _delivered_email(doc)

    with pytest.raises(CollectionAccountError, match='ya se envió al cliente'):
        delete_collection_account(doc, acting_user=admin_actor)
    assert Document.objects.filter(pk=doc.pk).exists()


def test_delete_removes_a_cancelled_cuenta_even_when_it_was_delivered(
    admin_actor, project, client_user,
):
    """Anular is what told the client it stopped counting; the row can go."""
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.CANCELLED,
        public_number='ZZ-2026-0003',
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)
    _delivered_email(doc)

    delete_collection_account(doc, acting_user=admin_actor)

    assert not Document.objects.filter(pk=doc.pk).exists()


def test_delete_removes_the_archived_pdf_after_commit(
    admin_actor, project, client_user, settings, tmp_path,
    django_capture_on_commit_callbacks,
):
    settings.MEDIA_ROOT = tmp_path
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.CANCELLED,
        public_number='ZZ-2026-0008',
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)
    doc.generated_file.save(
        'ZZ-2026-0008.pdf', ContentFile(b'%PDF cancelled account'), save=True,
    )
    storage = doc.generated_file.storage
    stored_name = doc.generated_file.name

    with django_capture_on_commit_callbacks(execute=True):
        delete_collection_account(doc, acting_user=admin_actor)

    assert not storage.exists(stored_name)


def test_a_bounced_send_still_counts_as_delivered(project, client_user):
    """A bounce cannot prove the client never got it; the bias is not to delete."""
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.ISSUED,
        public_number='ZZ-2026-0007',
        project=project,
        client_user=client_user,
    )
    _delivered_email(doc, status=EmailLog.Status.BOUNCED)

    assert collection_account_was_delivered(doc) is True


def test_delete_refuses_a_paid_cuenta(admin_actor, project, client_user):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.PAID,
        public_number='ZZ-2026-0004',
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)

    with pytest.raises(CollectionAccountError, match='pagada no se puede eliminar'):
        delete_collection_account(doc, acting_user=admin_actor)
    assert Document.objects.filter(pk=doc.pk).exists()


def test_delete_refuses_a_document_that_is_not_a_collection_account(admin_actor, project):
    doc = Document.objects.create(
        title='X',
        document_type=get_markdown_document_type(),
        project=project,
    )

    with pytest.raises(CollectionAccountError, match='not a collection account'):
        delete_collection_account(doc, acting_user=admin_actor)


def test_delete_leaves_the_consecutivo_in_the_history_after_the_row_is_gone(
    admin_actor, project, client_user,
):
    """The trail has no FK precisely so it can outlive the document."""
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.CANCELLED,
        public_number='ZZ-2026-0005',
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)
    doc_id = doc.pk

    delete_collection_account(doc, acting_user=admin_actor)

    entry = AccountingChangeLog.objects.get(
        entity_type=AccountingChangeLog.EntityType.COLLECTION_ACCOUNT,
        object_id=doc_id,
        action=AccountingChangeLog.Action.DELETED,
    )
    assert entry.object_repr == 'ZZ-2026-0005'
    assert entry.actor_username == admin_actor.username


def test_delete_frees_the_linked_income_to_be_billed_again(
    admin_actor, project, client_user,
):
    income = IncomeRecord.objects.create(
        concept='Anticipo',
        kind=IncomeRecord.Kind.EXPECTED,
        period_date=date(2026, 8, 1),
        total_amount=Decimal('1000'),
    )
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.ISSUED,
        public_number='ZZ-2026-0006',
        project=project,
        client_user=client_user,
        income_record=income,
    )
    DocumentCollectionAccount.objects.create(document=doc)
    assert income.collection_documents.exclude(
        commercial_status=Document.CommercialStatus.CANCELLED,
    ).exists()

    delete_collection_account(doc, acting_user=admin_actor)

    assert not income.collection_documents.exclude(
        commercial_status=Document.CommercialStatus.CANCELLED,
    ).exists()


def test_assert_draft_for_mutation_raises_when_document_is_not_collection_account(project, client_user):
    md = get_markdown_document_type()
    doc = Document.objects.create(
        title='X',
        document_type=md,
        commercial_status=Document.CommercialStatus.DRAFT,
        project=project,
        client_user=client_user,
    )

    with pytest.raises(CollectionAccountError, match='not a collection account') as exc_info:
        assert_draft_for_mutation(doc)
    assert isinstance(exc_info.value, CollectionAccountError)


def test_assert_draft_for_mutation_raises_when_document_is_not_draft(project, client_user):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.ISSUED,
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)

    with pytest.raises(CollectionAccountError, match='Only draft collection accounts') as exc_info:
        assert_draft_for_mutation(doc)
    assert isinstance(exc_info.value, CollectionAccountError)


def test_assert_draft_for_mutation_succeeds_for_draft_collection_account(project, client_user):
    doc = _ca_document(
        commercial_status=Document.CommercialStatus.DRAFT,
        project=project,
        client_user=client_user,
    )
    DocumentCollectionAccount.objects.create(document=doc)

    assert_draft_for_mutation(doc)
    assert doc.commercial_status == Document.CommercialStatus.DRAFT


def test_is_collection_account_returns_true_for_collection_document_type():
    doc = _ca_document()

    assert is_collection_account(doc) is True


def test_issue_collection_account_uses_project_client_when_client_user_not_set(issuer, project, client_user):
    doc = _ca_document(project=project, client_user=None)
    DocumentCollectionAccount.objects.create(document=doc)

    issue_collection_account(doc, issuer=issuer)
    doc.refresh_from_db()
    ext = doc.collection_account

    assert ext.customer_email == client_user.email


def test_issue_collection_account_uses_person_name_when_user_has_no_profile(
    issuer, admin_actor,
):
    """issue_collection_account uses first and last name when the client has no profile."""
    user = User.objects.create_user(
        username='svc-person@test.com',
        email='svc-person@test.com',
        password='pass12345',
        first_name='Sam',
        last_name='Rivera',
    )
    project_local = Project.objects.create(
        name='Personal Project',
        client=user,
        status=Project.STATUS_ACTIVE,
        progress=0,
    )
    doc = _ca_document(project=project_local, client_user=user)
    DocumentCollectionAccount.objects.create(document=doc)

    issue_collection_account(doc, issuer=issuer, acting_user=admin_actor)
    ext = DocumentCollectionAccount.objects.get(document=doc)

    assert ext.customer_name == 'Sam Rivera'
    assert ext.customer_contact_name == 'Sam Rivera'


@pytest.fixture
def bank_settings():
    """The contract's payment clause source, which now also feeds the cuenta."""
    company = CompanySettings.load()
    company.contractor_full_name = 'GUSTAVO ADOLFO PEREZ PEREZ'
    company.contractor_nit = '1021513348-7'
    company.contractor_cedula = ''
    company.bank_name = 'Bancolombia'
    company.bank_account_type = 'Ahorros'
    company.bank_account_number = '00774149350'
    company.save()
    return company


def test_default_payment_methods_come_from_company_settings(issuer, bank_settings):
    """One source for the bank account: updating CompanySettings has to reach
    the cuenta de cobro, not just the contract."""
    issuer.default_payment_methods = []
    issuer.save()

    methods = default_payment_methods_config(issuer)

    assert len(methods) == 1
    assert methods[0] == {
        'payment_method_type': DocumentPaymentMethod.MethodType.BANK_TRANSFER,
        'bank_name': 'Bancolombia',
        'account_type': 'Ahorros',
        'account_number': '00774149350',
        'account_holder_name': 'GUSTAVO ADOLFO PEREZ PEREZ',
        'account_holder_identification': 'NIT 1021513348-7',
    }


def test_default_payment_methods_label_the_holder_id_by_document_type(
    issuer, bank_settings,
):
    """Naming a cédula 'NIT' on a billing document is a defect, not cosmetics."""
    bank_settings.contractor_nit = ''
    bank_settings.contractor_cedula = '1037635428'
    bank_settings.save()

    methods = default_payment_methods_config(issuer)

    assert methods[0]['account_holder_identification'] == 'C.C. 1037635428'


def test_default_payment_methods_keep_the_issuer_extras_after_the_bank(
    issuer, bank_settings,
):
    """The issuer JSON stays the place to add a second channel without a migration."""
    issuer.default_payment_methods = [
        {'payment_method_type': 'nequi', 'account_number': '3238122373'},
    ]
    issuer.save()

    methods = default_payment_methods_config(issuer)

    assert [m['payment_method_type'] for m in methods] == [
        DocumentPaymentMethod.MethodType.BANK_TRANSFER, 'nequi',
    ]


def test_default_payment_methods_skip_the_bank_when_unconfigured(issuer):
    """A half-filled CompanySettings must yield no method rather than a block
    of labels with nothing beside them."""
    company = CompanySettings.load()
    company.bank_name = 'Bancolombia'
    company.bank_account_number = ''
    company.save()
    issuer.default_payment_methods = []
    issuer.save()

    assert default_payment_methods_config(issuer) == []
