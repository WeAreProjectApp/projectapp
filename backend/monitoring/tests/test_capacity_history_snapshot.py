"""Frozen pagination contracts for capacity allocation audit history."""

import pytest

from monitoring.models import CapacityAllocation, CapacityChange, Resource

pytest_plugins = ('monitoring.tests.dashboard_fixtures',)


@pytest.fixture(name='dashboard_fixture')
def _dashboard_fixture(dashboard):
    """Expose the shared dashboard setup without shadowing its plugin fixture."""
    return dashboard


def _history_url(resource):
    """Return the history endpoint for one project capacity allocation."""
    return f'/api/monitoring/resources/{resource.pk}/capacity/history/'


def _create_changes(allocation, actor, total, *, start=0):
    """Create numbered audit records whose IDs make a frozen history observable."""
    return CapacityChange.objects.bulk_create([
        CapacityChange(
            allocation=allocation,
            actor=actor,
            actor_name=actor.get_username(),
            before={'ram_bytes': start + number},
            after={'ram_bytes': start + number + 1},
        )
        for number in range(total)
    ])


@pytest.mark.django_db
def test_capacity_history_bound_keeps_pages_stable_after_a_new_change(dashboard_fixture):
    """Fails if an inserted audit record shifts a bounded second page or leaks another allocation's records."""
    allocation = CapacityAllocation.objects.create(resource=dashboard_fixture['project'])
    initial = _create_changes(allocation, dashboard_fixture['actor'], 30)
    other_project = Resource.objects.create(
        key='other-capacity-history-project',
        name='Other capacity history project',
        kind='project',
        server=dashboard_fixture['server'],
    )
    other_allocation = CapacityAllocation.objects.create(resource=other_project)
    foreign_change = _create_changes(other_allocation, dashboard_fixture['actor'], 1)[0]

    first = dashboard_fixture['client'].get(_history_url(dashboard_fixture['project'])).json()
    new_change = _create_changes(allocation, dashboard_fixture['actor'], 1, start=100)[0]
    second_response = dashboard_fixture['client'].get(
        _history_url(dashboard_fixture['project']),
        {'page': 2, 'changes_before': first['history_bounds']['changes']},
    )
    second = second_response.json()
    frozen_ids = {row['id'] for row in first['results'] + second['results']}
    fresh = dashboard_fixture['client'].get(_history_url(dashboard_fixture['project'])).json()

    assert second_response.status_code == 200
    assert first['history_bounds']['changes'] == second['history_bounds']['changes']
    assert (first['count'], second['count'], frozen_ids) == (30, 30, {change.pk for change in initial})
    assert {new_change.pk, foreign_change.pk}.isdisjoint(frozen_ids)
    assert (
        fresh['count'],
        fresh['history_bounds']['changes'],
        new_change.pk in {row['id'] for row in fresh['results']},
    ) == (31, new_change.pk, True)


@pytest.mark.django_db
def test_zero_capacity_history_bound_remains_empty_after_an_insert(dashboard_fixture):
    """Fails if a zero bound begins showing records created after an initially empty history."""
    allocation = CapacityAllocation.objects.create(resource=dashboard_fixture['project'])
    first = dashboard_fixture['client'].get(_history_url(dashboard_fixture['project'])).json()
    _create_changes(allocation, dashboard_fixture['actor'], 1)

    frozen_response = dashboard_fixture['client'].get(
        _history_url(dashboard_fixture['project']),
        {'changes_before': first['history_bounds']['changes']},
    )
    frozen = frozen_response.json()

    assert first['count'] == 0
    assert first['history_bounds'] == {'changes': 0}
    assert frozen_response.status_code == 200
    assert frozen['history_bounds'] == {'changes': 0}
    assert frozen['count'] == 0
    assert frozen['results'] == []


@pytest.mark.django_db
@pytest.mark.parametrize('bound', ['not-an-id', -1])
def test_invalid_capacity_history_bound_is_rejected_without_writes(dashboard_fixture, bound):
    """Fails if an invalid history bound is accepted or a rejected read mutates capacity audit data."""
    CapacityAllocation.objects.create(resource=dashboard_fixture['project'])

    response = dashboard_fixture['client'].get(
        _history_url(dashboard_fixture['project']),
        {'changes_before': bound},
    )

    assert response.status_code == 400
    assert CapacityAllocation.objects.filter(resource=dashboard_fixture['project']).count() == 1
    assert CapacityChange.objects.count() == 0
