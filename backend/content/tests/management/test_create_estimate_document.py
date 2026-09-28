"""Tests for the `create_estimate_document` management command.

Business rules asserted:
- Creates a markdown Document inside the configured existing folder
- The configured folder is reused independently of its parent
- Content, status and language land on the created Document
- A missing or empty markdown file aborts with CommandError
- Title collisions version (" — vN") by default, or update in place with
  --on-conflict replace
- content_json is parsed from the markdown on both paths, so the PDF download
  works instead of answering 400
- Output always includes the direct panel URL
"""
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from content.models import Document, DocumentFolder
from content.services.document_type_codes import MARKDOWN

pytestmark = pytest.mark.django_db



@pytest.fixture(autouse=True)
def estimate_destination(settings):
    parent = DocumentFolder.objects.create(name='ProjectApp')
    folder = DocumentFolder.objects.create(name='Requirement Estimates', parent=parent)
    settings.REQUIREMENT_ESTIMATES_FOLDER_ID = folder.pk
    return folder

def _write_markdown(tmp_path, body='# Estimate\n\nDemo content.\n'):
    md_file = tmp_path / 'estimate.md'
    md_file.write_text(body, encoding='utf-8')
    return md_file


def _run(md_file, title='Estimate: demo — 01072026', **extra):
    args = ['--title', title, '--file', str(md_file)]
    for flag, value in extra.items():
        args += [f'--{flag}', value]
    call_command('create_estimate_document', *args)


class TestCreateEstimateDocument:
    def test_creates_document_in_default_folder(self, tmp_path):
        _run(_write_markdown(tmp_path))

        document = Document.objects.get(title='Estimate: demo — 01072026')
        assert document.folder.name == 'Requirement Estimates'
        assert document.folder.parent.name == 'ProjectApp'
        assert document.document_type.code == MARKDOWN

    def test_folder_is_created_only_once_across_runs(self, tmp_path):
        md_file = _write_markdown(tmp_path)
        _run(md_file, title='Estimate: uno — 01072026')
        _run(md_file, title='Estimate: dos — 01072026')

        assert DocumentFolder.objects.filter(name='Requirement Estimates').count() == 1
        assert Document.objects.filter(folder__name='Requirement Estimates').count() == 2

    def test_content_status_and_language_are_persisted(self, tmp_path):
        md_file = _write_markdown(tmp_path, body='# Custom body\n')
        _run(md_file, status='draft', language='en')

        document = Document.objects.get()
        assert document.content_markdown == '# Custom body\n'
        assert document.status == Document.Status.DRAFT
        assert document.language == Document.Language.EN

    def test_custom_folder_name_is_used(self, tmp_path):
        DocumentFolder.objects.create(name='Other Estimates')
        _run(_write_markdown(tmp_path), folder='Other Estimates')

        assert Document.objects.get().folder.name == 'Other Estimates'

    def test_missing_file_raises_command_error(self, tmp_path):
        with pytest.raises(CommandError, match='not found'):
            _run(tmp_path / 'does-not-exist.md')
        assert not Document.objects.exists()

    def test_empty_file_raises_command_error(self, tmp_path):
        with pytest.raises(CommandError, match='empty'):
            _run(_write_markdown(tmp_path, body='   \n'))
        assert not Document.objects.exists()

    def test_same_title_creates_versioned_document(self, tmp_path):
        md_file = _write_markdown(tmp_path)
        _run(md_file)
        _run(md_file)

        titles = set(Document.objects.values_list('title', flat=True))
        assert titles == {
            'Estimate: demo — 01072026',
            'Estimate: demo — 01072026 — v2',
        }

    def test_on_conflict_replace_updates_newest_without_creating(self, tmp_path):
        _run(_write_markdown(tmp_path, body='# Original\n'))
        md_file = _write_markdown(tmp_path, body='# Corrected\n')
        call_command(
            'create_estimate_document',
            '--title', 'Estimate: demo — 01072026',
            '--file', str(md_file),
            '--on-conflict', 'replace',
        )

        document = Document.objects.get()
        assert document.content_markdown == '# Corrected\n'

    def test_created_document_carries_parsed_blocks(self, tmp_path):
        """Sin bloques la descarga de PDF responde 400 pese al markdown intacto."""
        _run(_write_markdown(tmp_path, body='# Título\n\nUn párrafo.\n'))

        blocks = Document.objects.get().content_json['blocks']
        assert [b['type'] for b in blocks] == ['heading', 'paragraph']
        assert blocks[0]['text'] == 'Título'

    def test_on_conflict_replace_reparses_blocks(self, tmp_path):
        """El markdown nuevo manda: dejar los bloques viejos saca un PDF obsoleto."""
        _run(_write_markdown(tmp_path, body='# Original\n'))
        md_file = _write_markdown(tmp_path, body='# Corrected\n')
        call_command(
            'create_estimate_document',
            '--title', 'Estimate: demo — 01072026',
            '--file', str(md_file),
            '--on-conflict', 'replace',
        )

        blocks = Document.objects.get().content_json['blocks']
        assert [b['text'] for b in blocks] == ['Corrected']

    def test_output_includes_panel_url(self, tmp_path):
        out = StringIO()
        call_command(
            'create_estimate_document',
            '--title', 'Estimate: demo — 01072026',
            '--file', str(_write_markdown(tmp_path)),
            stdout=out,
        )

        document = Document.objects.get()
        assert f'Panel URL: /panel/documents/{document.pk}/edit' in out.getvalue()


def test_configured_folder_survives_rename(tmp_path, estimate_destination):
    estimate_destination.name = 'Renamed estimates'
    estimate_destination.save()
    _run(_write_markdown(tmp_path))
    assert Document.objects.get().folder_id == estimate_destination.pk
    assert not DocumentFolder.objects.filter(name='Requirement Estimates', parent=None).exists()


def test_missing_configuration_never_creates_folder(tmp_path, settings):
    settings.REQUIREMENT_ESTIMATES_FOLDER_ID = None
    with pytest.raises(CommandError, match='Configura'):
        _run(_write_markdown(tmp_path))
    assert not Document.objects.exists()
    assert not DocumentFolder.objects.filter(name='Requirement Estimates', parent=None).exists()


def test_ambiguous_legacy_name_is_rejected(tmp_path):
    DocumentFolder.objects.create(name='Requirement Estimates')
    with pytest.raises(CommandError, match='única'):
        _run(_write_markdown(tmp_path), folder='Requirement Estimates')
    assert not Document.objects.exists()


def test_archived_destination_is_rejected(tmp_path, estimate_destination):
    estimate_destination.is_archived = True
    estimate_destination.save()
    with pytest.raises(CommandError, match='archivada'):
        _run(_write_markdown(tmp_path))
    assert not Document.objects.exists()


def test_explicit_id_overrides_configuration(tmp_path, estimate_destination):
    target = DocumentFolder.objects.create(name='Explicit')
    _run(_write_markdown(tmp_path), **{'folder-id': str(target.pk)})
    assert Document.objects.get().folder_id == target.pk
