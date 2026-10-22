"""Documents exposes the same reviewed reconciliation service as the Panel."""
from content.mcp.operation_builder import _op
from content.mcp.protocol import ToolError


def _review(arguments):
    return RECONCILIATION_TOOLS[0]['handler']({'proposal_id': arguments['proposal_id']})


def _impact(arguments):
    review = _review(arguments)
    if arguments.get('expected_hash') != review['expected_hash']:
        raise ToolError('El cierre cambió. Consulta nuevamente sus vínculos.', code='STALE_VERSION')
    if review['blockers']:
        raise ToolError('Resuelve los bloqueos antes de recuperar los documentos.',
                        details={'documents': review['blockers']})
    return review


RECONCILIATION_TOOLS = [
    _op('preview_proposal_document_reconciliation',
        'Consulta vínculos faltantes, bloqueos y anexos que requieren otra revisión; no crea documentos ni regenera archivos.',
        'proposal-document-reconciliation', path=('proposal_id',),
        query_schema={'type': 'object', 'properties': {}, 'additionalProperties': False}, envelope_aliases=False),
    _op('reconcile_proposal_documents',
        'Recupera únicamente vínculos faltantes de archivos ya aprobados usando expected_hash de la vista previa; conserva sus bytes e identidades y exige confirmar la acción.',
        'proposal-document-reconciliation', 'POST', ('proposal_id',), 'sensitive', True,
        payload_schema={'type': 'object', 'properties': {'expected_hash': {
                            'type': 'string', 'minLength': 64, 'maxLength': 64,
                            'description': 'Huella vigente devuelta por preview_proposal_document_reconciliation; rechaza cambios en archivos, propietario o vínculos.',
                        }},
                        'required': ['expected_hash'], 'additionalProperties': False}, envelope_aliases=False),
]
RECONCILIATION_TOOLS[1]['impact_builder'] = _impact
RECONCILIATION_TOOLS[1]['etag_resolver'] = lambda arguments: _review(arguments)['expected_hash']
