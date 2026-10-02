from django.db import models

from content.models.history_tracked import HistoryTrackedModel


class ProposalSection(HistoryTrackedModel):
    """
    Individual section within a business proposal.

    Each section maps to a Vue component on the frontend via section_type.
    Content is stored as JSON matching the props schema of each component.
    """

    class SectionType(models.TextChoices):
        GREETING = 'greeting', 'Greeting'
        EXECUTIVE_SUMMARY = 'executive_summary', 'Executive Summary'
        CONTEXT_DIAGNOSTIC = 'context_diagnostic', 'Context & Diagnostic'
        CONVERSION_STRATEGY = 'conversion_strategy', 'Conversion Strategy'
        DESIGN_UX = 'design_ux', 'Design & UX'
        CREATIVE_SUPPORT = 'creative_support', 'Creative Support'
        DEVELOPMENT_STAGES = 'development_stages', 'Development Stages'
        PROCESS_METHODOLOGY = 'process_methodology', 'Process Methodology'
        FUNCTIONAL_REQUIREMENTS = 'functional_requirements', 'Functional Requirements'
        TIMELINE = 'timeline', 'Timeline'
        INVESTMENT = 'investment', 'Investment'
        PROPOSAL_SUMMARY = 'proposal_summary', 'Proposal Summary'
        FINAL_NOTE = 'final_note', 'Final Note'
        NEXT_STEPS = 'next_steps', 'Next Steps'
        TECHNICAL_DOCUMENT = 'technical_document', 'Technical Document'
        VALUE_ADDED_MODULES = 'value_added_modules', 'Value Added Modules'
        ROI_PROJECTION = 'roi_projection', 'ROI Projection'
        COMMERCIAL_CONDITIONS = 'commercial_conditions', 'Commercial Conditions'

    proposal = models.ForeignKey(
        'BusinessProposal',
        on_delete=models.CASCADE,
        related_name='sections',
    )
    section_type = models.CharField(max_length=30, choices=SectionType.choices)
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_enabled = models.BooleanField(default=True)
    content_json = models.JSONField(default=dict, blank=True)
    is_wide_panel = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']
        unique_together = ['proposal', 'section_type']
        verbose_name = 'Proposal Section'
        verbose_name_plural = 'Proposal Sections'

    def __str__(self):
        return f'{self.proposal.client_name} — {self.get_section_type_display()}'


    def save(self, *args, **kwargs):
        from content.services.proposal_content_cleanup import without_module_percentages
        self.content_json = without_module_percentages(self.content_json)
        return super().save(*args, **kwargs)
