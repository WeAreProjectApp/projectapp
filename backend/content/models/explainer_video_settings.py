from django.db import models


class ExplainerVideoSettings(models.Model):
    """
    Singleton with the panel switches that show or hide each explainer video
    in the client-facing views.

    A video is visible only when its switch is on AND a render exists for the
    visitor's language (see frontend/composables/useExplainerVideos.js). Shared
    catalog links add their own switch on top: the catalog switch governs.

    Usage:
        settings = ExplainerVideoSettings.load()
        settings.show_financing_video  # → True | False
    """

    show_additional_modules_video = models.BooleanField(default=True)
    show_financing_video = models.BooleanField(default=True)
    show_proposal_video = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Explainer video settings'
        verbose_name_plural = 'Explainer video settings'

    def __str__(self):
        return (
            'ExplainerVideoSettings — '
            f'catálogo {"visible" if self.show_additional_modules_video else "oculto"}, '
            f'alianza {"visible" if self.show_financing_video else "oculto"}, '
            f'propuestas {"visible" if self.show_proposal_video else "oculto"}'
        )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Return the singleton instance, creating it if needed."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
