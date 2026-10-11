"""Structured operation failures preserve the immutable program and owned data."""

from copy import deepcopy

import pytest

from content.models import BuildingOnDemandProgram, BuildingOnDemandProgramRevision
from content.services import building_on_demand_program_service as service
from content.services.building_on_demand_content import BuildingOnDemandError
from content.tests.building_on_demand_fixtures import (
    hero_update, make_tier_item, make_term_item, make_estimator_task_item, make_faq_item, make_card_item,
)

pytestmark = pytest.mark.django_db

OPERATION_NAMES = [
    'update_program', 'restore_version', 'create_tier', 'update_tier', 'remove_tier',
    'create_term', 'update_term', 'remove_term', 'create_estimator_task', 'update_estimator_task',
    'remove_estimator_task', 'create_faq', 'update_faq', 'remove_faq', 'create_card', 'update_card',
    'remove_card', 'reorder_items', 'update_estimator_sizes', 'update_economics',
]
REQUIRED_ARGUMENTS = [
    ('restore_version', 'version_id'), ('create_tier', 'tier'), ('update_tier', 'changes'),
    ('remove_tier', 'tier_id'), ('create_term', 'term'), ('update_term', 'changes'), ('remove_term', 'term_id'),
    ('create_estimator_task', 'task'), ('update_estimator_task', 'changes'), ('remove_estimator_task', 'task_id'),
    ('create_faq', 'item'), ('update_faq', 'changes'), ('remove_faq', 'item_id'),
    ('create_card', 'collection'), ('update_card', 'changes'), ('remove_card', 'collection'),
    ('reorder_items', 'collection'), ('update_estimator_sizes', 'sizes'), ('update_economics', 'economics'),
]
UNKNOWN_IDS = [
    ('update_tier', {'tier_id': 'missing', 'changes': {'monthly_price': 2000000}}),
    ('remove_tier', {'tier_id': 'missing'}),
    ('update_term', {'term_id': 'missing', 'changes': {'months': 12}}),
    ('remove_term', {'term_id': 'missing'}),
    ('update_estimator_task', {'task_id': 'missing', 'changes': {'size': 's'}}),
    ('remove_estimator_task', {'task_id': 'missing'}),
    ('update_faq', {'item_id': 'missing', 'changes': {'es': {'answer': 'Nueva respuesta.'}}}),
    ('remove_faq', {'item_id': 'missing'}),
    ('update_card', {'collection': 'roles', 'item_id': 'missing', 'changes': {'es': {'title': 'Nuevo título'}}}),
    ('remove_card', {'collection': 'roles', 'item_id': 'missing'}),
]
EMPTY_PATCHES = [
    ('update_program', {'sections': {}}), ('update_program', {'settings': {}}),
    ('update_tier', {'tier_id': 'starter', 'changes': {}}),
    ('update_term', {'term_id': 'quarterly', 'changes': {}}),
    ('update_estimator_task', {'task_id': 'small-change', 'changes': {}}),
    ('update_faq', None), ('update_card', None), ('update_economics', {'economics': {}}),
]


def _matching(arguments):
    return {**deepcopy(arguments), 'if_match': service.read_program()['etag'], 'change_note': 'Cambio revisado.'}


def _existing_item_arguments(operation, content):
    if operation == 'update_faq':
        return {'item_id': content['es']['faq']['items'][0]['id'], 'changes': {}}
    return {'collection': 'roles', 'item_id': content['es']['cell']['roles'][0]['id'], 'changes': {}}


def _create_arguments(operation, content, *, duplicate=False):
    if operation == 'create_tier':
        return {'tier': make_tier_item(content, tier_id='starter' if duplicate else 'scale')}
    if operation == 'create_term':
        return {'term': make_term_item(content, term_id='monthly' if duplicate else 'annual')}
    if operation == 'create_estimator_task':
        return {'task': make_estimator_task_item(task_id='requirements-session' if duplicate else 'integration')}
    if operation == 'create_faq':
        item_id = content['es']['faq']['items'][0]['id'] if duplicate else 'support'
        return {'item': make_faq_item(item_id=item_id)}
    item_id = content['es']['cell']['roles'][0]['id'] if duplicate else 'monitoring'
    return {'collection': 'roles', 'item': make_card_item(item_id=item_id)}


def _single_tier_content(content):
    tier = content['offer']['tiers'][0]
    tier['recommended'] = True
    content['offer']['tiers'] = [tier]
    content['internal']['servers'] = {'starter': content['internal']['servers']['starter']}
    for language in ('es', 'en'):
        content[language]['tiers']['items'] = content[language]['tiers']['items'][:1]
    for task in content['offer']['estimator']['tasks']:
        task['min_tier'] = 'starter'
    return content


def _replace_current_content(program, content):
    BuildingOnDemandProgramRevision.objects.filter(pk=program.current_revision_id).update(content=content)


def _invalid_permutation(content, kind):
    ids = [item['id'] for item in content['es']['cell']['roles']]
    return {
        'missing': ids[:-1], 'duplicate': [ids[0], *ids[:-1]],
        'unknown': ['unknown', *ids[1:]], 'not-list': 'roles', 'non-string': [True, *ids[1:]],
    }[kind]


@pytest.mark.parametrize('operation', OPERATION_NAMES)
def test_operation_rejects_unknown_arguments(building_on_demand_program, operation):
    """Fails if undeclared operation inputs bypass the shared closed argument contract."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation(operation, {'unexpected': True})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Hay argumentos desconocidos.'
    assert BuildingOnDemandProgramRevision.objects.count() == 1


@pytest.mark.parametrize('operation,path', REQUIRED_ARGUMENTS)
def test_operation_requires_its_payload(building_on_demand_program, operation, path):
    """Fails if a missing required input reaches an internal dictionary lookup."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation(operation, {})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': path}
    assert BuildingOnDemandProgramRevision.objects.count() == 1


@pytest.mark.parametrize('operation', [None, [], 'remove_estimator_size'])
def test_unknown_operation_is_a_validation_error(building_on_demand_program, operation):
    """Fails if an unknown operation or invented size removal escapes validation."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation(operation, {})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'operation'}


@pytest.mark.parametrize('arguments', [None, []])
def test_operation_requires_an_argument_object(building_on_demand_program, arguments):
    """Fails if non-object operation arguments raise an unstructured internal error."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('update_program', arguments)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Hay argumentos desconocidos.'


def test_update_program_requires_a_text_or_settings_patch(building_on_demand_program):
    """Fails if an empty presentation update is accepted without an editable block."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('update_program', {})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'sections'}


@pytest.mark.parametrize('operation,arguments', EMPTY_PATCHES)
def test_update_rejects_an_empty_patch(building_on_demand_content, operation, arguments):
    """Fails if an empty update patch silently becomes an accepted operation."""
    selected = arguments or _existing_item_arguments(operation, building_on_demand_content)

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation(operation, selected)

    assert error.value.code == 'VALIDATION_ERROR'
    assert BuildingOnDemandProgramRevision.objects.count() == 1


@pytest.mark.parametrize('translations', [None, {'es': {}}, {'en': {}}])
def test_section_update_requires_both_languages(building_on_demand_program, translations):
    """Fails if a section edit can replace only one of its public translations."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('update_program', {'sections': {'hero': translations}})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'sections.hero'}


@pytest.mark.parametrize('operation,arguments', UNKNOWN_IDS)
def test_item_operation_requires_an_existing_id(building_on_demand_program, operation, arguments):
    """Fails if updating or removing an absent item creates data or raises KeyError."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation(operation, arguments)

    assert error.value.code == 'NOT_FOUND'
    assert error.value.details['id'] == 'missing'
    assert BuildingOnDemandProgramRevision.objects.count() == 1


@pytest.mark.parametrize('operation', ['create_tier', 'create_term', 'create_estimator_task', 'create_faq', 'create_card'])
def test_create_rejects_a_duplicate_id(building_on_demand_content, operation):
    """Fails if creation silently adds a second item with the same stable identifier."""
    arguments = _create_arguments(operation, building_on_demand_content, duplicate=True)

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation(operation, arguments)

    assert error.value.code == 'DUPLICATE_ID'
    assert BuildingOnDemandProgramRevision.objects.count() == 1


@pytest.mark.parametrize('operation', ['create_tier', 'create_estimator_task', 'create_faq', 'create_card'])
@pytest.mark.parametrize('position', [-1, True, '0', 100])
def test_create_rejects_an_invalid_position(building_on_demand_content, operation, position):
    """Fails if insertion coerces booleans or accepts positions outside the selected list."""
    arguments = _create_arguments(operation, building_on_demand_content)
    arguments['position'] = position

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation(operation, arguments)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'position'}


@pytest.mark.parametrize('operation,id_key', [
    ('remove_tier', 'tier_id'), ('remove_term', 'term_id'),
    ('remove_estimator_task', 'task_id'), ('remove_faq', 'item_id'),
])
@pytest.mark.parametrize('value', [True, None, 1, 'BAD_ID'])
def test_item_operation_rejects_invalid_identifier_types(building_on_demand_program, operation, id_key, value):
    """Fails if coercion allows a boolean, numeric or malformed stable identifier."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation(operation, {id_key: value})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': id_key}


@pytest.mark.parametrize('operation', ['update_tier', 'update_term', 'update_estimator_task', 'update_faq', 'update_card'])
def test_update_forbids_changing_an_item_id(building_on_demand_content, operation):
    """Fails if a partial edit renames an identifier without preserving references."""
    arguments_by_operation = {
        'update_tier': {'tier_id': 'starter'}, 'update_term': {'term_id': 'quarterly'},
        'update_estimator_task': {'task_id': 'small-change'},
        'update_faq': {'item_id': building_on_demand_content['es']['faq']['items'][0]['id']},
        'update_card': {'collection': 'roles', 'item_id': building_on_demand_content['es']['cell']['roles'][0]['id']},
    }
    arguments = {**arguments_by_operation[operation], 'changes': {'id': 'renamed'}}

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation(operation, arguments)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'changes'}


def test_create_tier_requires_owned_hosting_costs(building_on_demand_content):
    """Fails if tier creation can omit the economics entry required by the panel."""
    tier = make_tier_item(building_on_demand_content)
    tier.pop('hosting')

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('create_tier', {'tier': tier})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'tier'}


def test_invalid_candidate_preserves_the_current_version(building_on_demand_content, django_capture_on_commit_callbacks):
    """Fails if a rejected tier creation clears the previous recommendation or appends history."""
    before = service.read_program()
    tier = make_tier_item(building_on_demand_content, monthly_price=100000, recommended=True)

    with django_capture_on_commit_callbacks() as callbacks:
        with pytest.raises(BuildingOnDemandError) as error:
            service.apply_operation('create_tier', _matching({'tier': tier}), actor=None)

    assert error.value.code == 'VALIDATION_ERROR'
    assert service.read_program()['content'] == before['content']
    assert service.read_program()['version_id'] == before['version_id']
    assert BuildingOnDemandProgramRevision.objects.count() == 1
    assert callbacks == []


def test_remove_tier_reports_real_estimator_references(building_on_demand_program):
    """Fails if tier removal drops another item's minimum tier reference."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('remove_tier', {'tier_id': 'enterprise'})

    assert error.value.code == 'REFERENCED_ITEM'
    assert error.value.details == {'references': ['offer.estimator.tasks[continuous-devops].min_tier']}
    assert service.read_program()['content']['internal']['servers']['enterprise']['plan'] == 'KVM 8'


def test_remove_tier_rejects_the_recommended_plan(building_on_demand_program):
    """Fails if deleting the recommended tier leaves no recommended public option."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('remove_tier', {'tier_id': 'business'})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'No puedes eliminar el plan recomendado; recomienda otro primero.'
    assert error.value.details == {'path': 'tier_id'}


def test_remove_tier_rejects_the_last_plan(building_on_demand_program, building_on_demand_content):
    """Fails if deleting the last tier destroys the program instead of reporting the rule."""
    _replace_current_content(building_on_demand_program, _single_tier_content(building_on_demand_content))

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('remove_tier', {'tier_id': 'starter'})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'No puedes eliminar el último plan.'


def test_remove_term_rejects_the_monthly_baseline(building_on_demand_program):
    """Fails if the mandatory monthly baseline can be removed with its discounts."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('remove_term', {'term_id': 'monthly'})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'No puedes eliminar el plazo mensual.'
    assert error.value.details == {'path': 'term_id'}


@pytest.mark.parametrize('discounts', [
    {'starter': 20, 'business': 25}, {'starter': 20, 'business': 25, 'enterprise': 30, 'missing': 35},
])
def test_create_term_requires_a_discount_for_each_tier(building_on_demand_content, discounts):
    """Fails if term creation omits a current tier or assigns an unknown tier a discount."""
    term = make_term_item(building_on_demand_content, discounts=discounts)

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('create_term', {'term': term})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'term.discounts'}


@pytest.mark.parametrize('term_id,discounts', [('monthly', {'starter': 5}), ('quarterly', {'missing': 5})])
def test_update_term_rejects_invalid_discount_targets(building_on_demand_program, term_id, discounts):
    """Fails if monthly or nonexistent tier discount keys become part of the offer."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('update_term', {'term_id': term_id, 'changes': {'discounts': discounts}})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'changes.discounts'}


@pytest.mark.parametrize('changes', [{'size': 'unknown'}, {'min_tier': 'unknown'}])
def test_estimator_update_rejects_unknown_references(building_on_demand_program, changes):
    """Fails if estimator editing leaves a task pointing to an absent size or tier."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('update_estimator_task', {'task_id': 'small-change', 'changes': changes})

    assert error.value.code == 'VALIDATION_ERROR'
    assert BuildingOnDemandProgramRevision.objects.count() == 1


@pytest.mark.parametrize('changes', [{'size': 'unknown'}, {'min_tier': 'unknown'}])
def test_estimator_creation_rejects_unknown_references(building_on_demand_program, changes):
    """Fails if estimator creation publishes a task with a nonexistent prerequisite."""
    task = make_estimator_task_item(**changes)

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('create_estimator_task', {'task': task})

    assert error.value.code == 'VALIDATION_ERROR'
    assert BuildingOnDemandProgramRevision.objects.count() == 1


@pytest.mark.parametrize('operation', ['create_card', 'update_card', 'remove_card'])
def test_card_operation_rejects_unknown_collections(building_on_demand_program, operation):
    """Fails if a card operation treats a non-card collection as an editable card list."""
    arguments = {'collection': 'tiers', 'item': make_card_item(), 'item_id': 'starter', 'changes': {'es': {'title': 'Texto'}}}
    allowed = {
        'create_card': {'collection', 'item'}, 'update_card': {'collection', 'item_id', 'changes'},
        'remove_card': {'collection', 'item_id'},
    }
    selected = dict(filter(lambda pair: pair[0] in allowed[operation], arguments.items()))

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation(operation, selected)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'collection'}


@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'unknown', 'not-list', 'non-string'])
def test_reorder_requires_an_exact_permutation(building_on_demand_content, kind):
    """Fails if reordering duplicates, drops or invents items in a public collection."""
    ids = _invalid_permutation(building_on_demand_content, kind)

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('reorder_items', {'collection': 'roles', 'ids': ids})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'ids'}


@pytest.mark.parametrize('collection', ['tiers', 'terms'])
def test_reorder_preserves_numeric_ordering_rules(building_on_demand_content, collection):
    """Fails if a permutation can bypass ascending tier prices or term duration rules."""
    ids = list(reversed(list(map(lambda item: item['id'], building_on_demand_content['offer'][collection]))))

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('reorder_items', {'collection': collection, 'ids': ids})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details['path'].startswith(f'offer.{collection}')


def test_reorder_rejects_an_unknown_collection(building_on_demand_program):
    """Fails if an invented reorder collection reaches a private mapping lookup."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('reorder_items', {'collection': 'sizes', 'ids': ['xs', 's', 'm', 'l']})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'collection'}


def test_estimator_size_update_requires_the_fixed_list(building_on_demand_content):
    """Fails if size editing removes a fixed size used by existing estimator tasks."""
    sizes = building_on_demand_content['offer']['estimator']['sizes'][:-1]

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('update_estimator_sizes', {'sizes': sizes})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'sizes'}


def test_economics_update_rejects_an_unknown_tier(building_on_demand_program):
    """Fails if private hosting costs can be assigned to a tier absent from the offer."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('update_economics', {'economics': {'servers': {'missing': {'renewal_monthly': 10000}}}})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'economics.servers'}


@pytest.mark.parametrize('changes,path', [
    ({'server': {'unknown': 1}}, 'changes.server'), ({'es': {'unknown': 'Texto'}}, 'changes.es'),
    ({'hosting': {}}, 'changes.hosting'), ({'discounts': {}}, 'changes.discounts'),
])
def test_tier_patch_rejects_invalid_nested_fields(building_on_demand_program, changes, path):
    """Fails if nested patches escape closed schemas or discard siblings through emptiness."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('update_tier', {'tier_id': 'starter', 'changes': changes})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': path}


@pytest.mark.parametrize('version_id', [None, True, 0, '1'])
def test_restore_requires_a_positive_version_id(building_on_demand_program, version_id):
    """Fails if a restore coerces a boolean or invalid value into a revision identity."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('restore_version', {'version_id': version_id})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'version_id'}


def test_restore_requires_an_existing_revision(building_on_demand_program):
    """Fails if restoring a missing revision yields an unstructured database error."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('restore_version', {'version_id': building_on_demand_program.current_revision_id + 10000})

    assert error.value.code == 'NOT_FOUND'
    assert error.value.message == 'La versión no existe.'


@pytest.mark.parametrize('require_match', [False, True])
def test_preview_rejects_a_stale_etag(building_on_demand_program, require_match):
    """Fails if a stale resource identity is accepted even by a non-mandatory preview."""
    before = service.read_program()
    arguments = {**hero_update(before), 'if_match': 'stale'}

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('update_program', arguments, require_match=require_match)

    assert error.value.code == 'STALE_VERSION'
    assert error.value.details == {'current_etag': before['etag']}


def test_required_preview_needs_a_precondition(building_on_demand_program):
    """Fails if a confirmation-ready preview can omit its expected resource version."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('update_program', {'settings': {'days_per_week': 5}, 'change_note': 'Revisado.'}, require_match=True)

    assert error.value.code == 'PRECONDITION_REQUIRED'
    assert error.value.message == 'if_match es obligatorio.'


def test_apply_needs_a_precondition(building_on_demand_program):
    """Fails if the writer publishes an unversioned modification."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.apply_operation('update_program', {'settings': {'days_per_week': 5}, 'change_note': 'Revisado.'}, actor=None)

    assert error.value.code == 'PRECONDITION_REQUIRED'
    assert BuildingOnDemandProgramRevision.objects.count() == 1


@pytest.mark.parametrize('note', [None, '   ', 'x' * 4001])
def test_apply_requires_a_valid_audit_note(building_on_demand_program, note):
    """Fails if publication accepts a missing, empty or oversized change explanation."""
    arguments = {**_matching({'settings': {'days_per_week': 5}}), 'change_note': note}

    with pytest.raises(BuildingOnDemandError) as error:
        service.apply_operation('update_program', arguments, actor=None)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'change_note debe explicar el cambio (entre 1 y 4000 caracteres).'
    assert BuildingOnDemandProgramRevision.objects.count() == 1


@pytest.mark.parametrize('arguments', [
    {'offset': -1}, {'offset': '0'}, {'offset': False}, {'limit': 0},
    {'limit': 51}, {'limit': '1'}, {'limit': True}, {'include_content': 1},
])
def test_history_rejects_invalid_pagination(building_on_demand_program, arguments):
    """Fails if pagination coercion accepts invalid limits, offsets or content flags."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.list_versions(**arguments)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Usa offset >= 0, limit entre 1 y 50 e include_content booleano.'


@pytest.mark.parametrize('language', [None, ['es'], 'fr'])
def test_public_read_rejects_an_unsupported_language(building_on_demand_program, language):
    """Fails if unsupported locales silently select a translation or raise TypeError."""
    with pytest.raises(BuildingOnDemandError) as error:
        service.serialize_public_program(language)

    assert error.value.code == 'INVALID_LANGUAGE'
    assert error.value.message == 'Usa es o en.'


def test_program_read_requires_the_seeded_singleton(building_on_demand_program):
    """Fails if a missing presentation reports an internal DoesNotExist error."""
    BuildingOnDemandProgram.objects.filter(pk=building_on_demand_program.pk).delete()

    with pytest.raises(BuildingOnDemandError) as error:
        service.read_program()

    assert error.value.code == 'NOT_FOUND'
    assert error.value.message == 'La presentación no está configurada.'


def test_operation_revalidates_the_current_content(building_on_demand_program):
    """Fails if corrupted stored offer data raises KeyError before structured validation."""
    content = deepcopy(building_on_demand_program.current_revision.content)
    content['offer'].pop('tiers')
    _replace_current_content(building_on_demand_program, content)

    with pytest.raises(BuildingOnDemandError) as error:
        service.prepare_operation('remove_tier', {'tier_id': 'starter'})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'offer'}
