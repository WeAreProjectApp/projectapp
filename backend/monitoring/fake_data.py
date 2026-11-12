"""Ownership boundary of the local monitoring examples."""
from content.fake_data import ensure_fake_data_allowed

from monitoring.models import CapacityAllocation, CapacityChange, Case, CaseActivity, Delivery, Report, Resource, Source

RESOURCE_KEYS = ('demo-server', 'demo-project')


def clear_fake_monitoring():
    ensure_fake_data_allowed('clear_fake_monitoring')
    sources = Source.objects.filter(resource__key__in=RESOURCE_KEYS, key__in=['demo', 'telemetry', 'demo-no-data', 'demo-stale', 'demo-disabled'])
    CapacityChange.objects.filter(allocation__resource__key__in=RESOURCE_KEYS).delete()
    CapacityAllocation.objects.filter(resource__key__in=RESOURCE_KEYS).delete()
    Delivery.objects.filter(source__in=sources).delete()
    CaseActivity.objects.filter(case__source__in=sources).delete()
    Case.objects.filter(source__in=sources).delete()
    Report.objects.filter(source__in=sources).delete()
    sources.delete()
    # Independently configured sources/resources keep their own ownership.
    Resource.objects.filter(key='demo-project', sources__isnull=True).delete()
    Resource.objects.filter(key='demo-server', sources__isnull=True).exclude(
        pk__in=Resource.objects.exclude(server=None).values('server_id'),
    ).delete()
