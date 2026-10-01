"""Soft-archive helpers: retain rows for audit instead of CASCADE deletes."""

from django.utils import timezone


def wants_include_archived(request) -> bool:
    v = str(request.query_params.get('include_archived', '')).lower()
    return v in ('1', 'true', 'yes')


def filter_not_archived(qs, request, *, admin_may_include_archived: bool):
    """
    Restrict queryset to is_archived=False unless admin passes include_archived=1.
    """
    profile = getattr(request.user, 'profile', None)
    if admin_may_include_archived and profile and profile.is_admin and wants_include_archived(request):
        return qs
    return qs.filter(is_archived=False)


def filter_deliverables_for_list(qs, request, *, is_admin: bool):
    return filter_not_archived(qs, request, admin_may_include_archived=is_admin)


def filter_change_requests_for_list(qs, request, *, is_admin: bool):
    return filter_not_archived(qs, request, admin_may_include_archived=is_admin)


def filter_bug_reports_for_list(qs, request, *, is_admin: bool):
    return filter_not_archived(qs, request, admin_may_include_archived=is_admin)


def filter_subscriptions_for_list(qs, request, *, is_admin: bool):
    return filter_not_archived(qs, request, admin_may_include_archived=is_admin)


def deliverable_visible_for_request(deliverable, request) -> bool:
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_admin:
        return True
    return not deliverable.is_archived


def bug_visible_for_request(bug, request) -> bool:
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_admin:
        return True
    return not bug.is_archived


def change_request_visible_for_request(cr, request) -> bool:
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_admin:
        return True
    return not cr.is_archived


def archive_record(instance, *, extra_update_fields=()):
    instance.is_archived = True
    instance.archived_at = timezone.now()
    fields = ['is_archived', 'archived_at'] + list(extra_update_fields)
    instance.save(update_fields=list(dict.fromkeys(fields)))


def unarchive_record(instance, *, extra_update_fields=()):
    instance.is_archived = False
    instance.archived_at = None
    fields = ['is_archived', 'archived_at'] + list(extra_update_fields)
    instance.save(update_fields=list(dict.fromkeys(fields)))
