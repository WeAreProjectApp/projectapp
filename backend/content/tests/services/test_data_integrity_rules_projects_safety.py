"""Project fixes preserve cascades and refuse retained side effects."""
from decimal import Decimal

import pytest
from accounts.models import ProjectPhase

from content.models import ContractTemplate, Document, DocumentFolder, IncomeRecord
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope
from content.tests.data_integrity_accounting_factories import (
    associate_hosting_context,
    make_cuenta,
    make_hosting,
)
from content.tests.data_integrity_helpers import (
    apply,
    make_phase,
    make_project,
    make_proposal,
    only,
    scan,
    selection,
    undo,
)
from content.tests.data_integrity_projects_factories import make_retention_context

pytestmark = pytest.mark.django_db


def found(rule_id, scope_kind='all', scope_id=None):
    return only(scan(scope_kind, scope_id, rule_ids=[rule_id]), rule_id)


def preview(actor, finding, **params):
    return engine.preview_fixes(resolve_scope('all'), [selection(finding, **params)], actor=actor)


def test_income_relink_records_liquid_and_draft_account_cascades(make_client_profile, make_income, superuser):
    """Fails if an income's liquid or draft account stays unlinked or loses its old project on undo."""
    client = make_client_profile()
    project = make_project(client)
    expected = make_income(client=client)
    liquid = make_income(client=client, kind='liquid', expected_income=expected)
    draft = make_cuenta(client, None, status='draft', income_record=liquid)
    [finding] = [row for row in found('PJ1') if row.evidence['model'] == 'content.incomerecord']

    impact, result = apply(superuser, [selection(finding, project=project.pk)])

    assert impact['records'] == 3
    assert list(IncomeRecord.objects.filter(pk__in=[expected.pk, liquid.pk]).values_list('project_id', flat=True)) == [
        project.pk, project.pk]
    assert Document.objects.get(pk=draft.pk).project_id == project.pk
    undo(superuser, result['operation_id'])
    assert list(IncomeRecord.objects.filter(pk__in=[expected.pk, liquid.pk]).values_list('project_id', flat=True)) == [
        None, None]
    assert Document.objects.get(pk=draft.pk).project_id is None


def test_hosting_relink_can_restore_its_original_project_without_changing_totals(make_client_profile, superuser):
    """Fails if linking hosting changes its billing amounts or undo leaves it linked."""
    client = make_client_profile()
    project = make_project(client)
    hosting = make_hosting(client, total_paid=Decimal('500000.00'), cycles_count=2)
    [finding] = found('PJ1')

    _, result = apply(superuser, [selection(finding, project=project.pk)])

    hosting.refresh_from_db()
    assert (hosting.project_id, hosting.total_paid, hosting.cycles_count) == (project.pk, Decimal('500000.00'), 2)
    undo(superuser, result['operation_id'])
    hosting.refresh_from_db()
    assert hosting.project_id is None


def test_income_relink_is_blocked_when_a_liquid_child_is_retained(make_client_profile, make_income, superuser):
    """Fails if the project's income writer can rewrite a retained liquid through its cascade."""
    client = make_client_profile()
    project = make_project(client)
    parent = make_income(client=client)
    make_income(client=client, kind='liquid', expected_income=parent,
                retention_context=make_retention_context(client, superuser))
    [finding] = found('PJ1')

    impact = preview(superuser, finding, project=project.pk)

    assert [entry['code'] for entry in impact['steps'][0]['blockers']] == ['retained_read_only']
    assert impact['blocked'] is True


def test_duplicate_project_rename_restores_descendant_client_and_root_archive_cause(make_client_profile, superuser):
    """Fails if undo misses a descendant realignment or an archive cause cleared by root synchronization."""
    client = make_client_profile()
    other = make_client_profile()
    make_project(client, 'Portal')
    renamed = make_project(client, 'PORTAL')
    root = DocumentFolder.objects.get(managed_project=renamed)
    descendant = DocumentFolder.objects.get(project=renamed, name='QA')
    archive_cause = DocumentFolder.objects.create(name='Archivo')
    DocumentFolder.objects.filter(pk=root.pk).update(archived_via_folder=archive_cause)
    DocumentFolder.objects.filter(pk=descendant.pk).update(client_user=other.user)
    [finding] = found('PJ4')

    _, result = apply(superuser, [selection(finding, project=renamed.pk, name='Portal nuevo')])

    assert DocumentFolder.objects.get(pk=root.pk).archived_via_folder_id is None
    assert DocumentFolder.objects.get(pk=descendant.pk).client_user_id == client.user_id
    undo(superuser, result['operation_id'])
    assert DocumentFolder.objects.get(pk=root.pk).archived_via_folder_id == archive_cause.pk
    assert DocumentFolder.objects.get(pk=descendant.pk).client_user_id == other.user_id


def test_duplicate_project_rename_refuses_a_retained_descendant_realign(make_client_profile, superuser):
    """Fails if a project rename can alter a retained folder through its synchronization signal."""
    client = make_client_profile()
    other = make_client_profile()
    make_project(client, 'Portal')
    renamed = make_project(client, 'PORTAL')
    descendant = DocumentFolder.objects.get(project=renamed, name='QA')
    DocumentFolder.objects.filter(pk=descendant.pk).update(
        client_user=other.user, retention_context=make_retention_context(client, superuser))
    [finding] = found('PJ4')

    impact = preview(superuser, finding, project=renamed.pk, name='Portal nuevo')

    assert [entry['code'] for entry in impact['steps'][0]['blockers']] == ['retained_read_only']


def test_client_scope_includes_only_its_adoptable_retained_records(make_client_profile, make_income, superuser):
    """Fails if retained records waiting for another client leak into a client review."""
    client = make_client_profile()
    other = make_client_profile()
    target = make_project(client)
    make_project(other, 'Otro')
    make_income(client=client, retention_context=make_retention_context(client, superuser))
    make_income(client=other, retention_context=make_retention_context(other, superuser, original_project_id=9002))

    [finding] = found('PJ3', 'client', client.pk)

    assert finding.evidence['project'] == target.pk


def test_empty_retained_folder_with_an_operational_project_offers_container_cleanup(make_client_profile, superuser):
    """Fails if a retained folder is missed after its contents have already been moved."""
    client = make_client_profile()
    target = make_project(client)
    context = make_retention_context(client, superuser)
    DocumentFolder.objects.create(name='Carpeta conservada', client_user=client.user, retention_context=context)

    [finding] = found('PJ3', 'client', client.pk)

    assert finding.evidence['project'] == target.pk
    assert finding.tool == {'connector': 'projects', 'name': 'delete_empty_retained_containers',
                            'arguments': {'context_id': context.pk}}


@pytest.mark.parametrize('value', [True, 1.5, []])
def test_invalid_project_choices_are_blocked_without_coercion(make_client_profile, make_income, superuser, value):
    """Fails if a boolean, decimal or collection is accepted as a project identifier."""
    client = make_client_profile()
    make_project(client)
    make_income(client=client)
    [finding] = found('PJ1')

    impact = preview(superuser, finding, project=value)

    assert [entry['code'] for entry in impact['steps'][0]['blockers']] == ['invalid_input']


def test_income_relink_refuses_a_child_belonging_to_another_client(make_client_profile, make_income, superuser):
    """Fails if a mechanical liquid cascade creates a foreign-client project link."""
    client = make_client_profile()
    project = make_project(client)
    parent = make_income(client=client)
    make_income(client=make_client_profile(), kind='liquid', expected_income=parent)
    [finding] = found('PJ1')

    impact = preview(superuser, finding, project=project.pk)

    assert [entry['code'] for entry in impact['steps'][0]['blockers']] == ['child_client_mismatch']


def test_income_relink_refuses_a_child_with_associated_billing(make_client_profile, make_income, superuser):
    """Fails if a liquid's existing billing association is bypassed by its parent cascade."""
    client = make_client_profile()
    target = make_project(client, 'Destino')
    original = make_project(client, 'Facturado')
    parent = make_income(client=client)
    child = make_income(client=client, kind='liquid', expected_income=parent, project=original)
    associate_hosting_context(make_cuenta(client, original, income_record=child))
    [finding] = found('PJ1')

    impact = preview(superuser, finding, project=target.pk)

    assert [entry['code'] for entry in impact['steps'][0]['blockers']] == ['billing_guard']


def test_unlinked_contract_template_only_reports_its_association(make_client_profile):
    """Fails if an unlinked contractual mirror is offered a generic document rewrite."""
    client = make_client_profile()
    make_project(client)
    document = Document.objects.create(title='Plantilla', client_user=client.user)
    ContractTemplate.objects.create(name='Plantilla', content_markdown='# Contrato', mirror_document=document)

    [finding] = found('PJ1')

    assert finding.fix_kinds == ('report_only',)
    assert finding.tool is None
    assert finding.inputs == {}


def test_moved_phase_blocks_reorder_undo(make_client_profile, superuser):
    """Fails if undo rewrites a phase moved to another project after its order was repaired."""
    client = make_client_profile()
    project = make_project(client)
    target = make_project(client, 'Destino')
    phase = make_phase(project, make_proposal(client), 3)
    [finding] = found('PJ7', 'project', project.pk)
    _, result = apply(superuser, [selection(finding)])
    ProjectPhase.objects.filter(pk=phase.pk).update(project=target)

    impact = engine.preview_undo(result['operation_id'])

    assert [entry['code'] for entry in impact['blockers']] == ['guard_changed']


def test_new_phase_blocks_reorder_undo(make_client_profile, superuser):
    """Fails if undo includes a phase created after the project's order was repaired."""
    client = make_client_profile()
    project = make_project(client)
    make_phase(project, make_proposal(client), 3)
    [finding] = found('PJ7', 'project', project.pk)
    _, result = apply(superuser, [selection(finding)])
    make_phase(project, make_proposal(client), 2)

    impact = engine.preview_undo(result['operation_id'])

    assert [entry['code'] for entry in impact['blockers']] == ['guard_changed']
