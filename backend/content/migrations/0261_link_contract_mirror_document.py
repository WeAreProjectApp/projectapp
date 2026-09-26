"""Turn the hand-kept contract copy in the Document manager into its window.

Production kept a manual copy of the contract template in the Document
manager ("Contrato_Master_Prestacion_Servicios_v6_10082026", folder
Templates). It had drifted to v6 while the real contract moved on. The
operator chose to keep that document as the place to consult and download
the contract, read-only: it is linked to the default template, renamed, and
its stale text is replaced by a pointer — readers render the contract live.

Only an exact, single, active match is linked, so any other environment is a
no-op. Reversing unlinks and restores the title but not the v6 text: that
text survives in migration 0179, and serving it again would bring back the
very drift this removes.
"""

from django.db import migrations

LEGACY_TITLE = 'Contrato_Master_Prestacion_Servicios_v6_10082026'
LEGACY_FOLDER = 'Templates'
MIRROR_TITLE = 'Contrato de prestación de servicios — borrador vigente'
POINTER_MARKDOWN = (
    f'# {MIRROR_TITLE}\n\n'
    'Este documento muestra en vivo el contrato vigente de ProjectApp, el '
    'mismo que ven los clientes en la sección legal de su propuesta. Su '
    'contenido no se guarda aquí.\n'
)


def link_mirror(apps, schema_editor):
    ContractTemplate = apps.get_model('content', 'ContractTemplate')
    Document = apps.get_model('content', 'Document')
    database = schema_editor.connection.alias

    template = ContractTemplate.objects.using(database).filter(is_default=True).first()
    if template is None or template.mirror_document_id:
        return
    candidates = list(
        Document.objects.using(database).filter(
            title=LEGACY_TITLE, folder__name=LEGACY_FOLDER, is_archived=False,
        )[:2]
    )
    if len(candidates) != 1:
        return
    document = candidates[0]
    document.title = MIRROR_TITLE
    document.content_markdown = POINTER_MARKDOWN
    document.content_json = {}
    document.save(using=database, update_fields=['title', 'content_markdown', 'content_json', 'updated_at'])
    template.mirror_document = document
    template.save(using=database, update_fields=['mirror_document'])


def unlink_mirror(apps, schema_editor):
    ContractTemplate = apps.get_model('content', 'ContractTemplate')
    database = schema_editor.connection.alias
    for template in ContractTemplate.objects.using(database).exclude(mirror_document=None):
        document = template.mirror_document
        template.mirror_document = None
        template.save(using=database, update_fields=['mirror_document'])
        if document.title == MIRROR_TITLE:
            document.title = LEGACY_TITLE
            document.save(using=database, update_fields=['title', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0260_contracttemplate_mirror_document'),
    ]

    operations = [
        migrations.RunPython(link_mirror, unlink_mirror),
    ]
