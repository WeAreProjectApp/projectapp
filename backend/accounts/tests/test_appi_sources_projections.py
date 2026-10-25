"""Client-safe Appi source projections for project, delivery, bug, and deliverable data."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import BugReport, Deliverable, Project, UserProfile
from accounts.services import appi_sources, delivery_workflow
from accounts.tests.delivery_helpers import build_delivery_context, decisions, publish

pytestmark = pytest.mark.django_db
pytest_plugins = ('accounts.tests.appi_test_support',)


def test_project_status_lists_only_the_clients_projects(appi_context):
    """Fails if an all-project status projection includes another client's project."""
    second = Project.objects.create(client=appi_context.actor, name='Second owned project')
    other = get_user_model().objects.create_user('projection-other', email='projection-other@appi.test')
    UserProfile.objects.update_or_create(user=other, defaults={'role': UserProfile.ROLE_CLIENT})
    Project.objects.create(client=other, name='Foreign project')

    result = appi_sources.snapshot(
        appi_context.actor,
        None,
        {'scenario': 'project_status', 'topic': 'general', 'explain': False},
        'es',
    )

    assert {source['id'] for source in result['sources']} == {
        f'project:{appi_context.project.pk}', f'project:{second.pk}',
    }
    assert [row['name'] for row in result['basis']['projects']] == ['Appi project', 'Second owned project']


def test_overdue_project_health_reports_its_recorded_evidence(appi_context):
    """Fails if project health omits recorded evidence for an overdue incomplete project."""
    overdue = Project.objects.create(
        client=appi_context.actor,
        name='Overdue project',
        progress=40,
        estimated_end_date=timezone.localdate() - timedelta(days=1),
    )
    BugReport.objects.create(
        project=overdue,
        reported_by=appi_context.actor,
        title='Open checkout bug',
        status=BugReport.STATUS_CONFIRMED,
    )

    result = appi_sources.snapshot(
        appi_context.actor,
        overdue.pk,
        {'scenario': 'project_health', 'topic': 'general', 'explain': False},
        'es',
    )

    facts = '\n'.join(item['text'] for item in result['facts'])
    assert 'Avance registrado: 40 %' in facts
    assert 'Bugs abiertos: 1' in facts
    assert overdue.estimated_end_date.isoformat() in facts
    assert 'La fecha estimada ya pasó' in facts


def test_project_health_without_estimated_date_omits_the_overdue_warning(appi_context):
    """Fails if Appi reports an overdue warning for a project with no recorded deadline."""
    undated = Project.objects.create(client=appi_context.actor, name='Undated project', progress=40)

    result = appi_sources.snapshot(
        appi_context.actor,
        undated.pk,
        {'scenario': 'project_health', 'topic': 'general', 'explain': False},
        'es',
    )

    facts = '\n'.join(item['text'] for item in result['facts'])
    assert result['basis']['projects'][0]['estimated_end_date'] is None
    assert 'La fecha estimada ya pasó' not in facts


def test_bug_selection_includes_description_only_for_the_selected_open_bug(appi_context):
    """Fails if archived bug content leaks or a selected detail expands every visible bug."""
    selected = BugReport.objects.create(
        project=appi_context.project,
        reported_by=appi_context.actor,
        title='Selected bug',
        description='Selected private reproduction detail.',
    )
    BugReport.objects.create(
        project=appi_context.project,
        reported_by=appi_context.actor,
        title='Other open bug',
        description='Other reproduction detail.',
    )
    BugReport.objects.create(
        project=appi_context.project,
        reported_by=appi_context.actor,
        title='Archived bug',
        description='Archived reproduction detail.',
        is_archived=True,
    )

    listing = appi_sources.snapshot(
        appi_context.actor,
        appi_context.project.pk,
        {'scenario': 'bugs', 'topic': 'general', 'explain': False},
        'es',
    )
    selected_result = appi_sources.snapshot(
        appi_context.actor,
        appi_context.project.pk,
        {'scenario': 'bugs', 'topic': 'general', 'explain': False, 'entity_id': str(selected.pk)},
        'es',
    )

    listing_text = '\n'.join(item['text'] for item in listing['facts'])
    selected_text = '\n'.join(item['text'] for item in selected_result['facts'])
    assert 'Archived bug' not in listing_text
    assert 'Selected private reproduction detail.' in selected_text
    assert 'Other reproduction detail.' not in selected_text
    assert selected_result['sources'] == [{
        'id': f'bug:{selected.pk}',
        'label': 'Selected bug',
        'href': f'/platform/projects/{appi_context.project.pk}/bugs',
    }]


def test_deliverable_projection_omits_administrative_categories(appi_context):
    """Fails if an Appi deliverable list exposes resources reserved for administrators."""
    shared = Deliverable.objects.create(
        project=appi_context.project,
        uploaded_by=appi_context.actor,
        title='Client handbook',
        category=Deliverable.CATEGORY_DOCUMENTS,
    )
    Deliverable.objects.create(
        project=appi_context.project,
        uploaded_by=appi_context.actor,
        title='Internal design source',
        category=Deliverable.CATEGORY_DESIGNS,
    )

    result = appi_sources.snapshot(
        appi_context.actor,
        appi_context.project.pk,
        {'scenario': 'deliverables', 'topic': 'general', 'explain': False},
        'es',
    )

    assert result['candidates'] == [{'id': shared.pk, 'title': 'Client handbook'}]
    assert result['sources'] == [{
        'id': f'deliverable:{shared.pk}',
        'label': 'Client handbook',
        'href': f'/platform/projects/{appi_context.project.pk}/deliverables/{shared.pk}',
    }]


def test_phase_status_reads_the_published_delivery_projection():
    """Fails if phase status ignores the canonical publication and its review decisions."""
    context = build_delivery_context()
    publish(context)
    delivery_workflow.review_stage(
        context.project.pk,
        context.client,
        context.stage.pk,
        decisions(context, (context.first, 'approved')),
    )

    result = appi_sources.snapshot(
        context.client,
        context.project.pk,
        {'scenario': 'phase_status', 'topic': 'general', 'explain': False},
        'es',
    )

    phase = result['basis']['phases'][0]
    facts = '\n'.join(item['text'] for item in result['facts'])
    assert phase['title'] == 'Fase'
    assert phase['stages'][0]['title'] == 'Etapa'
    assert [item['status'] for item in phase['stages'][0]['requirements']] == ['approved', 'in_review']
    assert 'Pendientes de aprobación: 1' in facts


def test_phase_status_without_a_project_requires_project_selection():
    """Fails if phase status invents a delivery phase without a selected project."""
    context = build_delivery_context()

    result = appi_sources.snapshot(
        context.client,
        None,
        {'scenario': 'phase_status', 'topic': 'general', 'explain': False},
        'es',
    )

    assert result['needs_project'] is True
    assert result['facts'] == []
    assert result['sources'] == []
