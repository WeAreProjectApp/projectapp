import secrets
import string

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.template.loader import render_to_string

from accounts.models import UserProfile
from content.services.email_delivery_service import (
    DeliveryClassification,
    EmailDeliveryGateway,
)

User = get_user_model()

TEMP_PASSWORD_LENGTH = 16


def generate_temp_password():
    """Generate a secure temporary password."""
    alphabet = string.ascii_letters + string.digits + '!@#$%'
    return ''.join(secrets.choice(alphabet) for _ in range(TEMP_PASSWORD_LENGTH))


@transaction.atomic
def create_client(*, email, first_name, last_name, company_name='', phone='', created_by=None):
    """
    Create a new client user with a temporary password and send an invitation email.
    Returns (user, temp_password).
    """
    email = email.lower().strip()

    if User.objects.filter(Q(email=email) | Q(username=email)).exists():
        raise ValueError(f'Ya existe un usuario con el email {email}')

    temp_password = generate_temp_password()

    user = User.objects.create_user(
        username=email,
        email=email,
        password=temp_password,
        first_name=first_name,
        last_name=last_name,
        is_active=False,
    )

    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=False,
        company_name=company_name,
        phone=phone,
        created_by=created_by,
    )

    _send_invitation_email(user, temp_password)

    return user, temp_password


def resend_invitation(user):
    """Reset the user's password to a new temp and resend invitation."""
    temp_password = generate_temp_password()
    user.set_password(temp_password)
    user.save(update_fields=['password'])

    profile = user.profile
    profile.is_onboarded = False
    profile.save(update_fields=['is_onboarded'])

    if profile.role == UserProfile.ROLE_ADMIN:
        _send_admin_invitation_email(user, temp_password)
    else:
        _send_invitation_email(user, temp_password)
    return temp_password


@transaction.atomic
def create_admin(*, email, first_name, last_name, created_by=None):
    """
    Create a new platform admin with a temporary password and send an invitation email.
    Returns (user, temp_password).
    """
    email = email.lower().strip()

    if User.objects.filter(Q(email=email) | Q(username=email)).exists():
        raise ValueError(f'Ya existe un usuario con el email {email}')

    temp_password = generate_temp_password()

    user = User.objects.create_user(
        username=email,
        email=email,
        password=temp_password,
        first_name=first_name,
        last_name=last_name,
        is_active=True,
    )

    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=False,
        profile_completed=True,
        created_by=created_by,
    )

    _send_admin_invitation_email(user, temp_password)

    return user, temp_password


def _send_invitation_email(user, temp_password):
    """Send the invitation email with temporary credentials."""
    platform_url = f'{settings.FRONTEND_BASE_URL}/platform/login'

    from content.services.proposal_email_service import _build_design_context

    subject = 'Bienvenido a ProjectApp — Tu acceso a la plataforma'
    invitation_context = {
        'user': user,
        'temp_password': temp_password,
        'platform_url': platform_url,
    }
    invitation_context.update(_build_design_context())
    html_message = render_to_string('emails/invitation.html', invitation_context)

    EmailDeliveryGateway.send_plain(
        subject=subject,
        body=(
            f'Hola {user.first_name},\n\n'
            f'Tu cuenta en ProjectApp ha sido creada.\n'
            f'Email: {user.email}\n'
            f'Contraseña temporal: {temp_password}\n\n'
            f'Ingresa aquí: {platform_url}\n\n'
            f'Al iniciar sesión por primera vez, te pediremos verificar tu email '
            f'y configurar tu contraseña definitiva.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipients=[user.email],
        html_body=html_message,
        template_key='client_invitation',
        classification=DeliveryClassification.SECURITY,
        fail_silently=False,
    )


def _send_admin_invitation_email(user, temp_password):
    """Send the admin invitation email with temporary credentials."""
    platform_url = f'{settings.FRONTEND_BASE_URL}/platform/login'

    subject = 'ProjectApp — Has sido agregado como administrador'
    html_message = render_to_string('emails/admin_invitation.html', {
        'user': user,
        'temp_password': temp_password,
        'platform_url': platform_url,
    })

    EmailDeliveryGateway.send_plain(
        subject=subject,
        body=(
            f'Hola {user.first_name},\n\n'
            f'Has sido agregado como administrador en ProjectApp.\n'
            f'Email: {user.email}\n'
            f'Contraseña temporal: {temp_password}\n\n'
            f'Ingresa aquí: {platform_url}\n\n'
            f'Al iniciar sesión por primera vez, te pediremos verificar tu email '
            f'y configurar tu contraseña definitiva.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipients=[user.email],
        html_body=html_message,
        template_key='admin_invitation',
        classification=DeliveryClassification.SECURITY,
        fail_silently=False,
    )
