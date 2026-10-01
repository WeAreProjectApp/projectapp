"""Business rules for secure project URLs, credentials, and notes."""

from content.services.entity_history import historical_write
from django.db import transaction

from accounts.models import Project, ProjectAccessNote, ProjectAdminAccess
from accounts.services.credential_cipher import decrypt_secret, encrypt_secret


class ProjectAccessConflict(ValueError):
    """A legacy classification would overwrite existing environment data."""


class ProjectAccessSecretMissing(ValueError):
    """The requested password or note secret no longer exists."""


def _actor_label(user):
    if not user:
        return ''
    return user.get_full_name().strip() or user.email or user.username


def _serialize_note(note):
    return {
        'id': note.pk,
        'title': note.title,
        'content': '' if note.is_sensitive else decrypt_secret(note.content_encrypted),
        'has_content': bool(note.content_encrypted),
        'is_sensitive': note.is_sensitive,
        'created_at': note.created_at,
        'updated_at': note.updated_at,
        'updated_by': _actor_label(note.updated_by),
    }


def serialize_project_access(project):
    """Return the complete non-secret editor payload for one project."""
    access_by_environment = {
        access.environment: access
        for access in project.admin_accesses.all()
    }
    site_urls = {
        ProjectAdminAccess.Environment.PRODUCTION: project.production_url,
        ProjectAdminAccess.Environment.STAGING: project.staging_url,
    }
    environments = []
    for environment, label in ProjectAdminAccess.Environment.choices:
        access = access_by_environment.get(environment)
        environments.append({
            'environment': environment,
            'label': label,
            'site_url': site_urls[environment],
            'admin_url': access.admin_url if access else '',
            'admin_username': access.admin_username if access else '',
            'has_password': bool(access and access.admin_password_encrypted),
            'updated_at': access.updated_at if access else None,
            'updated_by': _actor_label(access.updated_by) if access else '',
        })

    has_legacy_access = bool(
        project.admin_url
        or project.admin_username
        or project.admin_password_encrypted
    )
    legacy_access = None
    if has_legacy_access:
        legacy_access = {
            'admin_url': project.admin_url,
            'admin_username': project.admin_username,
            'has_password': bool(project.admin_password_encrypted),
            'status': 'unclassified',
        }

    client = project.client
    client_name = client.get_full_name().strip() or client.email
    return {
        'project': {
            'id': project.pk,
            'name': project.name,
            'client_name': client_name,
        },
        'repository_url': project.repository_url,
        'environments': environments,
        'notes': [_serialize_note(note) for note in project.access_notes.all()],
        'legacy_access': legacy_access,
    }


@historical_write
def update_access_field(project, validated_data, actor):
    Project.objects.select_for_update().get(pk=project.pk)
    field = validated_data['field']
    value = validated_data[field]
    if field == 'repository_url':
        project.repository_url = value
        project.save(update_fields=['repository_url', 'updated_at'])
        return

    environment = validated_data['environment']
    from accounts.services.project_client_access import revoke_grants
    revoke_grants(project, actor=actor, fields=[f'{environment}.{field}'])
    if field == 'site_url':
        model_field = (
            'production_url'
            if environment == ProjectAdminAccess.Environment.PRODUCTION
            else 'staging_url'
        )
        setattr(project, model_field, value)
        project.save(update_fields=[model_field, 'updated_at'])
        return

    access, _ = ProjectAdminAccess.objects.get_or_create(
        project=project,
        environment=environment,
    )
    model_field = field
    if field == 'admin_password':
        model_field = 'admin_password_encrypted'
        value = encrypt_secret(value)
    setattr(access, model_field, value)
    access.updated_by = actor
    access.save(update_fields=[model_field, 'updated_by', 'updated_at'])


def reveal_environment_password(project, environment):
    access = project.admin_accesses.filter(environment=environment).first()
    if not access or not access.admin_password_encrypted:
        raise ProjectAccessSecretMissing('No hay una contraseña guardada para este ambiente.')
    return decrypt_secret(access.admin_password_encrypted)


@historical_write
def delete_environment_password(project, environment, actor):
    Project.objects.select_for_update().get(pk=project.pk)
    from accounts.services.project_client_access import revoke_grants
    revoke_grants(project, actor=actor, fields=[f'{environment}.admin_password'])
    access = project.admin_accesses.filter(environment=environment).first()
    if not access or not access.admin_password_encrypted:
        return
    access.admin_password_encrypted = ''
    access.updated_by = actor
    access.save(update_fields=['admin_password_encrypted', 'updated_by', 'updated_at'])


@historical_write
def create_note(project, validated_data, actor):
    return ProjectAccessNote.objects.create(
        project=project,
        title=validated_data['title'],
        content_encrypted=encrypt_secret(validated_data['content']),
        is_sensitive=validated_data['is_sensitive'],
        created_by=actor,
        updated_by=actor,
    )


@historical_write
def update_note(note, validated_data, actor):
    update_fields = ['updated_by', 'updated_at']
    if 'title' in validated_data:
        note.title = validated_data['title']
        update_fields.append('title')
    if 'content' in validated_data:
        note.content_encrypted = encrypt_secret(validated_data['content'])
        update_fields.append('content_encrypted')
    if 'is_sensitive' in validated_data:
        note.is_sensitive = validated_data['is_sensitive']
        update_fields.append('is_sensitive')
    note.updated_by = actor
    note.save(update_fields=update_fields)
    return note


def reveal_note_content(note):
    if not note.content_encrypted:
        raise ProjectAccessSecretMissing('La nota ya no tiene contenido guardado.')
    return decrypt_secret(note.content_encrypted)


@historical_write
@transaction.atomic
def classify_legacy_access(project, environment, actor):
    locked_project = project.__class__.objects.select_for_update().get(pk=project.pk)
    legacy_values = {
        'admin_url': locked_project.admin_url,
        'admin_username': locked_project.admin_username,
        'admin_password_encrypted': locked_project.admin_password_encrypted,
    }
    if not any(legacy_values.values()):
        raise ProjectAccessSecretMissing('Este proyecto ya no tiene un acceso anterior por clasificar.')

    access, _ = ProjectAdminAccess.objects.select_for_update().get_or_create(
        project=locked_project,
        environment=environment,
    )
    conflicts = [
        field for field, legacy_value in legacy_values.items()
        if legacy_value and getattr(access, field)
    ]
    if conflicts:
        raise ProjectAccessConflict(
            'El ambiente elegido ya tiene datos en los campos que se intenta clasificar.'
        )

    update_fields = ['updated_by', 'updated_at']
    for field, legacy_value in legacy_values.items():
        if legacy_value:
            setattr(access, field, legacy_value)
            update_fields.append(field)
    access.updated_by = actor
    access.save(update_fields=update_fields)

    locked_project.admin_url = ''
    locked_project.admin_username = ''
    locked_project.admin_password_encrypted = ''
    locked_project.save(update_fields=[
        'admin_url', 'admin_username', 'admin_password_encrypted', 'updated_at',
    ])
    return locked_project
