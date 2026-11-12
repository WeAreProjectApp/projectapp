"""The send log as a client's email history reads it.

Same row as the accounting Historial — deliberately a subclass, so that
surface's payload stays byte-identical — plus the audience the modal splits
on, and a notice label that also knows the proposal and diagnostic traffic
the accounting one has no reason to name.
"""

from rest_framework import serializers

from content.serializers.accounting import (
    EMAIL_TEMPLATE_LABELS,
    EmailLogSerializer,
)

# The keys in neither EMAIL_TEMPLATE_LABELS nor the editable template
# registry. Without them the "Aviso" column would render raw snake_case.
EXTRA_TEMPLATE_LABELS = {
    'login_code': 'Código de acceso',
    'magic_link': 'Acceso directo',
    'team_copy': 'Copia al equipo',
    'diagnostic_initial_sent': 'Diagnóstico inicial',
    'diagnostic_final_sent': 'Diagnóstico final',
    'diagnostic_custom_email': 'Correo de diagnóstico',
    'diagnostic_documents_sent': 'Documentos del diagnóstico',
}


class ClientEmailLogSerializer(EmailLogSerializer):
    audience_label = serializers.CharField(
        source='get_audience_display', read_only=True,
    )

    class Meta(EmailLogSerializer.Meta):
        fields = EmailLogSerializer.Meta.fields + (
            'audience', 'audience_label', 'proposal',
        )

    def get_template_label(self, obj):
        label = EMAIL_TEMPLATE_LABELS.get(obj.template_key)
        if label:
            return label
        from content.services.email_template_registry import get_template_entry

        entry = get_template_entry(obj.template_key) or {}
        return (
            entry.get('name')
            or EXTRA_TEMPLATE_LABELS.get(obj.template_key)
            or obj.template_key
        )
