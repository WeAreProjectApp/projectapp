"""Conservative clause projections; numbers and duties are never discarded."""
import re
import unicodedata
from functools import lru_cache

from content.services.contract_template_validation import ContractTemplateError, TEXT_FIELDS
from content.services.contract_variants import PRODUCT_ADJUSTMENTS

SERVICE_PAYMENT_SENTENCE = 'Tratándose de las obligaciones de pago del servicio de hosting, mantenimiento y soporte, se aplicará el protocolo previsto en la CLÁUSULA VIGÉSIMA CUARTA.'
ORDINAL = r'(?:(?:DÉCIMA|VIGÉSIMA) (?:PRIMER[OA]|SEGUND[OA]|TERCER[OA]|CUART[OA]|QUINT[OA]|SEXT[OA]|SÉPTIM[OA]|OCTAV[OA]|NOVEN[OA])|PRIMER[OA]|SEGUND[OA]|TERCER[OA]|CUART[OA]|QUINT[OA]|SEXT[OA]|SÉPTIM[OA]|OCTAV[OA]|NOVEN[OA]|DÉCIM[OA]|VIGÉSIM[OA])'
REFERENCE = re.compile(rf'PARÁGRAFO {ORDINAL}(?: de la (?:presente cláusula|CLÁUSULA {ORDINAL}))?|CLÁUSULAS? {ORDINAL}(?: a {ORDINAL})?', re.I)


@lru_cache(maxsize=128)
def _scope_pattern(before):
    parts, cursor = [], 0
    for reference in REFERENCE.finditer(before):
        parts.extend([re.escape(before[cursor:reference.start()]), '(?:' + REFERENCE.pattern + ')'])
        cursor = reference.end()
    parts.append(re.escape(before[cursor:]))
    return re.compile(''.join(parts), re.I)


def scope_replace(body, before, after):
    """Reviewed scope adapters also ignore numbering inside their references."""
    return _scope_pattern(before).sub(lambda _match: after, body)


def sections(markdown, level=2):
    headings = list(re.finditer(rf'^{"#" * level} (.+)$', markdown, re.M))
    result = {}
    for index, match in enumerate(headings):
        title = re.sub(rf'^(?:CLÁUSULA {ORDINAL}|Parágrafo [A-Za-zÁÉÍÓÚáéíóú]+)\s*[—–-]\s*', '', match.group(1))
        if title in result:
            raise ContractTemplateError('Hay encabezados contractuales ambiguos.', details={'heading': title})
        result[title] = markdown[match.end():headings[index + 1].start() if index + 1 < len(headings) else len(markdown)].strip()
    return result


def service_projection(topic, body):
    """Only reviewed differences in scope/location, never financial values."""
    if topic == 'Plazo para Subsanar':
        body = scope_replace(body, 'Tratándose de obligaciones de pago, el plazo para subsanar será de diez (10) días hábiles.', '')
        body = scope_replace(body, 'Tratándose de las obligaciones de pago del servicio de hosting, mantenimiento y soporte,', 'Tratándose de obligaciones de pago,')
    if topic == 'Consecuencias del Incumplimiento No Subsanado':
        body = scope_replace(body, ', incluyendo el daño emergente y el lucro cesante', '')
    if topic == 'Intereses de Mora':
        body = scope_replace(body, 'sin perjuicio del aplazamiento de los plazos de entrega conforme a lo establecido en el PARÁGRAFO NOVENO de la CLÁUSULA SEGUNDA', 'sin perjuicio de la aplicación del protocolo previsto en la CLÁUSULA SÉPTIMA')
    if topic == 'ACUERDO':
        body = scope_replace(body, 'junto con el Documento Propuesta Comercial y demás anexos que se suscriban', 'incluidas sus condiciones particulares del servicio')
        body = scope_replace(body, 'El desarrollo del producto software se rige por el CONTRATO DE DESARROLLO.', '')
    if topic == 'MÉRITO EJECUTIVO':
        body = scope_replace(body, ', las actas de entrega', '')
        body = scope_replace(body, 'Documento Propuesta Comercial anexo', 'Documento Propuesta Comercial')
    if topic == 'Objeto del Servicio':
        body = scope_replace(body, 'Las CLÁUSULAS VIGÉSIMA PRIMERA a VIGÉSIMA CUARTA aplican únicamente cuando EL CONTRATANTE contrate con EL CONTRATISTA el servicio de hosting, mantenimiento y soporte del producto software, cuyo valor, periodicidad y condiciones económicas se definen en el Documento Propuesta Comercial o en el documento que las partes suscriban para el efecto.', '')
        body = scope_replace(body, 'EL CONTRATISTA se obliga a prestar, por sus propios medios y con plena autonomía técnica y administrativa, el servicio de hosting, mantenimiento y soporte del producto software desarrollado en virtud del contrato de prestación de servicios de desarrollo de software suscrito entre las partes (en adelante, el CONTRATO DE DESARROLLO). El valor, las modalidades de pago y las condiciones económicas del servicio se establecen en el apartado de Condiciones particulares del servicio de la CLÁUSULA SEGUNDA del presente contrato.', '')
        body = scope_replace(body, 'Como contraprestación, EL CONTRATANTE pagará a EL CONTRATISTA el valor del servicio conforme a la CLÁUSULA SEGUNDA.', '')
    if topic == 'Duración y Renovación del Servicio':
        body = scope_replace(body, 'La no renovación o la terminación del servicio no afecta las obligaciones relativas al desarrollo del producto software previstas en las demás cláusulas del presente contrato.', '')
        body = scope_replace(body, 'El servicio de hosting, mantenimiento y soporte', 'El presente contrato')
    if topic == 'Terminación del Servicio':
        body = scope_replace(body, 'Sin perjuicio de lo previsto en la CLÁUSULA DÉCIMA SEXTA respecto del desarrollo del producto software, el servicio de hosting, mantenimiento y soporte', 'El presente contrato')
        body = scope_replace(body, 'de forma independiente ', '')
        body = scope_replace(body, '**a) Por mutuo acuerdo:**', 'Las partes podrán dar por terminado el contrato')
        body = scope_replace(body, '**b) Por EL CONTRATANTE:**', 'EL CONTRATANTE podrá dar por terminado el contrato')
        body = scope_replace(body, '**c) Por EL CONTRATISTA:** **i)**', 'EL CONTRATISTA podrá dar por terminado el contrato en los siguientes casos:')
        body = scope_replace(body, '; o **ii)**', '.')
        body = scope_replace(body, 'terminación del servicio por cualquier causa', 'terminación del contrato por cualquier causa')
    if topic == 'ATENCIÓN DE INCIDENTES, NIVELES DE SERVICIO Y CONTINUIDAD OPERATIVA':
        body = scope_replace(body, 'El servicio de hosting, mantenimiento y soporte se apoya', 'El servicio se apoya')
        body = scope_replace(body, 'garantía prevista en el CONTRATO DE DESARROLLO', 'garantía')
        body = scope_replace(body, 'sea esta mensual, trimestral, semestral, anual u otra', '')
        body = scope_replace(body, 'En lo no previsto en este parágrafo, rige la CLÁUSULA VIGÉSIMA.', '')
        body = scope_replace(body, ' y sin que ello afecte las demás obligaciones del presente contrato', '')
        body = scope_replace(body, 'servicio de hosting, mantenimiento y soporte mediante notificación escrita', 'presente contrato mediante notificación escrita')
        body = scope_replace(body, 'y con la CLÁUSULA VIGÉSIMA, y prevalecerá', 'y prevalecerá')
        body = scope_replace(body, 'interrupción del servicio de hosting, mantenimiento y soporte', 'interrupción del servicio')
    if topic == 'PROTOCOLO DE MORA Y SUSPENSIÓN DEL SERVICIO':
        body = scope_replace(body, 'y para dar por terminado el servicio conforme al PARÁGRAFO SEXTO de la CLÁUSULA VIGÉSIMA PRIMERA, o el contrato conforme a la CLÁUSULA DÉCIMA SEXTA', 'y para dar por terminado el contrato conforme a la CLÁUSULA DÉCIMA CUARTA')
        body = scope_replace(body, 'la suspensión y la terminación previstas en la CLÁUSULA DÉCIMA SEXTA para las obligaciones del desarrollo, ', '')
        body = scope_replace(body, ', y el derecho de retención de la CLÁUSULA DÉCIMA SÉPTIMA', '')
        body = scope_replace(body, ', la terminación del servicio prevista', ' y la terminación prevista')
        body = scope_replace(body, 'la terminación del servicio prevista', 'la terminación prevista')
        body = scope_replace(body, 'Las obligaciones derivadas del desarrollo del producto software, incluidas su suspensión, terminación y el derecho de retención, se rigen por el CONTRATO DE DESARROLLO.', '')
    return body


def normalize(body):
    body = re.sub(r'^### .+\n?', '', body, flags=re.M)
    body = re.sub(rf'PARÁGRAFO {ORDINAL}(?: de la (?:presente cláusula|CLÁUSULA {ORDINAL}))?', 'REFERENCIA', body, flags=re.I)
    body = re.sub(rf'CLÁUSULAS? {ORDINAL}(?: a {ORDINAL})?', 'REFERENCIA', body)
    body = re.sub(r'\*\*(?:[a-z]|[ivx]+)\)\*\*|\((?:i|ii|iii|iv|v|vi)\)', ' ', body)
    body = body.replace(' DEL CONTRATO DE DESARROLLO', '')
    body = body.replace('CONTRATO DE DESARROLLO', 'REFERENCIA')
    body = body.replace('conforme a la REFERENCIA y al REFERENCIA', 'conforme a REFERENCIA')
    body = body.replace('conforme a lo pactado en el REFERENCIA', 'conforme a REFERENCIA')
    body = body.replace('la REFERENCIA', 'REFERENCIA').replace('el REFERENCIA', 'REFERENCIA')

    body = body.replace('apartado de Condiciones particulares del servicio del presente contrato', 'Documento Propuesta Comercial')
    body = body.replace('apartado de Condiciones particulares del servicio del presente', 'Documento Propuesta Comercial anexo al presente')
    body = body.replace('apartado de Condiciones particulares del servicio', 'Documento Propuesta Comercial')
    body = body.replace('la modalidad de pago elegida de las condiciones particulares del presente contrato', 'la periodicidad definida en el Documento Propuesta Comercial')
    body = body.replace('la periodicidad de pago pactada en el Documento Propuesta Comercial', 'la periodicidad definida en el Documento Propuesta Comercial')
    body = body.replace('Documento Propuesta Comercial aceptado por las partes', 'Documento Propuesta Comercial')
    body = body.replace('en la oportunidad pactada en estas condiciones particulares', 'en la oportunidad pactada en dicho documento')

    body = unicodedata.normalize('NFC', body).casefold()
    return ' '.join(re.findall(r'\{[a-z_]+\}|[-+]?\d+(?:[.,]\d+)*|[^\W\d]\w*|[%$€]', body))


def check_consistency(texts=None):
    if texts is None:
        from content.services.contract_template_service import default_template
        template = default_template()
        texts = {key: getattr(template, field) for key, field in TEXT_FIELDS.items()}
    findings, compared = [], []

    def compare(topic, left, right, *, pair):
        if left is None or right is None:
            findings.append({'topic': topic, 'variants': pair, 'kind': 'missing', 'missing_in': pair[0] if left is None else pair[1]})
            return
        compared.append({'topic': topic, 'variants': pair})
        if pair == ['combined', 'service']:
            left, right = service_projection(topic, left), service_projection(topic, right)
        if normalize(left) != normalize(right):
            findings.append({'topic': topic, 'variants': pair, 'kind': 'different', 'left_markdown': left, 'right_markdown': right})

    try:
        combined, product, service = (sections(texts[key]) for key in ('combined', 'product', 'service'))
        projected = texts['combined']
        for before, after in PRODUCT_ADJUSTMENTS:
            projected = scope_replace(projected, before, after)
        product_projection = sections(projected)
        topics = list(combined)
        hosting_topic = 'SERVICIO DE HOSTING, MANTENIMIENTO Y SOPORTE'
        service_start = topics.index(hosting_topic) if hosting_topic in topics else len(topics)
        product_topics = topics[:service_start]
        for topic in sorted(set(product_topics) | set(product)):
            left, right = product_projection.get(topic), product.get(topic)
            if left:
                left = scope_replace(left, SERVICE_PAYMENT_SENTENCE, '')
            compare(topic, left, right, pair=['combined', 'product'])
        shared = [
            'EXCLUSIÓN DE LA RELACIÓN LABORAL', 'CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN',
            'PROTECCIÓN Y TRATAMIENTO DE DATOS PERSONALES', 'MODIFICACIONES', 'ACUERDO', 'MÉRITO EJECUTIVO', 'NOTIFICACIÓN', 'RESOLUCIÓN DE CONFLICTOS',
            'ATENCIÓN DE INCIDENTES, NIVELES DE SERVICIO Y CONTINUIDAD OPERATIVA',
            'RECURSOS DE INFRAESTRUCTURA, CAPACIDAD OPERATIVA Y ESCALAMIENTO',
            'PROTOCOLO DE MORA Y SUSPENSIÓN DEL SERVICIO',
        ]
        for topic in shared:
            compare(topic, combined.get(topic), service.get(topic), pair=['combined', 'service'])
        hosting_body = combined.get('SERVICIO DE HOSTING, MANTENIMIENTO Y SOPORTE', '')
        compare('Objeto del Servicio', hosting_body.split('###', 1)[0] if hosting_body else None, service.get('OBJETO DEL CONTRATO'), pair=['combined', 'service'])
        hosting = sections(hosting_body, level=3)
        price = sections(service.get('PRECIO, INICIO DEL COBRO Y FORMA DE PAGO', ''), level=3)
        for topic in ['Inicio del Cobro', 'Forma y Fecha de Pago', 'Condiciones Mínimas de Reajuste del Valor del Servicio']:
            compare(topic, hosting.get(topic), price.get(topic), pair=['combined', 'service'])
        for topic, service_topic in [('Responsabilidad Operativa', 'RESPONSABILIDAD OPERATIVA'), ('Duración y Renovación del Servicio', 'DURACIÓN Y RENOVACIÓN'), ('Terminación del Servicio', 'TERMINACIÓN')]:
            compare(topic, hosting.get(topic), service.get(service_topic), pair=['combined', 'service'])
        product_price = sections(combined.get('PRECIO Y FORMA DE PAGO', ''), level=3)
        for topic in ['Medio de Pago', 'Intereses de Mora']:
            compare(topic, product_price.get(topic), price.get(topic), pair=['combined', 'service'])
        combined_breach = sections(combined.get('INCUMPLIMIENTO', ''), level=3)
        service_breach = sections(service.get('INCUMPLIMIENTO', ''), level=3)
        for topic in ['Plazo para Subsanar', 'Consecuencias del Incumplimiento No Subsanado']:
            compare(topic, combined_breach.get(topic), service_breach.get(topic), pair=['combined', 'service'])
        recognized_service = set(shared) | {'OBJETO DEL CONTRATO', 'PRECIO, INICIO DEL COBRO Y FORMA DE PAGO', 'DURACIÓN Y RENOVACIÓN', 'RESPONSABILIDAD OPERATIVA', 'TERMINACIÓN', 'INCUMPLIMIENTO'}
        extra_service_topics = (set(topics[service_start:]) - set(shared) - {hosting_topic}) | (set(service) - recognized_service)
        for topic in sorted(extra_service_topics):
            compare(topic, combined.get(topic), service.get(topic), pair=['combined', 'service'])
        service_cure = sections(service.get('INCUMPLIMIENTO', ''), level=3).get('Plazo para Subsanar')
        combined_cure = sections(combined.get('INCUMPLIMIENTO', ''), level=3).get('Plazo para Subsanar')
        if not combined_cure or scope_replace(combined_cure, SERVICE_PAYMENT_SENTENCE, '') == combined_cure or not service_cure or 'Tratándose de obligaciones de pago, se aplicará el protocolo' not in service_cure:
            findings.append({'topic': 'Protocolo de pago del servicio', 'variants': ['combined', 'service'], 'kind': 'missing'})
        for name, markdown in texts.items():
            if not sections(markdown):
                findings.append({'topic': 'Cláusulas', 'variants': [name], 'kind': 'missing'})
    except ContractTemplateError as exc:
        findings.append({'kind': 'structure_error', 'message': str(exc), **exc.details})
    return {'consistent': not findings, 'findings': findings, 'compared': compared,
            'method': 'Comparación conservadora por ámbito; normaliza formato, numeración y referencias.'}
