"""Opt-in format metadata; historical fields keep their original meaning."""
from django.db import models


class EditorialTextModel(models.Model):
    text_formats = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True
