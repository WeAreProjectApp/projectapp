"""Private cell rental contract revisions and their transactional Document mirror."""
from django.db import models

from .building_on_demand import BuildingOnDemandRevision


class BuildingOnDemandContractRevision(BuildingOnDemandRevision):
    markdown = models.TextField()


class BuildingOnDemandContract(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    current_revision = models.ForeignKey(BuildingOnDemandContractRevision, on_delete=models.PROTECT, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='building_on_demand_contract_singleton')]

    @classmethod
    def load(cls, lock=False):
        queryset = cls.objects.select_for_update() if lock else cls.objects
        return queryset.select_related('current_revision').get(pk=1)


class BuildingOnDemandContractMirror(models.Model):
    contract = models.OneToOneField(BuildingOnDemandContract, on_delete=models.PROTECT, related_name='mirror')
    document = models.OneToOneField('content.Document', on_delete=models.PROTECT, related_name='building_on_demand_mirror')
    revision = models.ForeignKey(BuildingOnDemandContractRevision, on_delete=models.PROTECT, related_name='+')
    pdf_content = models.BinaryField()
    synced_at = models.DateTimeField()
