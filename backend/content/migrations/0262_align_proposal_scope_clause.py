"""Align the proposal scope clause with the contract's Parágrafo Décimo.

The commercial proposal restates the contract's scope clause in its own
voice. It had drifted: it said a change only had to be "documentado y
cotizado ... o como un requerimiento independiente", while the contract
requires formalizing it through an OTROSÍ or an independent contract, and it
lacked the contract's literal d) (out-of-scope work creates no precedent).

Code defaults already carry the new text; this patches the stored
``ProposalDefaultConfig`` rows, which take priority over code, only where the
stored paragraphs are still exactly the shipped ones. Proposals already
created keep their own snapshot.
"""

from django.db import migrations

OLD_ES = ['El trabajo aprobado y cotizado corresponde únicamente a lo descrito dentro del alcance de esta '
 'propuesta comercial y de su detalle técnico. Cualquier conversación, mensaje, correo '
 'electrónico, reunión, idea, recurso, archivo, referencia o solicitud que surja **antes o '
 'durante** el proyecto y que no esté explícitamente descrita dentro de dicho alcance no '
 'constituye, por sí sola, un compromiso de implementación ni hace parte del trabajo contratado.',
 'Lo anterior no limita la comunicación: podemos conversar y explorar ideas libremente. Sin '
 'embargo, para que una funcionalidad, cambio o entregable pase a formar parte del trabajo '
 'aprobado, debe quedar documentado y cotizado como parte del alcance o como un requerimiento '
 'independiente. Esto protege a ambas partes: evita malentendidos sobre lo que está incluido, '
 'mantiene el proyecto enfocado y asegura que cada esfuerzo adicional se planifique y se remunere '
 'de forma justa.',
 'En consecuencia, los tiempos, costos y garantías de esta propuesta aplican solamente sobre el '
 'alcance descrito. Todo lo que lo exceda se gestionará mediante los paquetes de horas anteriores '
 '(para esfuerzos bajos o medio-bajos) o como una cotización independiente (para esfuerzos medios '
 'o superiores).']

NEW_ES = ['El trabajo aprobado y cotizado corresponde únicamente a lo descrito dentro del alcance de esta '
 'propuesta comercial y de su detalle técnico. Cualquier conversación, mensaje, correo '
 'electrónico, reunión, idea, recurso, archivo, referencia o solicitud que surja **antes o '
 'durante** el proyecto y que no esté explícitamente descrita dentro de dicho alcance no '
 'constituye, por sí sola, un compromiso de implementación ni hace parte del trabajo contratado.',
 'Lo anterior no limita la comunicación: podemos conversar y explorar ideas libremente. Sin '
 'embargo, para que una funcionalidad, cambio o entregable pase a formar parte del trabajo '
 'aprobado, debe quedar documentado y cotizado como parte del alcance, y formalizarse mediante un '
 'otrosí al contrato o mediante un contrato independiente. Esto protege a ambas partes: evita '
 'malentendidos sobre lo que está incluido, mantiene el proyecto enfocado y asegura que cada '
 'esfuerzo adicional se planifique y se remunere de forma justa.',
 'En consecuencia, los tiempos, costos y garantías de esta propuesta aplican solamente sobre el '
 'alcance descrito. Todo lo que lo exceda se gestionará mediante los paquetes de horas anteriores '
 '(para esfuerzos bajos o medio-bajos) o como una cotización independiente (para esfuerzos medios '
 'o superiores).',
 'La ejecución de cualquier actividad no comprendida en el alcance no lo modifica, no genera '
 'derecho a exigir prestaciones similares en el futuro ni implica renuncia a lo aquí establecido.']

OLD_EN = ['The approved and quoted work corresponds solely to what is described within the scope of this '
 'commercial proposal and its technical detail. Any conversation, message, email, meeting, idea, '
 'resource, file, reference or request that arises **before or during** the project and is not '
 'explicitly described within that scope does not, by itself, constitute a commitment to implement '
 'it, nor is it part of the contracted work.',
 'This does not limit communication: we can talk and explore ideas freely. However, for a feature, '
 'change or deliverable to become part of the approved work, it must be documented and quoted as '
 'part of the scope or as an independent requirement. This protects both parties: it avoids '
 'misunderstandings about what is included, keeps the project focused, and ensures every '
 'additional effort is planned and fairly paid.',
 'Consequently, the timelines, costs and warranties of this proposal apply only to the described '
 'scope. Anything beyond it will be handled via the hour packages above (for low or medium-low '
 'efforts) or as an independent quote (for medium or higher efforts).']

NEW_EN = ['The approved and quoted work corresponds solely to what is described within the scope of this '
 'commercial proposal and its technical detail. Any conversation, message, email, meeting, idea, '
 'resource, file, reference or request that arises **before or during** the project and is not '
 'explicitly described within that scope does not, by itself, constitute a commitment to implement '
 'it, nor is it part of the contracted work.',
 'This does not limit communication: we can talk and explore ideas freely. However, for a feature, '
 'change or deliverable to become part of the approved work, it must be documented and quoted as '
 'part of the scope, and formalized through an amendment to the contract or through an independent '
 'contract. This protects both parties: it avoids misunderstandings about what is included, keeps '
 'the project focused, and ensures every additional effort is planned and fairly paid.',
 'Consequently, the timelines, costs and warranties of this proposal apply only to the described '
 'scope. Anything beyond it will be handled via the hour packages above (for low or medium-low '
 'efforts) or as an independent quote (for medium or higher efforts).',
 'Carrying out any activity outside the scope does not modify it, does not create a right to '
 'demand similar work in the future, and does not waive anything stated here.']

PAIRS = {'es': (OLD_ES, NEW_ES), 'en': (OLD_EN, NEW_EN)}


def _patch(apps, schema_editor, reverse=False):
    ProposalDefaultConfig = apps.get_model('content', 'ProposalDefaultConfig')
    database = schema_editor.connection.alias
    for config in ProposalDefaultConfig.objects.using(database).all():
        pair = PAIRS.get(config.language)
        if pair is None:
            continue
        old, new = (pair[1], pair[0]) if reverse else pair
        changed = False
        for section in config.sections_json or []:
            if not isinstance(section, dict) or section.get('section_type') != 'commercial_conditions':
                continue
            content = section.get('content_json')
            if isinstance(content, dict) and content.get('scopeParagraphs') == old:
                content['scopeParagraphs'] = list(new)
                changed = True
        if changed:
            config.save(using=database, update_fields=['sections_json'])


def align_scope_clause(apps, schema_editor):
    _patch(apps, schema_editor)


def restore_scope_clause(apps, schema_editor):
    _patch(apps, schema_editor, reverse=True)


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0261_link_contract_mirror_document'),
    ]

    operations = [
        migrations.RunPython(align_scope_clause, restore_scope_clause),
    ]
