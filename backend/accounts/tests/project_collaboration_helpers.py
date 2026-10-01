"""Isolated project/actor fixtures for the P4 domain."""
from types import SimpleNamespace
from uuid import uuid4

from django.contrib.auth.models import User

from accounts.models import Project, UserProfile
from accounts.services import project_client_access as access, project_ideas as ideas


def context():
    admin = User.objects.create(username='ideas-admin', first_name='Equipo', is_staff=True)
    UserProfile.objects.create(user=admin, role='admin', is_onboarded=True)
    client = User.objects.create(username='ideas-client', first_name='Cliente')
    UserProfile.objects.create(user=client, role='client', is_onboarded=True)
    other = User.objects.create(username='ideas-other', first_name='Otra persona')
    UserProfile.objects.create(user=other, role='client', is_onboarded=True)
    project = Project.objects.create(name='Ideas de un proyecto', client=client)
    other_project = Project.objects.create(name='Otro proyecto', client=other)
    return SimpleNamespace(admin=admin, client=client, other=other, project=project, other_project=other_project)


def idea(c, *, actor=None, text='Conservar una sugerencia para el futuro'):
    return ideas.create_idea(c.project.pk, actor or c.client, {'text': text, 'request_id': str(uuid4())})


def enable(c, *fields):
    policy = access.get_policy(c.project.pk, c.admin)
    permissions = access.empty_matrix()
    for key in fields:
        environment, name = key.split('.')
        permissions[environment][name] = True
    return access.update_policy(c.project.pk, c.admin, {
        'expected_version': policy['version'], 'source_token': policy['source_token'], 'permissions': permissions})


def sources(c):
    from accounts.models import ProjectAdminAccess, ProjectAccessNote
    from accounts.services.credential_cipher import encrypt_secret
    c.project.production_url = 'https://client.example.test/'
    c.project.staging_url = 'https://qa.example.test/'
    c.project.repository_url = 'https://internal.example.test/repository'
    c.project.admin_url = 'https://legacy.example.test/admin/'
    c.project.save()
    production = ProjectAdminAccess.objects.create(
        project=c.project, environment='production', admin_url='https://client.example.test/admin/',
        admin_username='production-user', admin_password_encrypted=encrypt_secret('production-secret'))
    ProjectAccessNote.objects.create(project=c.project, title='Internal note',
                                    content_encrypted=encrypt_secret('Internal operations message'))
    return production
