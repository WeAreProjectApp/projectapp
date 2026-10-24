from content.serializers.editorial import EditorialModelSerializer
from rest_framework import serializers

from accounts.models import UserProfile
from accounts.services.proposal_client_service import build_client_display_name
from content.models import (
    AdditionalModule,
    AdditionalModuleCategory,
    AdditionalModuleShareLink,
)


class StringListField(serializers.ListField):
    child = serializers.CharField(max_length=500000, trim_whitespace=True)


class AdditionalModuleCategorySerializer(EditorialModelSerializer):
    module_count = serializers.SerializerMethodField()
    active_module_count = serializers.SerializerMethodField()

    class Meta:
        model = AdditionalModuleCategory
        fields = (
            'id', 'slug', 'name_es', 'name_en', 'order', 'is_active',
            'module_count', 'active_module_count', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'order', 'created_at', 'updated_at')

    def get_module_count(self, obj):
        annotated = getattr(obj, 'module_count_annotated', None)
        return annotated if annotated is not None else obj.modules.count()

    def get_active_module_count(self, obj):
        annotated = getattr(obj, 'active_module_count_annotated', None)
        return (
            annotated
            if annotated is not None
            else obj.modules.filter(is_active=True).count()
        )


class AdditionalModuleAdminSerializer(EditorialModelSerializer):
    problems_solved_es = StringListField()
    problems_solved_en = StringListField()
    integrations_es = StringListField()
    integrations_en = StringListField()
    implementation_requirements_es = StringListField()
    implementation_requirements_en = StringListField()
    category_name_es = serializers.CharField(source='category.name_es', read_only=True)
    category_name_en = serializers.CharField(source='category.name_en', read_only=True)

    class Meta:
        model = AdditionalModule
        fields = (
            'id', 'category', 'category_name_es', 'category_name_en', 'slug',
            'icon', 'order', 'is_active', 'name_es', 'name_en', 'summary_es',
            'summary_en', 'what_is_es', 'what_is_en', 'purpose_es',
            'purpose_en', 'problems_solved_es', 'problems_solved_en',
            'integrations_es', 'integrations_en',
            'implementation_requirements_es',
            'implementation_requirements_en', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'order', 'created_at', 'updated_at')
        # Position is assigned under a row lock by the catalog service. DRF's
        # generated unique-together validator sees the model default (0)
        # before that assignment and would reject every second module.
        validators = []

    def validate(self, attrs):
        from content.services.editorial_format import plain_text
        formats = attrs.get('text_formats', getattr(self.instance, 'text_formats', {})) or {}
        for field in ('summary_es', 'summary_en'):
            if field in attrs and len(plain_text(attrs[field], format=formats.get('/' + field, 'plain'))) > 360:
                raise serializers.ValidationError({field: 'Usa hasta 360 caracteres visibles.'})
        for field in (
            'problems_solved_es', 'problems_solved_en', 'integrations_es',
            'integrations_en', 'implementation_requirements_es',
            'implementation_requirements_en',
        ):
            value = attrs.get(field)
            for index, item in enumerate(value or []):
                if len(plain_text(item, format=formats.get(f'/{field}/{index}', 'plain'))) > 500:
                    raise serializers.ValidationError({field: 'Cada elemento admite hasta 500 caracteres visibles.'})
            if value is not None and not value:
                raise serializers.ValidationError({
                    field: 'Incluye al menos un elemento.',
                })
        return attrs


class AdditionalModuleShareCreateSerializer(serializers.Serializer):
    recipient_label = serializers.CharField(max_length=255, trim_whitespace=True)
    client_id = serializers.PrimaryKeyRelatedField(
        source='client',
        queryset=UserProfile.objects.clients(),
        allow_null=True,
        required=False,
    )
    language = serializers.ChoiceField(
        choices=AdditionalModuleShareLink.Language.choices,
        required=False,
        default=AdditionalModuleShareLink.Language.SPANISH,
    )
    selected_module_ids = serializers.PrimaryKeyRelatedField(
        source='selected_modules',
        queryset=AdditionalModule.objects.filter(is_active=True),
        many=True,
    )
    show_explainer_video = serializers.BooleanField(required=False, default=True)

    def validate_selected_module_ids(self, value):
        ids = [module.pk for module in value]
        if not ids:
            raise serializers.ValidationError('Selecciona al menos un módulo.')
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('La selección contiene módulos repetidos.')
        return value

    def create(self, validated_data):
        modules = validated_data.pop('selected_modules')
        share_link = AdditionalModuleShareLink.objects.create(**validated_data)
        share_link.selected_modules.set(modules)
        return share_link


class AdditionalModuleShareAdminSerializer(EditorialModelSerializer):
    client_name = serializers.SerializerMethodField()
    selected_modules = serializers.SerializerMethodField()
    public_path = serializers.SerializerMethodField()

    class Meta:
        model = AdditionalModuleShareLink
        fields = (
            'id', 'uuid', 'recipient_label', 'client', 'client_name', 'language',
            'selected_modules', 'public_path', 'is_active', 'revoked_at',
            'show_explainer_video', 'view_count', 'first_viewed_at',
            'last_viewed_at', 'created_at',
        )

    def get_client_name(self, obj):
        return build_client_display_name(obj.client) if obj.client else ''

    def get_selected_modules(self, obj):
        modules = obj.selected_modules.select_related('category').order_by(
            'category__order', 'order', 'id',
        )
        return [
            {
                'id': module.id,
                'slug': module.slug,
                'name_es': module.name_es,
                'name_en': module.name_en,
                'is_active': module.is_active,
            }
            for module in modules
        ]

    def get_public_path(self, obj):
        locale = 'es-co' if obj.language == 'es' else 'en-us'
        return f'/{locale}/additional-modules/share/{obj.uuid}'


class AdditionalModuleShareVideoSerializer(EditorialModelSerializer):
    """Only the explainer switch is editable once a link has been shared."""

    class Meta:
        model = AdditionalModuleShareLink
        fields = ('show_explainer_video',)
        extra_kwargs = {'show_explainer_video': {'required': True}}


class AdditionalModulePdfSelectionSerializer(serializers.Serializer):
    language = serializers.ChoiceField(
        choices=AdditionalModuleShareLink.Language.choices,
        required=False,
        default=AdditionalModuleShareLink.Language.SPANISH,
    )
    recipient_label = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        default='',
    )
    module_ids = serializers.PrimaryKeyRelatedField(
        source='modules',
        queryset=AdditionalModule.objects.filter(is_active=True),
        many=True,
    )

    def validate_module_ids(self, value):
        ids = [module.pk for module in value]
        if not ids:
            raise serializers.ValidationError('Selecciona al menos un módulo.')
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('La selección contiene módulos repetidos.')
        return value


class AdditionalModuleTrackSerializer(serializers.Serializer):
    session_id = serializers.RegexField(
        regex=r'^[A-Za-z0-9_-]{8,64}$',
        max_length=64,
        error_messages={
            'invalid': 'Usa un identificador de sesión válido.',
        },
    )
