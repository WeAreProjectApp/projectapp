"""Durable identities for a hosting obligation, its cash receipt and its allocation."""
from django.db import models


class ReceiptIdentifierField(models.CharField):
    """A bank reference is opaque: MySQL's default accent/case folding changes its identity."""
    def db_parameters(self, connection):
        parameters = super().db_parameters(connection)
        if connection.vendor == 'mysql':
            parameters['collation'] = 'utf8mb4_bin'
        return parameters


class HostingIncomePeriod(models.Model):
    hosting = models.ForeignKey('accounts.ProjectHosting', on_delete=models.PROTECT)
    income = models.OneToOneField('content.IncomeRecord', on_delete=models.PROTECT, related_name='hosting_period')
    start = models.DateField()
    end = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['hosting', 'start', 'end'], name='hosting_income_window'),
            models.CheckConstraint(condition=models.Q(end__gte=models.F('start')), name='hosting_window_order'),
        ]


class HostingReceipt(models.Model):
    """A source's receipt number identifies actual cash across independent requests."""
    issuer = ReceiptIdentifierField(max_length=96)
    reference = ReceiptIdentifierField(max_length=128)
    settlement = models.OneToOneField('content.IncomeSettlement', null=True, on_delete=models.PROTECT,
                                      related_name='hosting_receipt')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['issuer', 'reference'], name='hosting_cash_receipt'),
        ]


class HostingReceiptAttempt(models.Model):
    id = models.UUIDField(primary_key=True)
    receipt = models.ForeignKey(HostingReceipt, on_delete=models.PROTECT)
    payload_hash = models.CharField(max_length=64)


class HostingReceiptAllocation(models.Model):
    receipt = models.ForeignKey(HostingReceipt, related_name='allocations', on_delete=models.PROTECT)
    period = models.ForeignKey(HostingIncomePeriod, related_name='allocations', on_delete=models.PROTECT)
    liquid = models.OneToOneField('content.IncomeRecord', related_name='hosting_allocation', on_delete=models.PROTECT)
    cycle = models.OneToOneField('content.HostingCycle', related_name='receipt_allocation', on_delete=models.PROTECT)
    # An explicitly adopted pre-existing cycle survives financial reversal.
    existing_cycle = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['receipt', 'period'], name='hosting_receipt_allocation'),
        ]
