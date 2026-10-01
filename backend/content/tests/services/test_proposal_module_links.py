"""Tests for content.services.proposal_module_links — 100% coverage target."""

from content.services.proposal_module_links import (
    build_item_id,
    build_item_requirements_map,
    build_proposal_module_link_catalog,
    ensure_functional_requirements_item_ids,
    normalize_linked_module_ids,
    normalize_technical_document_module_links,
)


def _fr(content_json):
    return {'section_type': 'functional_requirements', 'content_json': content_json}


def _inv(modules):
    return {'section_type': 'investment', 'content_json': {'modules': modules}}


# ---------------------------------------------------------------------------
# build_proposal_module_link_catalog
# ---------------------------------------------------------------------------

class TestBuildProposalModuleLinkCatalog:
    def test_returns_empty_when_sections_is_none(self):
        result = build_proposal_module_link_catalog(None)
        assert result == {'options': [], 'alias_map': {}, 'always_included_ids': []}

    def test_returns_empty_when_sections_is_not_list(self):
        result = build_proposal_module_link_catalog('not_a_list')
        assert result == {'options': [], 'alias_map': {}, 'always_included_ids': []}

    def test_returns_empty_when_sections_is_dict(self):
        result = build_proposal_module_link_catalog({'section_type': 'functional_requirements'})
        assert result == {'options': [], 'alias_map': {}, 'always_included_ids': []}

    def test_fr_groups_empty_when_no_fr_section_but_inv_modules_still_added(self):
        result = build_proposal_module_link_catalog([_inv([{'id': 'm1', 'title': 'M'}])])
        # No FR section → no group options; but investment modules are still processed
        assert any(opt['id'] == 'm1' for opt in result['options'])

    def test_skips_groups_when_fr_content_json_is_not_dict(self):
        result = build_proposal_module_link_catalog([_fr('not_a_dict')])
        assert result['options'] == []

    def test_skips_group_with_no_id(self):
        result = build_proposal_module_link_catalog([_fr({'groups': [{'title': 'No ID'}]})])
        assert result['options'] == []

    def test_skips_group_with_empty_id(self):
        result = build_proposal_module_link_catalog([_fr({'groups': [{'id': '', 'title': 'Empty'}]})])
        assert result['options'] == []

    def test_skips_invisible_group(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{'id': 'g1', 'title': 'Hidden', 'is_visible': False}]})]
        )
        assert result['options'] == []

    def test_skips_group_with_no_title_and_no_items(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{'id': 'g1', 'title': '', 'items': []}]})]
        )
        assert result['options'] == []

    def test_includes_group_with_title_and_no_items(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{'id': 'g1', 'title': 'Real Title', 'items': []}]})]
        )
        assert len(result['options']) == 1

    def test_includes_group_with_items_and_no_title(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{'id': 'g1', 'title': '', 'items': ['item1']}]})]
        )
        assert len(result['options']) == 1

    def test_price_percent_conversion_failure_defaults_to_zero(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{'id': 'g1', 'title': 'G', 'price_percent': 'bad_value'}]})]
        )
        assert len(result['options']) == 1
        assert 'group-g1' in result['always_included_ids']

    def test_non_calculator_group_with_zero_price_is_always_included(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{'id': 'g1', 'title': 'G', 'price_percent': 0}]})]
        )
        assert 'group-g1' in result['always_included_ids']

    def test_non_calculator_group_can_be_explicitly_optional(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{
                'id': 'g1',
                'title': 'G',
                'is_always_included': False,
            }]})]
        )
        assert 'group-g1' not in result['always_included_ids']

    def test_calculator_module_defaults_to_optional(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{
                'id': 'g1',
                'title': 'Calc',
                'is_calculator_module': True,
            }]})]
        )
        assert 'module-g1' not in result['always_included_ids']

    def test_calculator_module_with_invite_flag_is_not_always_included(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{'id': 'g1', 'title': 'Calc', 'price_percent': 0, 'is_calculator_module': True, 'is_invite': True}]})]
        )
        assert 'module-g1' not in result['always_included_ids']

    def test_calculator_module_id_has_module_prefix(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{'id': 'g1', 'title': 'Calc', 'is_calculator_module': True, 'price_percent': 10}]})]
        )
        assert result['options'][0]['id'] == 'module-g1'

    def test_non_calculator_group_id_has_group_prefix(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{'id': 'g1', 'title': 'Group', 'price_percent': 10}]})]
        )
        assert result['options'][0]['id'] == 'group-g1'

    def test_alias_map_contains_canonical_and_raw_id(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{'id': 'g1', 'title': 'Group'}]})]
        )
        assert result['alias_map']['group-g1'] == 'group-g1'
        assert result['alias_map']['g1'] == 'group-g1'

    def test_label_includes_icon_and_title(self):
        result = build_proposal_module_link_catalog(
            [_fr({'groups': [{'id': 'g1', 'title': 'My Module', 'icon': '🚀'}]})]
        )
        assert '🚀' in result['options'][0]['label']
        assert 'My Module' in result['options'][0]['label']

    def test_additional_modules_from_fr_content_json(self):
        result = build_proposal_module_link_catalog(
            [_fr({'additionalModules': [{'id': 'am1', 'title': 'Extra'}]})]
        )
        assert any(opt['id'] == 'group-am1' for opt in result['options'])

    def test_investment_modules_added_to_options(self):
        result = build_proposal_module_link_catalog([
            _fr({}),
            _inv([{'id': 'm1', 'title': 'Module 1', 'is_required': True}]),
        ])
        assert any(opt['id'] == 'm1' for opt in result['options'])
        assert 'm1' in result['always_included_ids']

    def test_investment_module_not_required_not_always_included(self):
        result = build_proposal_module_link_catalog([
            _fr({}),
            _inv([{'id': 'm1', 'title': 'Optional', 'is_required': False}]),
        ])
        assert 'm1' not in result['always_included_ids']

    def test_investment_module_skipped_if_not_dict(self):
        result = build_proposal_module_link_catalog([
            _fr({}),
            _inv(['not_a_dict', None]),
        ])
        assert result['options'] == []

    def test_investment_module_skipped_if_no_id(self):
        result = build_proposal_module_link_catalog([
            _fr({}),
            _inv([{'title': 'No ID module'}]),
        ])
        assert result['options'] == []

    def test_inv_section_missing_returns_empty_inv_options(self):
        result = build_proposal_module_link_catalog([_fr({'groups': []})])
        assert result['options'] == []

    def test_always_included_ids_are_unique(self):
        sections = [_fr({'groups': [{'id': 'g1', 'title': 'G', 'price_percent': 0}]})]
        result = build_proposal_module_link_catalog(sections)
        assert len(result['always_included_ids']) == len(set(result['always_included_ids']))


# ---------------------------------------------------------------------------
# normalize_linked_module_ids
# ---------------------------------------------------------------------------

class TestNormalizeLinkedModuleIds:
    def test_list_input_returns_unique_strings(self):
        assert normalize_linked_module_ids(['a', 'b', 'a']) == ['a', 'b']

    def test_string_input_returns_single_element_list(self):
        assert normalize_linked_module_ids('abc') == ['abc']

    def test_non_list_non_string_integer_returns_empty_list(self):
        assert normalize_linked_module_ids(123) == []

    def test_none_input_returns_empty_list(self):
        assert normalize_linked_module_ids(None) == []

    def test_dict_input_returns_empty_list(self):
        assert normalize_linked_module_ids({'key': 'value'}) == []

    def test_empty_string_values_are_filtered_out(self):
        assert normalize_linked_module_ids(['a', '', '  ']) == ['a']

    def test_alias_map_resolves_known_alias(self):
        alias_map = {'g1': 'group-g1', 'group-g1': 'group-g1'}
        result = normalize_linked_module_ids(['g1', 'group-g1'], alias_map=alias_map)
        assert result == ['group-g1']

    def test_unknown_alias_passes_through(self):
        result = normalize_linked_module_ids(['unknown-id'], alias_map={'known': 'group-known'})
        assert result == ['unknown-id']

    def test_none_alias_map_defaults_to_empty(self):
        result = normalize_linked_module_ids(['a', 'b'], alias_map=None)
        assert result == ['a', 'b']

    def test_string_input_stripped_of_whitespace(self):
        result = normalize_linked_module_ids('  abc  ')
        assert result == ['abc']


# ---------------------------------------------------------------------------
# normalize_technical_document_module_links
# ---------------------------------------------------------------------------

class TestNormalizeTechnicalDocumentModuleLinks:
    def test_returns_empty_dict_when_content_json_is_none(self):
        assert normalize_technical_document_module_links(None, []) == {}

    def test_returns_empty_dict_when_content_json_is_string(self):
        assert normalize_technical_document_module_links('not_a_dict', []) == {}

    def test_returns_empty_dict_when_content_json_is_list(self):
        assert normalize_technical_document_module_links([], []) == {}

    def test_returns_content_unchanged_when_no_epics_key(self):
        content = {'title': 'Test', 'no_epics': True}
        result = normalize_technical_document_module_links(content, [])
        assert result['title'] == 'Test'
        assert 'epics' not in result

    def test_returns_content_unchanged_when_epics_is_not_list(self):
        content = {'epics': 'not_a_list'}
        result = normalize_technical_document_module_links(content, [])
        assert result['epics'] == 'not_a_list'

    def test_skips_non_dict_epics(self):
        content = {'epics': ['not_a_dict', None, 42]}
        result = normalize_technical_document_module_links(content, [])
        assert result['epics'] == []

    def test_normalizes_linked_module_ids_in_epic(self):
        content = {'epics': [{'id': 'e1', 'linked_module_ids': ['a', 'b']}]}
        result = normalize_technical_document_module_links(content, [])
        assert result['epics'][0]['linked_module_ids'] == ['a', 'b']

    def test_falls_back_to_linkedModuleIds_when_linked_module_ids_absent(self):
        content = {'epics': [{'id': 'e1', 'linkedModuleIds': ['mod1']}]}
        result = normalize_technical_document_module_links(content, [])
        assert result['epics'][0]['linked_module_ids'] == ['mod1']
        assert 'linkedModuleIds' not in result['epics'][0]

    def test_removes_linkedModuleIds_camelCase_from_output(self):
        content = {'epics': [{'id': 'e1', 'linked_module_ids': ['x'], 'linkedModuleIds': ['x']}]}
        result = normalize_technical_document_module_links(content, [])
        assert 'linkedModuleIds' not in result['epics'][0]

    def test_normalizes_requirements_within_epic(self):
        content = {
            'epics': [{
                'id': 'e1',
                'linked_module_ids': [],
                'requirements': [{'id': 'r1', 'linkedModuleIds': ['m1']}],
            }]
        }
        result = normalize_technical_document_module_links(content, [])
        req = result['epics'][0]['requirements'][0]
        assert req['linked_module_ids'] == ['m1']
        assert 'linkedModuleIds' not in req

    def test_skips_non_dict_requirements(self):
        content = {
            'epics': [{
                'id': 'e1',
                'linked_module_ids': [],
                'requirements': ['not_a_dict', None],
            }]
        }
        result = normalize_technical_document_module_links(content, [])
        assert result['epics'][0]['requirements'] == []

    def test_applies_alias_map_from_sections(self):
        sections = [_fr({'groups': [{'id': 'g1', 'title': 'Group', 'price_percent': 0}]})]
        content = {'epics': [{'id': 'e1', 'linked_module_ids': ['g1']}]}
        result = normalize_technical_document_module_links(content, sections)
        assert result['epics'][0]['linked_module_ids'] == ['group-g1']

    def test_does_not_mutate_original_content(self):
        content = {'epics': [{'id': 'e1', 'linked_module_ids': ['a']}]}
        original = {'epics': [{'id': 'e1', 'linked_module_ids': ['a']}]}
        normalize_technical_document_module_links(content, [])
        assert content == original

    def test_epic_without_requirements_key_is_handled(self):
        content = {'epics': [{'id': 'e1', 'linked_module_ids': ['a']}]}
        result = normalize_technical_document_module_links(content, [])
        assert result['epics'][0]['linked_module_ids'] == ['a']
        assert 'requirements' not in result['epics'][0]


# ---------------------------------------------------------------------------
# ensure_functional_requirements_item_ids
# ---------------------------------------------------------------------------

class TestEnsureFunctionalRequirementsItemIds:
    def test_returns_empty_dict_for_non_dict(self):
        assert ensure_functional_requirements_item_ids(None) == {}
        assert ensure_functional_requirements_item_ids('nope') == {}

    def test_assigns_id_from_group_and_name(self):
        content = {'groups': [{'id': 'views', 'items': [{'name': 'Registro de usuario'}]}]}
        result = ensure_functional_requirements_item_ids(content)
        assert result['groups'][0]['items'][0]['id'] == 'item-views-registro-de-usuario'

    def test_preserves_existing_id_verbatim(self):
        content = {'groups': [{'id': 'views', 'items': [{'name': 'Home', 'id': 'custom_id'}]}]}
        result = ensure_functional_requirements_item_ids(content)
        assert result['groups'][0]['items'][0]['id'] == 'custom_id'

    def test_dedupes_generated_ids_with_numeric_suffix(self):
        content = {'groups': [{'id': 'views', 'items': [{'name': 'Home'}, {'name': 'Home'}, {'name': 'Home'}]}]}
        result = ensure_functional_requirements_item_ids(content)
        ids = [i['id'] for i in result['groups'][0]['items']]
        assert ids == ['item-views-home', 'item-views-home-2', 'item-views-home-3']

    def test_generated_id_avoids_collision_with_existing_id(self):
        content = {'groups': [{'id': 'views', 'items': [
            {'name': 'Home', 'id': 'item-views-home'},
            {'name': 'Home'},
        ]}]}
        result = ensure_functional_requirements_item_ids(content)
        assert result['groups'][0]['items'][1]['id'] == 'item-views-home-2'

    def test_covers_additional_modules(self):
        content = {'additionalModules': [{'id': 'billing_module', 'items': [{'name': 'Factura DIAN'}]}]}
        result = ensure_functional_requirements_item_ids(content)
        assert result['additionalModules'][0]['items'][0]['id'] == 'item-billing_module-factura-dian'

    def test_skips_item_without_name(self):
        content = {'groups': [{'id': 'views', 'items': [{'name': '', 'description': 'x'}]}]}
        result = ensure_functional_requirements_item_ids(content)
        assert 'id' not in result['groups'][0]['items'][0]

    def test_tolerates_non_dict_groups_and_items(self):
        content = {'groups': ['nope', {'id': 'views', 'items': [None, 'str', {'name': 'Home'}]}]}
        result = ensure_functional_requirements_item_ids(content)
        assert result['groups'][1]['items'][2]['id'] == 'item-views-home'

    def test_does_not_mutate_original(self):
        content = {'groups': [{'id': 'views', 'items': [{'name': 'Home'}]}]}
        ensure_functional_requirements_item_ids(content)
        assert 'id' not in content['groups'][0]['items'][0]

    def test_group_without_id_uses_group_fallback(self):
        content = {'groups': [{'items': [{'name': 'Home'}]}]}
        result = ensure_functional_requirements_item_ids(content)
        assert result['groups'][0]['items'][0]['id'] == 'item-group-home'


class TestBuildItemId:
    def test_builds_slug(self):
        assert build_item_id('views', 'Registro de Usuario') == 'item-views-registro-de-usuario'

    def test_empty_name_returns_empty(self):
        assert build_item_id('views', '  ') == ''


# ---------------------------------------------------------------------------
# linked_item_ids normalization in normalize_technical_document_module_links
# ---------------------------------------------------------------------------

class TestNormalizeLinkedItemIds:
    def test_camelcase_key_is_canonicalized(self):
        content = {'epics': [{'requirements': [{'title': 'R', 'linkedItemIds': ['item-views-home']}]}]}
        result = normalize_technical_document_module_links(content, [])
        req = result['epics'][0]['requirements'][0]
        assert req['linked_item_ids'] == ['item-views-home']
        assert 'linkedItemIds' not in req

    def test_dedupes_and_strips(self):
        content = {'epics': [{'requirements': [
            {'title': 'R', 'linked_item_ids': [' item-views-home ', 'item-views-home', '', None]},
        ]}]}
        result = normalize_technical_document_module_links(content, [])
        assert result['epics'][0]['requirements'][0]['linked_item_ids'] == ['item-views-home']

    def test_unknown_ids_are_preserved(self):
        content = {'epics': [{'requirements': [{'title': 'R', 'linked_item_ids': ['item-dead-ref']}]}]}
        result = normalize_technical_document_module_links(content, [])
        assert result['epics'][0]['requirements'][0]['linked_item_ids'] == ['item-dead-ref']

    def test_missing_key_defaults_to_empty_list(self):
        content = {'epics': [{'requirements': [{'title': 'R'}]}]}
        result = normalize_technical_document_module_links(content, [])
        assert result['epics'][0]['requirements'][0]['linked_item_ids'] == []


# ---------------------------------------------------------------------------
# build_item_requirements_map
# ---------------------------------------------------------------------------

class TestBuildItemRequirementsMap:
    def test_returns_empty_for_non_dict(self):
        assert build_item_requirements_map(None) == {}
        assert build_item_requirements_map({'epics': 'nope'}) == {}

    def test_maps_items_to_requirements(self):
        content = {'epics': [{
            'epicKey': 'views',
            'requirements': [
                {'flowKey': 'r1', 'title': 'Registro', 'description': 'Alta de usuario',
                 'priority': 'high', 'linked_item_ids': ['item-views-registro', 'item-views-home']},
                {'flowKey': 'r2', 'title': 'Login', 'linked_item_ids': ['item-views-registro']},
            ],
        }]}
        result = build_item_requirements_map(content)
        assert [r['title'] for r in result['item-views-registro']] == ['Registro', 'Login']
        assert result['item-views-home'][0] == {
            'title': 'Registro',
            'description': 'Alta de usuario',
            'priority': 'high',
            'epicKey': 'views',
            'flowKey': 'r1',
        }

    def test_accepts_camelcase_linked_item_ids(self):
        content = {'epics': [{'requirements': [{'title': 'R', 'linkedItemIds': ['item-x']}]}]}
        assert 'item-x' in build_item_requirements_map(content)

    def test_requirements_without_links_are_ignored(self):
        content = {'epics': [{'requirements': [{'title': 'R'}]}]}
        assert build_item_requirements_map(content) == {}

    def test_tolerates_non_dict_epics_and_requirements(self):
        content = {'epics': ['nope', {'requirements': [None, {'title': 'R', 'linked_item_ids': ['i']}]}]}
        result = build_item_requirements_map(content)
        assert 'i' in result
