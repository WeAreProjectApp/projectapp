"""Resolve an estimate destination by identity without provisioning folders."""

from content.models import DocumentFolder
from django.conf import settings
from django.core.management.base import CommandError


def resolve_estimate_folder(*, folder_id=None, folder_name=None):
    if folder_id is not None and folder_name is not None:
        raise CommandError("Usa --folder-id o --folder, no ambos.")
    if folder_name is not None:
        matches = list(
            DocumentFolder.objects.filter(name__iexact=folder_name.strip())[:2]
        )
        if len(matches) != 1:
            raise CommandError(
                "El nombre no identifica una única carpeta. Usa --folder-id."
            )
        folder = matches[0]
    else:
        folder_id = folder_id or getattr(
            settings, "REQUIREMENT_ESTIMATES_FOLDER_ID", None
        )
        if not folder_id:
            raise CommandError(
                "Configura REQUIREMENT_ESTIMATES_FOLDER_ID o indica --folder-id."
            )
        folder = DocumentFolder.objects.filter(pk=folder_id).first()
        if folder is None:
            raise CommandError("La carpeta configurada no existe.")
    if folder.is_archived or folder.is_system_managed:
        raise CommandError("La carpeta configurada está archivada o protegida.")
    return folder
