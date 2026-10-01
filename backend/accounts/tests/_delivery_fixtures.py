"""Contractual hierarchy builders for retained bugs, requests and resources tests."""

from django.utils.text import slugify

from accounts.models import (
    DeliveryPhase, DeliveryPublication, DeliveryScope, DeliveryStage,
    ProjectContract, Requirement,
)
from content.models import Document


def make_delivery_stage(project, *, key=None, published=True, phase_title=None):
    key = key or f'stage-{DeliveryStage.objects.count() + 1}'
    contract = ProjectContract.objects.filter(project=project, key='test-contract').first()
    if contract is None:
        document = Document.objects.create(
            title='Test contract', project=project, client_user=project.client,
            created_by=project.client, is_client_visible=True,
        )
        contract = ProjectContract.objects.create(
            project=project, document=document, key='test-contract',
            title='Test contract', client_visible=True,
        )
    scope, _ = DeliveryScope.objects.get_or_create(
        contract=contract, key='test-scope', defaults={'title': 'Test scope'},
    )
    phase = DeliveryPhase.objects.create(scope=scope, key=key, title=phase_title or f'Phase {key}')
    return DeliveryStage.objects.create(
        phase=phase, key=key, title=f'Stage {key}',
        editorial_status='published' if published else 'draft',
    )


def make_requirement(stage, *, title='Source requirement', key=None, published=True, **kwargs):
    key = key or slugify(title)[:100]
    requirement = Requirement.objects.create(
        stage=stage, key=key, title=title,
        review_status='in_review' if published else 'pending', **kwargs,
    )
    if published:
        DeliveryPublication.objects.update_or_create(
            stage=stage, round=1, defaults={
                'published_by': stage.project.client,
                'payload': {
                    'id': stage.id, 'key': stage.key, 'title': stage.title, 'version': stage.version,
                    'requirements': [
                        {name: getattr(req, name) for name in (
                            'id', 'key', 'title', 'description', 'guide', 'version', 'review_status',
                        )}
                        for req in stage.requirements.all()
                    ],
                },
            },
        )
    return requirement
