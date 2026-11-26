"""Check hosting cash, invoicing and forecast races on a private, socket-only MySQL 8 fixture."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from importlib import import_module
import os
from pathlib import Path
import sys
from threading import Barrier
from uuid import uuid4


def configure(socket):
    import MySQLdb
    import django
    from django.conf import settings

    root = socket.parent
    if (not socket.is_socket() or root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077
            or os.environ.get('DJANGO_ENV') == 'production' or os.environ.get('DJANGO_SETTINGS_MODULE')):
        raise SystemExit('Expected a private fixture socket and a clean test environment.')
    database = 'test_pa_receipts_' + uuid4().hex
    with MySQLdb.connect(user='root', unix_socket=str(socket)) as control, control.cursor() as cursor:
        cursor.execute('SELECT @@datadir, @@skip_networking, VERSION()')
        directory, private, version = cursor.fetchone()
        if Path(directory).resolve() != root / 'data' or not private or not version.startswith('8.'):
            raise SystemExit('Expected a socket-only MySQL 8 fixture with its data next to the socket.')
        cursor.execute(f'CREATE DATABASE {database} CHARACTER SET utf8mb4')

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
    safe = import_module('projectapp.settings_test')
    values = {key: getattr(safe, key) for key in dir(safe) if key.isupper()}
    values['ALLOWED_HOSTS'] = ['testserver']
    values['DATABASES'] = {'default': {
        'ENGINE': 'django.db.backends.mysql', 'NAME': database, 'USER': 'root',
        'HOST': str(socket), 'OPTIONS': {'charset': 'utf8mb4'},
    }}
    settings.configure(**values)
    django.setup()
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    migrations = MigrationExecutor(connection)
    migrations.migrate(migrations.loader.graph.leaf_nodes())


def mapped_service(actor):
    from django.contrib.auth import get_user_model
    from accounts.models import HostingSubscription, Payment, Project, UserProfile
    from accounts.services.hosting_context import reconcile_hosting
    from content.models import HostingRecord, IncomeRecord

    customer = get_user_model().objects.create(username=f'fixture-{uuid4()}', email='customer@example.test',
                                               first_name='Cliente', last_name='DEV')
    profile, _ = UserProfile.objects.update_or_create(user=customer, defaults={'role': UserProfile.ROLE_CLIENT})
    project = Project.objects.create(name='Servicio DEV', client=customer, status=Project.STATUS_ACTIVE)
    record = HostingRecord.objects.create(
        project=project, client=profile, client_name='Cliente DEV', monthly_value=77760, payment_per_cycle=233280,
        valid_from=date(2026, 1, 1), valid_to=date(2026, 3, 31),
    )
    subscription = HostingSubscription.objects.create(
        project=project, plan='quarterly', base_monthly_amount=77760, effective_monthly_amount=77760,
        billing_amount=233280, start_date=date(2026, 1, 1), status='active',
    )
    reconcile_hosting(project.pk, actor, {
        'expected_version': 0, 'reason': 'Fixture concurrente', 'subscription_id': subscription.pk,
        'hosting_record_ids': [record.pk], 'operational_record_id': record.pk,
    })
    payment = Payment.objects.create(
        subscription=subscription, amount=233280, status='pending', billing_period_start=date(2026, 4, 1),
        billing_period_end=date(2026, 6, 30), due_date=date(2026, 4, 5),
    )
    income = IncomeRecord.objects.create(
        project=project, client=profile, kind='expected', origin='hosting', concept='Servicio DEV',
        period_start=payment.billing_period_start, period_end=payment.billing_period_end, period_date=payment.due_date,
        period_cadence='quarterly', total_amount=payment.amount,
    )
    return record, income, payment


def client(actor):
    from rest_framework.test import APIClient
    api = APIClient()
    api.force_authenticate(user=actor)
    return api


def compete(actor, first, second):
    from django.db import connections
    gate = Barrier(2, timeout=20)

    def confirm(request):
        url, payload = request
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute('SELECT CONNECTION_ID()')
                connection_id = cursor.fetchone()[0]
            gate.wait()
            response = client(actor).post(url, payload, format='json')
            return connection_id, response.status_code, response.json()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(confirm, [first, second]))
    assert results[0][0] != results[1][0], 'The confirmations must use independent transactions'
    return [(status, result) for _, status, result in results]


def check_receipt_and_next(actor):
    from content.models import HostingCycle, HostingReceiptAllocation, IncomeRecord, PocketMovement
    record, income, _ = mapped_service(actor)
    cycle_url = f'/api/accounting/hostings/{record.pk}/cycle-receipt/'
    incomes_url = '/api/accounting/incomes/'
    evidence = {'issuer': 'Banco DEV', 'reference': 'A-001',
                'entries': [{'hosting_record_id': record.pk, 'income_id': income.pk}]}
    cycle = {'income_id': income.pk, 'amount': '233280.00', 'paid_at': '2026-05-02',
             'request_id': str(uuid4()), 'hosting_receipt': evidence, 'destination': 'pocket'}
    settlement = {'income_ids': [income.pk], 'total_amount': '233280.00', 'period_date': '2026-05-02',
                  'request_id': str(uuid4()), 'hosting_receipt': evidence, 'destination': 'pocket'}
    api = client(actor)
    cycle['preview_hash'] = api.post(cycle_url + '?preview=1', cycle, format='json').json()['preview_hash']
    settlement['preview_hash'] = api.post(incomes_url + 'settlement-preview/', settlement, format='json').json()['preview_hash']
    results = compete(actor, (cycle_url, cycle), (incomes_url + 'bulk-settle/', settlement))
    assert all(status in (200, 201) for status, _ in results), results
    assert results[0][1]['settlement_id'] == results[1][1]['settlement_id']
    assert HostingReceiptAllocation.objects.filter(period__income=income).count() == 1
    assert HostingCycle.objects.filter(hosting_record=record).count() == 1
    liquid = IncomeRecord.objects.get(expected_income=income, kind='liquid')
    assert PocketMovement.objects.filter(pk=liquid.pocket_movement_id).count() == 1
    print('PASS same payment, two requests, two connections: one settlement, liquid, cycle and movement.')

    url = f'/api/accounting/hostings/{record.pk}/next-income/'
    proposal = {'version': api.get(url).json()['version']}
    results = compete(actor, (url, proposal), (url, proposal))
    assert sorted(status for status, _ in results) == [200, 201], results
    assert results[0][1]['existing_income_id'] == results[1][1]['existing_income_id'] == api.get(url).json()['existing_income_id']
    print('PASS concurrent next-period confirmations and reopening: one expected income.')


def check_invoice(actor):
    from django.core import mail
    from content.models import Document
    from content.services.hosting_periods import current_summary
    record, income, payment = mapped_service(actor)
    reviewed = current_summary(record.project_id)
    context = {'hosting_payment_id': payment.pk, 'period_version': reviewed['version']}
    from_income = {**context, 'client_profile_id': income.client_id, 'income_record_id': income.pk,
                   'billing_nature': 'hosting', 'project_hosting_id': reviewed['project_hosting_id'],
                   'items': [{'description': 'Servicio DEV', 'quantity': 1, 'amount': '233280.00'}]}
    sent_before = len(getattr(mail, 'outbox', []))
    results = compete(actor, (f'/api/accounting/hostings/{record.pk}/send-collection-account/', context),
                      ('/api/accounting/collection-accounts/create/', from_income))
    assert sorted(status for status, _ in results) in ([201, 400], [201, 409]), results
    document = Document.objects.get(project_id=record.project_id)
    assert document.items.get().period_start == payment.billing_period_start
    messages = [message for message in mail.outbox[sent_before:]
                if message.to == [record.billing_email] and document.public_number in message.subject]
    assert len(messages) == 1 and messages[0].attachments[0].mimetype == 'application/pdf'
    print('PASS concurrent billing from both entries: one document and one PDF email to the client.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', type=Path, required=True)
    configure(parser.parse_args().socket.resolve())
    from django.contrib.auth import get_user_model
    operator = get_user_model().objects.create(username='fixture-admin', is_superuser=True, is_staff=True)
    check_receipt_and_next(operator)
    check_invoice(operator)
