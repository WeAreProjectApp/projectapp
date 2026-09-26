"""The proposal scope clause says what the contract's Parágrafo Décimo says."""

import copy
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection

from content.models import ProposalDefaultConfig
from content.services.proposal_service import DEFAULT_SECTIONS, DEFAULT_SECTIONS_EN

pytestmark = pytest.mark.django_db
migration = import_module('content.migrations.0262_align_proposal_scope_clause')
schema_editor = SimpleNamespace(connection=connection)


def _scope(sections):
    return next(
        s['content_json']['scopeParagraphs'] for s in sections
        if s['section_type'] == 'commercial_conditions'
    )


@pytest.mark.parametrize('sections,formalize,no_waiver', [
    (DEFAULT_SECTIONS, 'otrosí al contrato', 'ni implica renuncia'),
    (DEFAULT_SECTIONS_EN, 'amendment to the contract', 'does not waive'),
])
def test_default_clause_requires_formalizing_changes_and_waives_nothing(sections, formalize, no_waiver):
    paragraphs = _scope(sections)

    assert any(formalize in p for p in paragraphs)
    assert any(no_waiver in p for p in paragraphs)


def _config(language, paragraphs):
    sections = copy.deepcopy(DEFAULT_SECTIONS if language == 'es' else DEFAULT_SECTIONS_EN)
    for section in sections:
        if section['section_type'] == 'commercial_conditions':
            section['content_json']['scopeParagraphs'] = list(paragraphs)
    ProposalDefaultConfig.objects.filter(language=language).delete()
    return ProposalDefaultConfig.objects.create(language=language, sections_json=sections)


@pytest.mark.parametrize('language,old,new', [
    ('es', migration.OLD_ES, migration.NEW_ES),
    ('en', migration.OLD_EN, migration.NEW_EN),
])
def test_stored_defaults_with_the_shipped_text_are_aligned_and_reversible(language, old, new):
    config = _config(language, old)

    migration.align_scope_clause(apps, schema_editor)
    config.refresh_from_db()
    assert _scope(config.sections_json) == new

    migration.restore_scope_clause(apps, schema_editor)
    config.refresh_from_db()
    assert _scope(config.sections_json) == old


def test_hand_edited_defaults_are_left_alone():
    config = _config('es', ['Cláusula negociada a mano.'])

    migration.align_scope_clause(apps, schema_editor)

    config.refresh_from_db()
    assert _scope(config.sections_json) == ['Cláusula negociada a mano.']


def test_new_defaults_match_the_code():
    assert migration.NEW_ES == _scope(DEFAULT_SECTIONS)
    assert migration.NEW_EN == _scope(DEFAULT_SECTIONS_EN)
