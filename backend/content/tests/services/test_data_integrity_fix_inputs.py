"""Required choices reject values outside the offered type and options."""
import pytest

from content.services.data_integrity.fixes.base import required_choice


@pytest.mark.parametrize('value', [None, ''])
def test_empty_choice_requires_operator_input(value):
    chosen, blockers = required_choice({'project': value}, 'project', [{'value': 1}], 'el proyecto')

    assert chosen is None
    assert [entry['code'] for entry in blockers] == ['input_required']


def test_missing_choice_requires_operator_input():
    chosen, blockers = required_choice({}, 'project', [{'value': 1}], 'el proyecto')

    assert chosen is None
    assert [entry['code'] for entry in blockers] == ['input_required']


@pytest.mark.parametrize('value', [True, False, 1.0, '1', [], [1], {}, {1}, (1,), b'1', 2])
def test_invalid_integer_choice_returns_a_blocker(value):
    chosen, blockers = required_choice({'project': value}, 'project', [{'value': 1}], 'el proyecto')

    assert chosen is None
    assert [entry['code'] for entry in blockers] == ['invalid_input']


@pytest.mark.parametrize('value', [1, 'keep'])
def test_offered_choice_is_accepted(value):
    chosen, blockers = required_choice({'choice': value}, 'choice', [{'value': value}], 'la opción')

    assert chosen == value
    assert blockers == []


def test_integer_choice_is_invalid_for_string_options():
    chosen, blockers = required_choice({'side': 1}, 'side', [{'value': '1'}], 'el origen')

    assert chosen is None
    assert [entry['code'] for entry in blockers] == ['invalid_input']
