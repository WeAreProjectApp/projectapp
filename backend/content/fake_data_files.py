"""Local fixture files and commit-aware cleanup for management commands."""

from contextlib import contextmanager
from io import BytesIO

from django.db import transaction
from django.db.models.signals import post_save, pre_delete

from content.services.project_file_cleanup import (
    deferred_project_cleanup,
    project_cleanup_active,
    project_row_files,
    schedule_project_files,
)


def sample_pdf(name, text='ProjectApp - documento ficticio, sin valor comercial'):
    """Return a real, reproducible PDF; a filename alone is not a fixture."""
    from django.core.files.base import ContentFile
    from reportlab.pdfgen.canvas import Canvas

    output = BytesIO()
    canvas = Canvas(output, invariant=1)
    canvas.drawString(40, 800, text)
    canvas.save()
    return ContentFile(output.getvalue(), name=name)


def sample_file(name):
    from django.core.files.base import ContentFile
    if name.lower().endswith('.pdf'):
        return sample_pdf(name)
    return ContentFile(b'ProjectApp: archivo ficticio local. Sin credenciales ni datos reales.\n', name=name)


@contextmanager
def fake_data_transaction():
    """Keep old files through rollback; remove replaced files only on commit.

    Nested seed/reset commands share the outer tracker. All receivers are
    removed before returning; normal application writes keep their behavior.
    New files are collected after save, including PDFs written by real services.
    """
    if project_cleanup_active():
        with transaction.atomic():
            yield
        return

    created_files, removed_files = [], []

    def collect_save(sender, instance, **kwargs):
        created_files.extend(project_row_files(instance))

    def collect_delete(sender, instance, **kwargs):
        removed_files.extend(project_row_files(instance))

    post_save.connect(collect_save, weak=False)
    pre_delete.connect(collect_delete, weak=False)
    try:
        with deferred_project_cleanup(), transaction.atomic():
            yield
            # Uploading several resource versions can supersede a current-file
            # path without deleting its row. Retain the final references only.
            schedule_project_files([*removed_files, *created_files])
    except BaseException:
        # The failed savepoint is already gone. The shared cleanup protects
        # every path still referenced by restored rows, including reused files.
        schedule_project_files(created_files)
        raise
    finally:
        post_save.disconnect(collect_save)
        pre_delete.disconnect(collect_delete)
