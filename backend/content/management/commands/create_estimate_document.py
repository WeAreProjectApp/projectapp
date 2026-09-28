"""Management command — create a markdown Document inside a panel folder.

Used by the ``requirement-calculator`` skill to persist estimation results
as real documents visible under ``/panel/documents``. The target folder is
resolved by a configured ID, independently of its name and parent.
"""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from content.models import Document, DocumentType
from content.services.document_content import build_content_json
from content.services.document_type_codes import MARKDOWN
from content.services.estimate_folder_service import resolve_estimate_folder

User = get_user_model()

class Command(BaseCommand):
    help = (
        'Create a markdown Document in the configured estimate folder without creating folders.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--title', required=True, help='Document title.')
        parser.add_argument(
            '--file', required=True,
            help='Path to the markdown file with the document content.',
        )
        parser.add_argument(
            '--folder', default=None,
            help='Legacy selector: exact globally unique name; never creates a folder.',
        )
        parser.add_argument('--folder-id', type=int, help='Existing destination folder ID.')
        parser.add_argument(
            '--status', default=Document.Status.PUBLISHED,
            choices=[choice for choice, _ in Document.Status.choices],
            help='Document status (default: published).',
        )
        parser.add_argument(
            '--language', default=Document.Language.ES,
            choices=[choice for choice, _ in Document.Language.choices],
            help='Document language (default: es).',
        )
        parser.add_argument(
            '--on-conflict', default='version', choices=['version', 'replace', 'new'],
            help=(
                'Same title in folder: version = append " — vN"; '
                'replace = update the newest match; new = allow duplicate.'
            ),
        )

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.is_file():
            raise CommandError(f'Markdown file not found: {path}')
        content = path.read_text(encoding='utf-8')
        if not content.strip():
            raise CommandError(f'Markdown file is empty: {path}')

        # `is_archived=False`: nunca archivar estimates nuevos en una carpeta
        # que el usuario sacó de circulación.
        folder = resolve_estimate_folder(folder_id=options['folder_id'], folder_name=options['folder'])
        doc_type, _ = DocumentType.objects.get_or_create(
            code=MARKDOWN, defaults={'name': 'Documento markdown'},
        )
        admin = User.objects.filter(is_staff=True).order_by('pk').first()

        title = options['title']
        existing = Document.objects.filter(folder=folder, title=title)
        if existing.exists():
            if options['on_conflict'] == 'replace':
                document = existing.latest('created_at')
                document.content_markdown = content
                # `content_json` viaja siempre con el markdown: si sólo se pisa
                # el texto, el PDF sigue saliendo con los bloques anteriores.
                document.content_json = build_content_json(document, content)
                document.status = options['status']
                document.is_client_visible = (
                    options['status'] == Document.Status.PUBLISHED
                )
                document.updated_by = admin
                document.save()
                self.stdout.write(self.style.SUCCESS(
                    f'Document #{document.pk} "{document.title}" updated (replaced).'
                ))
                self.stdout.write(f'Panel URL: /panel/documents/{document.pk}/edit')
                return
            if options['on_conflict'] == 'version':
                title = f'{title} — v{existing.count() + 1}'

        document = Document(
            document_type=doc_type,
            folder=folder,
            title=title,
            status=options['status'],
            is_client_visible=(options['status'] == Document.Status.PUBLISHED),
            content_markdown=content,
            language=options['language'],
            created_by=admin,
            updated_by=admin,
        )
        # Sin `content_json` el documento nace sin bloques y la descarga de PDF
        # responde 400 aunque el markdown esté completo.
        document.content_json = build_content_json(document, content)
        document.save()

        self.stdout.write(self.style.SUCCESS(
            f'Document #{document.pk} "{document.title}" created in '
            f'folder "{folder.name}" (id={folder.pk}).'
        ))
        self.stdout.write(f'Panel URL: /panel/documents/{document.pk}/edit')
