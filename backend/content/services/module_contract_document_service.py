"""Document-manager editing of the two versioned program contracts."""
from rest_framework import serializers

from content.models import Document
from content.services.contract_mirror_service import module_contract_mirror


class ModuleContractDocumentError(ValueError):
    def __init__(self, message, *, code='VALIDATION_ERROR', details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


PRESENTATION_FIELDS = ('include_portada', 'include_subportada', 'include_contraportada', 'template_style')


class ModuleContractUpdateSerializer(serializers.Serializer):
    if_match = serializers.CharField()
    change_note = serializers.CharField(max_length=4000)
    content_markdown = serializers.CharField(required=False, trim_whitespace=False, max_length=250000)
    text_formats = serializers.JSONField(required=False)
    include_portada = serializers.BooleanField(required=False)
    include_subportada = serializers.BooleanField(required=False)
    include_contraportada = serializers.BooleanField(required=False)
    template_style = serializers.ChoiceField(choices=Document.TemplateStyle.choices, required=False)

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: 'Este campo permanece protegido en el contrato.' for key in sorted(unknown)})
        return super().to_internal_value(data)

    def validate_text_formats(self, value):
        if not isinstance(value, dict) or set(value) - {'/content_markdown'} or value.get('/content_markdown') not in ('markdown', 'markdown_html_v1'):
            raise serializers.ValidationError('El contrato usa Markdown con el formato editorial admitido.')
        return value


def update_contract_document(document, data, *, actor, credential=None):
    """Delegate to the domain writer; it locks and checks both identities."""
    from content.services import building_with_us_contract_service, building_on_demand_contract_service
    from content.services.building_with_us_content import BuildingWithUsError
    from content.services.building_on_demand_content import BuildingOnDemandError

    binding = module_contract_mirror(document)
    if binding is None:
        raise ModuleContractDocumentError('El documento no corresponde a un contrato de programa.')
    if not data.get('if_match'):
        raise ModuleContractDocumentError('Vuelve a cargar el contrato antes de guardar.', code='PRECONDITION_REQUIRED')
    serializer = ModuleContractUpdateSerializer(data=data)
    if not serializer.is_valid():
        raise ModuleContractDocumentError('Revisa los campos del contrato.', details=serializer.errors)
    values = serializer.validated_data
    service = building_with_us_contract_service if binding[1] == 'building_with_us' else building_on_demand_contract_service
    try:
        service.apply_update({
            **({'markdown': values['content_markdown']} if 'content_markdown' in values else {}),
            'change_note': values['change_note'],
        }, actor=actor, credential=credential,
            document_if_match=(document.pk, values['if_match']),
            document_options={key: values[key] for key in PRESENTATION_FIELDS if key in values})
    except (BuildingWithUsError, BuildingOnDemandError) as exc:
        raise ModuleContractDocumentError(str(exc), code=exc.code, details=exc.details) from exc
    return Document.objects.select_related('folder', 'document_type').get(pk=document.pk)
