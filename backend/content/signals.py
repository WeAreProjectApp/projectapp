"""
post_delete signals: remove physical files from storage when DB records are deleted.
Prevents orphaned public images after hard deletes. Document and statement
PDFs are retained for immutable history.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from content.models.blog_post import BlogPost
from content.models.issuer_profile import IssuerProfile
from content.models.portfolio_works import PortfolioWork
from content.models.document import Document


def _delete_file(field):
    """Delete a FileField/ImageField file from storage if it has a value."""
    from content.services.project_file_cleanup import project_cleanup_active
    if project_cleanup_active():
        return
    if field and field.name:
        try:
            field.storage.delete(field.name)
        except Exception:
            pass


@receiver(post_delete, sender=BlogPost)
def delete_blog_post_files(sender, instance, **kwargs):
    _delete_file(instance.cover_image)


@receiver(post_delete, sender=PortfolioWork)
def delete_portfolio_work_files(sender, instance, **kwargs):
    _delete_file(instance.cover_image)


@receiver(post_delete, sender=IssuerProfile)
def delete_issuer_profile_files(sender, instance, **kwargs):
    _delete_file(instance.logo)


@receiver(post_save, sender=Document)
def initialize_document_workflow(sender, instance, created, raw=False, **kwargs):
    """Seed the workflow for every new generic document write path."""
    if not created or raw:
        return
    from content.services.document_note_service import sync_legacy_notes
    from content.services.document_state_service import ensure_initial_state

    actor = instance.created_by
    ensure_initial_state(instance, actor=actor)
    sync_legacy_notes(instance, actor=actor)
