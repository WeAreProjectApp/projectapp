"""Mirror proposal resources and data models without authoring client reviews.

Commercial ProjectPhase records retain their existing proposal/hosting role.
Contractual delivery guides are authored separately and are never synchronized
from technical epics or commercial functionality groups.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Max

from accounts.models import (
    DataModelEntity,
    Deliverable,
    ProjectPhase,
)
from accounts.services.archive import archive_record
from content.models import ProposalSection


User = get_user_model()


def _str(value: Any) -> str:
    """Normalize any value to a stripped string ('' for None)."""
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def _ensure_phase(project, bp) -> ProjectPhase:
    """Keep the commercial proposal association available to hosting and resources."""
    phase = ProjectPhase.objects.filter(project=project, business_proposal=bp).first()
    if phase:
        return phase
    next_order = (project.phases.aggregate(m=Max('order'))['m'] or 0) + 1
    return ProjectPhase.objects.create(
        project=project, business_proposal=bp, order=next_order,
    )


def _parse_epics_from_json(content_json: dict) -> list:
    """Extract and normalize the epics list from a technical_document content_json."""
    epics = (content_json or {}).get('epics') or []
    return epics if isinstance(epics, list) else []


def _parse_data_model_entities(content_json: dict) -> list:
    """Extract and normalize the entities list from a technical_document content_json."""
    dm = (content_json or {}).get('dataModel') or {}
    entities = dm.get('entities') or []
    return entities if isinstance(entities, list) else []


def filtered_technical_doc_for_sync(bp, doc: dict) -> dict:
    """Reduce *doc* to what the client actually contracted before syncing.

    Resources mirror the contracted selection only: epics linked
    to unselected optional modules (including backend-seeded module catalogs)
    stay out of the client project until the module joins the selection.
    """
    if not isinstance(doc, dict):
        return {}
    from content.services.proposal_pdf_service import (
        default_selected_modules_from_content,
    )
    from content.services.technical_document_filter import (
        get_filtered_technical_document,
    )

    section_payloads = [
        {
            'section_type': s.section_type,
            'content_json': s.content_json if isinstance(s.content_json, dict) else {},
        }
        for s in bp.sections.all()
    ]
    return get_filtered_technical_document(
        doc, section_payloads, default_selected_modules_from_content(bp),
    )


def compute_sync_diff(project, new_content_json: dict) -> dict[str, Any]:
    """Preview resource and data-model changes without writing delivery guides."""
    epics_list = _parse_epics_from_json(new_content_json)

    # Build lookup of current non-archived Deliverables by source_epic_key
    current_deliverables = {
        d.source_epic_key: d
        for d in Deliverable.objects.filter(
            project=project,
            source_epic_key__isnull=False,
            is_archived=False,
        )
        if d.source_epic_key
    }

    diff: dict[str, Any] = {
        'epics': {'to_create': [], 'to_update': [], 'to_delete': []},
        'data_model_entities': {'to_create': [], 'to_update': [], 'to_delete': []},
    }

    seen_epic_keys: set[str] = set()

    for idx, epic in enumerate(epics_list):
        if not isinstance(epic, dict):
            continue
        key = (epic.get('epicKey') or '').strip()
        title = (epic.get('title') or '').strip() or key or f'Módulo {idx + 1}'
        description = (epic.get('description') or '')
        reqs = epic.get('requirements') or []
        if not isinstance(reqs, list):
            reqs = []

        if not key:
            if not reqs:
                continue
            key = f'_sync_epic_{idx}'

        seen_epic_keys.add(key)

        if key not in current_deliverables:
            diff['epics']['to_create'].append({'epicKey': key, 'title': title})
        else:
            d = current_deliverables[key]
            changed: list[str] = []
            if d.title != title[:300]:
                changed.append('title')
            if d.description != description[:2000]:
                changed.append('description')
            if changed:
                diff['epics']['to_update'].append({'epicKey': key, 'title': title, 'changed_fields': changed})

    # Records that exist in DB but are not in the new JSON → to_delete
    for key, d in current_deliverables.items():
        if key not in seen_epic_keys:
            diff['epics']['to_delete'].append({'epicKey': key, 'title': d.title})

    # --- Data model entities diff ---
    # Entities are duplicated per deliverable; diff only needs one representative
    # per source_entity_name, so we use setdefault to keep the first occurrence.
    entities_list = _parse_data_model_entities(new_content_json)
    current_entities: dict[str, DataModelEntity] = {}
    for e in DataModelEntity.objects.filter(
        deliverable__project=project,
        is_archived=False,
    ):
        if e.source_entity_name:
            current_entities.setdefault(e.source_entity_name, e)
    seen_entity_names: set[str] = set()

    for ent in entities_list:
        if not isinstance(ent, dict):
            continue
        ent_name = (ent.get('name') or '').strip()
        if not ent_name:
            continue
        seen_entity_names.add(ent_name)
        ent_desc = (ent.get('description') or '').strip()
        ent_kf = (ent.get('keyFields') or '').strip()

        if ent_name not in current_entities:
            diff['data_model_entities']['to_create'].append({
                'name': ent_name, 'description': ent_desc,
            })
        else:
            existing = current_entities[ent_name]
            changed_e: list[str] = []
            if existing.description != ent_desc:
                changed_e.append('description')
            if existing.key_fields != ent_kf:
                changed_e.append('key_fields')
            if changed_e:
                diff['data_model_entities']['to_update'].append({
                    'name': ent_name, 'changed_fields': changed_e,
                })

    for ent_name, ent_obj in current_entities.items():
        if ent_name not in seen_entity_names:
            diff['data_model_entities']['to_delete'].append({'name': ent_name})

    return diff


def _sync_technical_resources_core(
    project,
    bp,
    acting_user: User,
    delete_removed: bool = False,
    preserve_existing: bool = False,
    content_json_override=None,
    content_is_filtered=False,
) -> dict[str, Any]:
    """Upsert selected epic resources and their data-model entities."""
    section = (
        ProposalSection.objects.filter(
            proposal=bp,
            section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
            is_enabled=True,
        )
        .values('content_json')
        .first()
    )
    if content_json_override is not None:
        section = {'content_json': content_json_override}
    if not section:
        return {'ok': False, 'error': 'no_technical_section', 'detail': 'No hay sección técnica habilitada en la propuesta.'}

    doc = (section['content_json'] or {}) if content_is_filtered else filtered_technical_doc_for_sync(bp, section['content_json'] or {})
    epics = doc.get('epics') or []
    if not isinstance(epics, list):
        epics = []

    stats = {
        'ok': True,
        'epics_processed': 0,
        'deliverables_created': 0,
        'deliverables_updated': 0,
        'deliverables_deleted': 0,
        'entities_created': 0,
        'entities_updated': 0,
        'entities_deleted': 0,
    }

    with transaction.atomic():
        _ensure_phase(project, bp)
        seen_epic_keys: set[str] = set()
        synced_deliverables: list[Deliverable] = []

        for idx, epic in enumerate(epics):
            if not isinstance(epic, dict):
                continue
            key = (epic.get('epicKey') or '').strip()
            title = (epic.get('title') or '').strip() or key or f'Módulo {idx + 1}'
            description = epic.get('description') or ''
            reqs = epic.get('requirements') or []
            if not isinstance(reqs, list):
                reqs = []

            if not key:
                if not reqs:
                    continue
                key = f'_sync_epic_{idx}'

            seen_epic_keys.add(key)

            preserved = Deliverable.objects.filter(project=project, source_epic_key=key).order_by('pk').first() if preserve_existing else None
            if preserved is not None:
                d, created = preserved, False
            else:
                d, created = Deliverable.objects.get_or_create(
                    project=project,
                    source_epic_key=key,
                    defaults={
                        'category': Deliverable.CATEGORY_DOCUMENTS,
                        'title': title[:300],
                        'description': (description or '')[:2000],
                        'file': None,
                        'uploaded_by': acting_user,
                        'source_epic_title': title[:300],
                    },
                )
            if created or not preserve_existing:
                synced_deliverables.append(d)
            if created:
                stats['deliverables_created'] += 1
            elif not preserve_existing:
                updated = False
                if d.title != title[:300]:
                    d.title = title[:300]
                    updated = True
                if d.source_epic_title != title[:300]:
                    d.source_epic_title = title[:300]
                    updated = True
                if d.description != (description or '')[:2000]:
                    d.description = (description or '')[:2000]
                    updated = True
                if updated:
                    d.save()
                    stats['deliverables_updated'] += 1

            stats['epics_processed'] += 1

        if delete_removed and seen_epic_keys:
            to_del_d = Deliverable.objects.filter(
                project=project,
                source_epic_key__isnull=False,
                is_archived=False,
            ).exclude(source_epic_key__in=seen_epic_keys)
            for d_del in to_del_d:
                archive_record(d_del)
                stats['deliverables_deleted'] += 1

        # --- Sync data model entities ---
        entities_list = _parse_data_model_entities(doc)
        seen_entity_names: set[str] = set()

        # Prefetch all existing entities in one query → in-memory lookup
        existing_entity_map: dict[tuple[int, str], DataModelEntity] = {
            (e.deliverable_id, e.source_entity_name): e
            for e in DataModelEntity.objects.filter(
                deliverable__in=synced_deliverables,
            )
            if e.source_entity_name
        }

        to_create: list[DataModelEntity] = []
        to_update: list[DataModelEntity] = []

        for ent in entities_list:
            if not isinstance(ent, dict):
                continue
            ent_name = (ent.get('name') or '').strip()
            if not ent_name:
                continue
            seen_entity_names.add(ent_name)
            ent_desc = (ent.get('description') or '')[:5000]
            ent_kf = (ent.get('keyFields') or '')[:5000]

            for d in synced_deliverables:
                existing = existing_entity_map.get((d.id, ent_name))
                if existing and preserve_existing:
                    continue
                if existing:
                    updated = False
                    if existing.name != ent_name[:300]:
                        existing.name = ent_name[:300]
                        updated = True
                    if existing.description != ent_desc:
                        existing.description = ent_desc
                        updated = True
                    if existing.key_fields != ent_kf:
                        existing.key_fields = ent_kf
                        updated = True
                    if updated:
                        existing.synced_from_proposal = True
                        to_update.append(existing)
                        stats['entities_updated'] += 1
                else:
                    to_create.append(DataModelEntity(
                        deliverable=d,
                        name=ent_name[:300],
                        description=ent_desc,
                        key_fields=ent_kf,
                        source_entity_name=ent_name[:300],
                        synced_from_proposal=True,
                    ))
                    stats['entities_created'] += 1

        if to_create:
            DataModelEntity.objects.bulk_create(to_create)
        if to_update:
            DataModelEntity.objects.bulk_update(
                to_update, ['name', 'description', 'key_fields', 'synced_from_proposal'],
            )

        if delete_removed and seen_entity_names:
            to_del_e = DataModelEntity.objects.filter(
                deliverable__project=project,
                source_entity_name__isnull=False,
                is_archived=False,
            ).exclude(source_entity_name='').exclude(
                source_entity_name__in=seen_entity_names,
            )
            for e_del in to_del_e:
                archive_record(e_del)
                stats['entities_deleted'] += 1

    return stats


def sync_technical_resources_for_project(
    project, acting_user: User, delete_removed: bool = False,
) -> dict[str, Any]:
    """
    Upsert resources (per epic) from the linked proposal's
    technical_document section (first BusinessProposal on a project deliverable).
    """
    bp = project.linked_business_proposal()
    if not bp:
        return {'ok': False, 'error': 'no_linked_proposal', 'detail': 'El proyecto no tiene propuesta en un entregable.'}

    return _sync_technical_resources_core(project, bp, acting_user, delete_removed=delete_removed)


def sync_technical_resources_for_deliverable(
    deliverable, acting_user: User, delete_removed: bool = False,
) -> dict[str, Any]:
    """
    Same as project sync but anchored to the deliverable that owns the BusinessProposal.
    """
    bp = getattr(deliverable, 'business_proposal', None)
    if not bp:
        return {
            'ok': False,
            'error': 'no_business_proposal',
            'detail': 'Este entregable no tiene propuesta comercial vinculada.',
        }
    project = deliverable.project
    return _sync_technical_resources_core(project, bp, acting_user, delete_removed=delete_removed)
