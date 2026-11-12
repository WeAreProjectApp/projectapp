"""Workers receive challenge IDs only; the OTP exists only during SMTP delivery."""
import logging
import secrets

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import periodic_task, task

from accounts.access_models import AccessRateBucket, LoginChallenge
from accounts.services.access import digest, eligible, identity_digest
from content.services.email_delivery_service import DeliveryClassification, EmailDeliveryGateway

logger = logging.getLogger(__name__)


@task(retries=0)
def deliver_login_code(challenge_id):
    from django.contrib.auth import get_user_model
    candidate = LoginChallenge.objects.filter(pk=challenge_id).first()
    if candidate is None or not candidate.user_id:
        return
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().select_related('profile').get(pk=candidate.user_id)
        challenge = LoginChallenge.objects.select_for_update().get(pk=challenge_id)
        if challenge.closed or challenge.code_digest or challenge.expires_at <= timezone.now() or not eligible(user, challenge.surface) or challenge.identity_digest != identity_digest(user):
            return
        code = f'{secrets.randbelow(1_000_000):06d}'
        challenge.code_digest = digest(f'{challenge.pk}:{code}')
        challenge.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        challenge.save(update_fields=['code_digest', 'expires_at'])
    from content.services.proposal_email_service import _build_design_context
    context = {**_build_design_context(), 'code': code, 'code_digits': list(code), 'device': challenge.device or 'Dispositivo no identificado', 'expiry_minutes': 10}
    try:
        sent = EmailDeliveryGateway.send_plain(
            subject='Tu código de acceso — ProjectApp',
            body=f'Tu código de acceso es {code}. Vence en 10 minutos. Dispositivo: {context["device"]}. Si no lo solicitaste, ignora este correo.',
            html_body=render_to_string('emails/login_code.html', context),
            from_email=settings.DEFAULT_FROM_EMAIL, recipients=[user.email],
            template_key='login_code', classification=DeliveryClassification.SECURITY,
        )
        if not sent:
            LoginChallenge.objects.filter(pk=challenge_id).update(closed=True, code_digest='')
    except Exception:
        LoginChallenge.objects.filter(pk=challenge_id).update(closed=True, code_digest='')
        logger.warning('Login code delivery failed challenge=%s code=ACCESS_DELIVERY_FAILED', challenge_id)


def enqueue_login_code(challenge_id):
    try:
        deliver_login_code(challenge_id)
    except Exception:
        LoginChallenge.objects.filter(pk=challenge_id).update(closed=True, code_digest='')
        logger.warning('Login code queue unavailable challenge=%s code=ACCESS_QUEUE_UNAVAILABLE', challenge_id)


@periodic_task(crontab(hour='4', minute='15'))
def cleanup_access_challenges():
    cutoff = timezone.now() - timezone.timedelta(days=1)
    LoginChallenge.objects.filter(expires_at__lt=cutoff).delete()
    AccessRateBucket.objects.filter(updated_at__lt=cutoff).delete()
