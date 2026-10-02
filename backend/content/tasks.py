"""
Huey tasks for the business proposal feature.

Tasks:
  - send_proposal_reminder: Send reminder email N days after proposal was sent.
  - expire_stale_proposals: Daily task to mark expired proposals.
"""

import logging
from datetime import timedelta

from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import lock_task, periodic_task, task

from accounts.models import UserProfile
from content.services.proposal_email_service import _is_unsendable_client_email

logger = logging.getLogger(__name__)


@task()
def send_proposal_reminder(proposal_id):
    """
    Huey task: send reminder email N days after proposal was sent.

    Skips if:
    - Proposal not found
    - Status is not SENT or VIEWED
    - No client_email set
    - Reminder already sent (reminder_sent_at is not null)
    """
    from content.models import BusinessProposal
    from content.services.proposal_email_service import ProposalEmailService

    try:
        proposal = BusinessProposal.objects.get(pk=proposal_id)
    except BusinessProposal.DoesNotExist:
        logger.warning('Proposal %s not found for reminder task.', proposal_id)
        return

    if proposal.automations_paused:
        logger.info(
            'Skipping reminder for proposal %s: automations paused',
            proposal.uuid,
        )
        return

    if proposal.status not in ('sent', 'viewed'):
        logger.info(
            'Skipping reminder for proposal %s: status is %s',
            proposal.uuid, proposal.status,
        )
        return

    if _is_unsendable_client_email(proposal.client_email):
        logger.info(
            'Skipping reminder for proposal %s: missing or placeholder client_email',
            proposal.uuid,
        )
        return

    if proposal.reminder_sent_at is not None:
        logger.info(
            'Skipping reminder for proposal %s: already sent at %s',
            proposal.uuid, proposal.reminder_sent_at,
        )
        return

    ProposalEmailService.send_reminder(proposal)


@task()
def send_urgency_reminder(proposal_id):
    """
    Huey task: send urgency/discount email at day 15 after proposal was sent.

    Skips if:
    - Proposal not found
    - Status is not SENT or VIEWED
    - No client_email set
    - Urgency email already sent (urgency_email_sent_at is not null)
    """
    from content.models import BusinessProposal
    from content.services.proposal_email_service import ProposalEmailService

    try:
        proposal = BusinessProposal.objects.get(pk=proposal_id)
    except BusinessProposal.DoesNotExist:
        logger.warning('Proposal %s not found for urgency task.', proposal_id)
        return

    if proposal.automations_paused:
        logger.info(
            'Skipping urgency for proposal %s: automations paused',
            proposal.uuid,
        )
        return

    if proposal.status not in ('sent', 'viewed'):
        logger.info(
            'Skipping urgency for proposal %s: status is %s',
            proposal.uuid, proposal.status,
        )
        return

    if _is_unsendable_client_email(proposal.client_email):
        logger.info(
            'Skipping urgency for proposal %s: missing or placeholder client_email',
            proposal.uuid,
        )
        return

    if proposal.urgency_email_sent_at is not None:
        logger.info(
            'Skipping urgency for proposal %s: already sent at %s',
            proposal.uuid, proposal.urgency_email_sent_at,
        )
        return

    if proposal.discount_percent and proposal.discount_percent > 0:
        # Discount offers are never auto-sent; the seller sends them manually
        # via the "Enviar oferta de descuento" proposal action.
        logger.info(
            'Skipping urgency for proposal %s: discount emails are sent manually',
            proposal.uuid,
        )
        return

    ProposalEmailService.send_urgency_email(proposal)


@task()
def send_rejection_reengagement(proposal_id):
    """
    Huey task: send re-engagement email 48h after a budget-related rejection.

    Skips if:
    - Proposal not found
    - Status is not REJECTED
    - No client_email set
    - Re-engagement email already sent (ProposalChangeLog entry exists)
    """
    from content.models import BusinessProposal, ProposalChangeLog
    from content.services.proposal_email_service import ProposalEmailService

    try:
        proposal = BusinessProposal.objects.get(pk=proposal_id)
    except BusinessProposal.DoesNotExist:
        logger.warning(
            'Proposal %s not found for re-engagement task.', proposal_id
        )
        return

    if proposal.status != 'rejected':
        logger.info(
            'Skipping re-engagement for proposal %s: status is %s',
            proposal.uuid, proposal.status,
        )
        return

    if _is_unsendable_client_email(proposal.client_email):
        logger.info(
            'Skipping re-engagement for proposal %s: missing or placeholder client_email',
            proposal.uuid,
        )
        return

    already_sent = ProposalChangeLog.objects.filter(
        proposal=proposal,
        change_type='reengagement',
    ).exists()
    if already_sent:
        logger.info(
            'Skipping re-engagement for proposal %s: already sent',
            proposal.uuid,
        )
        return

    if proposal.discount_percent and proposal.discount_percent > 0:
        # Discount-bearing re-engagement is never auto-sent; the seller offers
        # the discount manually via the proposal action.
        logger.info(
            'Skipping re-engagement for proposal %s: discount emails are sent manually',
            proposal.uuid,
        )
        return

    success = ProposalEmailService.send_rejection_reengagement(proposal)
    if success:
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type='reengagement',
            actor_type='system',
            description='Re-engagement email sent 48h after budget rejection.',
        )


@periodic_task(crontab(hour='8', minute='0'))
def suggest_pre_expiration_discount():
    """
    Daily task: for proposals expiring within 5 days that were viewed but
    not responded and have no discount, create a discount_suggestion alert
    (if one doesn't already exist).
    """
    from datetime import timedelta

    from content.models import BusinessProposal, ProposalAlert

    now = timezone.now()
    candidates = BusinessProposal.objects.filter(
        status='viewed',
        is_active=True,
        discount_percent=0,
        responded_at__isnull=True,
        expires_at__isnull=False,
        expires_at__gt=now,
        expires_at__lte=now + timedelta(days=5),
    )

    created_count = 0
    for proposal in candidates:
        already_exists = ProposalAlert.objects.filter(
            proposal=proposal,
            alert_type='discount_suggestion',
            is_dismissed=False,
        ).exists()
        if not already_exists:
            days_left = (proposal.expires_at - now).days
            ProposalAlert.objects.create(
                proposal=proposal,
                alert_type='discount_suggestion',
                message=(
                    f'Expira en {days_left}d, vista pero sin respuesta. '
                    f'Considera activar descuento o re-enviar con nota personalizada.'
                ),
                alert_date=now,
            )
            created_count += 1

    if created_count > 0:
        logger.info(
            'Created %d pre-expiration discount suggestions.', created_count
        )


@periodic_task(crontab(hour='0', minute='30'))
def expire_stale_proposals():
    """
    Daily task: mark proposals as EXPIRED when expires_at < now().

    Only affects active proposals with status SENT or VIEWED.
    Auto-extends by 7 days if the client had recent activity (last 3 days).
    """
    from content.models import BusinessProposal, ProposalChangeLog
    from content.models import ProposalViewEvent

    now = timezone.now()
    candidates = BusinessProposal.objects.filter(
        status__in=['sent', 'viewed'],
        is_active=True,
        expires_at__lt=now,
    )

    expired = 0
    extended = 0
    for proposal in candidates:
        # Check for recent client activity (view event in last 3 days)
        recent_activity = ProposalViewEvent.objects.filter(
            proposal=proposal,
            viewed_at__gte=now - timedelta(days=3),
        ).exists()

        if recent_activity:
            # Auto-extend by 7 days
            proposal.expires_at = now + timedelta(days=7)
            proposal.save(update_fields=['expires_at'])
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='updated',
                actor_type='system',
                description=(
                    'Auto-extended expiration by 7 days due to recent client activity.'
                ),
            )
            extended += 1
        else:
            proposal.status = 'expired'
            proposal.save(update_fields=['status'])
            expired += 1

    if expired > 0:
        logger.info('Expired %d stale proposals.', expired)
    if extended > 0:
        logger.info('Auto-extended %d proposals with recent activity.', extended)


@periodic_task(crontab(hour='9', minute='0'))
def escalate_seller_inactivity():
    """
    Daily task: if a proposal has had no seller activity for >=5 days
    (sent/viewed, client has viewed), send an escalation email to the
    sales team. Only sends once per proposal (tracked via ProposalChangeLog).
    """
    from datetime import timedelta

    from content.models import BusinessProposal, ProposalChangeLog
    from content.services.proposal_email_service import ProposalEmailService

    now = timezone.now()
    five_days_ago = now - timedelta(days=5)
    seller_activity_types = {'call', 'meeting', 'followup', 'note'}

    candidates = BusinessProposal.objects.filter(
        status__in=['sent', 'viewed'],
        is_active=True,
        automations_paused=False,
        first_viewed_at__isnull=False,
    )

    escalated = 0
    for p in candidates:
        ref_date = p.last_activity_at or p.sent_at
        if not ref_date or ref_date > five_days_ago:
            continue

        has_recent = ProposalChangeLog.objects.filter(
            proposal=p,
            change_type__in=seller_activity_types,
            created_at__gte=five_days_ago,
        ).exists()
        if has_recent:
            continue

        already_escalated = ProposalChangeLog.objects.filter(
            proposal=p,
            change_type=ProposalChangeLog.ChangeType.SELLER_INACTIVITY_ESCALATION,
        ).exists()
        if already_escalated:
            continue

        days = (now - ref_date).days
        try:
            ProposalEmailService.send_seller_inactivity_escalation(p, days)
            ProposalChangeLog.objects.create(
                proposal=p,
                change_type=ProposalChangeLog.ChangeType.SELLER_INACTIVITY_ESCALATION,
                actor_type='system',
                description=f'Seller inactivity escalation sent after {days} days.',
            )
            escalated += 1
        except Exception:
            logger.exception(
                'Failed seller inactivity escalation for proposal %s',
                p.uuid,
            )

    if escalated > 0:
        logger.info('Escalated %d seller-inactive proposals.', escalated)


@periodic_task(crontab(hour='*/2', minute='15'))
def check_engagement_followups():
    """
    Periodic task (every 2 hours): check viewed proposals for
    engagement-based follow-up email triggers.

    1. Abandonment: client viewed but never reached investment section,
       and first view was >4h ago.
    2. Investment interest: client spent >60s on investment section,
       and last view was >2h ago.
    """
    from datetime import timedelta

    from django.db.models import Sum

    from content.models import (
        BusinessProposal, ProposalSectionView, ProposalViewEvent,
    )
    from content.services.proposal_email_service import ProposalEmailService

    now = timezone.now()
    four_hours_ago = now - timedelta(hours=4)
    two_hours_ago = now - timedelta(hours=2)

    # --- Abandonment follow-up ---
    abandonment_candidates = BusinessProposal.objects.filter(
        status='viewed',
        is_active=True,
        automations_paused=False,
        client_email__gt='',
        abandonment_email_sent_at__isnull=True,
        first_viewed_at__isnull=False,
        first_viewed_at__lt=four_hours_ago,
    ).exclude(client_email__iendswith=UserProfile.PLACEHOLDER_EMAIL_DOMAIN)

    for proposal in abandonment_candidates:
        visited_types = set(
            ProposalSectionView.objects
            .filter(view_event__proposal=proposal)
            .values_list('section_type', flat=True)
            .distinct()
        )
        if 'investment' not in visited_types:
            try:
                ProposalEmailService.send_abandonment_followup(proposal)
                logger.info(
                    'Sent abandonment followup for proposal %s',
                    proposal.uuid,
                )
            except Exception:
                logger.exception(
                    'Failed abandonment followup for proposal %s',
                    proposal.uuid,
                )

    # --- Investment interest follow-up ---
    interest_candidates = BusinessProposal.objects.filter(
        status='viewed',
        is_active=True,
        automations_paused=False,
        client_email__gt='',
        investment_interest_email_sent_at__isnull=True,
        first_viewed_at__isnull=False,
    ).exclude(client_email__iendswith=UserProfile.PLACEHOLDER_EMAIL_DOMAIN)

    for proposal in interest_candidates:
        last_event = (
            ProposalViewEvent.objects
            .filter(proposal=proposal)
            .order_by('-viewed_at')
            .first()
        )
        if not last_event or last_event.viewed_at > two_hours_ago:
            continue

        investment_time = (
            ProposalSectionView.objects
            .filter(
                view_event__proposal=proposal,
                section_type='investment',
            )
            .aggregate(total=Sum('time_spent_seconds'))
        )['total'] or 0

        if investment_time >= 60:
            try:
                ProposalEmailService.send_investment_interest_followup(
                    proposal, investment_time,
                )
                logger.info('Sent investment interest followup for proposal %s (time=%ds)', proposal.uuid, investment_time)
            except Exception:
                logger.exception(
                    'Failed investment interest followup for proposal %s',
                    proposal.uuid,
                )


@task()
def send_scheduled_followup(proposal_id):
    """
    Huey task: send a scheduled follow-up email for a previously
    rejected proposal (client asked to be reminded later).

    Skips if:
    - Proposal not found
    - No client_email set
    - No followup_scheduled_at set
    """
    from content.models import BusinessProposal
    from content.services.proposal_email_service import ProposalEmailService

    try:
        proposal = BusinessProposal.objects.get(pk=proposal_id)
    except BusinessProposal.DoesNotExist:
        logger.warning(
            'Proposal %s not found for scheduled followup task.',
            proposal_id,
        )
        return

    if _is_unsendable_client_email(proposal.client_email):
        logger.info(
            'Skipping scheduled followup for proposal %s: missing or placeholder client_email',
            proposal.uuid,
        )
        return

    if not proposal.followup_scheduled_at:
        logger.info(
            'Skipping scheduled followup for proposal %s: no scheduled date',
            proposal.uuid,
        )
        return

    ProposalEmailService.send_scheduled_followup(proposal)


@task()
def publish_single_scheduled_blog(post_id):
    """
    Publish a single scheduled blog post by id.

    Enqueued with eta=published_at from the blog create/update views so the
    post goes live (site + LinkedIn) within seconds of its scheduled time,
    without waiting for the 1-minute safety-net sweep.

    Safe to enqueue multiple times: re-entrant by design via the guards below.
    """
    from content.models import BlogPost
    from content.views.blog import auto_publish_blog_to_linkedin

    now = timezone.now()
    logger.info('[Sched-ETA] fired for post_id=%s now=%s', post_id, now)

    post = BlogPost.objects.filter(pk=post_id).first()
    if not post:
        logger.warning('[Sched-ETA] post %s no existe', post_id)
        return
    logger.info(
        '[Sched-ETA] post %s slug=%s is_published=%s published_at=%s',
        post_id, post.slug, post.is_published, post.published_at,
    )
    if post.is_published:
        logger.info('[Sched-ETA] post %s ya publicado, skip', post_id)
        return
    if not post.published_at:
        logger.info('[Sched-ETA] post %s sin published_at, skip', post_id)
        return
    if post.published_at > now:
        logger.info(
            '[Sched-ETA] post %s aún no es hora: published_at=%s > now=%s — skip',
            post_id, post.published_at, now,
        )
        return

    try:
        updated = BlogPost.objects.filter(pk=post.id, is_published=False).update(
            is_published=True
        )
        if not updated:
            logger.info('[Sched-ETA] post %s ya fue publicado por otro proceso', post_id)
            return
        post.refresh_from_db()
        logger.info('[Sched-ETA] post %s marcado is_published=True, lanzando LinkedIn', post_id)
        auto_publish_blog_to_linkedin(post)
        logger.info('[Sched-ETA] post %s publicado ok (slug=%s)', post.id, post.slug)
        from content.services.frontend_build import schedule_rebuild_after_publish
        schedule_rebuild_after_publish(reason='blog')
    except Exception:
        logger.exception('[Sched-ETA] error publicando post %s', post_id)


@periodic_task(crontab(minute='*'))
def publish_scheduled_blog_posts():
    """
    Periodic safety-net (every minute): publish blog posts whose
    published_at datetime has passed but are still marked as drafts,
    and fire the LinkedIn auto-publish pipeline for each one.

    The primary path is the per-post ETA task enqueued on save
    (publish_single_scheduled_blog). This sweep catches cases where the
    ETA was missed: Huey was down at trigger time, migrated data, etc.
    """
    from content.models import BlogPost
    from content.views.blog import auto_publish_blog_to_linkedin

    now = timezone.now()
    scheduled = BlogPost.objects.filter(
        is_published=False,
        published_at__isnull=False,
        published_at__lte=now,
    )

    candidates = list(scheduled)
    if not candidates:
        return

    logger.info('[Sched-Sweep] %d post(s) listos para publicar', len(candidates))
    for post in candidates:
        logger.info(
            '[Sched-Sweep] procesando post %s slug=%s published_at=%s',
            post.id, post.slug, post.published_at,
        )

    count = 0
    for post in candidates:
        try:
            updated = BlogPost.objects.filter(
                pk=post.id, is_published=False
            ).update(is_published=True)
            if not updated:
                logger.info('[Sched-Sweep] post %s ya publicado por otro proceso', post.id)
                continue
            post.refresh_from_db()
            logger.info('[Sched-Sweep] post %s marcado is_published=True, lanzando LinkedIn', post.id)
            auto_publish_blog_to_linkedin(post)
            count += 1
        except Exception:
            logger.exception('[Sched-Sweep] error publicando post %s', post.id)

    if count > 0:
        logger.info('[Sched-Sweep] publicados %d post(s)', count)
        from content.services.frontend_build import schedule_rebuild_after_publish
        schedule_rebuild_after_publish(reason='blog')


@task()
def publish_single_scheduled_linkedin_post(post_id):
    """
    Publish a single scheduled freeform LinkedIn post by id.

    Enqueued with eta=scheduled_at on create/update. Re-entrant: the
    atomic claim inside publish_linkedin_post_now prevents doubles.
    """
    from content.models import LinkedInPost
    from content.services.linkedin_post_service import publish_linkedin_post_now

    now = timezone.now()
    post = LinkedInPost.objects.filter(pk=post_id).first()
    if not post:
        logger.warning('[LI-Sched-ETA] post %s no existe', post_id)
        return
    if post.status != LinkedInPost.STATUS_SCHEDULED:
        logger.info('[LI-Sched-ETA] post %s status=%s, skip', post_id, post.status)
        return
    if not post.scheduled_at or post.scheduled_at > now:
        logger.info('[LI-Sched-ETA] post %s aún no es hora, skip', post_id)
        return

    result = publish_linkedin_post_now(post)
    logger.info('[LI-Sched-ETA] post %s → success=%s', post_id, result.get('success'))


@periodic_task(crontab(minute='*'))
def publish_scheduled_linkedin_posts():
    """
    Periodic safety-net (every minute) for scheduled LinkedIn posts whose
    time has passed (Huey down at ETA, migrated data, etc.).
    """
    from content.models import LinkedInPost
    from content.services.linkedin_post_service import publish_linkedin_post_now

    now = timezone.now()
    due = list(LinkedInPost.objects.filter(
        status=LinkedInPost.STATUS_SCHEDULED,
        scheduled_at__isnull=False,
        scheduled_at__lte=now,
    ))
    if not due:
        return

    logger.info('[LI-Sched-Sweep] %d post(s) listos para publicar', len(due))
    for post in due:
        try:
            result = publish_linkedin_post_now(post)
            logger.info('[LI-Sched-Sweep] post %s → success=%s', post.id, result.get('success'))
        except Exception:
            logger.exception('[LI-Sched-Sweep] error publicando post %s', post.id)


@periodic_task(crontab(hour='9', minute='30'))
def warn_linkedin_token_expiry():
    """Daily: email staff when the LinkedIn token expires in <=7 days."""
    from content.services.linkedin_expiry_service import check_linkedin_token_expiry
    return check_linkedin_token_expiry()


@task(retries=2, retry_delay=600)
@lock_task('frontend-rebuild')
def rebuild_frontend_prerender():
    """
    Rebuild the prerendered frontend in-process (FRONTEND_REBUILD_MODE=inline,
    local development only) so published changes reach the static HTML that
    crawlers and link previews read.

    Enqueued (with a coalescing delay) by schedule_rebuild_after_publish in
    inline mode. The service skips the build when nothing changed since the
    last one, and always skips in request mode (production), where the ops
    toolkit regenerates the build. The Redis lock serializes builds; a locked
    attempt fails and Huey retries it in 10 minutes.
    """
    from content.services.frontend_build import run_frontend_rebuild

    result = run_frontend_rebuild()
    logger.info(
        '[FrontendRebuild] %s — %s',
        result['status'], (result['detail'] or '')[:300],
    )


@periodic_task(crontab(hour='2', minute='30'))
def reconcile_frontend_rebuild_request():
    """
    Nightly safety net: request a regeneration when prerendered content changed
    after the last build and no write path asked for it (Django admin, shell,
    bulk updates). Never builds: in request mode it only writes the request
    file the ops toolkit consumes.
    """
    from content.services.frontend_build import reconcile_rebuild_request

    if reconcile_rebuild_request():
        logger.info('[FrontendRebuild reconcile] stale prerender — regeneration requested')


def _suggest_action_for_proposal(proposal, now):
    """
    Generate a contextual suggested action for a single proposal
    based on its current state, engagement signals, and timing.

    Returns a short actionable string for the daily digest email.
    """
    from datetime import timedelta

    # Negotiating → follow up on the negotiation
    if proposal.status == 'negotiating':
        return 'Seguir negociación: enviar opciones de ajuste o agendar llamada.'

    # High view count today-ish → call now
    if proposal.view_count and proposal.view_count >= 3:
        return f'Llamar hoy: {proposal.view_count} visitas registradas. Alta intención.'

    # Expiring soon → offer discount or extend
    if proposal.expires_at:
        days_left = (proposal.expires_at - now).days
        if 0 < days_left <= 3:
            if not proposal.discount_percent:
                return f'Expira en {days_left}d. Considerar activar descuento o re-enviar con nota.'
            return f'Expira en {days_left}d. Enviar recordatorio de urgencia.'

    # Viewed but no response → WhatsApp follow-up
    if proposal.status == 'viewed':
        ref_date = proposal.last_activity_at or proposal.first_viewed_at
        if ref_date and (now - ref_date) > timedelta(days=2):
            days_waiting = (now - ref_date).days
            return f'Sin respuesta hace {days_waiting}d. Enviar WhatsApp personalizado.'
        return 'Visto recientemente. Esperar 24-48h o enviar WhatsApp de refuerzo.'

    # Sent but never viewed → re-send or call
    if proposal.status == 'sent':
        if proposal.sent_at and (now - proposal.sent_at) > timedelta(days=3):
            return 'Sin abrir hace >3d. Re-enviar propuesta o contactar por teléfono.'
        return 'Enviada recientemente. Esperar a que la abra.'

    return 'Revisar estado y dar seguimiento.'


@periodic_task(crontab(hour='7', minute='0'))
def send_daily_pipeline_digest():
    """
    Daily task (7 AM): compile and send a pipeline digest email
    summarising: proposals viewed yesterday, inactive proposals,
    proposals expiring within 5 days, total active count, and
    a suggested action #1 per proposal.
    """
    from datetime import timedelta

    from content.models import BusinessProposal, ProposalViewEvent
    from content.services.proposal_email_service import ProposalEmailService
    from content.utils import format_bogota_date

    now = timezone.now()
    yesterday_start = (now - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    three_days_ago = now - timedelta(days=3)

    active_proposals = BusinessProposal.objects.filter(
        status__in=['sent', 'viewed', 'negotiating'],
        is_active=True,
    )

    # Proposals viewed yesterday
    viewed_yesterday_ids = (
        ProposalViewEvent.objects
        .filter(viewed_at__gte=yesterday_start, viewed_at__lt=yesterday_end)
        .values_list('proposal_id', flat=True)
        .distinct()
    )
    viewed_yesterday_qs = active_proposals.filter(pk__in=viewed_yesterday_ids)
    viewed_yesterday = []
    for p in viewed_yesterday_qs:
        viewed_yesterday.append({
            'id': p.id,
            'client_name': p.client_name,
            'title': p.title,
            'status': p.status,
            'total_investment': p.total_investment,
            'currency': p.currency,
            'suggested_action': _suggest_action_for_proposal(p, now),
        })

    # Inactive proposals (no activity >3 days)
    inactive = []
    for p in active_proposals.filter(status__in=['sent', 'viewed', 'negotiating']):
        ref_date = p.last_activity_at or p.sent_at
        if ref_date and ref_date < three_days_ago:
            inactive.append({
                'id': p.id,
                'client_name': p.client_name,
                'title': p.title,
                'days_inactive': (now - ref_date).days,
                'suggested_action': _suggest_action_for_proposal(p, now),
            })

    # Expiring within 5 days
    expiring_soon_qs = active_proposals.filter(
        expires_at__isnull=False,
        expires_at__gt=now,
        expires_at__lte=now + timedelta(days=5),
    )
    expiring_soon = []
    for p in expiring_soon_qs:
        expiring_soon.append({
            'id': p.id,
            'client_name': p.client_name,
            'title': p.title,
            'expires_at': p.expires_at,
            'suggested_action': _suggest_action_for_proposal(p, now),
        })

    digest_data = {
        'viewed_yesterday': viewed_yesterday,
        'inactive': inactive,
        'expiring_soon': expiring_soon,
        'total_active': active_proposals.count(),
        'date': format_bogota_date(now),
    }

    ProposalEmailService.send_daily_pipeline_digest(digest_data)


@periodic_task(crontab(hour='*/3', minute='45'))
def detect_high_engagement_today():
    """
    Periodic task (every 3 hours): if a client has >=3 unique view sessions
    on a proposal today, create a high_engagement_today alert for the seller.
    Rate-limited to one alert per day per proposal.
    """
    from datetime import timedelta

    from content.models import BusinessProposal, ProposalAlert, ProposalViewEvent

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    active_proposals = BusinessProposal.objects.filter(
        status__in=['sent', 'viewed', 'negotiating'],
        is_active=True,
    )

    created = 0
    for proposal in active_proposals:
        sessions_today = (
            ProposalViewEvent.objects
            .filter(proposal=proposal, viewed_at__gte=today_start)
            .values('session_id')
            .distinct()
            .count()
        )
        if sessions_today < 3:
            continue

        already_alerted = ProposalAlert.objects.filter(
            proposal=proposal,
            alert_type='high_engagement_today',
            is_dismissed=False,
            created_at__gte=today_start,
        ).exists()
        if already_alerted:
            continue

        ProposalAlert.objects.create(
            proposal=proposal,
            alert_type='high_engagement_today',
            message=(
                f'{proposal.client_name} visitó la propuesta '
                f'{sessions_today} veces hoy. Considera llamar ahora.'
            ),
            alert_date=now,
        )
        created += 1

    if created > 0:
        logger.info('Created %d high-engagement alerts.', created)


@task()
def check_calculator_abandonment_followup():
    """Retired task kept as a no-op for jobs already queued before deployment."""
    return None


@periodic_task(crontab(hour='9', minute='30'))
def generate_whatsapp_suggestions():
    """
    Daily task (9:30 AM): for proposals viewed >48h ago without response,
    generate a WhatsApp suggestion alert with a pre-drafted message
    mentioning the section where the client spent most time.
    """
    from datetime import timedelta

    from django.db.models import Sum

    from content.models import (
        BusinessProposal, ProposalAlert, ProposalSectionView,
    )

    now = timezone.now()
    two_days_ago = now - timedelta(hours=48)

    candidates = BusinessProposal.objects.filter(
        status='viewed',
        is_active=True,
        automations_paused=False,
        responded_at__isnull=True,
        first_viewed_at__isnull=False,
        first_viewed_at__lt=two_days_ago,
        client_phone__gt='',
    )

    created = 0
    for proposal in candidates:
        already_exists = ProposalAlert.objects.filter(
            proposal=proposal,
            alert_type='whatsapp_suggestion',
            is_dismissed=False,
        ).exists()
        if already_exists:
            continue

        top_section = (
            ProposalSectionView.objects
            .filter(view_event__proposal=proposal)
            .values('section_type')
            .annotate(total_time=Sum('time_spent_seconds'))
            .order_by('-total_time')
            .first()
        )

        section_name = (top_section['section_type'] if top_section else 'la propuesta')
        section_labels = {
            'greeting': 'bienvenida',
            'executive_summary': 'resumen ejecutivo',
            'context_diagnostic': 'diagnóstico y contexto',
            'conversion_strategy': 'estrategia de conversión',
            'design_ux': 'diseño y UX',
            'creative_support': 'soporte creativo',
            'development_stages': 'etapas de desarrollo',
            'functional_requirements': 'requerimientos funcionales',
            'timeline': 'cronograma',
            'investment': 'inversión',
            'final_note': 'nota final',
            'next_steps': 'próximos pasos',
            'proposal_summary': 'resumen',
            'process_methodology': 'proceso y metodología',
            'closing': 'cierre',
            'about_us': 'sobre nosotros',
        }
        label = section_labels.get(section_name, section_name)

        message_draft = (
            f'Hola {proposal.client_name}, vi que revisaste la sección de '
            f'{label} con mucho interés. ¿Te puedo ayudar con alguna duda?'
        )

        ProposalAlert.objects.create(
            proposal=proposal,
            alert_type='whatsapp_suggestion',
            message=f'Sugerencia de WhatsApp para {proposal.client_name}: "{message_draft}"',
            alert_date=now,
        )
        created += 1

    if created > 0:
        logger.info('Created %d WhatsApp suggestions.', created)


@periodic_task(crontab(hour='1', minute='30'))
def auto_archive_zombie_proposals():
    """
    Daily task: deactivate proposals that are expired and had no
    interaction (views or change logs) in the last 30 days.
    """
    from datetime import timedelta

    from django.db.models import Max

    from content.models import BusinessProposal, ProposalChangeLog

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    candidates = BusinessProposal.objects.filter(
        status='expired',
        is_active=True,
    )

    archived = 0
    for proposal in candidates:
        last_view = (
            proposal.view_events
            .aggregate(latest=Max('viewed_at'))['latest']
        )
        last_log = (
            ProposalChangeLog.objects
            .filter(proposal=proposal)
            .aggregate(latest=Max('created_at'))['latest']
        )

        latest_activity = max(
            filter(None, [last_view, last_log, proposal.created_at])
        )
        if latest_activity and latest_activity < thirty_days_ago:
            proposal.is_active = False
            proposal.save(update_fields=['is_active'])
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='auto_archived',
                actor_type='system',
                description='Auto-archived: expired with no activity for 30+ days.',
            )
            archived += 1

    if archived > 0:
        logger.info('Auto-archived %d zombie proposals.', archived)


@periodic_task(crontab(minute='*/30'))
def refresh_cached_heat_scores():
    """
    Periodic task (every 30 min): recompute cached_heat_score for all
    active proposals in sent/viewed status.
    """
    from content.models import BusinessProposal
    from content.services.proposal_analytics_service import compute_heat_score_for_proposal

    now = timezone.now()
    proposals = BusinessProposal.objects.filter(
        status__in=['sent', 'viewed'],
        is_active=True,
    ).values_list('id', 'cached_heat_score')

    updated = 0
    for pid, old_score in proposals:
        new_score = compute_heat_score_for_proposal(pid, now)
        if new_score != old_score:
            BusinessProposal.objects.filter(pk=pid).update(
                cached_heat_score=new_score
            )
            updated += 1

    if updated > 0:
        logger.info('Refreshed cached_heat_score for %d proposals.', updated)


@task(retries=3, retry_delay=60)
def notify_first_view(proposal_id):
    """
    Huey task: send real-time notification to the sales team when a
    client opens a proposal for the first time.

    Uses a row-level delivery state machine. Huey retries transport failures,
    while ``reconcile_first_view_notifications`` recovers broker outages and
    workers that died after claiming a row.
    """
    from django.db import transaction

    from content.models import BusinessProposal
    from content.services.proposal_email_service import ProposalEmailService
    from content.services.proposal_service import ProposalService

    state = BusinessProposal.FirstViewNotificationStatus
    max_attempts = 4
    now = timezone.now()

    with transaction.atomic():
        try:
            proposal = BusinessProposal.objects.select_for_update().get(
                pk=proposal_id,
            )
        except BusinessProposal.DoesNotExist:
            logger.warning(
                'Proposal %s not found for first-view notification task.',
                proposal_id,
            )
            return

        if proposal.first_view_notification_status in (
            state.SENT,
            state.SKIPPED,
            state.LEGACY_UNVERIFIED,
        ):
            return
        # Never infer a historical first view from old rows. Only the tracking
        # transaction is allowed to move not_started -> pending.
        if (
            not proposal.first_viewed_at
            or proposal.first_view_notification_status == state.NOT_STARTED
        ):
            return
        if ProposalService.open_notifications_suppressed(proposal):
            proposal.first_view_notification_status = state.SKIPPED
            proposal.first_view_notification_last_error = (
                f'Suppressed for proposal status {proposal.status}.'
            )
            proposal.save(update_fields=[
                'first_view_notification_status',
                'first_view_notification_last_error',
            ])
            return
        if not ProposalEmailService._is_template_active(
            'proposal_first_view_notification',
        ):
            proposal.first_view_notification_status = state.SKIPPED
            proposal.first_view_notification_last_error = 'Email template disabled.'
            proposal.save(update_fields=[
                'first_view_notification_status',
                'first_view_notification_last_error',
            ])
            return
        if (
            proposal.first_view_notification_status == state.SENDING
            and proposal.first_view_notification_attempted_at
            and proposal.first_view_notification_attempted_at
            > now - timedelta(minutes=10)
        ):
            return
        if proposal.first_view_notification_attempts >= max_attempts:
            return

        proposal.first_view_notification_status = state.SENDING
        proposal.first_view_notification_attempts += 1
        proposal.first_view_notification_attempted_at = now
        proposal.first_view_notification_last_error = ''
        proposal.save(update_fields=[
            'first_view_notification_status',
            'first_view_notification_attempts',
            'first_view_notification_attempted_at',
            'first_view_notification_last_error',
        ])

    try:
        sent = ProposalEmailService.send_first_view_notification(
            proposal,
            raise_on_error=True,
        )
        if not sent:
            raise RuntimeError('First-view notification was not delivered.')
    except Exception as exc:
        sanitized_error = ' '.join(str(exc).split())[:1000]
        BusinessProposal.objects.filter(pk=proposal_id).update(
            first_view_notification_status=state.FAILED,
            first_view_notification_last_error=sanitized_error,
        )
        raise

    sent_at = timezone.now()
    BusinessProposal.objects.filter(pk=proposal_id).update(
        first_view_notification_status=state.SENT,
        first_view_notification_sent_at=sent_at,
        first_view_notification_last_error='',
    )


@periodic_task(crontab(minute='*/5'))
def reconcile_first_view_notifications():
    """Re-enqueue pending, failed, or stale first-view deliveries."""
    from django.db.models import Q

    from content.models import BusinessProposal

    state = BusinessProposal.FirstViewNotificationStatus
    stale_before = timezone.now() - timedelta(minutes=10)
    candidates = (
        BusinessProposal.objects
        .filter(first_viewed_at__isnull=False)
        .filter(
            Q(first_view_notification_status=state.PENDING)
            | Q(
                first_view_notification_status=state.FAILED,
                first_view_notification_attempts__lt=4,
            )
            | Q(
                first_view_notification_status=state.SENDING,
                first_view_notification_attempted_at__lt=stale_before,
                first_view_notification_attempts__lt=4,
            )
        )
        .values_list('id', flat=True)[:100]
    )
    queued = 0
    for proposal_id in candidates:
        try:
            notify_first_view(proposal_id)
            queued += 1
        except Exception:
            logger.exception(
                'Failed to reconcile first-view notification for proposal %s',
                proposal_id,
            )
    if queued:
        logger.info('Re-enqueued %d first-view notification(s).', queued)


@task()
def run_platform_onboarding(proposal_id, acting_user_id=None, is_relaunch=False, send_email=None):
    """
    Huey task: run platform onboarding for an accepted proposal.

    Creates project, deliverable, syncs requirements and documents,
    and sends acceptance email (first launch only). Wrapped in
    transaction.atomic() so partial failures roll back cleanly.

    ``send_email``: None → decide automatically (first launch of an accepted
    proposal). Callers that own the acceptance email themselves (e.g. the
    client-response view) pass ``False`` to suppress a duplicate send.

    Updates platform_onboarding_status to 'completed' or 'failed'.
    """
    from django.db import transaction

    from content.models import BusinessProposal

    try:
        proposal = BusinessProposal.objects.get(pk=proposal_id)
    except BusinessProposal.DoesNotExist:
        logger.warning(
            'Proposal %s not found for platform onboarding task.',
            proposal_id,
        )
        return

    acting_user = None
    if acting_user_id:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        acting_user = User.objects.filter(pk=acting_user_id).first()

    try:
        with transaction.atomic():
            from accounts.services.proposal_platform_onboarding import (
                handle_proposal_accepted_for_platform,
            )

            # The "propuesta aceptada" confirmation email must only go out on a
            # first launch of a genuinely accepted proposal — not when launching
            # early from negotiation (the client still gets their invitation with
            # the temp password via create_client). Callers that already sent the
            # acceptance email themselves pass send_email=False to suppress it.
            effective_send_email = (
                (not is_relaunch and proposal.status == BusinessProposal.Status.ACCEPTED)
                if send_email is None
                else send_email
            )
            handle_proposal_accepted_for_platform(
                proposal,
                source='admin_panel',
                acting_user=acting_user,
                send_email=effective_send_email,
            )

        proposal.platform_onboarding_status = BusinessProposal.ONBOARDING_COMPLETED
        proposal.save(update_fields=['platform_onboarding_status'])
    except Exception:
        logger.exception(
            'Platform onboarding failed for proposal %s.', proposal_id,
        )
        proposal.platform_onboarding_status = BusinessProposal.ONBOARDING_FAILED
        proposal.save(update_fields=['platform_onboarding_status'])


# 13:30 UTC = 08:30 Bogotá. America/Bogota does not observe DST, so the
# offset (UTC-5) is stable year-round. Pick the time so the team's inbox
# has the email when they start the day.
@periodic_task(crontab(hour='13', minute='30'))
def notify_proposal_stage_deadlines():
    """
    Daily task: scan proposals with active project stages and send the team
    pre-deadline warnings (70% elapsed) and overdue reminders (every 3 days).

    Filter is by stage existence + dates + not-completed, NOT by proposal
    status — that way an admin can pre-schedule stages while the proposal
    is still in `negotiating` or `viewed`. Stages with NULL dates are
    silently skipped by ProposalStageTracker.
    """
    from content.models import BusinessProposal
    from content.services.proposal_stage_tracker import ProposalStageTracker

    candidates = (
        BusinessProposal.objects
        .filter(
            is_active=True,
            automations_paused=False,
            project_stages__start_date__isnull=False,
            project_stages__end_date__isnull=False,
            project_stages__completed_at__isnull=True,
        )
        .distinct()
        .prefetch_related('project_stages')
    )

    processed = 0
    for proposal in candidates:
        try:
            ProposalStageTracker.process(proposal)
            processed += 1
        except Exception:
            logger.exception(
                'notify_proposal_stage_deadlines: failed for proposal %s',
                proposal.uuid,
            )

    if processed:
        logger.info(
            'notify_proposal_stage_deadlines: processed %d proposals', processed,
        )


# ── Task deadline notifications ────────────────────────────────────────────
# 08:05 AM diario. Slight offset from the 08:00 tasks to avoid contention.
TASK_NOTIFICATION_RECIPIENTS = ['team@projectapp.co', 'carlos18bp@gmail.com']

# Priority labels in Spanish (model stores English labels: Low/Medium/High).
_PRIORITY_LABELS = {
    'low': 'Baja',
    'medium': 'Media',
    'high': 'Alta',
}

# Per-threshold email config. intro uses {title} as a placeholder for task.title.
_THRESHOLD_CONFIGS = {
    40: {
        'color': '#d97706',    # amber-600
        'icon': '📋',
        'title': 'Tarea al 40% de su tiempo límite',
        'subtitle': 'Quedan aprox. 60% del tiempo disponible',
        'intro': 'La tarea "{title}" ha consumido el 40% de su tiempo límite. Revisa el avance y ajusta las prioridades si es necesario.',
    },
    70: {
        'color': '#ea580c',    # orange-600
        'icon': '⚠️',
        'title': 'Tarea al 70% de su tiempo límite',
        'subtitle': 'Solo queda el 30% del tiempo disponible',
        'intro': 'La tarea "{title}" ha consumido el 70% de su tiempo límite. Se recomienda revisar el estado y tomar acciones correctivas.',
    },
    100: {
        'color': '#dc2626',    # red-600
        'icon': '🚨',
        'title': 'Tarea llegó a su fecha límite',
        'subtitle': 'La fecha límite se cumple hoy',
        'intro': 'La tarea "{title}" alcanzó su fecha límite. Ciérrala o actualiza la fecha si el trabajo continúa.',
    },
}


def _send_task_deadline_email(task, threshold_pct=None, days_overdue=None):
    """Send a deadline notification email for a single task.

    threshold_pct: 40, 70, or 100 (percentage of time elapsed).
    days_overdue: number of days past due_date (for recurring overdue reminders).
    """
    from django.template.loader import render_to_string
    from content.models import Task
    from content.services.email_delivery_service import (
        DeliveryClassification,
        EmailDeliveryGateway,
        EmailMultiAlternatives,
    )

    if threshold_pct is not None:
        cfg = _THRESHOLD_CONFIGS[threshold_pct]
        header_color = cfg['color']
        header_icon = cfg['icon']
        header_title = cfg['title']
        header_subtitle = cfg['subtitle']
        intro_text = cfg['intro'].format(title=task.title)
        subject = f'[ProjectApp] {header_title}: {task.title}'
        days_overdue_ctx = None
    else:
        header_color = '#7f1d1d'   # red-900
        header_icon = '🔴'
        header_title = 'Tarea vencida — Recordatorio'
        header_subtitle = f'Lleva {days_overdue} día(s) sin completarse'
        intro_text = (
            f'La tarea "{task.title}" sigue sin completarse {days_overdue} día(s) '
            'después de su fecha límite.'
        )
        subject = f'[ProjectApp] Tarea vencida ({days_overdue}d): {task.title}'
        days_overdue_ctx = days_overdue

    assignee_name = None
    if task.assignee:
        full = (task.assignee.get_full_name() or '').strip()
        assignee_name = full or task.assignee.username

    context = {
        'email_subject': subject,
        'header_color': header_color,
        'header_icon': header_icon,
        'header_title': header_title,
        'header_subtitle': header_subtitle,
        'intro_text': intro_text,
        'task_title': task.title,
        'task_status': Task.Status(task.status).label,
        'task_priority': _PRIORITY_LABELS.get(task.priority, task.priority),
        'task_assignee': assignee_name,
        'task_due_date': task.due_date.strftime('%d/%m/%Y'),
        'days_overdue': days_overdue_ctx,
    }

    html_body = render_to_string('emails/task_deadline_notification.html', context)
    txt_body = render_to_string('emails/task_deadline_notification.txt', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=txt_body,
        from_email='team@projectapp.co',
        to=TASK_NOTIFICATION_RECIPIENTS,
    )
    msg.attach_alternative(html_body, 'text/html')
    EmailDeliveryGateway.send(
        msg,
        template_key='task_deadline_notification',
        classification=DeliveryClassification.INTERNAL,
    )


@periodic_task(crontab(hour='8', minute='5'))
def check_task_deadline_notifications():
    """
    Daily at 08:05: scan non-done tasks with a due_date and send email
    notifications at 40%, 70%, 100% of elapsed time, and every 2 days
    after the due date passes.

    Recipients: team@projectapp.co and carlos18bp@gmail.com
    """
    from django.db.models import Q
    from content.models import Task

    today = timezone.localdate()
    candidates = Task.objects.filter(
        due_date__isnull=False,
    ).exclude(
        status=Task.Status.DONE,
    ).filter(
        Q(notified_40=False) | Q(notified_70=False) | Q(notified_100=False)
        | Q(last_overdue_notified_at__isnull=True)
        | Q(last_overdue_notified_at__lt=today - timedelta(days=2))
    ).select_related('assignee')

    processed = 0
    for task in candidates:
        try:
            _check_single_task_deadlines(task, today)
            processed += 1
        except Exception:
            logger.exception(
                'check_task_deadline_notifications: failed for task %s', task.pk,
            )

    if processed:
        logger.info('check_task_deadline_notifications: processed %d tasks', processed)


def _check_single_task_deadlines(task, today):
    """Evaluate and send deadline notifications for one task."""
    created_date = task.created_at.date()
    total_days = (task.due_date - created_date).days
    update_fields = []

    if total_days > 0:
        pct = (today - created_date).days / total_days * 100

        if pct >= 40 and not task.notified_40:
            _send_task_deadline_email(task, threshold_pct=40)
            task.notified_40 = True
            update_fields.append('notified_40')

        if pct >= 70 and not task.notified_70:
            _send_task_deadline_email(task, threshold_pct=70)
            task.notified_70 = True
            update_fields.append('notified_70')

    if today >= task.due_date and not task.notified_100:
        _send_task_deadline_email(task, threshold_pct=100)
        task.notified_100 = True
        update_fields.append('notified_100')

    if today > task.due_date:
        days_overdue = (today - task.due_date).days
        needs_overdue = (
            task.last_overdue_notified_at is None
            or (today - task.last_overdue_notified_at).days >= 2
        )
        if needs_overdue:
            _send_task_deadline_email(task, days_overdue=days_overdue)
            task.last_overdue_notified_at = today
            update_fields.append('last_overdue_notified_at')

    if update_fields:
        task.save(update_fields=update_fields)


# ── Manual task alert notifications ─────────────────────────────────────────
# 08:10 AM diario. Slight offset from the 08:05 deadline task.

def _send_task_alert_email(alert):
    """Send a manual-alert email for a single TaskAlert instance."""
    from django.template.loader import render_to_string
    from content.models import Task
    from content.services.email_delivery_service import (
        DeliveryClassification,
        EmailDeliveryGateway,
        EmailMultiAlternatives,
    )

    task = alert.task
    subject = f'[ProjectApp] Alerta de tarea: {task.title}'
    note_text = alert.note.strip() if alert.note else 'Alerta manual programada para esta tarea.'

    assignee_name = None
    if task.assignee:
        full = (task.assignee.get_full_name() or '').strip()
        assignee_name = full or task.assignee.username

    due_date_str = task.due_date.strftime('%d/%m/%Y') if task.due_date else 'No definida'

    context = {
        'email_subject': subject,
        'header_color': '#7c3aed',   # violet-600
        'header_icon': '🔔',
        'header_title': 'Alerta manual de tarea',
        'header_subtitle': f'Programada para el {alert.notify_at.strftime("%d/%m/%Y")}',
        'intro_text': note_text,
        'task_title': task.title,
        'task_status': Task.Status(task.status).label,
        'task_priority': _PRIORITY_LABELS.get(task.priority, task.priority),
        'task_assignee': assignee_name,
        'task_due_date': due_date_str,
        'days_overdue': None,
    }

    html_body = render_to_string('emails/task_deadline_notification.html', context)
    txt_body = render_to_string('emails/task_deadline_notification.txt', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=txt_body,
        from_email='team@projectapp.co',
        to=TASK_NOTIFICATION_RECIPIENTS,
    )
    msg.attach_alternative(html_body, 'text/html')
    EmailDeliveryGateway.send(
        msg,
        template_key='task_alert_notification',
        classification=DeliveryClassification.INTERNAL,
    )


@periodic_task(crontab(hour='8', minute='10'))
def check_task_alert_notifications():
    """
    Daily at 08:10: fire any pending manual task alerts whose notify_at <= today.
    Marks each alert as sent after the email is dispatched.
    """
    from content.models import TaskAlert

    today = timezone.localdate()
    pending = (
        TaskAlert.objects.filter(notify_at__lte=today, sent=False)
        .select_related('task', 'task__assignee')
    )

    processed = 0
    for alert in pending:
        try:
            _send_task_alert_email(alert)
            alert.sent = True
            alert.save(update_fields=['sent'])
            processed += 1
        except Exception:
            logger.exception(
                'check_task_alert_notifications: failed for alert %s', alert.pk,
            )

    if processed:
        logger.info('check_task_alert_notifications: processed %d alerts', processed)


@task()
def send_accounting_change_email(change_log_id):
    """
    Huey task: email an accounting change to the configured recipients.

    Thin async wrapper — all logic (recipients, templates, EmailLog)
    lives in content.services.accounting_email_service.
    """
    from content.services.accounting_email_service import (
        send_accounting_change_email as _send,
    )

    return _send(change_log_id)


# 14:00 UTC = 09:00 Bogotá. America/Bogota does not observe DST, so the
# offset (UTC-5) is stable year-round.
@periodic_task(crontab(hour='14', minute='0'))
@lock_task('accounting-card-reminder')
def send_card_debt_reminder():
    """
    Huey task (daily 9:00 Bogotá): weekly card-debt reminder.

    All cycle logic (Friday cycles, snapshot check, 2-day re-alerts)
    lives in content.services.accounting_card_reminder_service.
    """
    from content.services.accounting_card_reminder_service import (
        run_card_reminder,
    )

    return run_card_reminder()


# 14:05 UTC = 09:05 Bogotá — right after the card-debt reminder so both
# alerts arrive together when both are pending.
@periodic_task(crontab(hour='14', minute='5'))
@lock_task('accounting-statement-reminder')
def send_statement_reminder():
    """
    Huey task (daily 9:05 Bogotá): monthly statement reminder.

    Pending detection (previous month processed + PDF attached per active
    catalog card) and the 8-day re-alert cadence live in
    content.services.accounting_statement_reminder_service.
    """
    from content.services.accounting_statement_reminder_service import (
        run_statement_reminder,
    )

    return run_statement_reminder()


# 13:30 UTC = 08:30 Bogotá (UTC-5, no DST). Takes over the slot the standalone
# hosting-expiry task used: those notices are now a section of this calendar,
# and 08:30 puts it ahead of the card (09:00) and statement (09:05) reminders.
@periodic_task(crontab(hour='13', minute='30'))
@lock_task('accounting-payment-calendar')
def send_payment_calendar():
    """
    Huey task (daily 8:30 Bogotá): the consolidated payment calendar.

    One email with the expected incomes, the next charge of the recurring
    payments and the hostings about to expire — announced 15 and 7 days ahead
    and on the date itself, with expected incomes reminded every week or
    fortnight while they stay uncollected. Logic lives in
    content.services.accounting_payment_calendar_service.
    """
    from content.services.accounting_payment_calendar_service import (
        run_payment_calendar,
    )

    return run_payment_calendar()


@periodic_task(crontab(hour='4', minute='25'))
def cleanup_proposal_formalizations():
    """Remove expired private previews; sent email evidence remains in history."""
    from content.services.proposal_formalization_service import cleanup_expired

    return cleanup_expired()


@task(retries=3, retry_delay=30)
@lock_task('linktree-template-validation')
def validate_linktree_template(version_id):
    """One Chromium validation at a time; never occupies a web worker in production."""
    from content.services.linktree_templates.service import run_validation

    run_validation(version_id)
