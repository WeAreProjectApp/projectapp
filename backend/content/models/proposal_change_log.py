from django.db import models


class ProposalChangeLog(models.Model):
    """
    Tracks changes to a business proposal over time.

    Each row represents a single event or field change, enabling
    a full audit trail and version history for the proposal lifecycle.
    """

    class ChangeType(models.TextChoices):
        CREATED = 'created', 'Created'
        UPDATED = 'updated', 'Updated'
        SENT = 'sent', 'Sent'
        VIEWED = 'viewed', 'Viewed'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        RESENT = 'resent', 'Resent'
        EXPIRED = 'expired', 'Expired'
        DUPLICATED = 'duplicated', 'Duplicated'
        COMMENTED = 'commented', 'Commented'
        NEGOTIATING = 'negotiating', 'Negotiating'
        REENGAGEMENT = 'reengagement', 'Reengagement'
        CALL = 'call', 'Call'
        MEETING = 'meeting', 'Meeting'
        FOLLOWUP = 'followup', 'Follow-up'
        NOTE = 'note', 'Note'
        CALCULATOR_CONFIRMED = 'calc_confirmed', 'Calculator Confirmed'
        MODULE_INTERESTS = 'module_interests', 'Module interests updated'
        CALCULATOR_ABANDONED = 'calc_abandoned', 'Calculator Abandoned'
        AUTO_ARCHIVED = 'auto_archived', 'Auto Archived'
        STATUS_CHANGE = 'status_change', 'Status Change'
        CONDITIONAL_ACCEPT = 'cond_accepted', 'Conditional Acceptance'
        CALCULATOR_FOLLOWUP = 'calc_followup', 'Calculator Follow-up Sent'
        REQUIREMENT_CLICKED = 'req_clicked', 'Requirement Clicked'
        EMAIL_SENT = 'email_sent', 'Email Sent'
        SELLER_INACTIVITY_ESCALATION = 'seller_inactivity_escalation', 'Seller Inactivity Escalation'
        PLATFORM_LAUNCH = 'platform_launch', 'Platform Launch'
        STAGE_WARNING_SENT = 'stage_warning_sent', 'Stage Warning Sent'
        STAGE_OVERDUE_SENT = 'stage_overdue_sent', 'Stage Overdue Sent'
        STAGE_COMPLETED = 'stage_completed', 'Stage Completed'

    class ActorType(models.TextChoices):
        CLIENT = 'client', 'Client'
        SELLER = 'seller', 'Seller'
        SYSTEM = 'system', 'System'

    proposal = models.ForeignKey(
        'BusinessProposal',
        on_delete=models.CASCADE,
        related_name='change_logs',
    )
    change_type = models.CharField(
        max_length=30,
        choices=ChangeType.choices,
    )
    field_name = models.CharField(max_length=100, blank=True, default='')
    old_value = models.TextField(blank=True, default='')
    new_value = models.TextField(blank=True, default='')
    description = models.TextField(blank=True, default='')
    actor_type = models.CharField(
        max_length=10,
        choices=ActorType.choices,
        blank=True,
        default='',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Proposal Change Log'
        verbose_name_plural = 'Proposal Change Logs'
        indexes = [
            # Serves the per-proposal newest-first slice without a filesort
            # over the TEXT columns.
            models.Index(fields=['proposal', '-created_at'], name='pcl_proposal_created_idx'),
            # Serves the has_confirmed_module_selection EXISTS probes.
            models.Index(fields=['proposal', 'change_type'], name='pcl_proposal_type_idx'),
        ]

    def __str__(self):
        return (
            f'{self.proposal.client_name} — '
            f'{self.change_type} — {self.created_at}'
        )
