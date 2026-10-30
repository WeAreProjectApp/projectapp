"""Contract picker metadata, ordering and shared substring search."""
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from accounts.models import Project
from accounts.services.billing_contracts import (
    contract_source_options,
    filter_contract_source_options,
    normalize_source_search,
)
from django.core.files.base import ContentFile

from content.models import Document, DocumentFolder, DocumentType, ProposalDocument
from content.tests.views.test_billing_context_contract_link import _proposal_contract

pytestmark = pytest.mark.django_db
SEARCH_CASES = json.loads((
    Path(__file__).resolve().parents[4] / 'frontend/test/fixtures/contract-source-search.json'
).read_text())


@pytest.fixture
def project(make_client_profile):
    profile = make_client_profile()
    return Project.objects.create(name='Proyecto del buscador', client=profile.user)


@pytest.mark.parametrize('case', SEARCH_CASES, ids=[case['title'] for case in SEARCH_CASES])
def test_contract_search_matches_the_shared_unicode_corpus(case):
    assert normalize_source_search(case['title']) == case['normalized']
    assert filter_contract_source_options([{'title': case['title']}], case['query']) == [{'title': case['title']}]


def test_picker_keeps_versions_with_folder_paths_and_contracts_first(project):
    root = DocumentFolder.objects.create(name='Legales', project=project)
    folder = DocumentFolder.objects.create(name='Versiones', parent=root, project=project)
    original = Document.objects.create(title='Contrato_base', project=project, folder=folder)
    revised = Document.objects.create(title='Contrato_base', project=project, folder=root)
    evidence = Document.objects.create(title='Evidencia reciente', project=project)
    Document.objects.filter(pk=original.pk).update(created_at=datetime(2026, 1, 1, tzinfo=UTC))
    Document.objects.filter(pk=revised.pk).update(created_at=datetime(2026, 2, 1, tzinfo=UTC))
    Document.objects.filter(pk=evidence.pk).update(created_at=datetime(2026, 3, 1, tzinfo=UTC))

    options = contract_source_options(project)

    assert [row['id'] for row in options] == [revised.pk, original.pk, evidence.pk]
    assert [row['folder_path'] for row in options] == ['Legales', 'Legales / Versiones', '']
    assert options[1]['created_at'] == '2026-01-01T00:00:00+00:00'
    assert [row['is_contract_like'] for row in options] == [True, True, False]


@pytest.mark.parametrize(('code', 'title'), [
    ('contract_service', 'Acuerdo de prestación'),
    ('amendment', 'Cambio de condiciones'),
    ('markdown', 'OTROSÍ_Actualizado'),
    ('markdown', 'Contrato_base'),
])
def test_contract_group_uses_types_and_legacy_name_words(project, code, title):
    kind, _ = DocumentType.objects.get_or_create(code=code, defaults={'name': code})
    source = Document.objects.create(title=title, project=project, document_type=kind)

    options = contract_source_options(project)

    assert [(row['id'], row['is_contract_like']) for row in options] == [(source.pk, True)]


def test_contract_search_matches_substrings_with_accents_case_and_underscores(project):
    source = Document.objects.create(title='Revisión_CONTRATO_Final', project=project)
    Document.objects.create(title='Corrida de calculadora', project=project)

    options = filter_contract_source_options(contract_source_options(project), 'VISION contrato')

    assert [row['id'] for row in options] == [source.pk]
    assert filter_contract_source_options(options, 'inexistente') == []
    assert filter_contract_source_options(options, '  ') == options


def test_search_preserves_project_and_client_eligibility(super_client, project, make_client_profile):
    other = Project.objects.create(name='Otro del mismo cliente', client=project.client)
    foreign = make_client_profile()
    included = Document.objects.create(title='Contrato vigente', project=project)
    Document.objects.create(title='Contrato otro proyecto', project=other)
    Document.objects.create(title='Contrato archivado', project=project, is_archived=True)
    Document.objects.create(title='Contrato inconsistente', project=project, client_user=foreign.user)

    response = super_client.get(f'/api/admin/billing-context/projects/{project.pk}/options/')

    assert response.status_code == 200
    assert [row['id'] for row in response.data['contract_sources']] == [included.pk]


def test_folder_metadata_queries_are_batched(project, django_assert_num_queries):
    root = DocumentFolder.objects.create(name='Contratos raíz', project=project)
    folder = DocumentFolder.objects.create(name='Firmados', parent=root, project=project)
    Document.objects.create(title='Contrato uno', project=project, folder=folder)
    Document.objects.create(title='Contrato dos', project=project, folder=folder)

    with django_assert_num_queries(4):
        options = contract_source_options(project)

    assert [row['folder_path'] for row in options] == ['Contratos raíz / Firmados'] * 2


def test_five_level_folder_paths_use_queries_per_level(project, django_assert_num_queries):
    root = DocumentFolder.objects.create(name='Legal', project=project)
    level_two = DocumentFolder.objects.create(name='Contratos', project=project, parent=root)
    level_three = DocumentFolder.objects.create(name='2026', project=project, parent=level_two)
    level_four = DocumentFolder.objects.create(name='Firmados', project=project, parent=level_three)
    leaf = DocumentFolder.objects.create(name='Versiones', project=project, parent=level_four)
    sources = Document.objects.bulk_create([
        Document(title=f'Contrato {index}', project=project, folder=leaf) for index in range(8)
    ])

    with django_assert_num_queries(2 + 5):
        options = contract_source_options(project)

    assert {row['id'] for row in options} == {source.pk for source in sources}
    assert [row['folder_path'] for row in options] == ['Legal / Contratos / 2026 / Firmados / Versiones'] * 8


def test_legacy_folder_cycle_terminates_without_repeating_folder_queries(project, django_assert_num_queries):
    root = DocumentFolder.objects.create(name='Raíz circular', project=project)
    leaf = DocumentFolder.objects.create(name='Carpeta hija', parent=root, project=project)
    DocumentFolder.objects.filter(pk=root.pk).update(parent=leaf)
    Document.objects.create(title='Contrato legado', project=project, folder=leaf)

    with django_assert_num_queries(4):
        options = contract_source_options(project)

    assert options[0]['folder_path'] == 'Raíz circular / Carpeta hija'


def test_proposal_source_metadata_does_not_fetch_deferred_fields_per_option(project, superuser, django_assert_num_queries):
    source = _proposal_contract(project, project.client.profile, superuser)
    second = ProposalDocument.objects.create(
        proposal=source.proposal, document_type=ProposalDocument.DOC_TYPE_CONTRACT_SERVICE,
        title='Acuerdo de servicio', file=ContentFile(b'contract', name='service.pdf'),
    )

    with django_assert_num_queries(2):
        options = contract_source_options(project)

    assert [row['id'] for row in options] == [second.pk, source.pk]
    assert [row['proposal_title'] for row in options] == ['Propuesta Litigio'] * 2


def test_contract_search_only_uses_the_current_title_not_document_content(project):
    source = Document.objects.create(title='Acuerdo vigente', project=project, content_markdown='Contrato buscado')

    options = contract_source_options(project)

    assert filter_contract_source_options(options, 'Contrato buscado') == []
    assert [row['id'] for row in filter_contract_source_options(options, 'ACUERDO')] == [source.pk]
