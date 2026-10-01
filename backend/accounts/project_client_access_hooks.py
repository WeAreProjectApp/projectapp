"""Revoke grants on real source changes, including non-editor model writers."""
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from accounts.models import Project, ProjectAdminAccess
from content.models.entity_history import EntityRevision


@receiver(pre_save, sender=Project, dispatch_uid='client_access_capture_project')
def capture_project_source(sender, instance, **kwargs):
    instance._client_access_previous = sender.objects.filter(pk=instance.pk).values('client_id', 'production_url', 'staging_url').first()


@receiver(post_save, sender=Project, dispatch_uid='client_access_revoke_project')
def revoke_project_source(sender, instance, created, **kwargs):
    previous = getattr(instance, '_client_access_previous', None)
    if created or not previous:
        return
    from accounts.services.project_client_access import revoke_grants
    updated = kwargs.get('update_fields')
    if (updated is None or 'client' in updated or 'client_id' in updated) and previous['client_id'] != instance.client_id:
        revoke_grants(instance)
        return
    changed = [f'{environment}.site_url' for environment, name in [('production', 'production_url'), ('staging', 'staging_url')]
               if (updated is None or name in updated) and previous[name] != getattr(instance, name)]
    if changed:
        revoke_grants(instance, fields=changed)


@receiver(pre_save, sender=ProjectAdminAccess, dispatch_uid='client_access_capture_admin')
def capture_admin_source(sender, instance, **kwargs):
    instance._client_access_previous = sender.objects.filter(pk=instance.pk).values('project_id', 'environment', 'admin_url', 'admin_username', 'admin_password_encrypted').first()


@receiver(post_save, sender=ProjectAdminAccess, dispatch_uid='client_access_revoke_admin')
def revoke_admin_source(sender, instance, created, **kwargs):
    previous = getattr(instance, '_client_access_previous', None)
    if created or not previous:
        return
    from accounts.services.project_client_access import revoke_grants
    updated = kwargs.get('update_fields')
    moved_project = (updated is None or 'project' in updated or 'project_id' in updated) and previous['project_id'] != instance.project_id
    moved_environment = (updated is None or 'environment' in updated) and previous['environment'] != instance.environment
    if moved_project or moved_environment:
        previous_project = Project.objects.get(pk=previous['project_id'])
        revoke_grants(previous_project, fields=[f"{previous['environment']}.{field}" for field in ('admin_url', 'admin_username', 'admin_password')])
        revoke_grants(instance.project, fields=[f'{instance.environment}.{field}' for field in ('admin_url', 'admin_username', 'admin_password')])
        return
    changed = [f'{instance.environment}.{field}' for field, name in [('admin_url', 'admin_url'), ('admin_username', 'admin_username'), ('admin_password', 'admin_password_encrypted')]
               if (updated is None or name in updated) and previous[name] != getattr(instance, name)]
    if changed:
        revoke_grants(instance.project, fields=changed)


@receiver(post_delete, sender=ProjectAdminAccess, dispatch_uid='client_access_revoke_deleted_admin')
def revoke_deleted_admin_source(sender, instance, **kwargs):
    from accounts.services.project_client_access import revoke_grants
    revoke_grants(instance.project, fields=[f'{instance.environment}.{field}' for field in ('admin_url', 'admin_username', 'admin_password')])


@receiver(post_save, sender=EntityRevision, dispatch_uid='client_access_revoke_historical_writes')
def revoke_historical_sources(sender, instance, created, **kwargs):
    """HistoryQuerySet already observes bulk writes; consume its field names only."""
    if not created or instance.action != 'updated' or instance.history.entity_type != 'project':
        return
    project = Project.objects.filter(pk=instance.history.object_id).first()
    if not project:
        return
    from accounts.services.project_client_access import revoke_grants
    changed = {entry['field'] for entry in instance.changed_fields}
    if 'client' in changed:
        revoke_grants(project)
        return
    targets = []
    for name in changed:
        if name in ('production_url', 'staging_url'):
            targets.append(f"{'production' if name == 'production_url' else 'staging'}.site_url")
        parts = name.split('.')
        if len(parts) >= 2 and parts[0] == 'access' and parts[1] in ('production', 'staging'):
            fields = ('admin_url', 'admin_username', 'admin_password') if len(parts) == 2 else (
                ('admin_password' if parts[2] == 'password' else parts[2]),)
            targets.extend(f'{parts[1]}.{field}' for field in fields if field in ('admin_url', 'admin_username', 'admin_password'))
    if targets:
        revoke_grants(project, fields=sorted(set(targets)))
