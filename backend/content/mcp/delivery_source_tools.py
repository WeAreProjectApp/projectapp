"""Download confirmed contractual sources in their retained original format."""
from accounts.services.delivery_contract_sources import contract_source_file

from content.mcp.context import current_mcp_context
from content.mcp.delivery_tools import CONTRACT_KIND, ID, _call, _tool
from content.mcp.platform_resource_tools import _credential
from content.mcp.upload_tools import store_artifact


def _download(arguments, actor):
    credential = _credential()
    body, filename, mime = _call(contract_source_file, arguments['project_id'], actor,
                                arguments['kind'], arguments['node_id'])
    context = current_mcp_context()
    return store_artifact(connector=context.connector, credential=credential, filename=filename,
                          content_type=mime, content=body, request=context.request)


DELIVERY_SOURCE_TOOLS = [
    _tool('download_delivery_contract_source',
          'Descarga la copia contractual autorizada del paquete confirmado en su formato original; si consta firma, conserva el PDF firmado exacto.',
          _download, {'kind': CONTRACT_KIND, 'node_id': ID}, ('kind', 'node_id')),
]
