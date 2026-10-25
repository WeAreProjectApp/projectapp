"""Versioned, finite template catalog; safety rules are not editable content."""
import re
from string import Formatter

from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models_ai import PlatformAITemplate, PlatformAITemplateRevision
from accounts.services.appi_catalog import guide_slots


REPORT_SEEDS = {
    'voice_base': (
        'Organiza únicamente lo que dijo la persona. No inventes causas, pasos, prioridades ni resultados. Identifica los datos que faltan. Usa frases claras y concisas.',
        'Organize only what the person said. Do not invent causes, steps, priorities or results. Identify missing details. Use clear, concise sentences.',
    ),
    'bug': (
        'Presenta título, descripción del problema, pasos mencionados, resultado esperado y resultado observado. Separa los datos que faltan.',
        'Present a title, problem description, mentioned steps, expected behavior and actual behavior. List missing details separately.',
    ),
    'change': (
        'Presenta título, necesidad, cambio solicitado, pantalla o módulo y resultado esperado. No presupongas aprobación contractual.',
        'Present a title, need, requested change, screen or module and expected outcome. Do not imply contractual approval.',
    ),
    'stage_observation': (
        'Describe la observación de la etapa o requerimiento, dónde ocurre, qué se observó y qué necesita aclaración. No decidas aprobación, objeción ni rechazo.',
        'Describe the stage or requirement observation, where it happens, what was observed and what needs clarification. Do not decide approval, objection or rejection.',
    ),
}
CHAT_SCENARIOS = ('project_status', 'phase_status', 'deliverables', 'bugs', 'project_health', 'contract_clause')
CHAT_SLOTS = {scenario: {'scope_label', 'facts_text'} for scenario in CHAT_SCENARIOS}
CHAT_SLOTS.update(out_of_scope=set(), clarification={'choices_text'})
CHAT_SLOTS.update(guide_slots())


def defaults():
    rows = []
    for scenario, contents in REPORT_SEEDS.items():
        rows.extend({'family': 'report', 'scenario': scenario, 'language': language, 'content': content}
                    for language, content in zip(('es', 'en'), contents))
    for scenario in CHAT_SCENARIOS:
        rows.extend({'family': 'chatbot', 'scenario': scenario, 'language': language, 'content': '{scope_label}\n\n{facts_text}'}
                    for language in ('es', 'en'))
    for language, content in (
        ('es', 'Recuerda que mi propósito es brindarte información sobre tus proyectos y su estado. Puedo ayudarte a consultar contratos, fases, entregables, bugs y pendientes.'),
        ('en', 'My purpose is to provide information about your projects and their status. I can help you check contracts, phases, deliverables, reported bugs and pending work.'),
    ):
        rows.append({'family': 'chatbot', 'scenario': 'out_of_scope', 'language': language, 'content': content})
    for language, content in (('es', '¿Sobre cuál de estas opciones quieres consultar?\n{choices_text}'), ('en', 'Which of these options would you like to ask about?\n{choices_text}')):
        rows.append({'family': 'chatbot', 'scenario': 'clarification', 'language': language, 'content': content})
    return rows


def validate_content(family, scenario, content):
    if not isinstance(content, str) or not content.strip() or len(content) > 12000 or re.search(r'<[^>]*>|[\x00-\x08]', content):
        raise ValidationError({'content': 'Usa texto plano de hasta 12000 caracteres, sin HTML.'})
    try:
        slots = set()
        for _, field, spec, conversion in Formatter().parse(content):
            if field is not None:
                if spec or conversion or not re.fullmatch(r'[a-z_]+', field):
                    raise ValueError
                slots.add(field)
    except ValueError as exc:
        raise ValidationError({'content': 'Los marcadores no son válidos.'}) from exc
    expected = CHAT_SLOTS.get(scenario) if family == 'chatbot' else set() if scenario in REPORT_SEEDS else None
    if expected is None or slots != expected:
        raise ValidationError({'content': 'Conserva exactamente los marcadores admitidos para este escenario.'})
    return content.strip()


def template_data(item):
    return {'id': item.pk, 'family': item.family, 'scenario': item.scenario, 'language': item.language,
            'content': item.content, 'version': item.version, 'updated_at': item.updated_at,
            'placeholders': sorted(CHAT_SLOTS.get(item.scenario, set())) if item.family == 'chatbot' else []}


def get_template(family, scenario, language):
    item = PlatformAITemplate.objects.filter(family=family, scenario=scenario, language=language).first()
    if not item:
        raise NotFound('Plantilla no encontrada.')
    return item


def render_chat_template(scenario, language, values):
    item = get_template('chatbot', scenario, language)
    validate_content('chatbot', scenario, item.content)
    if set(values) != CHAT_SLOTS[scenario] or any(not isinstance(value, str) or len(value) > 20000 for value in values.values()):
        raise ValidationError('Los datos de la plantilla no son válidos.')
    return item.content.format(**values)


@transaction.atomic
def update_template(template_id, actor, content, expected_version, *, restore_version=None):
    from accounts.services.platform_ai import require_admin, check_version, event
    require_admin(actor)
    item = PlatformAITemplate.objects.select_for_update().filter(pk=template_id).first()
    if not item:
        raise NotFound('Plantilla no encontrada.')
    check_version(item.version, expected_version)
    if restore_version is not None:
        revision = item.revisions.filter(version=restore_version).first()
        if not revision:
            raise NotFound('Versión no encontrada.')
        content = revision.content
    item.content = validate_content(item.family, item.scenario, content)
    item.version += 1
    item.save(update_fields=['content', 'version', 'updated_at'])
    PlatformAITemplateRevision.objects.create(template=item, version=item.version, content=item.content, actor=actor)
    event(actor, 'template.restore' if restore_version else 'template.update', str(item.pk), {'version': item.version})
    return template_data(item)
