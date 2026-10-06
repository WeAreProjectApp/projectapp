"""Retain a confirmed graph without creating another operational project."""
from collections import defaultdict

from django.db import models

from accounts.models import Project
from content.models import ProjectRetentionContext
from content.services.entity_history import capture_instance
from content.services.project_deletion_catalog import CATEGORIES


def retain_project_records(plan, actor):
    retained = {key: row for key, row in plan.inventory.items() if key not in plan.rows}
    if not retained:
        return None
    index = defaultdict(list)
    for (model, pk) in retained:
        index[model._meta.label_lower].append(str(pk))
    context = ProjectRetentionContext.objects.create(
        client_id=plan.project.client_id, original_project_id=plan.project.pk,
        project_name=plan.project.name, retained_records=dict(index), created_by=actor,
        category_counts={label: len(ids) for label, ids in index.items()},
    )
    for row in retained.values():
        updates = {}
        for field in row._meta.concrete_fields:
            if (isinstance(field, models.ForeignKey) and field.remote_field.model is Project
                    and getattr(row, field.attname) == plan.project.pk):
                updates[field.attname] = None
        if updates:
            capture_instance(row)
            updates['retention_context_id'] = context.pk
            type(row)._base_manager.filter(pk=row.pk).update(**updates)
    return context


# An explicit allowlist prevents captured prompts, credentials and arbitrary
# metadata from leaking through the generic read-only consultation.
READ_FIELDS = {
    'title', 'name', 'description', 'content', 'content_markdown', 'text',
    'key_fields', 'relationship', 'concept', 'status', 'category', 'order',
    'environment', 'admin_url', 'admin_username', 'is_sensitive',
    'created_at', 'updated_at', 'opened_at', 'closed_at', 'effective_at',
    'event_type', 'action', 'origin', 'outcome', 'close_note', 'version_number',
    'period_date', 'movement_date', 'due_date', 'currency', 'amount',
    'total_amount', 'subtotal', 'total', 'billing_amount', 'direction', 'kind',
    'hosting_start_date', 'hosting_activated_at', 'label', 'severity',
    'steps_to_reproduce', 'expected_behavior', 'actual_behavior', 'admin_response',
    'author_label', 'revision_number', 'filename', 'size', 'sha256',
}


def retained_record_payload(row):
    fields, files = {}, []
    for field in row._meta.concrete_fields:
        if isinstance(field, models.FileField):
            value = getattr(row, field.name)
            if value:
                files.append({'field': field.name, 'name': value.name.rsplit('/', 1)[-1]})
        elif field.name in READ_FIELDS and not isinstance(field, models.ForeignKey):
            display = getattr(row, f'get_{field.name}_display', None)
            fields[field.name] = display() if display else getattr(row, field.name)
    title = next((fields.get(key) for key in ('title', 'name', 'concept', 'label') if fields.get(key)), '')
    category = CATEGORIES[row._meta.label_lower]
    return {'id': str(row.pk), 'key': category['key'], 'title': title or category['label'],
            'fields': fields, 'files': files,
            'can_reveal': row._meta.label_lower in ('accounts.projectadminaccess', 'accounts.projectaccessnote')}
