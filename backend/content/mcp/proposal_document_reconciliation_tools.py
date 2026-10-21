"""Documents exposes the same reviewed reconciliation service as the Panel."""
from content.mcp.operation_builder import _op


def _review(arguments):
    return RECONCILIATION_TOOLS[0]['handler']({'proposal_id': arguments['proposal_id']})


RECONCILIATION_TOOLS = [
    _op('preview_proposal_document_reconciliation',
        'Consulta vínculos faltantes, bloqueos y anexos que requieren otra revisión; no crea documentos ni regenera archivos.',
        'proposal-document-reconciliation', path=('proposal_id',),
        query_schema={'type': 'object', 'properties': {}, 'additionalProperties': False}, envelope_aliases=False),
    _op('reconcile_proposal_documents',
        'Recupera únicamente vínculos faltantes de archivos ya aprobados usando expected_hash de la vista previa; conserva sus bytes e identidades y exige confirmar la acción.',
        'proposal-document-reconciliation', 'POST', ('proposal_id',), 'sensitive', True,
        payload_schema={'type': 'object', 'properties': {'expected_hash': {'type': 'string', 'minLength': 64, 'maxLength': 64}},
                        'required': ['expected_hash'], 'additionalProperties': False}, envelope_aliases=False),
]
RECONCILIATION_TOOLS[1]['impact_builder'] = _review
RECONCILIATION_TOOLS[1]['etag_resolver'] = lambda arguments: _review(arguments)['expected_hash']
