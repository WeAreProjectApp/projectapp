import hashlib
import json

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from content.models import (
    AdditionalModule,
    AdditionalModuleCategory,
    AdditionalModuleShareLink,
    AdditionalModuleShareView,
)


class CatalogOrderError(ValueError):
    pass


class CatalogRevisionConflict(RuntimeError):
    pass


class ActiveCategoryModulesConflict(RuntimeError):
    def __init__(self, count):
        self.count = count
        super().__init__(f'Category still contains {count} active modules.')


def catalog_revision():
    """Stable optimistic-lock token for catalog structure and content."""

    categories = list(
        AdditionalModuleCategory.objects.order_by('id').values_list(
            'id', 'order', 'is_active', 'updated_at',
        )
    )
    modules = list(
        AdditionalModule.objects.order_by('id').values_list(
            'id', 'category_id', 'order', 'is_active', 'updated_at',
        )
    )
    payload = json.dumps(
        {
            'categories': [
                [row[0], row[1], row[2], row[3].isoformat()] for row in categories
            ],
            'modules': [
                [row[0], row[1], row[2], row[3], row[4].isoformat()]
                for row in modules
            ],
        },
        separators=(',', ':'),
    )
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]


def next_category_order():
    maximum = AdditionalModuleCategory.objects.aggregate(value=Max('order'))['value']
    return (maximum if maximum is not None else -1) + 1


def next_module_order(category):
    maximum = category.modules.aggregate(value=Max('order'))['value']
    return (maximum if maximum is not None else -1) + 1


def set_category_active(category, is_active):
    if not is_active:
        active_count = category.modules.filter(is_active=True).count()
        if active_count:
            raise ActiveCategoryModulesConflict(active_count)
    category.is_active = is_active
    category.save(update_fields=['is_active', 'updated_at'])
    return category


@transaction.atomic
def reorder_catalog(*, expected_revision, category_ids, module_groups):
    """Apply the complete catalog order and optional module category moves."""

    categories = list(
        AdditionalModuleCategory.objects.select_for_update().order_by('id')
    )
    modules = list(
        AdditionalModule.objects.select_for_update().order_by('id')
    )

    if expected_revision != catalog_revision():
        raise CatalogRevisionConflict('El catálogo cambió; vuelve a cargarlo.')

    current_category_ids = {category.id for category in categories}
    if (
        not isinstance(category_ids, list)
        or len(category_ids) != len(set(category_ids))
        or set(category_ids) != current_category_ids
    ):
        raise CatalogOrderError('La lista de categorías debe incluir el catálogo completo.')

    if not isinstance(module_groups, list):
        raise CatalogOrderError('Los grupos de módulos deben ser una lista.')

    group_category_ids = []
    ordered_module_ids = []
    module_destination = {}
    for group in module_groups:
        if not isinstance(group, dict):
            raise CatalogOrderError('Cada grupo debe indicar category_id y module_ids.')
        category_id = group.get('category_id')
        module_ids = group.get('module_ids')
        if category_id not in current_category_ids or not isinstance(module_ids, list):
            raise CatalogOrderError('Hay un grupo de módulos inválido.')
        group_category_ids.append(category_id)
        for module_id in module_ids:
            ordered_module_ids.append(module_id)
            module_destination[module_id] = category_id

    if len(group_category_ids) != len(set(group_category_ids)):
        raise CatalogOrderError('Cada categoría debe aparecer una sola vez.')
    if set(group_category_ids) != current_category_ids:
        raise CatalogOrderError('Faltan categorías en los grupos de módulos.')

    current_module_ids = {module.id for module in modules}
    if (
        len(ordered_module_ids) != len(set(ordered_module_ids))
        or set(ordered_module_ids) != current_module_ids
    ):
        raise CatalogOrderError('La lista de módulos debe incluir el catálogo completo.')

    categories_by_id = {category.id: category for category in categories}
    modules_by_id = {module.id: module for module in modules}
    now = timezone.now()

    for category in categories:
        category.order = 1_000_000 + category.id
        category.updated_at = now
    AdditionalModuleCategory.objects.bulk_update(categories, ['order', 'updated_at'])
    for order, category_id in enumerate(category_ids):
        categories_by_id[category_id].order = order
    AdditionalModuleCategory.objects.bulk_update(categories, ['order', 'updated_at'])

    for module in modules:
        module.order = 1_000_000 + module.id
        module.updated_at = now
    AdditionalModule.objects.bulk_update(modules, ['order', 'updated_at'])
    module_orders = {category_id: 0 for category_id in current_category_ids}
    for module_id in ordered_module_ids:
        module = modules_by_id[module_id]
        category_id = module_destination[module_id]
        module.category_id = category_id
        module.order = module_orders[category_id]
        module_orders[category_id] += 1
    AdditionalModule.objects.bulk_update(
        modules,
        ['category', 'order', 'updated_at'],
    )

    return catalog_revision()


def _localized_module(module, language):
    suffix = 'en' if language == 'en' else 'es'
    return {
        'id': module.pk,
        'slug': module.slug,
        'icon': module.icon,
        'name': getattr(module, f'name_{suffix}'),
        'summary': getattr(module, f'summary_{suffix}'),
        'what_is': getattr(module, f'what_is_{suffix}'),
        'purpose': getattr(module, f'purpose_{suffix}'),
        'problems_solved': getattr(module, f'problems_solved_{suffix}'),
        'integrations': getattr(module, f'integrations_{suffix}'),
        'implementation_requirements': getattr(
            module,
            f'implementation_requirements_{suffix}',
        ),
    }


def serialize_public_catalog(*, language, module_ids=None):
    """Return only public catalog content, grouped in the live catalog order."""

    suffix = 'en' if language == 'en' else 'es'
    modules = AdditionalModule.objects.filter(
        is_active=True,
        category__is_active=True,
    ).select_related('category').order_by('category__order', 'order', 'id')
    if module_ids is not None:
        modules = modules.filter(id__in=module_ids)

    grouped = {}
    for module in modules:
        category = module.category
        group = grouped.setdefault(category.id, {
            'slug': category.slug,
            'name': getattr(category, f'name_{suffix}'),
            'modules': [],
        })
        group['modules'].append(_localized_module(module, language))

    categories = list(grouped.values())
    return {
        'language': language,
        'total_modules': sum(len(category['modules']) for category in categories),
        'categories': categories,
    }


@transaction.atomic
def record_share_view(*, share_link, session_id, ip_address, user_agent):
    """Record one unique browser session and update the denormalized metrics."""

    locked_link = AdditionalModuleShareLink.objects.select_for_update().get(
        pk=share_link.pk,
    )
    view_event, created = AdditionalModuleShareView.objects.get_or_create(
        share_link=locked_link,
        session_id=session_id,
        defaults={
            'ip_address': ip_address,
            'user_agent': (user_agent or '')[:500],
        },
    )
    if created:
        viewed_at = view_event.viewed_at
        locked_link.view_count += 1
        locked_link.last_viewed_at = viewed_at
        if locked_link.first_viewed_at is None:
            locked_link.first_viewed_at = viewed_at
        locked_link.save(update_fields=[
            'view_count', 'first_viewed_at', 'last_viewed_at',
        ])
    return view_event, created
