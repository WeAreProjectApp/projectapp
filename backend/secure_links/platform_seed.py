"""Fictitious owned-link states for development; no outgoing notifications."""

from datetime import timedelta

from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model
from django.utils import timezone
from content.fake_data import ensure_fake_data_allowed, seed_context
from content.services.project_state_service import ensure_initial_project_state
from .fake_data import stamp_link

from . import platform_services, services
from .models import SecureLink


def create_platform_samples(context=None):
    ensure_fake_data_allowed('create_platform_samples')
    context = context or seed_context({}, 'secure-links')
    for number in (1, 2):
        user, created = get_user_model().objects.get_or_create(
            username=f'secure-platform-demo-{number}', defaults={
                'first_name': f'Cliente demo {number}', 'is_active': True,
                'email': f'secure-platform-demo-{number}@example.test'},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=['password'])
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.ROLE_CLIENT
        profile.is_onboarded = True
        profile.save(update_fields=['role', 'is_onboarded'])
        project, _ = Project.objects.get_or_create(client=user, name=f'Secure links demo {number}')
        ensure_initial_project_state(project)
        for state in SecureLink.STATUSES:
            link, url, replayed = platform_services.create_owned_link(
                owner_id=profile.pk, project_id=project.pk, actor=user,
                request_id=context.uuid(f'platform:{number}:{state}'),
                title=f'Demo {number} — {state}', secret_type='credentials', fields={'password': 'demo-only-not-a-real-secret'},
            )
            if replayed:
                continue
            if state == 'consumed':
                services.reveal(url.split('#', 1)[1], staff=True)
            elif state == 'expired':
                SecureLink.objects.filter(pk=link.pk).update(expires_at=timezone.now() - timedelta(days=1))
            elif state == 'revoked':
                services.revoke(link, actor=user)
                platform_services.create_owned_link(
                    owner_id=profile.pk, project_id=project.pk, actor=user, replaces=link.pk,
                    request_id=context.uuid(f'platform:{number}:replacement'),
                    title=f'Demo {number} — replacement', secret_type='confidential_message',
                    fields={'message': 'Contenido ficticio corregido para el equipo.'},
                )
            stamp_link(link, context, state)
        for replacement in SecureLink.objects.filter(project=project, title=f'Demo {number} — replacement'):
            stamp_link(replacement, context, 'ready')
