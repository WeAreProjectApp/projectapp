"""Client interests are commercial leads, never contracted scope or prices."""

import json

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from content.models import AdditionalModule, BusinessProposal, ProposalChangeLog


class ModuleInterestsSerializer(serializers.Serializer):
    module_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=200,
    )

    def validate_module_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError('No repitas módulos en la selección.')
        return value


def interest_payload(proposal):
    return {
        'modules': proposal.module_interests,
        'updated_at': proposal.module_interests_updated_at,
    }


@transaction.atomic
def save_module_interests(proposal_id, module_ids):
    proposal = BusinessProposal.objects.select_for_update().get(pk=proposal_id)
    if not proposal.is_active or proposal.is_expired:
        raise serializers.ValidationError('Esta propuesta ya no admite cambios.')
    previous = {item['id']: item for item in proposal.module_interests}
    active = {
        module.pk: module for module in AdditionalModule.objects.select_related('category')
        .filter(pk__in=module_ids, is_active=True, category__is_active=True)
    }
    # Existing interests remain readable/removable after catalog deactivation.
    if set(module_ids) - active.keys() - previous.keys():
        raise serializers.ValidationError({'module_ids': 'Hay módulos que ya no están disponibles.'})
    if set(previous) == set(module_ids):
        return proposal

    interests = []
    for module_id in sorted(module_ids):
        if module_id in previous:
            interests.append(previous[module_id])
            continue
        module = active[module_id]
        interests.append({
            'id': module.pk,
            'slug': module.slug,
            'name_es': module.name_es,
            'name_en': module.name_en,
            'category_es': module.category.name_es,
            'category_en': module.category.name_en,
        })
    proposal.module_interests = interests
    proposal.module_interests_updated_at = timezone.now()
    proposal.save(update_fields=['module_interests', 'module_interests_updated_at'])
    ProposalChangeLog.objects.create(
        proposal=proposal, change_type=ProposalChangeLog.ChangeType.MODULE_INTERESTS,
        actor_type='client', description=json.dumps(interests, ensure_ascii=False),
    )
    return proposal
