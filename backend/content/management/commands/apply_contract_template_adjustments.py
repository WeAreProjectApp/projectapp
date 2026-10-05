"""Apply the reviewed document through the actual MCP confirmation machinery."""
import json
import uuid
from django.core.management.base import BaseCommand, CommandError

from content.models import Document, McpCredential
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.confirmation import confirm_action, preview_sensitive_action
from content.mcp.contract_template_tools import CONTRACT_TEMPLATE_TOOLS
from content.mcp.protocol import ToolError
from content.services.contract_template_rollout import approved_adjustments, source_hash
from content.services.contract_template_service import default_template, list_mirrors, prepare_update, template_etag
from content.services.contract_template_validation import ContractTemplateError, TEXT_FIELDS


class Command(BaseCommand):
    help = 'Previsualiza el documento 237 y plazos aprobados; --apply confirma por MCP.'

    def add_arguments(self, parser):
        parser.add_argument('--source-document-id', type=int, default=237)
        parser.add_argument('--credential-id', type=int)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            source = Document.objects.get(pk=options['source_document_id'], is_archived=False)
            template = default_template()
            texts = {key: getattr(template, field) for key, field in TEXT_FIELDS.items()}
            candidates = approved_adjustments(texts, source.content_markdown)
            entries = [{'variant': key, 'markdown': value, 'if_match': template_etag(template, key)} for key, value in candidates.items()]
            arguments = {**entries[0], 'related_updates': entries[1:],
                'change_note': f'Ajustes del documento {source.pk} (SHA256 {source_hash(source.content_markdown)}). Confidencialidad y no circunvención: tres años en las tres variantes. Garantía del producto: tres años. Confidencialidad del servicio ampliada por instrucción del operador.'}
            preview = prepare_update(arguments, require_match=True)
            if not options['apply']:
                self.stdout.write(json.dumps(preview, ensure_ascii=False))
                return
            if not options['credential_id']:
                raise CommandError('--credential-id es obligatorio al confirmar.')
            credential = McpCredential.objects.select_related('connector', 'actor').get(pk=options['credential_id'], connector__slug='proposals')
            if not credential.is_usable or not credential.allows('update_proposal_contract_template') or not credential.connector.is_active:
                raise CommandError('La credencial no permite editar las plantillas de propuestas.')
            context = McpExecutionContext(connector=credential.connector, credential=credential,
                request_id=str(uuid.uuid4()), actor=credential.actor)
            tool = next(row for row in CONTRACT_TEMPLATE_TOOLS if row['name'] == 'update_proposal_contract_template')
            with use_mcp_context(context):
                intent = preview_sensitive_action(tool, arguments)
                result = confirm_action({'confirmation_id': intent['confirmation_id']}, CONTRACT_TEMPLATE_TOOLS)
            self.stdout.write(json.dumps({'confirmation': result, **list_mirrors()}, ensure_ascii=False))
        except (ContractTemplateError, ToolError, Document.DoesNotExist, McpCredential.DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
