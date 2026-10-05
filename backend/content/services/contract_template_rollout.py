"""The operator's approved first use: document 237 plus three-year terms."""
import hashlib
import re

from content.services.contract_template_validation import ContractTemplateError, apply_patches, heading_span
from content.services.contract_template_consistency import SERVICE_PAYMENT_SENTENCE


def _replace_once(text, before, after):
    if text.count(after) == 1:
        return text
    if text.count(before) != 1:
        raise ContractTemplateError('El ajuste no encuentra un único texto vigente.', code='PATCH_TARGET_ERROR', details={'text': before})
    return text.replace(before, after, 1)


def approved_adjustments(texts, source_markdown):
    """Read the actual document, refusing changed/missing instructions."""
    if not isinstance(source_markdown, str):
        raise ContractTemplateError('El documento de ajustes no contiene Markdown.')
    start = source_markdown.find('### Parágrafo Quinto — Duración y Renovación del Servicio')
    end = source_markdown.find('\n---', start)
    additions = source_markdown[start:end].strip() if start >= 0 and end > start else ''
    if '### Parágrafo Sexto — Terminación del Servicio' not in additions:
        raise ContractTemplateError('El documento no incluye los dos parágrafos aprobados.')
    replacements = [
        ('junto con sus anexos, las actas de entrega y los comprobantes de pago',
         'junto con sus anexos, las actas de entrega, las cuentas de cobro o facturas y los comprobantes de pago'),
        ('y para dar por terminado el servicio o el contrato conforme a la CLÁUSULA DÉCIMA SEXTA',
         'y para dar por terminado el servicio conforme al PARÁGRAFO SEXTO de la CLÁUSULA VIGÉSIMA PRIMERA, o el contrato conforme a la CLÁUSULA DÉCIMA SEXTA'),
        ('la suspensión y la terminación previstas en la CLÁUSULA DÉCIMA SEXTA para las obligaciones del desarrollo',
         'la suspensión y la terminación previstas en la CLÁUSULA DÉCIMA SEXTA para las obligaciones del desarrollo, la terminación del servicio prevista en el PARÁGRAFO SEXTO de la CLÁUSULA VIGÉSIMA PRIMERA'),
    ]
    # Every supplied phrase is verified against the source document before use.
    for before, after in replacements[:2]:
        if before not in source_markdown or after not in source_markdown:
            raise ContractTemplateError('Las instrucciones del documento cambiaron; vuelve a revisar el ajuste.')
    if replacements[2][0] not in source_markdown or ', la terminación del servicio prevista en el PARÁGRAFO SEXTO de la CLÁUSULA VIGÉSIMA PRIMERA' not in source_markdown:
        raise ContractTemplateError('Falta el ajuste de concordancia de la cláusula vigésima cuarta.')
    if SERVICE_PAYMENT_SENTENCE not in source_markdown:
        raise ContractTemplateError('Falta el ajuste del protocolo de pago en el documento.')
    combined = texts['combined']
    if '### Parágrafo Quinto — Duración y Renovación del Servicio' not in combined:
        combined = apply_patches(combined, [{'operation': 'insert_before', 'heading': 'CLÁUSULA VIGÉSIMA SEGUNDA — ATENCIÓN DE INCIDENTES, NIVELES DE SERVICIO Y CONTINUIDAD OPERATIVA', 'markdown': additions + '\n\n---\n\n'}])
    if SERVICE_PAYMENT_SENTENCE not in combined:
        start_cure, end_cure = heading_span(combined, 'Parágrafo Primero — Plazo para Subsanar', clause='CLÁUSULA DÉCIMA SÉPTIMA — INCUMPLIMIENTO')
        combined = combined[:end_cure].rstrip() + ' ' + SERVICE_PAYMENT_SENTENCE + '\n\n' + combined[end_cure:]
    for before, after in replacements:
        combined = _replace_once(combined, before, after)
    product = _replace_once(texts['product'], *replacements[0])
    for key, value in [('combined', combined), ('product', product)]:
        start_warranty, end_warranty = heading_span(value, 'Parágrafo Sexto — Garantía y Soporte', clause='CLÁUSULA SEGUNDA — EJECUCIÓN DEL CONTRATO')
        block = value[start_warranty:end_warranty]
        block = _replace_once(block, 'garantía por un periodo de un (1) año', 'garantía por un periodo de tres (3) años')
        value = value[:start_warranty] + block + value[end_warranty:]
        start_conf, end_conf = heading_span(value, 'CLÁUSULA DÉCIMA PRIMERA — CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN')
        block = value[start_conf:end_conf].replace('dos (2) años', 'tres (3) años')
        if key == 'combined':
            combined = value[:start_conf] + block + value[end_conf:]
        else:
            product = value[:start_conf] + block + value[end_conf:]
    # Copy the approved full confidentiality clause; product references are external.
    start_conf, end_conf = heading_span(combined, 'CLÁUSULA DÉCIMA PRIMERA — CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN')
    confidentiality = combined[start_conf:end_conf]
    for ordinal in ['SEGUNDA', 'CUARTA', 'NOVENA', 'DÉCIMA']:
        confidentiality = re.sub(rf'\bCLÁUSULA {ordinal}\b(?! [A-ZÁÉÍÓÚ])', f'CLÁUSULA {ordinal} DEL CONTRATO DE DESARROLLO', confidentiality)
    confidentiality = confidentiality.replace('CLÁUSULA DÉCIMA SEGUNDA', 'CLÁUSULA DÉCIMA')
    confidentiality = confidentiality.replace('## CLÁUSULA DÉCIMA PRIMERA', '## CLÁUSULA NOVENA', 1)
    service = texts['service']
    # Running again is a no-op rather than a duplicate clause.
    old_heading = 'CLÁUSULA NOVENA — CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN' if '## CLÁUSULA NOVENA — CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN' in service else 'CLÁUSULA NOVENA — CONFIDENCIALIDAD'
    service = apply_patches(service, [{'operation': 'replace', 'heading': old_heading, 'markdown': confidentiality}])
    return {'combined': combined, 'product': product, 'service': service}


def source_hash(markdown):
    return hashlib.sha256(markdown.encode()).hexdigest()
