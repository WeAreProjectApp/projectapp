"""One contract, three presentations.

A deal closes with the single contract (``combined``) or with two separate
documents: the product contract (software development and implementation) and
the service contract (hosting, maintenance and support). The clauses do not
change; only the separation does.

- ``combined`` renders ``ContractTemplate.content_markdown``.
- ``product`` is derived from that same text at runtime: clauses 21-24 are
  cut and three anchored adjustments replace the references that pointed at
  them. Any later patch to clauses 1-20 therefore reaches it on its own, and a
  patch that rewrites an anchored paragraph makes the derivation fail loudly.
- ``service`` renders ``ContractTemplate.service_content_markdown``, a
  standalone text built from clauses 21-24 plus the general clauses it needs.

Every consumer of "the contract" resolves its documents through this registry.
"""

from dataclasses import dataclass

from content.models import BusinessProposal, ContractTemplate, ProposalDocument

COMBINED = 'combined'
PRODUCT = 'product'
SERVICE = 'service'


@dataclass(frozen=True)
class ContractVariant:
    key: str
    doc_type: str
    source_key: str
    custom_key: str
    title_lines: tuple
    heading: str
    file_prefix: str
    document_title: str
    label: str
    description: str


VARIANTS = {
    COMBINED: ContractVariant(
        key=COMBINED,
        doc_type=ProposalDocument.DOC_TYPE_CONTRACT,
        source_key='contract_source',
        custom_key='custom_contract_markdown',
        title_lines=('CONTRATO DE PRESTACIÓN', 'DE SERVICIOS'),
        heading='CONTRATO DE PRESTACIÓN DE SERVICIOS',
        file_prefix='Contrato_Desarrollo_Software',
        document_title='Contrato de desarrollo de software',
        label='Contrato de desarrollo de software',
        description='Datos y condiciones del contrato para revisión y firma.',
    ),
    PRODUCT: ContractVariant(
        key=PRODUCT,
        doc_type=ProposalDocument.DOC_TYPE_CONTRACT_PRODUCT,
        source_key='product_contract_source',
        custom_key='product_custom_contract_markdown',
        title_lines=('CONTRATO DE PRESTACIÓN', 'DE SERVICIOS'),
        heading='CONTRATO DE PRESTACIÓN DE SERVICIOS',
        file_prefix='Contrato_Producto_Software',
        document_title='Contrato de producto: desarrollo e implementación del software',
        label='Contrato de producto (desarrollo de software)',
        description='Desarrollo e implementación del software, para revisión y firma.',
    ),
    SERVICE: ContractVariant(
        key=SERVICE,
        doc_type=ProposalDocument.DOC_TYPE_CONTRACT_SERVICE,
        source_key='service_contract_source',
        custom_key='service_custom_contract_markdown',
        title_lines=(
            'CONTRATO DE PRESTACIÓN DEL SERVICIO',
            'DE HOSTING, MANTENIMIENTO Y SOPORTE',
        ),
        heading='CONTRATO DE PRESTACIÓN DEL SERVICIO DE HOSTING, MANTENIMIENTO Y SOPORTE',
        file_prefix='Contrato_Servicio_Hosting',
        document_title='Contrato de servicio: hosting, mantenimiento y soporte',
        label='Contrato de servicio (hosting, mantenimiento y soporte)',
        description='Hosting, mantenimiento y soporte del software, para revisión y firma.',
    ),
}

MODALITY_VARIANTS = {
    BusinessProposal.ContractModality.SINGLE: (COMBINED,),
    BusinessProposal.ContractModality.SPLIT: (PRODUCT, SERVICE),
}

CONTRACT_DOC_TYPES = ProposalDocument.CONTRACT_DOC_TYPES
DOC_TYPE_VARIANTS = {spec.doc_type: key for key, spec in VARIANTS.items()}

# The three service terms the operator left as "XXX" in the standalone text.
SERVICE_PARAM_KEYS = (
    'service_initial_term',
    'service_renewal_notice_days',
    'service_termination_notice_days',
)

# Parameters a final contract needs before it can be sent for signature.
FINAL_REQUIRED_PARAMS = (
    'contractor_full_name', 'contractor_email', 'contract_city', 'bank_name',
    'bank_account_number', 'client_full_name', 'client_cedula', 'client_email',
    'contract_date',
)

# Clauses 21-24 are the tail of the default text (appended by migration 0179).
PRODUCT_CUT = '\n\n---\n\n## CLÁUSULA VIGÉSIMA PRIMERA'
PRODUCT_ADJUSTMENTS = (
    # Cl. 2 Par. 6 c): the incident-report protocol lived in Cl. 22 Par. 1.
    (
        '**c)** EL CONTRATANTE deberá reportar los problemas detectados a través del '
        'medio de notificación definido en la CLÁUSULA DÉCIMA QUINTA, cumpliendo el '
        'protocolo de reporte de incidentes definido en el PARÁGRAFO PRIMERO de la '
        'CLÁUSULA VIGÉSIMA SEGUNDA. El reporte que no reúna la información allí '
        'señalada no dará inicio al cómputo de los plazos del presente parágrafo sino '
        'desde el momento en que sea completado.',
        '**c)** EL CONTRATANTE deberá reportar los problemas detectados a través del '
        'medio de notificación definido en la CLÁUSULA DÉCIMA QUINTA. Todo reporte '
        'incluirá, en el cuerpo del mensaje o en documento adjunto: **i)** título corto '
        'que identifique el problema; **ii)** dirección (URL) de la página en la que '
        'inició la operación; **iii)** dirección (URL) de la página en la que se '
        'presentó el problema, si es distinta de la anterior; **iv)** pasos realizados, '
        'enumerados en orden; **v)** lo que ocurrió, con el mensaje de error exacto o '
        'una captura de pantalla; **vi)** lo que se esperaba que ocurriera; **vii)** '
        'dispositivo y navegador utilizados; y **viii)** fecha y hora aproximada del '
        'suceso. El reporte que no reúna la información aquí señalada no dará inicio '
        'al cómputo de los plazos del presente parágrafo sino desde el momento en que '
        'sea completado.',
    ),
    # Cl. 2 Par. 7 h): the service is governed by its own contract.
    (
        'dicho servicio se regirá por las CLÁUSULAS VIGÉSIMA PRIMERA a VIGÉSIMA CUARTA '
        'del presente contrato y por las condiciones económicas definidas en el '
        'Documento Propuesta Comercial.',
        'dicho servicio se regirá por el contrato de prestación del servicio de hosting, '
        'mantenimiento y soporte que las partes suscriban de manera independiente y por '
        'las condiciones económicas definidas en el Documento Propuesta Comercial.',
    ),
    # Cl. 15: the business-day definition lived in Cl. 22 Par. 1 a).
    (
        'con al menos cinco (5) días hábiles de antelación.\n\n---\n\n'
        '## CLÁUSULA DÉCIMA SEXTA',
        'con al menos cinco (5) días hábiles de antelación.\n\n'
        'Para todos los efectos del presente contrato, se entiende por día hábil el '
        'comprendido de lunes a viernes, con exclusión de sábados, domingos y días '
        'festivos de la República de Colombia conforme a la Ley 51 de 1983 y las normas '
        'que la modifiquen.\n\n---\n\n## CLÁUSULA DÉCIMA SEXTA',
    ),
)


def derive_product_markdown(combined_markdown):
    """Return the product contract, or None when the default text has drifted."""
    text = combined_markdown or ''
    if text.count(PRODUCT_CUT) != 1:
        return None
    product = text[:text.index(PRODUCT_CUT)]
    for old, new in PRODUCT_ADJUSTMENTS:
        if product.count(old) != 1:
            return None
        product = product.replace(old, new, 1)
    return product


def template_markdown(template, variant):
    """The unsubstituted standard text of *variant*, or '' when it is unavailable."""
    if template is None:
        return ''
    if variant == PRODUCT:
        return derive_product_markdown(template.content_markdown) or ''
    if variant == SERVICE:
        return template.service_content_markdown or ''
    return template.content_markdown or ''


def split_available(template=None):
    """Both separate documents have a standard text to start from."""
    template = template if template is not None else ContractTemplate.get_default()
    return bool(template_markdown(template, PRODUCT).strip()) and bool(
        template_markdown(template, SERVICE).strip()
    )


def modality(proposal):
    value = getattr(proposal, 'contract_modality', '') or BusinessProposal.ContractModality.SINGLE
    return value if value in MODALITY_VARIANTS else BusinessProposal.ContractModality.SINGLE


def active_variants(proposal):
    return MODALITY_VARIANTS[modality(proposal)]


def active_doc_types(proposal):
    return {VARIANTS[key].doc_type for key in active_variants(proposal)}


def contract_source(params, variant):
    return (params or {}).get(VARIANTS[variant].source_key) or 'default'


def _filled(params, key):
    return bool(str((params or {}).get(key) or '').strip())


def missing_generation_params(params, variant):
    """Keys still needed before *variant* can be generated at all."""
    params = params or {}
    spec = VARIANTS[variant]
    if contract_source(params, variant) == 'custom':
        return [] if _filled(params, spec.custom_key) else [spec.custom_key]
    missing = [] if _filled(params, 'client_cedula') else ['client_cedula']
    if not (_filled(params, 'contractor_nit') or _filled(params, 'contractor_cedula')):
        missing.append('contractor_identity')
    if variant == SERVICE:
        missing += [key for key in SERVICE_PARAM_KEYS if not _filled(params, key)]
    return missing


def missing_final_params(params, variant):
    """Keys a final contract still needs before it can be sent for signature."""
    params = params or {}
    spec = VARIANTS[variant]
    if contract_source(params, variant) == 'custom':
        required = ['contract_date', spec.custom_key]
    else:
        required = list(FINAL_REQUIRED_PARAMS)
        if variant == SERVICE:
            required += list(SERVICE_PARAM_KEYS)
    missing = [key for key in required if not _filled(params, key)]
    if contract_source(params, variant) != 'custom' and not (
        _filled(params, 'contractor_nit') or _filled(params, 'contractor_cedula')
    ):
        missing.append('contractor_identity')
    return missing


def can_generate(params, variant):
    return not missing_generation_params(params, variant)


def contract_document(proposal, variant):
    """The stored generated document of *variant*, newest first; None if absent."""
    return (
        ProposalDocument.objects.filter(
            proposal=proposal, document_type=VARIANTS[variant].doc_type, is_generated=True,
        )
        .order_by('-updated_at', '-pk')
        .first()
    )
