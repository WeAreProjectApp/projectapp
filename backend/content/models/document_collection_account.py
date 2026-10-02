from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

from content.models.history_tracked import HistoryTrackedModel


class DocumentCollectionAccount(HistoryTrackedModel):
    """1:1 extension for collection_account document type; stores snapshots at issue time."""

    class PaymentTermType(models.TextChoices):
        AGAINST_DELIVERY = 'against_delivery', 'Against delivery'
        FIXED_DATE = 'fixed_date', 'Fixed date'
        DAYS_AFTER_ISSUE = 'days_after_issue', 'Days after issue'

    document = models.OneToOneField(
        'content.Document',
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='collection_account',
    )
    vat_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
    )
    billing_concept = models.CharField(max_length=512, blank=True, default='')
    payment_term_type = models.CharField(
        max_length=32,
        choices=PaymentTermType.choices,
        default=PaymentTermType.DAYS_AFTER_ISSUE,
    )
    payment_term_days = models.PositiveIntegerField(null=True, blank=True)

    payer_name = models.CharField(max_length=255, blank=True, default='')
    payer_identification = models.CharField(max_length=64, blank=True, default='')
    payer_identification_type = models.CharField(max_length=32, blank=True, default='')
    payer_address = models.CharField(max_length=512, blank=True, default='')
    payer_phone = models.CharField(max_length=64, blank=True, default='')
    payer_email = models.EmailField(blank=True, default='')

    customer_name = models.CharField(max_length=255, blank=True, default='')
    customer_identification = models.CharField(max_length=64, blank=True, default='')
    customer_identification_type = models.CharField(max_length=32, blank=True, default='')
    customer_contact_name = models.CharField(max_length=255, blank=True, default='')
    customer_email = models.EmailField(blank=True, default='')
    customer_address = models.CharField(max_length=512, blank=True, default='')
    # The brand/project the cobro is for, printed on its own line so it never
    # again has to masquerade as the client's name. Snapshot rather than a
    # live read of `Document.project`: that FK is SET_NULL, so deleting a
    # project would silently erase the line from a reprint of an already
    # issued document.
    customer_project_name = models.CharField(
        max_length=200, blank=True, default='',
    )

    observations = models.TextField(blank=True, default='')
    support_reference = models.CharField(max_length=512, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'CollectionAccount doc={self.document_id}'
