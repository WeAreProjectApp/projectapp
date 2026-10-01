"""
Canonical commercial-module ids shared by technical_document filtering and admin editing.
"""

from __future__ import annotations

import copy
from typing import Any

from django.utils.text import slugify


def _string_id(value: Any) -> str:
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = _string_id(raw)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _iter_functional_requirement_groups(content_json: Any):
    if not isinstance(content_json, dict):
        return
    for key in ('groups', 'additionalModules'):
        entries = content_json.get(key)
        if not isinstance(entries, list):
            continue
        for group in entries:
            if isinstance(group, dict):
                yield group


def build_item_id(group_id: Any, name: Any) -> str:
    group_slug = _string_id(group_id) or 'group'
    name_slug = slugify(_string_id(name))
    if not name_slug:
        return ''
    return f'item-{group_slug}-{name_slug}'


def ensure_functional_requirements_item_ids(content_json: Any) -> dict[str, Any]:
    """Assign stable ids to functional-requirements items that lack one.

    Existing ids are preserved verbatim (they are opaque strings); generated
    ids follow ``item-<group_id>-<slug(name)>`` and are deduped across the
    whole section with a numeric suffix.
    """
    if not isinstance(content_json, dict):
        return {}

    out = copy.deepcopy(content_json)
    seen: set[str] = set()
    for group in _iter_functional_requirement_groups(out):
        for item in group.get('items') or []:
            if not isinstance(item, dict):
                continue
            existing = _string_id(item.get('id'))
            if existing:
                seen.add(existing)

    for group in _iter_functional_requirement_groups(out):
        for item in group.get('items') or []:
            if not isinstance(item, dict):
                continue
            if _string_id(item.get('id')):
                item['id'] = _string_id(item.get('id'))
                continue
            base = build_item_id(group.get('id'), item.get('name'))
            if not base:
                continue
            candidate = base
            suffix = 2
            while candidate in seen:
                candidate = f'{base}-{suffix}'
                suffix += 1
            item['id'] = candidate
            seen.add(candidate)
    return out


def build_item_requirements_map(technical_content_json: Any) -> dict[str, list[dict[str, Any]]]:
    """Map functional-requirements item ids to the technical requirements linked to them."""
    result: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(technical_content_json, dict):
        return result
    epics = technical_content_json.get('epics')
    if not isinstance(epics, list):
        return result
    for epic in epics:
        if not isinstance(epic, dict):
            continue
        requirements = epic.get('requirements')
        if not isinstance(requirements, list):
            continue
        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue
            linked = requirement.get('linked_item_ids') or requirement.get('linkedItemIds')
            for item_id in normalize_linked_module_ids(linked):
                result.setdefault(item_id, []).append({
                    'title': requirement.get('title') or '',
                    'description': requirement.get('description') or '',
                    'priority': requirement.get('priority') or '',
                    'epicKey': epic.get('epicKey') or '',
                    'flowKey': requirement.get('flowKey') or '',
                })
    return result


def build_item_link_options(sections: list[dict] | None) -> list[dict[str, Any]]:
    """Group the commercial items a technical document is expected to cover.

    Python mirror of ``buildProposalItemLinkOptions`` in
    ``frontend/utils/proposalModuleLinkOptions.js`` — keep both in step.

    ``groups`` are contractual scope, so their items are always required.
    ``additionalModules`` are an optional catalog: they only become coverage
    once the seller selected them (or a legacy proposal defaulted them in),
    otherwise an unsold module would block every save.
    """
    if not isinstance(sections, list):
        return []

    functional = next(
        (
            section for section in sections
            if isinstance(section, dict)
            and section.get('section_type') == 'functional_requirements'
        ),
        None,
    )
    content_json = (functional or {}).get('content_json')
    if not isinstance(content_json, dict):
        return []

    def _entries(key: str) -> list[Any]:
        value = content_json.get(key)
        return value if isinstance(value, list) else []

    candidates: list[tuple[dict[str, Any], bool]] = []
    for group in _entries('groups'):
        if isinstance(group, dict):
            candidates.append((group, True))
    for group in _entries('additionalModules'):
        if not isinstance(group, dict):
            continue
        selected = group.get('selected')
        required = (
            selected is True
            or (selected is None and group.get('default_selected') is True)
        )
        candidates.append((group, required))

    out: list[dict[str, Any]] = []
    for group, required in candidates:
        if group.get('is_visible') is False:
            continue
        group_id = _string_id(group.get('id'))
        if not group_id:
            continue
        items = []
        for item in group.get('items') or []:
            if not isinstance(item, dict):
                continue
            item_id = _string_id(item.get('id'))
            if not item_id:
                continue
            label = f"{item.get('icon') or ''} {item.get('name') or item_id}".strip()
            items.append({'id': item_id, 'label': label})
        if not items:
            continue
        out.append({
            'groupId': group_id,
            'groupLabel': f"{group.get('icon') or ''} {group.get('title') or group_id}".strip(),
            'isRequiredForCoverage': required,
            'items': items,
        })
    return out


def build_technical_item_coverage(
    item_link_options: list[dict[str, Any]] | None,
    technical_content_json: Any,
) -> dict[str, Any]:
    """Report which required commercial items no technical requirement covers.

    Python mirror of ``buildTechnicalItemCoverage`` in
    ``frontend/utils/proposalModuleLinkOptions.js``.
    """
    linked: set[str] = set()
    if isinstance(technical_content_json, dict):
        epics = technical_content_json.get('epics')
        if isinstance(epics, list):
            for epic in epics:
                if not isinstance(epic, dict):
                    continue
                requirements = epic.get('requirements')
                if not isinstance(requirements, list):
                    continue
                for requirement in requirements:
                    if not isinstance(requirement, dict):
                        continue
                    raw = (
                        requirement.get('linked_item_ids')
                        or requirement.get('linkedItemIds')
                    )
                    linked.update(normalize_linked_module_ids(raw))

    missing_required: list[dict[str, Any]] = []
    missing_optional: list[dict[str, Any]] = []
    required_count = 0
    covered_required_count = 0

    for group in item_link_options or []:
        if not isinstance(group, dict):
            continue
        is_required = group.get('isRequiredForCoverage') is True
        group_id = group.get('groupId') or ''
        for item in group.get('items') or []:
            item_id = (item or {}).get('id')
            if not item_id:
                continue
            entry = {
                'id': item_id,
                'label': item.get('label') or item_id,
                'groupId': group_id,
                'groupLabel': group.get('groupLabel') or group_id,
            }
            if is_required:
                required_count += 1
                if item_id in linked:
                    covered_required_count += 1
                else:
                    missing_required.append(entry)
            elif item_id not in linked:
                missing_optional.append(entry)

    return {
        'missingRequired': missing_required,
        'missingOptional': missing_optional,
        'requiredCount': required_count,
        'coveredRequiredCount': covered_required_count,
    }


def build_proposal_module_link_catalog(sections: list[dict] | None) -> dict[str, Any]:
    options: list[dict[str, Any]] = []
    alias_map: dict[str, str] = {}
    always_included_ids: list[str] = []

    if not isinstance(sections, list):
        return {
            'options': options,
            'alias_map': alias_map,
            'always_included_ids': always_included_ids,
        }

    def add_option(option: dict[str, Any]) -> None:
        options.append(option)
        for alias in option.get('aliases', []):
            alias_map[alias] = option['id']
        if option.get('is_always_included'):
            always_included_ids.append(option['id'])

    fr = next(
        (section for section in sections if section.get('section_type') == 'functional_requirements'),
        None,
    )
    inv = next(
        (section for section in sections if section.get('section_type') == 'investment'),
        None,
    )
    content_json = fr.get('content_json') if isinstance(fr, dict) else {}
    groups = []
    if isinstance(content_json, dict):
        groups.extend(content_json.get('groups') or [])
        groups.extend(content_json.get('additionalModules') or [])

    for group in groups:
        if not isinstance(group, dict) or group.get('is_visible') is False:
            continue
        raw_id = _string_id(group.get('id'))
        if not raw_id:
            continue
        if not group.get('title') and not (group.get('items') or []):
            continue
        is_calc = group.get('is_calculator_module') is True
        canonical_id = f'module-{raw_id}' if is_calc else f'group-{raw_id}'
        label = f'{group.get("icon") or ""} {group.get("title") or raw_id}'.strip()
        is_always_included = group.get('is_always_included', not is_calc) is True
        aliases = _unique_strings([canonical_id, raw_id])
        add_option({
            'id': canonical_id,
            'label': label,
            'aliases': aliases,
            'is_always_included': is_always_included,
        })

    inv_content = inv.get('content_json') if isinstance(inv, dict) else {}
    modules = inv_content.get('modules') if isinstance(inv_content, dict) else []
    for module in modules or []:
        if not isinstance(module, dict):
            continue
        module_id = _string_id(module.get('id'))
        if not module_id:
            continue
        label = f'{module.get("icon") or ""} {module.get("title") or module_id}'.strip()
        add_option({
            'id': module_id,
            'label': label,
            'aliases': [module_id],
            'is_always_included': module.get('is_required') is True,
        })

    return {
        'options': options,
        'alias_map': alias_map,
        'always_included_ids': _unique_strings(always_included_ids),
    }


def normalize_linked_module_ids(raw: Any, alias_map: dict[str, str] | None = None) -> list[str]:
    alias_map = alias_map or {}
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = raw
    else:
        values = []
    return _unique_strings([
        alias_map.get(_string_id(value), _string_id(value))
        for value in values
    ])


def normalize_technical_document_module_links(
    content_json: dict[str, Any] | None,
    sections: list[dict] | None,
) -> dict[str, Any]:
    if not isinstance(content_json, dict):
        return {}

    catalog = build_proposal_module_link_catalog(sections)
    alias_map = catalog['alias_map']
    out = copy.deepcopy(content_json)
    epics = out.get('epics')
    if not isinstance(epics, list):
        return out

    normalized_epics: list[dict[str, Any]] = []
    for epic in epics:
        if not isinstance(epic, dict):
            continue
        normalized_epic = copy.deepcopy(epic)
        normalized_epic.pop('linkedModuleIds', None)
        normalized_epic['linked_module_ids'] = normalize_linked_module_ids(
            epic.get('linked_module_ids') or epic.get('linkedModuleIds'),
            alias_map,
        )
        requirements = epic.get('requirements')
        if isinstance(requirements, list):
            normalized_requirements: list[dict[str, Any]] = []
            for requirement in requirements:
                if not isinstance(requirement, dict):
                    continue
                normalized_requirement = copy.deepcopy(requirement)
                normalized_requirement.pop('linkedModuleIds', None)
                normalized_requirement['linked_module_ids'] = normalize_linked_module_ids(
                    requirement.get('linked_module_ids') or requirement.get('linkedModuleIds'),
                    alias_map,
                )
                normalized_requirement.pop('linkedItemIds', None)
                normalized_requirement['linked_item_ids'] = normalize_linked_module_ids(
                    requirement.get('linked_item_ids') or requirement.get('linkedItemIds'),
                )
                normalized_requirements.append(normalized_requirement)
            normalized_epic['requirements'] = normalized_requirements
        normalized_epics.append(normalized_epic)

    out['epics'] = normalized_epics
    return out
