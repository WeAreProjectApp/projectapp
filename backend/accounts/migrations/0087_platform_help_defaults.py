from django.db import migrations


DEFAULT_TOURS = [('platform-general',
  'general',
  {'title_es': 'Recorrido de la plataforma',
   'title_en': 'Platform tour',
   'steps': [{'target': 'welcome',
              'title_es': 'Bienvenido a tu plataforma',
              'title_en': 'Welcome to your platform',
              'description_es': 'Aquí puedes seguir tus proyectos y encontrar los recursos del equipo. '
                                'Puedes saltar esta guía cuando quieras.',
              'description_en': 'Follow your projects and find your team’s resources here. You can skip this '
                                'guide at any time.'},
             {'target': 'projects',
              'title_es': 'Tus proyectos',
              'title_en': 'Your projects',
              'description_es': 'Abre un proyecto para consultar su entrega, solicitudes y recursos.',
              'description_en': 'Open a project to find its delivery, requests and resources.'},
             {'target': 'documents',
              'title_es': 'Documentos',
              'title_en': 'Documents',
              'description_es': 'Consulta y descarga tus documentos. Cuando corresponda, también podrás '
                                'revisarlos y firmarlos.',
              'description_en': 'Read and download your documents. When applicable, you can also review and '
                                'sign them.'},
             {'target': 'collection-accounts',
              'title_es': 'Cuentas de cobro',
              'title_en': 'Billing statements',
              'description_es': 'Aquí encuentras tus cuentas de cobro y su estado.',
              'description_en': 'Find your billing statements and their status here.'},
             {'target': 'hosting',
              'title_es': 'Hosting',
              'title_en': 'Hosting',
              'description_es': 'Consulta el servicio y los pagos de hosting disponibles para tu cuenta.',
              'description_en': 'Find hosting services and payments available to your account.'},
             {'target': 'notifications',
              'title_es': 'Notificaciones',
              'title_en': 'Notifications',
              'description_es': 'Revisa aquí los avisos y novedades de tus proyectos.',
              'description_en': 'Review project updates and notifications here.'},
             {'target': 'profile',
              'title_es': 'Tu perfil',
              'title_en': 'Your profile',
              'description_es': 'Actualiza tus datos y personaliza tu cuenta.',
              'description_en': 'Update your details and personalize your account.'},
             {'target': 'platform-appi-launcher',
              'title_es': 'Consulta a Appi',
              'title_en': 'Ask Appi',
              'description_es': 'Puedes preguntar por el estado de tus proyectos o cómo usar la plataforma. '
                                'El chat se abre cuando tú lo eliges.',
              'description_en': 'Ask about your project status or how to use the platform. The chat opens '
                                'when you choose.'},
             {'target': 'help',
              'title_es': 'Vuelve a esta guía',
              'title_en': 'Return to this guide',
              'description_es': 'Desde Ayuda puedes repetir los recorridos y ver los videos disponibles.',
              'description_en': 'Use Help to repeat tours and watch available videos.'}]}),
 ('platform-project',
  'project',
  {'title_es': 'Guía del proyecto',
   'title_en': 'Project guide',
   'steps': [{'target': 'project-summary',
              'title_es': 'Resumen',
              'title_en': 'Overview',
              'description_es': 'Consulta el estado general de este proyecto.',
              'description_en': 'Check this project’s overall status.'},
             {'target': 'project-delivery',
              'title_es': 'Entrega y revisiones',
              'title_en': 'Delivery and reviews',
              'description_es': 'Revisa las fases y etapas disponibles y registra tus observaciones donde '
                                'corresponda.',
              'description_en': 'Review available phases and stages and leave feedback where applicable.'},
             {'target': 'project-ideas',
              'title_es': 'Ideas',
              'title_en': 'Ideas',
              'description_es': 'Comparte sugerencias para considerar en el futuro. Una idea no cambia por '
                                'sí sola el alcance acordado.',
              'description_en': 'Share suggestions for the future. An idea does not change the agreed scope '
                                'on its own.'},
             {'target': 'project-changes',
              'title_es': 'Solicitudes',
              'title_en': 'Requests',
              'description_es': 'Encuentra tus solicitudes y sigue su evaluación.',
              'description_en': 'Find your requests and track their evaluation.'},
             {'target': 'project-bugs',
              'title_es': 'Reportar un problema',
              'title_en': 'Report an issue',
              'description_es': 'Reporta lo que no funciona y consulta su estado. Si tienes voz habilitada, '
                                'el formulario te mostrará esa opción.',
              'description_en': 'Report something that is not working and track its status. If voice '
                                'reporting is available, the form will show that option.'},
             {'target': 'project-resources',
              'title_es': 'Recursos',
              'title_en': 'Resources',
              'description_es': 'Consulta los archivos y materiales compartidos para este proyecto.',
              'description_en': 'Find the files and materials shared for this project.'},
             {'target': 'project-access',
              'title_es': 'Accesos',
              'title_en': 'Access',
              'description_es': 'Encuentra los accesos que el equipo haya habilitado para ti.',
              'description_en': 'Find the access details the team has made available to you.'},
             {'target': 'project-secure-links',
              'title_es': 'Enlaces seguros',
              'title_en': 'Secure links',
              'description_es': 'Abre los enlaces seguros disponibles para tu proyecto.',
              'description_en': 'Open secure links available for your project.'}]}),
 ('platform-voice',
  'voice',
  {'title_es': 'Reportar con una nota de voz',
   'title_en': 'Report with a voice note',
   'steps': [{'target': 'voice-report',
              'title_es': 'Explica lo ocurrido con tu voz',
              'title_en': 'Describe the issue with your voice',
              'description_es': 'Al pulsar este botón puedes grabar una nota. Después podrás corregir la '
                                'transcripción, revisar la propuesta y usarla en el formulario. El envío '
                                'siempre lo decides tú. También puedes seguir escribiendo manualmente.',
              'description_en': 'Use this button to record a voice note. Then correct the transcript, review '
                                'the draft and use it in the form. You always choose when to submit. You can '
                                'also keep typing manually.'}]})]


def seed(apps, schema_editor):
    Settings = apps.get_model('accounts', 'PlatformHelpSettings')
    Tour = apps.get_model('accounts', 'PlatformGuidedTour')
    Revision = apps.get_model('accounts', 'PlatformGuidedTourRevision')
    db = schema_editor.connection.alias
    Settings.objects.using(db).get_or_create(pk=1)
    for index, (slug, context, content) in enumerate(DEFAULT_TOURS):
        tour, created = Tour.objects.using(db).get_or_create(slug=slug, defaults={
            'context': context, 'kind': 'onboarding', 'priority': index,
            'draft': content, 'published_revision': 1, 'version': 1,
        })
        if created:
            Revision.objects.using(db).create(tour=tour, number=1, content=content)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0086_platform_help')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
