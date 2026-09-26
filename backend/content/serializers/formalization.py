"""Input validation for a private, reviewable formalization delivery."""
from rest_framework import serializers

from content.services.email_recipient_service import EmailRecipientValidationError, parse_email_recipients


class FormalizationSectionSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=10000, allow_blank=True)
    markdown = serializers.BooleanField(default=False)


class FormalizationPrepareSerializer(serializers.Serializer):
    # One contract, or the product and service contracts of a split closing,
    # plus the two annexes. The service layer checks them against the modality.
    documents = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'contract', 'contract_product', 'contract_service', 'commercial', 'technical',
        ]),
        max_length=4, default=list,
    )
    additional_doc_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=20, default=list)
    subject = serializers.CharField(max_length=500)
    greeting = serializers.CharField(max_length=1000)
    body = serializers.CharField(max_length=10000)
    footer = serializers.CharField(max_length=10000, allow_blank=True)
    sections = FormalizationSectionSerializer(many=True, max_length=20, default=list)
    recipient_emails = serializers.ListField(child=serializers.EmailField(), max_length=10)
    cc_emails = serializers.ListField(child=serializers.EmailField(), max_length=10, default=list)

    def validate_subject(self, value):
        if '\r' in value or '\n' in value:
            raise serializers.ValidationError('El asunto debe ocupar una sola línea.')
        return value

    def validate(self, attrs):
        if not attrs['documents'] and not attrs['additional_doc_ids']:
            raise serializers.ValidationError('Selecciona al menos un documento.')
        for field in ('documents', 'additional_doc_ids'):
            if len(set(attrs[field])) != len(attrs[field]):
                raise serializers.ValidationError({field: 'No repitas documentos.'})
        try:
            attrs['recipient_emails'], attrs['cc_emails'] = parse_email_recipients(attrs)
        except EmailRecipientValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs
