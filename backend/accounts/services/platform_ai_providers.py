"""Small bounded provider adapters. No retries, provider switching or raw error logging."""
import json
import time
from decimal import Decimal

import requests
from django.utils import timezone

from accounts.models_ai import PlatformAICredential, PlatformAIUsage
from accounts.services.platform_ai import AIUnavailable, credential, provider_for_model, require_admin, credential_status


def _response(response):
    if response.status_code >= 400:
        raise AIUnavailable()
    try:
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise AIUnavailable() from None


def _usage(row, data, started):
    usage = data.get('usage') or {}
    row.input_tokens = max(0, int(usage.get('input_tokens', 0)))
    row.output_tokens = max(0, int(usage.get('output_tokens', 0)))
    if row.provider == 'anthropic':
        row.cache_read_tokens = max(0, int(usage.get('cache_read_input_tokens', 0)))
        row.cache_write_tokens = max(0, int(usage.get('cache_creation_input_tokens', 0)))
        cost = row.input_tokens * .10 + row.output_tokens * .50 + row.cache_read_tokens * .01 + row.cache_write_tokens * .125
    else:
        row.cache_read_tokens = min(row.input_tokens, max(0, int((usage.get('input_tokens_details') or {}).get('cached_tokens', 0))))
        cost = (row.input_tokens - row.cache_read_tokens) * .10 + row.cache_read_tokens * .01 + row.output_tokens * .50
    row.estimated_cost = Decimal(str(cost / 1000000))
    if row.operation == 'transcription':
        row.estimated_cost = Decimal(str(row.audio_seconds / 60 * .0045))
    row.latency_ms = max(0, int((time.monotonic() - started) * 1000))
    row.status = 'succeeded'
    row.save()


def generate_text(*, actor, project, purpose, model, instructions, text, schema=None, max_tokens=1000):
    """Return text and usage id; caller owns authorization and result validation."""
    if len(instructions) + len(text) > 24000 or max_tokens > 2000:
        raise AIUnavailable()
    provider = provider_for_model(model)
    key = credential(provider)
    row = PlatformAIUsage.objects.create(actor=actor, project=project, purpose=purpose, operation='generation', provider=provider, model=model)
    started = time.monotonic()
    try:
        if provider == 'anthropic':
            block = {'type': 'text', 'text': instructions}
            # Cache only the stable prefix; do not pad short instructions.
            if len(instructions) >= 2560:
                block['cache_control'] = {'type': 'ephemeral', 'ttl': '5m'}
            config = {'effort': 'low'}
            if schema:
                config['format'] = {'type': 'json_schema', 'schema': schema}
            response = requests.post('https://api.anthropic.com/v1/messages',
                headers={'x-api-key': key, 'anthropic-version': '2023-06-01'},
                json={'model': model, 'max_tokens': max_tokens, 'system': [block], 'output_config': config, 'thinking': {'type': 'disabled'},
                      'messages': [{'role': 'user', 'content': text}]}, timeout=(5, 45))
            data = _response(response)
            result = ''.join(block.get('text', '') for block in data.get('content', []) if block.get('type') == 'text')
            if data.get('stop_reason') == 'max_tokens':
                raise AIUnavailable()
        else:
            body = {'model': model, 'instructions': instructions, 'input': text,
                    'max_output_tokens': max_tokens, 'reasoning': {'effort': 'none'}, 'store': False}
            if schema:
                body['text'] = {'format': {'type': 'json_schema', 'name': 'report', 'strict': True, 'schema': schema}}
            response = requests.post('https://api.openai.com/v1/responses', headers={'Authorization': f'Bearer {key}'}, json=body, timeout=(5, 45))
            data = _response(response)
            result = ''.join(part.get('text', '') for item in data.get('output', []) for part in item.get('content', []) if part.get('type') == 'output_text')
            if data.get('status') != 'completed':
                raise AIUnavailable()
        if not result or len(result) > 20000:
            raise AIUnavailable()
        _usage(row, data, started)
        return result, row.pk
    except (requests.RequestException, AIUnavailable, ValueError, TypeError, KeyError):
        row.status = 'failed'
        row.latency_ms = max(0, int((time.monotonic() - started) * 1000))
        row.save(update_fields=['status', 'latency_ms'])
        raise AIUnavailable() from None


def transcribe(*, actor, project, purpose, audio, seconds, filename):
    key = credential('openai')
    row = PlatformAIUsage.objects.create(actor=actor, project=project, purpose=purpose, operation='transcription', provider='openai', model='gpt-transcribe', audio_seconds=seconds)
    started = time.monotonic()
    try:
        response = requests.post('https://api.openai.com/v1/audio/transcriptions',
            headers={'Authorization': f'Bearer {key}'}, data={'model': 'gpt-transcribe', 'response_format': 'json'},
            files={'file': (filename, audio)}, timeout=(5, 60))
        data = _response(response)
        text = data.get('text', '')
        if not isinstance(text, str) or not text.strip() or len(text) > 6000:
            raise AIUnavailable()
        _usage(row, data, started)
        return text.strip()
    except (requests.RequestException, AIUnavailable, ValueError, TypeError):
        row.status = 'failed'
        row.latency_ms = max(0, int((time.monotonic() - started) * 1000))
        row.save(update_fields=['status', 'latency_ms'])
        raise AIUnavailable() from None


def test_credential(actor, provider):
    require_admin(actor)
    key = credential(provider)
    item = PlatformAICredential.objects.get(provider=provider)
    try:
        if provider == 'anthropic':
            result = requests.get('https://api.anthropic.com/v1/models/claude-haiku-5-5', headers={'x-api-key': key, 'anthropic-version': '2023-06-01'}, timeout=(5, 10))
        elif provider == 'openai':
            result = requests.get('https://api.openai.com/v1/models/gpt-transcribe', headers={'Authorization': f'Bearer {key}'}, timeout=(5, 10))
        else:
            # A tiny explicit test, no client data; Jev exposes its inference endpoint.
            result = requests.post('https://api.typesafe.ai/v1/systemone', headers={'Authorization': f'Bearer {key}'},
                json={'model': 'jev-latest', 'state': 'connection test', 'questions': {'ok': {'type': 'noul', 'instructions': 'This is a connection test.'}}}, timeout=(5, 10))
        status = 'valid' if 200 <= result.status_code < 300 else 'failed'
    except requests.RequestException:
        status = 'failed'
    PlatformAICredential.objects.filter(pk=item.pk, version=item.version).update(last_test_status=status, tested_at=timezone.now())
    return credential_status()[provider]
