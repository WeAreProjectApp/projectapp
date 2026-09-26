from django.db import models


class ProposalDocument(models.Model):
    """
    Documents attached to a proposal during negotiation phase.

    System-generated documents (contract PDF) have is_generated=True
    and cannot be deleted by the user. User-uploaded documents (annexes,
    client docs) have is_generated=False.

    On proposal acceptance, these documents are synced to the platform
    deliverable as DeliverableFile attachments.
    """

    DOC_TYPE_CONTRACT = 'contract'
    DOC_TYPE_CONTRACT_PRODUCT = 'contract_product'
    DOC_TYPE_CONTRACT_SERVICE = 'contract_service'
    DOC_TYPE_AMENDMENT = 'amendment'
    DOC_TYPE_LEGAL_ANNEX = 'legal_annex'
    DOC_TYPE_CLIENT_DOCUMENT = 'client_document'
    DOC_TYPE_OTHER = 'other'

    # Generated contracts: the single contract and the two separate documents.
    CONTRACT_DOC_TYPES = frozenset({
        DOC_TYPE_CONTRACT, DOC_TYPE_CONTRACT_PRODUCT, DOC_TYPE_CONTRACT_SERVICE,
    })

    DOC_TYPE_CHOICES = [
        (DOC_TYPE_CONTRACT, 'Contrato'),
        (DOC_TYPE_CONTRACT_PRODUCT, 'Contrato de producto'),
        (DOC_TYPE_CONTRACT_SERVICE, 'Contrato de servicio'),
        (DOC_TYPE_AMENDMENT, 'Otrosí'),
        (DOC_TYPE_LEGAL_ANNEX, 'Anexo legal'),
        (DOC_TYPE_CLIENT_DOCUMENT, 'Documento del cliente'),
        (DOC_TYPE_OTHER, 'Otro'),
    ]

    proposal = models.ForeignKey(
        'content.BusinessProposal',
        on_delete=models.CASCADE,
        related_name='proposal_documents',
    )
    document_type = models.CharField(
        max_length=30,
        choices=DOC_TYPE_CHOICES,
        default=DOC_TYPE_OTHER,
    )
    title = models.CharField(max_length=300)
    file = models.FileField(upload_to='proposal_documents/')
    custom_type_label = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Custom label when document_type is "other".',
    )
    is_generated = models.BooleanField(
        default=False,
        help_text='True for system-generated PDFs (contract). Cannot be deleted by user.',
    )
    content_markdown = models.TextField(
        blank=True, default='',
        help_text='Internal snapshot of the text used to generate the stored contract PDF.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_document_type_display()} — {self.title}'
