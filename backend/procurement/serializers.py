from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .filters import StrictSerializer, validate_filters
from .models import Alert, Classification, Delivery, Opportunity, SavedSearch, Settings, SyncRun


class OpportunitySerializer(serializers.ModelSerializer):
    is_open = serializers.BooleanField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = Opportunity
        exclude = ['source_data']


class OpportunityListSerializer(OpportunitySerializer):
    class Meta(OpportunitySerializer.Meta):
        exclude = ['source_data', 'description']


class ClassificationSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = Classification
        fields = ['id', 'opportunity', 'owner', 'owner_name', 'state', 'notes', 'updated_at']


class ClassificationWriteSerializer(StrictSerializer):
    state = serializers.ChoiceField(choices=Classification.STATES)
    notes = serializers.CharField(max_length=12000, allow_blank=True, required=False, default='')

    def validate(self, attrs):
        if attrs['state'] == 'discarded' and not attrs['notes'].strip():
            raise serializers.ValidationError({'notes': 'Indica el motivo del descarte.'})
        return attrs


class SettingsWriteSerializer(StrictSerializer):
    sync_enabled = serializers.BooleanField(required=False)
    email_enabled = serializers.BooleanField(required=False)
    sync_time = serializers.TimeField(required=False)
    daily_time = serializers.TimeField(required=False)
    weekly_time = serializers.TimeField(required=False)
    weekly_day = serializers.IntegerField(min_value=0, max_value=6, required=False)
    lookback_days = serializers.IntegerField(min_value=1, max_value=365, required=False)


class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Settings
        fields = '__all__'


class AlertWriteSerializer(StrictSerializer):
    name = serializers.CharField(max_length=150, required=False)
    filters = serializers.JSONField(required=False)
    recipients = serializers.ListField(child=serializers.EmailField(), min_length=1, max_length=10, required=False)
    frequency = serializers.ChoiceField(choices=Alert.FREQUENCIES, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate_filters(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Usa un objeto de filtros.')
        return validate_filters(value)

    def validate_recipients(self, value):
        emails = [email.strip().lower() for email in value]
        if len(set(emails)) != len(emails):
            raise serializers.ValidationError('No repitas destinatarios.')
        return emails

    def validate(self, attrs):
        if self.context.get('creating'):
            missing = [key for key in ('name', 'recipients', 'filters') if key not in attrs]
            if missing:
                raise serializers.ValidationError({key: 'Campo obligatorio.' for key in missing})
        return attrs


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = '__all__'


class SavedSearchWriteSerializer(StrictSerializer):
    name = serializers.CharField(max_length=150, required=False)
    filters = serializers.JSONField(required=False)
    is_favorite = serializers.BooleanField(required=False)

    def validate_filters(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Usa un objeto de filtros.')
        return validate_filters(value)


class SavedSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedSearch
        fields = '__all__'


class DeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = Delivery
        fields = '__all__'


class DeliverySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Delivery
        exclude = ['snapshot']


class SyncRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncRun
        fields = '__all__'


class QuerySerializer(StrictSerializer):
    filters = serializers.JSONField(required=False, default=dict)
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=25)
    ordering = serializers.ChoiceField(choices=['-published_at', 'closing_at', '-budget', 'entity_name'], required=False, default='-published_at')
    classified = serializers.BooleanField(required=False, default=False)
    state = serializers.ChoiceField(choices=Classification.STATES, required=False)

    def validate_filters(self, value):
        return validate_filters(value)


def validated(cls, data, **context):
    serializer = cls(data=data, context=context)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def owner_for_mcp(owner_id):
    return get_user_model().objects.get(pk=owner_id, is_staff=True, is_active=True)
