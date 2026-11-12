"""Release calculator business records during a confirmed development reset."""

from accounts.models import Project
from content.fake_data import ensure_fake_data_allowed
from content.models import (
    CalculatorActual,
    CalculatorEstimate,
    Document,
    ProjectCalculatorChange,
    ProjectCalculatorVersion,
    RequirementCalculator,
)
from content.services.calculator_documents import calculator_document_write
from django.db import transaction


@transaction.atomic
def clear_fake_calculator_data():
    """Preserve the general catalog while dissolving the protected test graph."""
    ensure_fake_data_allowed('delete_fake_data')
    document_ids = list(RequirementCalculator.objects.values_list('document_id', flat=True))
    CalculatorActual.objects.update(supersedes=None)
    CalculatorActual.objects.all().delete()
    CalculatorEstimate.objects.all().delete()
    ProjectCalculatorChange.objects.all().delete()
    Project.objects.exclude(calculator_document=None).update(calculator_document=None)
    ProjectCalculatorVersion.objects.all().delete()
    # A formerly adopted document may still belong to a demo project/folder.
    # Configuration must survive the wipe without protecting those demo roots.
    with calculator_document_write():
        Document.objects.filter(pk__in=document_ids).update(project=None, client_user=None, folder=None)
    return document_ids
