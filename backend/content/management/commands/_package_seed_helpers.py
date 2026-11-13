"""Explicit isolated QA scenarios; never calls a payment provider or fabricates actual effort."""
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.models import ChangeRequest, Project
from accounts.models_requirement_packages import (
    PackageDecision, PackageExampleRevision, PackageMovement, PackageOperation,
    PackageOrder, PackageProjectSettings, PackageRequest, PackageSizingProposal,
)
from accounts.services.package_commerce import activate, quote
from accounts.services.issue_context import save_context
from content.fake_data import ensure_fake_data_allowed
from content.models import HourPackage


@transaction.atomic
def clear_fake_package_data():
    ensure_fake_data_allowed('delete_fake_data')
    PackageMovement.objects.update(reverses=None)
    PackageMovement.objects.all().delete()
    PackageDecision.objects.all().delete()
    PackageRequest.objects.update(current_proposal=None)
    PackageSizingProposal.objects.all().delete()
    PackageRequest.objects.all().delete()
    PackageOrder.objects.all().delete()
    PackageOperation.objects.all().delete()
    PackageProjectSettings.objects.all().delete()
    PackageExampleRevision.objects.filter(project__isnull=False).delete()


def seed_fake_packages(*, context):
    ensure_fake_data_allowed('create_fake_data')
    actor = get_user_model().objects.filter(is_staff=True).order_by('pk').first()
    package = HourPackage.objects.filter(pricing_model='requirements', nationality='COL', is_active=True).order_by('pk').first()
    if actor is None or package is None:
        return
    paid_at = timezone.make_aware(datetime.combine(context.anchor_date, time(12))) - timedelta(days=1)
    for project in Project.objects.select_related('client').order_by('pk')[:2]:
        snapshot = quote(package, project)
        order = PackageOrder.objects.create(project=project, client=project.client, package=package,
            snapshot=snapshot, currency=snapshot['currency'], subtotal=snapshot['subtotal'],
            tax_rate=snapshot['tax_rate'], total=snapshot['total'], method='external', recorded_by=actor)
        activate(order, actor=actor, paid_at=paid_at, reference='FAKE PA-254 · pago ficticio para QA')
        PackageProjectSettings.objects.get_or_create(project=project)
        ticket = ChangeRequest.objects.create(project=project, created_by=project.client,
            title='QA PA-254 · solicitud pendiente', description='Mostrar un dato que ya existe en el detalle del proyecto.')
        save_context(ticket, 'change', None, {'origin_kind': 'package', 'project_id': project.pk})
        PackageRequest.objects.create(project=project, client=project.client, ticket=ticket)
        PackageExampleRevision.objects.create(project=project, language='es', author=actor,
            examples={'XS': ['Mostrar un dato ya registrado en la ficha de este proyecto de demostración.']}, note='FAKE PA-254 · ejemplo para QA')
