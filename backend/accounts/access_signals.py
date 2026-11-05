"""Invalidate credentials even when account identity changes through older entrypoints."""
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import pre_save
from django.dispatch import receiver


@receiver(pre_save, sender=get_user_model())
def revoke_changed_identity(sender, instance, raw=False, update_fields=None, **kwargs):
    fields = {'email', 'password', 'is_active', 'is_staff', 'is_superuser'}
    if raw or not instance.pk or (update_fields is not None and not fields.intersection(update_fields)):
        return
    previous = sender.objects.filter(pk=instance.pk).only(*fields).first()
    if previous and any(getattr(previous, name) != getattr(instance, name) for name in fields if update_fields is None or name in update_fields):
        from accounts.access_models import GoogleIdentity
        from accounts.services.access import revoke
        revoke(instance)
        if previous.email.lower().strip() != instance.email.lower().strip():
            GoogleIdentity.objects.filter(user=instance).delete()


@receiver(user_logged_in)
def stamp_native_login(sender, request, user, **kwargs):
    from accounts.models import UserProfile

    access_version = UserProfile.objects.filter(
        user_id=user.pk,
    ).values_list('access_version', flat=True).first()
    if access_version is not None:
        request.session['access_version'] = access_version
        if not getattr(request, '_access_login_recorded', False):
            from accounts.services.access import record_event
            record_event(user, 'login', method='password', surface='panel', request=request)
