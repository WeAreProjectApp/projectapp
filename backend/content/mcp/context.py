from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class McpExecutionContext:
    connector: Any
    credential: Any
    request_id: str
    actor: Any = None
    request: Any = None
    protocol_version: str = ''
    confirmation_bypass: bool = False


_current_context = ContextVar('mcp_execution_context', default=None)


def current_mcp_context():
    return _current_context.get()


@contextmanager
def use_mcp_context(context, *, atomic_history=True):
    token = _current_context.set(context)
    try:
        if atomic_history:
            from content.services.entity_history import history_operation
            with history_operation(actor=context.actor, source=f'mcp:{context.connector.slug}'):
                yield context
        else:
            # Durable deliveries own their claim and cannot share a transaction
            # with external I/O. Their receipt and email evidence remain audited.
            yield context
    finally:
        _current_context.reset(token)


@contextmanager
def bypass_confirmation():
    context = current_mcp_context()
    if context is None:
        yield None
        return
    token = _current_context.set(replace(context, confirmation_bypass=True))
    try:
        yield _current_context.get()
    finally:
        _current_context.reset(token)
