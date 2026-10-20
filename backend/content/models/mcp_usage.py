"""Durable migration evidence, independent of the panel's rolling event log."""
from django.db import models


class McpUsageDaily(models.Model):
    connector = models.ForeignKey('content.McpConnector', on_delete=models.PROTECT)
    credential = models.ForeignKey('content.McpCredential', on_delete=models.PROTECT)
    day = models.DateField()
    tool_name = models.CharField(max_length=120, default='')
    legacy = models.BooleanField(default=False)
    count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['connector', 'credential', 'day', 'tool_name', 'legacy'],
            name='mcp_usage_daily_key',
        )]


class McpObservation(models.Model):
    """A heartbeat gap restarts the continuous observation window."""
    key = models.CharField(max_length=20, primary_key=True, default='migration')
    continuous_since = models.DateTimeField()
    heartbeat_at = models.DateTimeField()
