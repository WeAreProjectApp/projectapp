"""Project suggestions remain separate from contractual delivery."""

from accounts.retention import RetainedProjectModel
import uuid

from django.conf import settings
from django.db import models


class ProjectIdea(RetainedProjectModel, models.Model):
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, related_name='ideas', null=True, blank=True)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    author_label = models.CharField(max_length=255)
    origin = models.CharField(max_length=10, choices=[('client', 'Cliente'), ('team', 'Equipo')])
    text = models.TextField()
    revision_number = models.PositiveIntegerField(default=1)
    version = models.PositiveIntegerField(default=1)
    request_id = models.UUIDField(default=uuid.uuid4)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(fields=['project', 'author', 'request_id'], name='idea_author_request_unique')]
        indexes = [models.Index(fields=['project', 'recipient', '-created_at'], name='idea_project_recipient')]


class ProjectIdeaRevision(models.Model):
    idea = models.ForeignKey(ProjectIdea, on_delete=models.CASCADE, related_name='revisions')
    number = models.PositiveIntegerField()
    text = models.TextField()
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    editor_label = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['idea', 'number'], name='idea_revision_unique')]


class ProjectIdeaCollection(RetainedProjectModel, models.Model):
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, related_name='idea_collections', null=True, blank=True)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    creator_label = models.CharField(max_length=255)
    request_id = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(fields=['project', 'created_by', 'request_id'], name='idea_collection_request_unique')]


class ProjectIdeaCollectionItem(models.Model):
    collection = models.ForeignKey(ProjectIdeaCollection, on_delete=models.CASCADE, related_name='items')
    idea = models.ForeignKey(ProjectIdea, on_delete=models.PROTECT, related_name='collection_items')
    revision_number = models.PositiveIntegerField()
    source_version = models.PositiveIntegerField()
    position = models.PositiveIntegerField()
    text = models.TextField()
    author_label = models.CharField(max_length=255)
    idea_created_at = models.DateTimeField()

    class Meta:
        ordering = ['position']
        constraints = [models.UniqueConstraint(fields=['collection', 'idea'], name='collection_idea_unique')]
