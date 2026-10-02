"""Credit-card statement list query and serialization contracts."""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models.signals import post_init
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from content.models import CreditCardStatement, CreditCardTransaction

pytestmark = pytest.mark.django_db
MAX_STATEMENT_LIST_QUERIES = 6
STATEMENTS_URL = '/api/accounting/statements/'


def _statement_client(user):
    client = APIClient()
    client.force_login(user)
    return client


def _create_statement_set(total):
    statements = []
    for index in range(total):
        statement = CreditCardStatement.objects.create(card_name=f'Query card {index:03d}', period_date=date(2020 + index // 12, index % 12 + 1, 1), purchases_total=Decimal('1.00'))
        CreditCardTransaction.objects.create(statement=statement, transaction_date=statement.period_date, raw_description=f'Query transaction {index:03d}', amount=Decimal('1.00'))
        statements.append(statement)
    return statements


def _count_statement_queries(client):
    with CaptureQueriesContext(connection) as queries:
        response = client.get(STATEMENTS_URL)
    return response, len(queries)


def _capture_transaction_initializations(client):
    initialized = []

    def remember_transaction(sender, instance, **kwargs):
        initialized.append(instance.pk)

    post_init.connect(remember_transaction, sender=CreditCardTransaction, weak=False)
    try:
        response = client.get(STATEMENTS_URL)
    finally:
        post_init.disconnect(remember_transaction, sender=CreditCardTransaction)
    return response, initialized


def _add_transactions(statement, amounts):
    for index, amount in enumerate(amounts):
        CreditCardTransaction.objects.create(statement=statement, transaction_date=date(2026, 9, index + 1), raw_description=f'Sum transaction {index}', amount=amount)


def test_statement_list_query_budget_does_not_grow_with_fifty_statements(record_property):
    """Falla si el serializer vuelve a consultar transacciones por extracto."""
    superuser = get_user_model().objects.create_superuser(username='statement-budget-admin', email='statement-budget@example.com', password='testpass123')
    _create_statement_set(1)
    single_response, single_queries = _count_statement_queries(_statement_client(superuser))
    CreditCardStatement.objects.all().delete()
    _create_statement_set(50)
    many_response, many_queries = _count_statement_queries(_statement_client(superuser))

    record_property('statement_queries_one', single_queries)
    record_property('statement_queries_fifty', many_queries)
    assert single_response.status_code == 200
    assert many_response.status_code == 200
    assert len(single_response.data['results']) == 1
    assert len(many_response.data['results']) == 50
    assert single_queries == many_queries
    assert many_queries <= MAX_STATEMENT_LIST_QUERIES


@pytest.mark.parametrize('total', [1, 50])
def test_statement_list_does_not_hydrate_transactions(total):
    """Falla si el listado materializa transacciones para serializar extractos."""
    superuser = get_user_model().objects.create_superuser(username=f'statement-hydration-{total}', email=f'statement-hydration-{total}@example.com', password='testpass123')
    statements = _create_statement_set(total)

    response, initialized = _capture_transaction_initializations(_statement_client(superuser))

    assert response.status_code == 200
    assert response.data['results'][0]['card_name'] == statements[-1].card_name
    assert initialized == []


@pytest.mark.parametrize(('amounts', 'expected_count', 'expected_sum'), [((Decimal('-7.25'),), 1, '-7.25'), ((Decimal('12.30'),), 1, '12.30'), ((), 0, '0'), ((Decimal('-4.00'), Decimal('4.00')), 2, '0.00')])
def test_statement_list_preserves_transaction_sum_contract(amounts, expected_count, expected_sum):
    """Falla si NULL, cero, negativos o decimales cambian el contrato de suma."""
    superuser = get_user_model().objects.create_superuser(username=f'statement-sum-{expected_sum}', email=f'statement-sum-{expected_count}@example.com', password='testpass123')
    statement = CreditCardStatement.objects.create(card_name='Sum contract', period_date=date(2026, 9, 1), purchases_total=Decimal('0.00'))
    _add_transactions(statement, amounts)

    response = _statement_client(superuser).get(STATEMENTS_URL)

    assert response.status_code == 200
    assert response.data['results'][0]['transactions_count'] == expected_count
    assert response.data['results'][0]['transactions_sum'] == expected_sum


def test_statement_list_orders_equal_periods_by_card_name():
    """Falla si extractos del mismo periodo dejan de conservar su orden estable."""
    superuser = get_user_model().objects.create_superuser(username='statement-order-admin', email='statement-order@example.com', password='testpass123')
    CreditCardStatement.objects.create(card_name='Zulu', period_date=date(2026, 9, 1), purchases_total=0)
    CreditCardStatement.objects.create(card_name='Alpha', period_date=date(2026, 9, 1), purchases_total=0)
    CreditCardStatement.objects.create(card_name='Later', period_date=date(2026, 10, 1), purchases_total=0)

    response = _statement_client(superuser).get(STATEMENTS_URL)

    assert response.status_code == 200
    assert [row['card_name'] for row in response.data['results']] == ['Later', 'Alpha', 'Zulu']


def test_statement_list_filters_a_status_for_one_card_name():
    """Falla si las anotaciones evitan los filtros sencillos del listado."""
    superuser = get_user_model().objects.create_superuser(username='statement-filter-admin', email='statement-filter@example.com', password='testpass123')
    CreditCardStatement.objects.create(card_name='Visa', period_date=date(2026, 9, 1), purchases_total=0)
    CreditCardStatement.objects.create(card_name='Visa', period_date=date(2026, 10, 1), purchases_total=0, status=CreditCardStatement.Status.PROCESSED)

    response = _statement_client(superuser).get(f'{STATEMENTS_URL}?status=processed&card_name=Visa')

    assert response.status_code == 200
    assert [row['status'] for row in response.data['results']] == ['processed']


def test_statement_detail_preserves_the_unannotated_total_fallback():
    """Falla si un caller sin anotaciones deja de contar sus transacciones reales."""
    superuser = get_user_model().objects.create_superuser(username='statement-fallback-admin', email='statement-fallback@example.com', password='testpass123')
    statement = CreditCardStatement.objects.create(card_name='Fallback card', period_date=date(2026, 9, 1), purchases_total=Decimal('4.00'))
    CreditCardTransaction.objects.create(statement=statement, transaction_date=date(2026, 9, 2), raw_description='Fallback purchase', amount=Decimal('4.00'))

    response = _statement_client(superuser).get(f'{STATEMENTS_URL}{statement.pk}/')

    assert response.status_code == 200
    assert response.data['transactions_count'] == 1
    assert response.data['transactions_sum'] == '4.00'
