"""New-round state is independent of previous objected decisions."""
import pytest
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import build_delivery_context, decisions, publish, stage_data, version

pytestmark = pytest.mark.django_db


def test_client_snapshot_status_stays_in_review_during_draft_edit():
    context = build_delivery_context()
    publish(context)
    delivery.mutate_node(context.project.pk, context.admin, 'requirements',
                         {'expected_version': version(context), 'title': 'Borrador privado'}, context.second.pk)

    response = delivery.overview(context.project.pk, context.client)

    assert stage_data(response)['status'] == 'in_review'
    assert stage_data(response)['editorial_status'] == 'published'
    assert stage_data(response)['requirements'][1]['title'] == 'Editar registro'


def test_unchanged_guide_reopens_in_a_new_publication():
    context = build_delivery_context()
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'objected')))
    publish(context, 'reopen')

    response = delivery.overview(context.project.pk, context.client)

    requirements = stage_data(response)['requirements']
    assert requirements[0]['review_status'] == 'approved'
    assert requirements[1]['review_status'] == 'in_review'
    assert requirements[1]['version'] == 1
    assert requirements[1]['reviews'][0]['decision'] == 'objected'
