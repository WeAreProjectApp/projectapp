"""Adopta como carpeta madre las raíces que ya representan a un cliente.

Dry-run por defecto, como el resto de los backfills del repo: imprime el plan
completo con el motivo de cada salto y sólo escribe con `--apply`.

No adivina identidades. El universo es estrecho a propósito: una raíz sin padre,
sin proyecto, no archivada, no gestionada por el sistema y con `client_user` YA
asignado — es decir, carpetas cuyo dueño una persona decidió antes. Nada se
infiere por nombre; eso es trabajo del manifiesto revisado de
`reconcile_project_folders`.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from content.models import DocumentFolder
from content.services.client_document_folder_service import adopt_client_folder


class Command(BaseCommand):
    help = (
        'Marca como carpeta madre de cliente las raíces que ya tienen dueño. '
        'Dry-run salvo que se pase --apply.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Escribe los cambios. Sin este flag sólo se imprime el plan.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']

        roots = (
            DocumentFolder.objects
            .filter(
                parent__isnull=True,
                client_user__isnull=False,
                project__isnull=True,
                managed_project__isnull=True,
                managed_client__isnull=True,
                is_archived=False,
                system_key__isnull=True,
            )
            .select_related('client_user')
            .order_by('pk')
        )
        # La raíz conservada de un proyecto eliminado luce idéntica a una raíz
        # de cliente, pero es de sólo consulta: adoptarla abortaría el --apply.
        candidates = roots.filter(retention_context__isnull=True)

        planned = []
        skipped = [
            (folder, 'conservada de un proyecto eliminado (sólo consulta)')
            for folder in roots.filter(retention_context__isnull=False)
        ]
        # Un cliente con dos raíces no se resuelve solo: elegir una por orden de
        # id sería inventar la decisión. Se reportan las dos y se saltan ambas.
        by_client = {}
        for folder in candidates:
            by_client.setdefault(folder.client_user_id, []).append(folder)

        for client_id, folders in sorted(by_client.items()):
            taken = DocumentFolder.objects.filter(managed_client_id=client_id).first()
            if taken is not None:
                skipped.append(
                    (folders[0], f'el cliente ya tiene la carpeta madre {taken.pk}')
                )
                continue
            if len(folders) > 1:
                ids = ', '.join(str(f.pk) for f in folders)
                skipped.append(
                    (folders[0], f'el cliente tiene {len(folders)} raíces ({ids}): elegí una a mano')
                )
                continue
            planned.append(folders[0])

        for folder in planned:
            who = folder.client_user.get_full_name() or folder.client_user.email
            self.stdout.write(f'  adoptar  carpeta {folder.pk} «{folder.name}» → {who}')
        for folder, reason in skipped:
            self.stdout.write(f'  saltar   carpeta {folder.pk} «{folder.name}» — {reason}')

        if not apply_changes:
            self.stdout.write(
                f'Dry-run: {len(planned)} por adoptar, {len(skipped)} saltada(s). '
                'Nada se escribió. Repetí con --apply.'
            )
            return

        adopted = 0
        with transaction.atomic():
            for folder in planned:
                adopt_client_folder(folder, folder.client_user)
                adopted += 1
        self.stdout.write(self.style.SUCCESS(
            f'{adopted} carpeta(s) adoptada(s); {len(skipped)} saltada(s).'
        ))
