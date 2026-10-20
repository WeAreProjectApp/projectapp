"""Shared HTTP helpers for MCP actions that require an explicit confirmation."""

import json


def call_confirmed(api_client, url, rpc, name, arguments):
    """Request a sensitive action and return the response after confirming it.

    The first response remains available to tests that need to verify the
    preview itself; callers of this helper assert the observable result of the
    action only after the confirmation boundary.
    """
    preview = api_client.post(
        url,
        rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )
    result = preview.data['result']
    if result['isError']:
        return preview
    confirmation_id = result['structuredContent']['confirmation_id']
    return api_client.post(
        url,
        rpc('tools/call', {
            'name': 'confirm_action',
            'arguments': {'confirmation_id': confirmation_id},
        }),
        format='json',
    )


def confirmed_payload(response):
    """Decode a successful MCP result, unwrapping the confirmation envelope."""
    payload = json.loads(response.data['result']['content'][0]['text'])
    return payload.get('result', payload) if payload.get('confirmed') else payload
