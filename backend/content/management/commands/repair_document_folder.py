"""Preview an exact folder repair; apply only the reviewed manifest."""

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from content.services.document_folder_repair import (
    FolderRepairError,
    apply_repair,
    fingerprint,
    prepare_repair,
)


class Command(BaseCommand):
    help = "Repara una carpeta duplicada. Previsualización por defecto; --apply usa un manifiesto revisado."

    def add_arguments(self, parser):
        parser.add_argument("--source-folder-id", type=int)
        parser.add_argument("--target-folder-id", type=int)
        parser.add_argument("--client-profile-id", type=int)
        parser.add_argument("--document-ids", type=int, nargs="+")
        parser.add_argument("--manifest", required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--sha256")
        parser.add_argument("--actor-id", type=int)
        parser.add_argument("--backup-ref")
        parser.add_argument("--creation-request-id")

    def handle(self, *args, **options):
        path = Path(options["manifest"])
        try:
            if options["apply"]:
                # Never run an operational write from a session worktree.
                from django.conf import settings

                if ".wt" in Path(settings.BASE_DIR).parts:
                    raise CommandError(
                        "Aplica desde el entorno de despliegue, nunca desde un worktree."
                    )
                if (
                    not options["sha256"]
                    or not options["actor_id"]
                    or not options["backup_ref"]
                ):
                    raise CommandError(
                        "--apply requiere --sha256, --actor-id y --backup-ref."
                    )
                backup = Path(options["backup_ref"])
                if not backup.is_file() or not backup.stat().st_size:
                    raise CommandError("El respaldo indicado no existe o está vacío.")
                actor = get_user_model().objects.get(pk=options["actor_id"])
                result = apply_repair(
                    json.loads(path.read_text()),
                    expected_hash=options["sha256"],
                    actor=actor,
                    backup_ref=str(backup.resolve()),
                )
                self.stdout.write(json.dumps(result))
                return
            required = (
                "source_folder_id",
                "target_folder_id",
                "client_profile_id",
                "document_ids",
            )
            if any(not options[key] for key in required):
                raise CommandError(
                    "La previsualización requiere ambas carpetas, perfil e IDs exactos de documentos."
                )
            manifest = prepare_repair(
                *(options[key] for key in required),
                creation_request_id=options["creation_request_id"],
            )
            # Refuse to replace a reviewed artifact accidentally.
            with path.open("x", encoding="utf-8") as output:
                json.dump(manifest, output, indent=2)
                output.write("\n")
            self.stdout.write(
                json.dumps(
                    {
                        "apply": False,
                        "manifest": str(path),
                        "sha256": fingerprint(manifest),
                    }
                )
            )
        except (
            FolderRepairError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            get_user_model().DoesNotExist,
        ) as exc:
            raise CommandError(str(exc)) from exc
