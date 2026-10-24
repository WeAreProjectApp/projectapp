from django.db import migrations


ROWS = [{'family': 'report',
  'scenario': 'voice_base',
  'language': 'es',
  'content': 'Organiza únicamente lo que dijo la persona. No inventes causas, pasos, prioridades ni '
             'resultados. Identifica los datos que faltan. Usa frases claras y concisas.'},
 {'family': 'report',
  'scenario': 'voice_base',
  'language': 'en',
  'content': 'Organize only what the person said. Do not invent causes, steps, priorities or results. '
             'Identify missing details. Use clear, concise sentences.'},
 {'family': 'report',
  'scenario': 'bug',
  'language': 'es',
  'content': 'Presenta título, descripción del problema, pasos mencionados, resultado esperado y '
             'resultado observado. Separa los datos que faltan.'},
 {'family': 'report',
  'scenario': 'bug',
  'language': 'en',
  'content': 'Present a title, problem description, mentioned steps, expected behavior and actual '
             'behavior. List missing details separately.'},
 {'family': 'report',
  'scenario': 'change',
  'language': 'es',
  'content': 'Presenta título, necesidad, cambio solicitado, pantalla o módulo y resultado esperado. No '
             'presupongas aprobación contractual.'},
 {'family': 'report',
  'scenario': 'change',
  'language': 'en',
  'content': 'Present a title, need, requested change, screen or module and expected outcome. Do not '
             'imply contractual approval.'},
 {'family': 'report',
  'scenario': 'stage_observation',
  'language': 'es',
  'content': 'Describe la observación de la etapa o requerimiento, dónde ocurre, qué se observó y qué '
             'necesita aclaración. No decidas aprobación, objeción ni rechazo.'},
 {'family': 'report',
  'scenario': 'stage_observation',
  'language': 'en',
  'content': 'Describe the stage or requirement observation, where it happens, what was observed and '
             'what needs clarification. Do not decide approval, objection or rejection.'},
 {'family': 'chatbot',
  'scenario': 'project_status',
  'language': 'es',
  'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot',
  'scenario': 'project_status',
  'language': 'en',
  'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot',
  'scenario': 'phase_status',
  'language': 'es',
  'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot',
  'scenario': 'phase_status',
  'language': 'en',
  'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot',
  'scenario': 'deliverables',
  'language': 'es',
  'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot',
  'scenario': 'deliverables',
  'language': 'en',
  'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot', 'scenario': 'bugs', 'language': 'es', 'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot', 'scenario': 'bugs', 'language': 'en', 'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot',
  'scenario': 'project_health',
  'language': 'es',
  'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot',
  'scenario': 'project_health',
  'language': 'en',
  'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot',
  'scenario': 'contract_clause',
  'language': 'es',
  'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot',
  'scenario': 'contract_clause',
  'language': 'en',
  'content': '{scope_label}\n\n{facts_text}'},
 {'family': 'chatbot',
  'scenario': 'out_of_scope',
  'language': 'es',
  'content': 'Recuerda que mi propósito es brindarte información sobre tus proyectos y su estado. Puedo '
             'ayudarte a consultar contratos, fases, entregables, bugs y pendientes.'},
 {'family': 'chatbot',
  'scenario': 'out_of_scope',
  'language': 'en',
  'content': 'My purpose is to provide information about your projects and their status. I can help you '
             'check contracts, phases, deliverables, reported bugs and pending work.'},
 {'family': 'chatbot',
  'scenario': 'clarification',
  'language': 'es',
  'content': '¿Sobre cuál de estas opciones quieres consultar?\n{choices_text}'},
 {'family': 'chatbot',
  'scenario': 'clarification',
  'language': 'en',
  'content': 'Which of these options would you like to ask about?\n{choices_text}'}]


def seed(apps, schema_editor):
    Settings = apps.get_model('accounts', 'PlatformAISettings')
    Template = apps.get_model('accounts', 'PlatformAITemplate')
    Revision = apps.get_model('accounts', 'PlatformAITemplateRevision')
    Settings.objects.get_or_create(pk=1)
    for row in ROWS:
        item, created = Template.objects.get_or_create(family=row['family'], scenario=row['scenario'], language=row['language'], defaults={'content': row['content']})
        if created:
            Revision.objects.create(template=item, version=1, content=item.content)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0083_platform_ai')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
