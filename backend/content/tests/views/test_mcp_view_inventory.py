"""Behavior witnesses for the read-only inventory's conservative AST analysis."""

from copy import deepcopy

import pytest
from accounts.models import Project
from rest_framework import serializers

from content.tests import mcp_schema_rules
from content.tests.mcp_view_inventory import collect_view_reads, inventory_tool
from content.views.mcp_blog import TOOLS_BY_SLUG


def test_synthetic_view_collects_literal_request_reads():
    source = """
    def helper(req, field):
        req.query_params.get(field)
        req.data.get('origin')

    def sample(request):
        request.query_params.get('search')
        request.query_params.getlist('tags')
        request.query_params['page']
        request.GET.get('archived')
        request.GET.getlist('languages')
        request.GET['scope']
        request.data.get('name')
        request.data.getlist('items')
        request.data['token']
        'optional' in request.data
        'excluded' not in request.data
        helper(request, 'limit')
    """

    result = collect_view_reads(source, function_name='sample')

    assert result['query_reads'] == ['archived', 'languages', 'limit', 'page', 'scope', 'search', 'tags']
    assert result['data_reads'] == ['excluded', 'items', 'name', 'optional', 'origin', 'token']
    assert result['helpers'] == ['helper']
    assert result['opaque'] == []


@pytest.mark.parametrize(('method', 'query', 'data'), [
    ('GET', ['inline'], []), ('PATCH', [], ['title']), ('DELETE', [], ['delete_keys']),
])
def test_method_selection_stops_at_its_response(method, query, data):
    source = """
    def sample(request):
        if request.method == 'GET':
            return request.GET.get('inline')
        if request.method == 'DELETE':
            return request.data.get('delete_keys')
        return request.data.get('title')
    """

    result = collect_view_reads(source, method=method)

    assert (result['query_reads'], result['data_reads'], result['opaque']) == (query, data, [])


def test_unresolved_reads_leave_explanatory_opaque_entries():
    source = """
    def deeper(req):
        req.data.get('beyond_limit')

    def helper(req):
        deeper(req)
        req.GET.get('helper_query')

    def sample(request):
        request.data.get(dynamic_key)
        helper(request)
        external(request)
        service(request.data)
        for key in request.data:
            pass
    """

    result = collect_view_reads(source, function_name='sample')

    assert result['query_reads'] == ['helper_query']
    assert result['data_reads'] == []
    assert {row['reason'] for row in result['opaque']} == {
        'Dynamic data key: dynamic_key', 'Helper exceeds one-hop limit: deeper',
        'Request passed to unresolved/external helper: external', 'Whole data mapping passed to service',
        'Iteration over the whole data mapping',
    }


class InventorySerializer(serializers.Serializer):
    count = serializers.IntegerField()
    note = serializers.CharField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=['draft', 'published'])
    audit = serializers.CharField(read_only=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=False)


def test_runtime_serializer_metadata_does_not_query_relations():
    source = """
    def sample(request):
        InventorySerializer(data=request.data)
    """

    result = collect_view_reads(source, namespace={'InventorySerializer': InventorySerializer})

    assert result['opaque'] == []
    assert result['data_reads'] == ['count', 'note', 'project', 'status']
    assert result['serializers'] == [{
        'class': f'{__name__}.InventorySerializer', 'channel': 'data', 'fields': {
            'count': {'type': 'IntegerField', 'required': True, 'read_only': False, 'allow_null': False},
            'note': {'type': 'CharField', 'required': False, 'read_only': False, 'allow_null': True},
            'status': {'type': 'ChoiceField', 'required': True, 'read_only': False, 'allow_null': False,
                       'choices': ['draft', 'published']},
            'audit': {'type': 'CharField', 'required': False, 'read_only': True, 'allow_null': False},
            'project': {'type': 'PrimaryKeyRelatedField', 'required': False, 'read_only': False, 'allow_null': False},
        },
    }]


def test_bridge_resolves_the_upload_view_without_executing_it():
    tool = next(tool for tool in TOOLS_BY_SLUG['projects'] if tool['name'] == 'upload_project_brand_asset')

    row = inventory_tool('projects', tool)

    assert (row['method'], row['path'], row['view']) == (
        'POST', '/api/projects/1/brand/', 'content.views.project_brand.project_brand',
    )
    assert row['asset_fields'] == {'asset_id': {'field': 'file'}}
    assert 'file' in row['data_reads']
    assert row['undeclared_data'] == []
    assert row['serializers'][0]['fields']['file']['type'] == 'FileField'
    assert row['opaque'] == []


def test_unresolved_serializer_factory_does_not_hide_its_payload():
    result = collect_view_reads('def sample(request):\n    factory(data=request.data)\n')

    assert result['serializers'] == []
    assert result['opaque'][0]['reason'] == 'Whole data mapping passed to factory'


def test_missing_panel_route_is_reported_as_opaque():
    tool = deepcopy(next(tool for tool in TOOLS_BY_SLUG['projects'] if tool['name'] == 'upload_project_brand_asset'))
    tool['_panel_operation']['route_name'] = 'missing-inventory-route'

    row = inventory_tool('projects', tool)

    assert row['view'] is None
    assert row['opaque'][0]['reason'].startswith('View resolution/source unavailable: NoReverseMatch:')


def test_parity_evidence_rejects_a_removed_apply_call(tmp_path, monkeypatch):
    path = tmp_path / 'test_pair.py'
    source = """
def apply_review():
    return invoke('apply_sample', {})

def test_pair():
    preview = invoke('preview_sample', {})
    apply_review()
    assert preview['ok']
"""
    path.write_text(source)
    key = ('documents', 'preview_sample')
    monkeypatch.setattr(mcp_schema_rules, 'PARITY_PAIRS', {
        key: ('test_pair.py', 'test_pair', ('apply_sample',)),
    })

    complete = mcp_schema_rules.parity_evidence_problems(tmp_path)
    path.write_text(source.replace("invoke('apply_sample', {})", 'None'))
    removed = mcp_schema_rules.parity_evidence_problems(tmp_path)

    assert complete == {}
    assert removed == {key: "Scenario no longer references operations: ['apply_sample']"}
