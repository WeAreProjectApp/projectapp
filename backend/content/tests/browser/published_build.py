"""Real SQLite and Chromium checks for the generated frontend. CI runs this module
explicitly after build:django and collectstatic, outside the backend unit shards.
"""
import json
import os
import secrets
import subprocess
from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings as django_settings
from django.db import connections, transaction

from content.email_copy_families import TASKS_OPERATIONS
from content.models import (
    Contact, Document, DocumentCollectionAccount, DocumentType, EmailCopyRecipient,
    EmailLog, IncomeRecord, IncomeSettlement, PocketMovement,
)


pytestmark = pytest.mark.django_db(transaction=True)
FRONTEND = django_settings.BASE_DIR.parent / 'frontend'


@pytest.fixture(scope='session')
def django_db_modify_db_settings(tmp_path_factory):
    # Independent live-server request threads need independent SQLite connections.
    database = tmp_path_factory.mktemp('published-django') / 'test.sqlite3'
    connections['default'].settings_dict['TEST']['NAME'] = str(database)


def run_browser(live_server, spec, **environment):
    subprocess.run(
        [str(FRONTEND / 'node_modules/.bin/playwright'), 'test',
         '--config', 'playwright.published.config.js', f'published/{spec}.spec.js'],
        cwd=FRONTEND,
        env={**os.environ, 'PUBLISHED_ORIGIN': live_server.url,
             'PUBLISHED_SUITE': spec, **environment},
        check=True,
    )


def test_contact_confirmation_uses_one_delivery(live_server, settings, mailoutbox):
    primary = 'contact-inbox@example.test'
    copies = ['contact-copy-one@example.test', 'contact-copy-two@example.test']
    settings.NOTIFICATION_EMAIL = primary
    settings.DEFAULT_FROM_EMAIL = 'sender@example.test'
    for address in copies:
        EmailCopyRecipient.objects.create(email=address, families=[TASKS_OPERATIONS])

    run_browser(live_server, 'contact-confirmation')

    assert list(Contact.objects.values_list('email', flat=True)) == ['contact-case@example.test']
    assert sorted(tuple(msg.recipients()) for msg in mailoutbox) == sorted(
        (address,) for address in [primary, *copies]
    )


def disposable_panel_login(superuser, tmp_path):
    password = secrets.token_urlsafe(32)
    superuser.set_password(password)
    superuser.save(update_fields=['password'])
    path = tmp_path / 'panel-actor.json'
    path.touch(mode=0o600)
    path.write_text(json.dumps({'username': superuser.get_username(), 'password': password}))
    return str(path)


def reviewable_income(make_income, client_profile, total):
    amount = Decimal(total)
    half = amount // 2
    income = make_income(
        concept=f'Cobro ficticio de {total}', period_date=date(2026, 11, 1),
        client=client_profile, total_amount=amount, gustavo_amount=half,
        carlos_amount=half, vat_rate=Decimal('19.00'),
    )
    doc_type, _ = DocumentType.objects.get_or_create(
        code='collection_account', defaults={'name': 'Cuenta de cobro'},
    )
    doc = Document.objects.create(
        document_type=doc_type, title=income.concept, income_record=income,
        client_user=client_profile.user, commercial_status=Document.CommercialStatus.ISSUED,
        public_number=f'PA-CI-{income.pk}', total=amount,
    )
    DocumentCollectionAccount.objects.create(document=doc, customer_email=client_profile.user.email)
    return income


def stored_amounts():
    return list(IncomeRecord.objects.order_by('pk').values_list(
        'pk', 'kind', 'total_amount', 'gustavo_amount', 'carlos_amount', 'vat_rate',
        'expected_income_id', 'updated_at',
    ))


def test_income_previews_preserve_the_book(
    live_server, superuser, make_income, make_client_profile, mailoutbox, tmp_path,
):
    # The user signal fills in a missing profile on commit. Create the explicit
    # profile in the same transaction as its user, as onboarding does.
    with transaction.atomic():
        owner = make_client_profile(email='settlement-recipient@example.test')
    unpaid = make_income(concept='Diagnóstico técnico - Cobro único', period_date=date(2025, 11, 1),
                         total_amount=Decimal('999999999999.99'))
    partial = make_income(concept='Cobro parcial ficticio', period_date=date(2025, 11, 2),
                          total_amount=Decimal('119.03'), gustavo_amount=59, carlos_amount=59)
    payment = make_income(concept='Abono ficticio', kind=IncomeRecord.Kind.LIQUID,
                          period_date=date(2025, 11, 3), expected_income=partial,
                          total_amount=Decimal('50.25'), gustavo_amount=25, carlos_amount=25)
    review = {amount: reviewable_income(make_income, owner, amount).pk
              for amount in ('119.03', '119.06', '120.00')}
    actor_path = disposable_panel_login(superuser, tmp_path)
    before = stored_amounts()
    totals = dict(IncomeRecord.objects.values_list('pk', 'total_amount'))
    assert totals[unpaid.pk] == Decimal('999999999999.99')
    assert totals[partial.pk] == Decimal('119.03')
    assert totals[payment.pk] == Decimal('50.25')
    assert totals[partial.pk] - totals[payment.pk] == Decimal('68.78')
    assert all(totals[record_id] == Decimal(amount) for amount, record_id in review.items())
    log_count = EmailLog.objects.count()
    mailbox_count = len(mailoutbox)

    run_browser(live_server, 'income-precision', PUBLISHED_PANEL_ACTOR=actor_path,
                PUBLISHED_INCOMES=json.dumps({
                    'unpaid': unpaid.pk, 'partial': partial.pk, 'payment': payment.pk,
                    'review': review, 'recipient': owner.user.email,
                }))

    assert stored_amounts() == before
    assert IncomeSettlement.objects.count() == 0
    assert PocketMovement.objects.count() == 0
    assert EmailLog.objects.count() == log_count
    assert len(mailoutbox) == mailbox_count
