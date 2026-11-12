"""Financial record scopes keep integrity scans local to their accounting graph."""
from datetime import date
from decimal import Decimal

import pytest

from content.models import PocketMovement
from content.services.data_integrity.scope import EXPENSE, INCOME, POCKET, PROJECT, resolve_scope
from content.tests.data_integrity_helpers import make_project

pytestmark = pytest.mark.django_db


def test_income_scope_keeps_its_expected_payment_pair_without_client_siblings(
    make_client_profile, make_income,
):
    """Fails if an income scan expands from one payment to every income of its client or project."""
    profile = make_client_profile()
    project = make_project(profile)
    expected = make_income(client=profile, project=project, concept='Fase uno')
    payment = make_income(
        client=profile, project=project, concept='Pago fase uno', kind='liquid',
        expected_income=expected,
    )
    sibling = make_income(client=profile, project=project, concept='Fase dos')

    scope = resolve_scope('income', payment.pk)

    assert scope.ids_for(INCOME) == {expected.pk, payment.pk}
    assert sibling.pk not in scope.ids_for(INCOME)
    assert scope.ids_for(PROJECT) == set()


def test_expense_scope_keeps_its_source_income_without_other_client_records(
    make_client_profile, make_expense, make_income,
):
    """Fails if a deduction scan exposes an unrelated income owned by the same client."""
    profile = make_client_profile()
    project = make_project(profile)
    source = make_income(client=profile, project=project, concept='Ingreso con retención')
    deduction = make_expense(concept='Retención', source_income=source)
    unrelated = make_income(client=profile, project=project, concept='Ingreso ajeno')

    scope = resolve_scope('expense', deduction.pk)

    assert scope.ids_for(EXPENSE) == {deduction.pk}
    assert scope.ids_for(INCOME) == {source.pk}
    assert unrelated.pk not in scope.ids_for(INCOME)


def test_pocket_scope_follows_linked_deduction_source_without_client_siblings(
    make_client_profile, make_expense, make_income,
):
    """Fails if a pocket review omits its deduction's source income or widens to another client income."""
    profile = make_client_profile()
    project = make_project(profile)
    pocket = PocketMovement.objects.create(
        concept='Pago compartido', movement_date=date(2026, 11, 5),
        direction=PocketMovement.Direction.IN, amount=Decimal('100.00'),
    )
    source = make_income(client=profile, project=project, concept='Ingreso base')
    payment = make_income(
        client=profile, project=project, concept='Pago base', kind='liquid',
        expected_income=source, pocket_movement=pocket,
    )
    deduction = make_expense(
        concept='Retención base', source_income=source, pocket_movement=pocket,
    )
    unrelated = make_income(client=profile, project=project, concept='Ingreso ajeno')

    scope = resolve_scope('pocket_movement', pocket.pk)

    assert scope.ids_for(POCKET) == {pocket.pk}
    assert scope.ids_for(EXPENSE) == {deduction.pk}
    assert scope.ids_for(INCOME) == {source.pk, payment.pk}
    assert unrelated.pk not in scope.ids_for(INCOME)


def test_hosting_scope_keeps_only_its_linked_documents(make_client_profile, make_income):
    from content.tests.data_integrity_accounting_factories import make_hosting
    from content.tests.data_integrity_documents_factories import make_document
    from content.services.data_integrity.scope import HOSTING, DOCUMENT
    client = make_client_profile()
    project = make_project(client)
    hosting = make_hosting(client, project)
    document = make_document('Cuenta vinculada', hosting_record=hosting)
    make_document('Documento ajeno', client_user=client.user, project=project)

    scope = resolve_scope('hosting', hosting.pk)

    assert scope.ids_for(HOSTING) == {hosting.pk}
    assert scope.ids_for(DOCUMENT) == {document.pk}
