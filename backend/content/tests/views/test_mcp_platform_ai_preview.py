"""A template rendering preview has no persistence or provider side effects."""
from unittest.mock import Mock

import pytest

from accounts.models_ai import PlatformAITemplate
from content.models import McpConnector, McpCredential
from content.tests.mcp_parity import assert_no_writes, call_tool_inprocess


pytestmark = pytest.mark.django_db


def test_mcp_template_preview_renders_without_saving(superuser, monkeypatch):
    """Fails if previewing unsaved wording persists a template or invokes paid AI."""
    template, _ = PlatformAITemplate.objects.update_or_create(
        family='chatbot', scenario='project_status', language='es',
        defaults={'content': '{scope_label}\n{facts_text}', 'version': 1},
    )
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    credential = McpCredential.objects.create(connector=connector, actor=superuser, label='AI preview witness')
    provider = Mock(side_effect=AssertionError('A local template preview must not call a provider.'))
    monkeypatch.setattr('requests.post', provider)

    result = assert_no_writes(call_tool_inprocess, 'projects', 'preview_platform_ai_template', {
        'template_id': template.pk,
        'content': 'Estado: {scope_label}\n{facts_text}',
        'expected_version': template.version,
    }, credential=credential)

    template.refresh_from_db()
    assert result == {'preview': 'Estado: scope label\nfacts text', 'provider_called': False}
    assert template.content == '{scope_label}\n{facts_text}'
    assert template.version == 1
    provider.assert_not_called()
