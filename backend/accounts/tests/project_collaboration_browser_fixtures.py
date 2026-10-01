"""Representative P4 fixtures for a disposable test database only."""
import secrets
from types import SimpleNamespace
from uuid import uuid4

from django.contrib.auth.models import User
from django.middleware.csrf import _get_new_csrf_string
from rest_framework.test import APIClient

from accounts.models import Project, UserProfile
from accounts.services import project_ideas as ideas
from accounts.tests.project_collaboration_helpers import sources, enable


def create_browser_fixture(key, grants):
    suffix = secrets.token_hex(5)
    password = secrets.token_urlsafe(24)
    actors = {}
    login = {}
    for role in ('admin', 'client', 'other'):
        email = f'p4-{role}-{suffix}@example.test'
        actor = User.objects.create_user(username=email, email=email, password=password,
                                        first_name='Equipo' if role == 'admin' else 'Cliente', is_staff=role == 'admin')
        UserProfile.objects.update_or_create(user=actor, defaults={
            'role': 'admin' if role == 'admin' else 'client', 'is_onboarded': True,
            'profile_completed': True, 'email_verified': True})
        actors[role] = actor
        login[role] = {'email': email, 'password': password}
    project = Project.objects.create(name=f'Ideas {key}', client=actors['client'])
    other = Project.objects.create(name=f'Otro proyecto {key}', client=actors['other'])
    context = SimpleNamespace(project=project, **actors)
    sources(context)
    if grants:
        enable(context, *grants)
    original = ideas.create_idea(project.pk, actors['client'], {
        'text': 'Un tablero de inventario para evaluar después', 'request_id': str(uuid4())})
    panel = APIClient()
    panel.force_login(actors['admin'])
    return {**login, 'project': {'id': project.pk, 'name': project.name}, 'other_project_id': other.pk,
            'idea': {'id': original['id'], 'text': original['text']},
            'panel_session': panel.cookies['sessionid'].value, 'csrf_token': _get_new_csrf_string()}
