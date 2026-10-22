"""Public serialization, append-only history and commit-bound cell publishing."""

import json
from copy import deepcopy
from urllib.parse import quote

import pytest

from content.models import BuildingOnDemandProgramRevision, McpConnector
from content.services import building_on_demand_program_service as service
from content.services.building_on_demand_content import BuildingOnDemandError
from content.services.financing_program_service import WHATSAPP_NUMBER
from content.tests.building_on_demand_fixtures import hero_update

pytestmark = pytest.mark.django_db

SECTION_ORDER = [
    'seo', 'hero', 'cell', 'fit', 'tiers', 'terms', 'bag', 'estimator', 'hosting', 'faq', 'cta', 'legal',
]
PUBLIC_KEYS = set(SECTION_ORDER) | {
    'language', 'version', 'updated_at', 'canonical_path', 'alternate_path', 'pdf_path', 'offer', 'contact',
}
PUBLIC_TIER_KEYS = {
    'id', 'name', 'badge', 'pace_label', 'pace_summary', 'ideal_for', 'roles', 'highlights', 'cta_label',
    'recommended', 'monthly_price', 'daily_hours', 'bag_hours', 'server', 'prices',
}
PRICE_CASES = [
    (0, 0, {'term': 'monthly', 'months': 1, 'discount_percent': 0, 'monthly_price': 1800000, 'total': 1800000, 'savings': 0}),
    (0, 1, {'term': 'quarterly', 'months': 3, 'discount_percent': 5, 'monthly_price': 1710000, 'total': 5130000, 'savings': 270000}),
    (0, 2, {'term': 'semiannual', 'months': 6, 'discount_percent': 10, 'monthly_price': 1620000, 'total': 9720000, 'savings': 1080000}),
    (0, 3, {'term': 'nine-month', 'months': 9, 'discount_percent': 15, 'monthly_price': 1530000, 'total': 13770000, 'savings': 2430000}),
    (1, 0, {'term': 'monthly', 'months': 1, 'discount_percent': 0, 'monthly_price': 4200000, 'total': 4200000, 'savings': 0}),
    (1, 1, {'term': 'quarterly', 'months': 3, 'discount_percent': 10, 'monthly_price': 3780000, 'total': 11340000, 'savings': 1260000}),
    (1, 2, {'term': 'semiannual', 'months': 6, 'discount_percent': 15, 'monthly_price': 3570000, 'total': 21420000, 'savings': 3780000}),
    (1, 3, {'term': 'nine-month', 'months': 9, 'discount_percent': 20, 'monthly_price': 3360000, 'total': 30240000, 'savings': 7560000}),
    (2, 0, {'term': 'monthly', 'months': 1, 'discount_percent': 0, 'monthly_price': 9600000, 'total': 9600000, 'savings': 0}),
    (2, 1, {'term': 'quarterly', 'months': 3, 'discount_percent': 15, 'monthly_price': 8160000, 'total': 24480000, 'savings': 4320000}),
    (2, 2, {'term': 'semiannual', 'months': 6, 'discount_percent': 20, 'monthly_price': 7680000, 'total': 46080000, 'savings': 11520000}),
    (2, 3, {'term': 'nine-month', 'months': 9, 'discount_percent': 25, 'monthly_price': 7200000, 'total': 64800000, 'savings': 21600000}),
]
PREVIEW_KEYS = {
    'operation', 'changed', 'changes', 'warnings', 'summary', 'change_note', 'if_match', 'resource_etags',
}
VERSION_KEYS = {
    'version_id', 'version', 'author', 'created_at', 'change_note', 'restored_from_version_id', 'restored_from_version',
}


def _matching_arguments(arguments):
    return {**deepcopy(arguments), 'if_match': service.read_program()['etag'], 'change_note': 'Cambio revisado.'}


def _changed_blocks(preview):
    return [change['block'] for change in preview['changes'] if change['changed']]


def _translated_terms(content, language):
    return [dict(text, months=term['months']) for text, term in zip(content[language]['terms']['items'], content['offer']['terms'])]


def _translated_tasks(content, language):
    return [dict(text, size=task['size'], min_tier=task['min_tier'])
            for text, task in zip(content[language]['estimator']['tasks'], content['offer']['estimator']['tasks'])]


@pytest.fixture
def changed_program(building_on_demand_program, admin_user):
    original = service.read_program()
    service.apply_operation('update_program', hero_update(original), actor=admin_user)
    return original


@pytest.mark.parametrize('language,canonical,alternate', [
    ('es', '/es-co/building-on-demand', '/en-us/building-on-demand'),
    ('en', '/en-us/building-on-demand', '/es-co/building-on-demand'),
])
def test_public_payload_matches_the_consumer_contract(building_on_demand_program, language, canonical, alternate):
    """Fails if public consumers receive missing paths or unexpected private resources."""
    payload = service.serialize_public_program(language)

    assert set(payload) == PUBLIC_KEYS
    assert payload['language'] == language
    assert payload['version'] == 1
    assert payload['updated_at'] == building_on_demand_program.updated_at.isoformat()
    assert payload['canonical_path'] == canonical
    assert payload['alternate_path'] == alternate
    assert payload['pdf_path'] == f'/api/building-on-demand/public/pdf/?lang={language}'


@pytest.mark.parametrize('language', ['es', 'en'])
def test_public_offer_contains_only_display_settings(building_on_demand_program, language):
    """Fails if public offer settings expose economics or lose the recommended plan."""
    payload = service.serialize_public_program(language)

    assert payload['offer'] == {
        'currency': 'COP', 'prices_include_vat': False, 'days_per_week': 6, 'weeks_per_month': 4,
        'recommended_tier': 'business',
    }
    assert payload['contact'] == {'whatsapp_base_url': f'https://wa.me/{WHATSAPP_NUMBER}'}


@pytest.mark.parametrize('language', ['es', 'en'])
def test_public_cta_encodes_the_seeded_message(building_on_demand_content, language):
    """Fails if the public WhatsApp link loses its locale message or exposes raw text."""
    text = building_on_demand_content[language]['cta']

    payload = service.serialize_public_program(language)

    assert payload['cta'] == {
        'title': text['title'], 'body': text['body'], 'button_label': text['button_label'],
        'whatsapp_url': f'https://wa.me/{WHATSAPP_NUMBER}?text=' + quote(text['whatsapp_message']),
    }


@pytest.mark.parametrize('language', ['es', 'en'])
def test_public_tier_has_exact_display_fields(building_on_demand_content, language):
    """Fails if tier cards omit capacity or leak their private hosting plan name."""
    payload = service.serialize_public_program(language)
    tier = payload['tiers']['items'][0]

    assert set(tier) == PUBLIC_TIER_KEYS
    assert tier['id'] == 'starter'
    assert tier['name'] == building_on_demand_content[language]['tiers']['items'][0]['name']
    assert tier['server'] == {'vcpu': 1, 'ram_gb': 4, 'disk_gb': 50, 'transfer_tb': 4}
    assert tier['daily_hours'] == 4
    assert tier['bag_hours'] == 96
    assert len(tier['prices']) == 4


@pytest.mark.parametrize('language', ['es', 'en'])
def test_public_terms_join_the_neutral_months(building_on_demand_content, language):
    """Fails if term labels no longer accompany their exact language-neutral durations."""
    payload = service.serialize_public_program(language)

    assert payload['terms'] == {
        **building_on_demand_content[language]['terms'],
        'items': _translated_terms(building_on_demand_content, language),
    }


@pytest.mark.parametrize('language', ['es', 'en'])
def test_public_estimator_joins_fixed_size_references(building_on_demand_content, language):
    """Fails if the estimator receives translated tasks without size or tier references."""
    payload = service.serialize_public_program(language)

    assert payload['estimator'] == {
        **building_on_demand_content[language]['estimator'],
        'sizes': building_on_demand_content['offer']['estimator']['sizes'],
        'tasks': _translated_tasks(building_on_demand_content, language),
    }


@pytest.mark.parametrize('tier_index,term_index,expected', PRICE_CASES)
def test_public_price_matches_the_pinned_commercial_offer(building_on_demand_program, tier_index, term_index, expected):
    """Fails if a published discount, advance total or savings changes by one peso."""
    payload = service.serialize_public_program('es')

    assert payload['tiers']['items'][tier_index]['prices'][term_index] == expected


@pytest.mark.parametrize('private_value', ['55000', 'Hostinger', 'KVM'])
def test_public_json_excludes_private_economics(building_on_demand_program, private_value):
    """Fails if any private cost or hosting provider marker appears in public JSON."""
    serialized = json.dumps(service.serialize_public_program('es'), ensure_ascii=False)

    assert private_value not in serialized
    assert '"internal"' not in serialized
    assert '"contract"' not in serialized


def test_public_serialization_preserves_the_stored_content(building_on_demand_program):
    """Fails if public enrichment removes the stored message or mutates the revision."""
    original = deepcopy(building_on_demand_program.current_revision.content)

    first = service.serialize_public_program('es')
    second = service.serialize_public_program('es')
    building_on_demand_program.current_revision.refresh_from_db()

    assert first == second
    assert building_on_demand_program.current_revision.content == original


def test_public_serialization_revalidates_the_stored_revision(building_on_demand_program):
    """Fails if invalid legacy public content bypasses validation during serialization."""
    content = deepcopy(building_on_demand_program.current_revision.content)
    content['es']['hero']['note'] = 'Valor en USD'
    BuildingOnDemandProgramRevision.objects.filter(pk=building_on_demand_program.current_revision_id).update(content=content)

    with pytest.raises(BuildingOnDemandError) as error:
        service.serialize_public_program('es')

    assert error.value.code == 'PUBLIC_FIGURE_NOT_ALLOWED'
    assert error.value.details == {'path': 'es.hero.note'}


def test_private_read_exposes_derived_capacities(building_on_demand_program):
    """Fails if editors cannot read the content, section order or derived tier figures."""
    snapshot = service.read_program()
    public = service.serialize_public_program('es')

    assert snapshot['sections'] == SECTION_ORDER
    assert snapshot['content'] == building_on_demand_program.current_revision.content
    assert snapshot['derived']['tiers'][0] == {'id': 'starter', 'bag_hours': 96, 'prices': public['tiers']['items'][0]['prices']}
    assert snapshot['author'] == 'Sistema'
    assert snapshot['change_note'] == 'Versión inicial de Building on Demand (PA-177).'
    assert snapshot['etag'] == service.program_etag(building_on_demand_program.current_revision)


def test_preview_contains_reviewable_diffs(building_on_demand_program):
    """Fails if a text preview omits the exact changed blocks or mutates history."""
    before = service.read_program()

    preview = service.prepare_operation('update_program', hero_update(before), require_match=True)

    assert set(preview) == PREVIEW_KEYS
    assert preview['operation'] == 'update_program'
    assert preview['changed'] is True
    assert _changed_blocks(preview) == ['hero.es', 'hero.en']
    assert preview['resource_etags'] == {'program': before['etag']}
    assert 'Tu producto avanza con criterio.' in preview['changes'][2]['diff']
    assert service.read_program()['version_id'] == before['version_id']


def test_publication_appends_an_attributed_revision(building_on_demand_program, admin_user):
    """Fails if publishing replaces history or loses its author and unchanged sections."""
    before = service.read_program()

    result = service.apply_operation('update_program', hero_update(before), actor=admin_user)
    revision = BuildingOnDemandProgramRevision.objects.get(pk=result['version_id'])

    assert result == {'applied': True, 'changed': True, 'version': 2, 'version_id': revision.pk, 'etag': service.program_etag(revision)}
    assert revision.author_id == admin_user.pk
    assert revision.author_label == admin_user.get_username()
    assert revision.content['es']['hero']['title'] == 'Tu producto avanza con criterio.'
    assert revision.content['en']['hosting'] == before['content']['en']['hosting']
    assert BuildingOnDemandProgramRevision.objects.count() == 2
    assert service.read_program()['version_id'] == revision.pk


def test_console_publication_records_credential_provenance(building_on_demand_program):
    """Fails if console publishing discards the credential responsible for the change."""
    connector = McpConnector.objects.get(slug='building-on-demand')
    token = connector.generate_token()
    credential = connector.credential_for_token(token)

    result = service.apply_operation('update_program', hero_update(service.read_program()), actor=None, credential=credential)
    revision = BuildingOnDemandProgramRevision.objects.get(pk=result['version_id'])

    assert revision.author_label == 'Consola'
    assert revision.author_id is None
    assert revision.credential_id == credential.pk


def test_restore_appends_an_auditable_revision(changed_program, admin_user):
    """Fails if restoring edits history instead of retaining the source revision."""
    arguments = _matching_arguments({'version_id': changed_program['version_id']})

    result = service.apply_operation('restore_version', arguments, actor=admin_user)
    revision = BuildingOnDemandProgramRevision.objects.get(pk=result['version_id'])

    assert result['version'] == 3
    assert revision.content == changed_program['content']
    assert revision.restored_from_id == changed_program['version_id']
    assert revision.author_id == admin_user.pk
    assert service.list_versions()['versions'][0]['restored_from_version'] == 1
    assert BuildingOnDemandProgramRevision.objects.count() == 3


def test_restore_revalidates_historical_content(changed_program):
    """Fails if restoration republishes invalid historical figures."""
    content = deepcopy(changed_program['content'])
    content['es']['hero']['note'] = 'Importe USD'
    historical = BuildingOnDemandProgramRevision.objects.create(version=3, content=content, change_note='Contenido legado inválido.')
    before = service.read_program()

    with pytest.raises(BuildingOnDemandError) as error:
        service.apply_operation('restore_version', _matching_arguments({'version_id': historical.pk}), actor=None)

    assert error.value.code == 'PUBLIC_FIGURE_NOT_ALLOWED'
    assert service.read_program()['version_id'] == before['version_id']


def test_history_paginates_newest_first(changed_program):
    """Fails if offset history returns the newest version instead of its predecessor."""
    page = service.list_versions(offset=1, limit=1)

    assert page['total'] == 2
    assert len(page['versions']) == 1
    assert set(page['versions'][0]) == VERSION_KEYS
    assert page['versions'][0]['version_id'] == changed_program['version_id']
    assert page['versions'][0]['version'] == 1
    assert page['versions'][0]['restored_from_version_id'] is None


def test_history_includes_content_only_when_requested(changed_program):
    """Fails if an explicit full historical read omits its immutable content."""
    page = service.list_versions(offset=1, limit=1, include_content=True)

    assert page['versions'][0]['content'] == changed_program['content']
    assert set(page['versions'][0]) == VERSION_KEYS | {'content'}
    assert service.list_versions(offset=20) == {'total': 2, 'versions': []}


def test_resource_etags_track_the_current_revision(building_on_demand_program):
    """Fails if the preview resource identity remains tied to the seed after a write."""
    before = service.resource_etags({'unused': 'argument'})

    result = service.apply_operation('update_program', hero_update(service.read_program()), actor=None)

    assert service.resource_etags() == {'program': result['etag']}
    assert result['etag'] != before['program']
    assert len(result['etag']) == 64


def test_stale_publication_preserves_the_current_revision(building_on_demand_program):
    """Fails if an obsolete etag can overwrite the current program."""
    before = service.read_program()
    arguments = {**hero_update(before), 'if_match': 'stale'}

    with pytest.raises(BuildingOnDemandError) as error:
        service.apply_operation('update_program', arguments, actor=None)

    assert error.value.code == 'STALE_VERSION'
    assert error.value.details == {'current_etag': before['etag']}
    assert service.read_program()['version_id'] == before['version_id']
    assert BuildingOnDemandProgramRevision.objects.count() == 1


def test_concurrent_confirmation_rechecks_preview_etags(building_on_demand_program):
    """Fails if a second preview can overwrite a publication confirmed in between."""
    before = service.read_program()
    second_arguments = _matching_arguments({'economics': {'hour_cost': 60000}})
    second_preview = service.prepare_operation('update_economics', second_arguments, require_match=True)
    winner = service.apply_operation('update_program', hero_update(before), actor=None)
    second_arguments['if_match'] = winner['etag']

    with pytest.raises(BuildingOnDemandError) as error:
        service.apply_operation('update_economics', second_arguments, actor=None, expected_etags=second_preview['resource_etags'])

    assert error.value.code == 'STALE_VERSION'
    assert error.value.details == {'current_etag': winner['etag']}
    assert service.read_program()['content']['internal']['hour_cost'] == 55000
    assert service.read_program()['version_id'] == winner['version_id']
    assert BuildingOnDemandProgramRevision.objects.count() == 2


def test_identical_publication_keeps_the_revision(building_on_demand_program, django_capture_on_commit_callbacks):
    """Fails if a no-op creates redundant history or a frontend rebuild."""
    before = service.read_program()
    arguments = _matching_arguments({'settings': {'days_per_week': 6}})

    with django_capture_on_commit_callbacks() as callbacks:
        result = service.apply_operation('update_program', arguments, actor=None)

    assert result == {'applied': True, 'changed': False, 'version': 1, 'version_id': before['version_id'], 'etag': before['etag']}
    assert BuildingOnDemandProgramRevision.objects.count() == 1
    assert callbacks == []


def test_restoring_the_current_version_keeps_the_revision(building_on_demand_program, django_capture_on_commit_callbacks):
    """Fails if restoring identical content appends history solely for its provenance."""
    before = service.read_program()
    arguments = _matching_arguments({'version_id': before['version_id']})

    with django_capture_on_commit_callbacks() as callbacks:
        result = service.apply_operation('restore_version', arguments, actor=None)

    assert result == {'applied': True, 'changed': False, 'version': 1, 'version_id': before['version_id'], 'etag': before['etag']}
    assert BuildingOnDemandProgramRevision.objects.count() == 1
    assert callbacks == []


def test_publication_strips_the_audit_note(building_on_demand_program):
    """Fails if a published audit explanation retains surrounding whitespace."""
    arguments = {**_matching_arguments({'settings': {'days_per_week': 5}}), 'change_note': '  Capacidad revisada.  '}

    preview = service.prepare_operation('update_program', arguments, require_match=True)
    result = service.apply_operation('update_program', arguments, actor=None, expected_etags=preview['resource_etags'])
    revision = BuildingOnDemandProgramRevision.objects.get(pk=result['version_id'])

    assert preview['change_note'] == 'Capacidad revisada.'
    assert revision.change_note == 'Capacidad revisada.'
    assert revision.version == 2


@pytest.mark.parametrize('operation,arguments', [
    ('update_program', {'settings': {'days_per_week': 5}}),
    ('update_program', {'settings': {'prices_include_vat': True}}),
    ('update_tier', {'tier_id': 'starter', 'changes': {'monthly_price': 1900000}}),
    ('update_estimator_task', {'task_id': 'small-change', 'changes': {'size': 's'}}),
])
def test_public_change_schedules_one_rebuild(building_on_demand_program, operation, arguments, monkeypatch, django_capture_on_commit_callbacks):
    """Fails if publication is invisible to prerendering or triggers repeated rebuilds."""
    calls = []
    monkeypatch.setattr(service, 'schedule_rebuild_after_publish', lambda **kwargs: calls.append(kwargs))

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        result = service.apply_operation(operation, _matching_arguments(arguments), actor=None)

    assert result['changed'] is True
    assert result['version'] == 2
    assert len(callbacks) == 1
    assert calls == [{'reason': 'building-on-demand'}]


@pytest.mark.parametrize('operation,arguments', [
    ('update_economics', {'economics': {'hour_cost': 60000}}),
    ('update_economics', {'economics': {'servers': {'starter': {'renewal_monthly': 40000}}}}),
    ('update_tier', {'tier_id': 'starter', 'changes': {'hosting': {'renewal_monthly': 40000}}}),
])
def test_private_change_keeps_publication_unchanged(building_on_demand_program, operation, arguments, django_capture_on_commit_callbacks):
    """Fails if private economics changes rebuild or alter public presentation fields."""
    before = service.read_program()

    with django_capture_on_commit_callbacks() as callbacks:
        result = service.apply_operation(operation, _matching_arguments(arguments), actor=None)
    after = service.read_program()

    assert result['version'] == 2
    assert after['content']['es'] == before['content']['es']
    assert after['content']['en'] == before['content']['en']
    assert after['content']['offer'] == before['content']['offer']
    assert after['content']['internal'] != before['content']['internal']
    assert callbacks == []


@pytest.mark.parametrize('operation,arguments,expected_callbacks', [
    ('update_economics', {'economics': {'hour_cost': 60000}}, 0),
    ('update_program', {'settings': {'days_per_week': 5}}, 1),
])
def test_restore_rebuilds_only_public_changes(building_on_demand_program, operation, arguments, expected_callbacks, django_capture_on_commit_callbacks):
    """Fails if restoration rebuild decisions depend on provenance instead of content."""
    original = service.read_program()
    service.apply_operation(operation, _matching_arguments(arguments), actor=None)

    with django_capture_on_commit_callbacks() as callbacks:
        result = service.apply_operation('restore_version', _matching_arguments({'version_id': original['version_id']}), actor=None)

    assert result['version'] == 3
    assert service.read_program()['content'] == original['content']
    assert len(callbacks) == expected_callbacks


def test_admin_overview_exposes_the_uninitialized_contract(building_on_demand_program, building_on_demand_contract):
    """Fails if the read-only panel cannot show an inactive connector before contract setup."""
    overview = service.admin_overview()

    assert set(overview) == {'program', 'contract', 'connector', 'public_paths', 'pdf_paths'}
    contract = building_on_demand_contract
    assert overview['contract'] == {
        'version': 1, 'version_id': contract.current_revision_id,
        'updated_at': contract.updated_at.isoformat(), 'author': 'Sistema',
        'change_note': contract.current_revision.change_note,
        'mirror': {
            'status': 'not_initialized', 'document_id': None,
            'title': 'Contrato de alquiler de célula — Building on Demand',
            'folder_id': None, 'folder_path': None, 'version': None, 'last_synced_at': None,
        },
    }
    assert overview['connector'] == {'slug': 'programs', 'is_active': False}
    assert overview['program']['version'] == 1
    assert overview['public_paths'] == {'es': '/es-co/building-on-demand', 'en': '/en-us/building-on-demand'}
    assert overview['pdf_paths'] == {'es': '/api/building-on-demand/public/pdf/?lang=es', 'en': '/api/building-on-demand/public/pdf/?lang=en'}


def test_admin_overview_reads_the_connector_activation(building_on_demand_program):
    """Fails if the panel hardcodes an inactive connector after activation."""
    McpConnector.objects.filter(slug='programs').update(is_active=True)

    overview = service.admin_overview()

    assert overview['connector'] == {'slug': 'programs', 'is_active': True}
