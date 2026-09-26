"""Make a Document-manager document the read-only window onto the contract.

Migration 0261 links production's legacy copy automatically. This command is
the fallback for any other document or environment:

    manage.py link_contract_document --document-id 104           # dry run
    manage.py link_contract_document --document-id 104 --apply   # write

The document keeps its id, folder, notes and history. Its title changes and
its stored text becomes a pointer: every reader renders the contract live.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from content.models import ContractTemplate, Document
from content.services.contract_mirror_service import (
    MIRROR_TITLE,
    mirror_placeholder_markdown,
)
from content.services.document_content import build_content_json
from content.services.document_type_codes import MARKDOWN


class Command(BaseCommand):
    help = 'Link a document as the read-only window onto the default contract.'

    def add_arguments(self, parser):
        parser.add_argument('--document-id', type=int, required=True)
        parser.add_argument('--apply', action='store_true', help='Write the link (default: dry run).')

    def handle(self, *args, **options):
        template = ContractTemplate.get_default()
        if template is None:
            raise CommandError('There is no default contract template.')
        try:
            document = Document.objects.get(pk=options['document_id'])
        except Document.DoesNotExist as exc:
            raise CommandError(f'Document {options["document_id"]} does not exist.') from exc
        if document.is_archived:
            raise CommandError('The document is archived; restore it first.')
        is_markdown = document.document_type is None or document.document_type.code == MARKDOWN
        if document.is_generated_snapshot or not is_markdown:
            raise CommandError('Only markdown documents can be the contract window.')
        if template.mirror_document_id == document.pk:
            self.stdout.write('Already linked; nothing to do.')
            return

        self.stdout.write(
            f'Document {document.pk} «{document.title}» ({len(document.content_markdown)} chars) '
            f'-> «{MIRROR_TITLE}», content replaced by a live pointer.'
        )
        if template.mirror_document_id:
            self.stdout.write(f'Replaces the current window: document {template.mirror_document_id}.')
        if not options['apply']:
            self.stdout.write(self.style.WARNING('Dry run: nothing written. Re-run with --apply.'))
            return

        with transaction.atomic():
            document.title = MIRROR_TITLE
            document.content_markdown = mirror_placeholder_markdown()
            document.content_json = build_content_json(document, document.content_markdown)
            document.save(update_fields=['title', 'content_markdown', 'content_json', 'updated_at'])
            template.mirror_document = document
            template.save(update_fields=['mirror_document'])
        self.stdout.write(self.style.SUCCESS(f'Document {document.pk} is now the contract window.'))
