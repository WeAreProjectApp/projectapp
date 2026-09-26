from content.services.entity_history import historical_write

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from accounts.models import Project, UserProfile
from content.models import (
    AccountingChangeLog,
    Document,
    DocumentFolder,
    DocumentTag,
    EmailLog,
    EmailLogTarget,
)
from content.serializers.document_state import (
    DocumentBrowseStateEpisodeSerializer,
    DocumentNoteSerializer,
    DocumentStateEpisodeSerializer,
)
from content.services.document_archive_service import (
    DocumentArchiveError, ensure_active_target,
)
from content.services.document_notes import (
    DocumentNotesValidationError, normalize_client_custom_notes,
)
from content.services.document_type_codes import COLLECTION_ACCOUNT


class ClientCustomNotesField(serializers.JSONField):
    """Ordered private-note payload with one contract for every write path."""

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_client_custom_notes(value)
        except DocumentNotesValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class _TagSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTag
        fields = ('id', 'name', 'color')


def _archived_cause(obj):
    """'folder' si lo arrastró el archivado de una carpeta, 'manual' si no."""
    if not obj.is_archived:
        return None
    return 'folder' if obj.archived_via_folder_id else 'manual'


def apply_client_project_association(attrs, instance=None, *, snapshot_client_name=True):
    """Resuelve el trío client/project/client_name manteniendo el invariante.

    Regla única para todas las vías de escritura del panel: un documento con
    proyecto siempre pertenece al cliente del proyecto. `client` llega como
    UserProfile (el vocabulario del panel) y se persiste como `client_user`
    (auth.User, lo que ya escriben las cuentas de cobro y lee el portal).
    Elegir proyecto sin cliente lo deriva; un par inconsistente se rechaza con
    error en `project`; cambiar de cliente sin reasignar el proyecto lo
    desvincula (patrón income). `client_name` se autocompleta con el display
    name sólo cuando el cliente cambia y no vino un valor propio: un texto
    personalizado sobrevive a los saves que no tocan la asociación.

    Las CARPETAS usan la misma regla con `snapshot_client_name=False`: llevan
    el par cliente/proyecto pero no el rótulo de texto libre, que existe sólo
    para que un documento conserve a quién se le emitió aunque el cliente
    cambie de nombre.
    """
    from accounts.services.proposal_client_service import build_client_display_name
    from content.serializers.accounting import validate_project_client_match

    client_sent = 'client' in attrs
    if client_sent:
        profile = attrs.pop('client')
        attrs['client_user'] = profile.user if profile else None

    previous_client = instance.client_user if instance else None
    if (
        instance is not None
        and client_sent
        and 'project' not in attrs
        and attrs['client_user'] != previous_client
    ):
        attrs['project'] = None

    project = attrs.get('project', instance.project if instance else None)
    client_user = attrs['client_user'] if 'client_user' in attrs else previous_client

    if project is not None and client_user is None:
        attrs['client_user'] = project.client
        client_user = project.client

    client_profile = getattr(client_user, 'profile', None) if client_user else None
    if project is not None and client_profile is not None:
        validate_project_client_match(project, client_profile)

    new_client = attrs.get('client_user')
    client_changed = (
        instance is None
        or instance.client_user_id != getattr(new_client, 'pk', None)
    )
    if (
        snapshot_client_name
        and 'client_user' in attrs
        and new_client is not None
        and client_changed
        and not attrs.get('client_name')
        and client_profile is not None
    ):
        attrs['client_name'] = build_client_display_name(client_profile)
    return attrs


def _inherit_from_folder(attrs, instance, *, adopt=False):
    """Toma cliente/proyecto de la carpeta destino cuando corresponde.

    La carpeta organiza, no es dueña: por eso heredar sólo ocurre cuando no
    pisa nada —el documento no tiene cliente— o cuando el operador lo pidió
    explícitamente con `adopt_folder_client` (la respuesta a la pregunta que
    hace el gestor al mover a la carpeta de otro cliente). Mandar `client` en
    la misma petición gana siempre: eso ya es una decisión, no una herencia.

    El proyecto sólo se copia si la carpeta tiene uno; si no, se deja que la
    regla común lo desvincule al cambiar de cliente.
    """
    folder = attrs.get('folder')
    if folder is None or 'client' in attrs:
        return
    profile = getattr(folder.client_user, 'profile', None)
    if profile is None:
        return
    current_client_id = instance.client_user_id if instance else None
    if current_client_id is not None and not adopt:
        return
    attrs['client'] = profile
    if folder.project_id:
        attrs['project'] = folder.project


class ClientProjectReadMixin:
    """Campos de asociación compartidos por los serializers de lectura.

    `client` habla en pk de UserProfile — el vocabulario de todo el panel —
    aunque el modelo persista `client_user` (auth.User): la conversión vive
    acá y no en cada consumidor.
    """

    def get_client(self, obj):
        profile = self._client_profile(obj)
        return profile.id if profile else None

    def get_client_display_name(self, obj):
        profile = self._client_profile(obj)
        if profile is None:
            return None
        from accounts.services.proposal_client_service import (
            build_client_display_name,
        )
        return build_client_display_name(profile)

    @staticmethod
    def _client_profile(obj):
        if not obj.client_user_id:
            return None
        return getattr(obj.client_user, 'profile', None)


class GeneratedDocumentReadMixin:
    """Derived status and immutable-source metadata for document readers."""

    def get_display_state(self, obj):
        document_type = getattr(obj, 'document_type', None)
        if getattr(document_type, 'code', None) != COLLECTION_ACCOUNT:
            return None

        states = {
            Document.CommercialStatus.DRAFT: {
                'key': 'draft', 'label': 'Borrador', 'variant': 'neutral',
            },
            Document.CommercialStatus.PAID: {
                'key': 'paid', 'label': 'Pagada', 'variant': 'success',
            },
            Document.CommercialStatus.CANCELLED: {
                'key': 'cancelled', 'label': 'Anulada', 'variant': 'danger',
            },
        }
        if obj.commercial_status in states:
            return states[obj.commercial_status]

        delivered = getattr(obj, '_has_delivered_collection_email', None)
        failed = getattr(obj, '_has_failed_collection_email', None)
        if delivered is None or failed is None:
            targets = EmailLogTarget.objects.filter(
                entity_type=AccountingChangeLog.EntityType.COLLECTION_ACCOUNT,
                object_id=obj.pk,
            )
            delivered = targets.exclude(email_log__status=EmailLog.Status.FAILED).exists()
            failed = targets.filter(email_log__status=EmailLog.Status.FAILED).exists()
        if delivered:
            return {'key': 'sent', 'label': 'Enviada', 'variant': 'success'}
        if failed:
            return {
                'key': 'send_failed',
                'label': 'Envío fallido',
                'variant': 'danger',
            }
        return {'key': 'issued', 'label': 'Emitida', 'variant': 'info'}

    def get_is_generated_snapshot(self, obj):
        return obj.is_generated_snapshot

    def get_is_contract_mirror(self, obj):
        return obj.is_contract_mirror


class DocumentThreadSummaryMixin:
    """Compact thread context shared by document list and detail payloads."""

    def get_thread_summary(self, obj):
        try:
            membership = obj.thread_item
        except (AttributeError, ObjectDoesNotExist):
            return None
        count = getattr(obj, 'thread_document_count', None)
        if count is None:
            count = membership.thread.items.count()
        return {
            'id': membership.thread_id,
            'title': membership.thread.title,
            'document_count': count,
        }


class DocumentListSerializer(
    GeneratedDocumentReadMixin,
    ClientProjectReadMixin,
    DocumentThreadSummaryMixin,
    serializers.ModelSerializer,
):
    """Lightweight serializer for document lists."""

    folder_name = serializers.CharField(source='folder.name', read_only=True, default=None)
    tag_details = _TagSummarySerializer(source='tags', many=True, read_only=True)
    content_excerpt = serializers.SerializerMethodField()
    archived_cause = serializers.SerializerMethodField()
    client = serializers.SerializerMethodField()
    client_display_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source='project.name', read_only=True, default=None)
    # The documents UI locks issued cuentas; both fields feed that branch.
    document_type_code = serializers.CharField(
        source='document_type.code', read_only=True, default=None,
    )
    active_states = serializers.SerializerMethodField()
    display_state = serializers.SerializerMethodField()
    is_generated_snapshot = serializers.SerializerMethodField()
    is_contract_mirror = serializers.SerializerMethodField()
    source_proposal_id = serializers.IntegerField(read_only=True)
    thread_summary = serializers.SerializerMethodField()

    EXCERPT_MAX_CHARS = 500

    class Meta:
        model = Document
        fields = (
            'id', 'uuid', 'title', 'slug', 'status', 'is_client_visible',
            'client_name', 'client', 'client_display_name',
            'project', 'project_name',
            'document_type_code', 'commercial_status',
            'display_state', 'is_generated_snapshot', 'is_contract_mirror',
            'source_proposal_id', 'source_version',
            'issue_date',
            'language', 'cover_type', 'template_style',
            'include_portada', 'include_subportada', 'include_contraportada',
            'folder', 'folder_name', 'tag_details', 'active_states',
            'thread_summary',
            'content_excerpt',
            'created_at', 'updated_at',
            'is_archived', 'archived_at', 'archived_cause',
        )

    def get_archived_cause(self, obj):
        return _archived_cause(obj)

    def get_active_states(self, obj):
        if (
            getattr(getattr(obj, 'document_type', None), 'code', None)
            == COLLECTION_ACCOUNT
        ):
            return []
        episodes = getattr(obj, 'prefetched_active_state_episodes', None)
        if episodes is None:
            episodes = (
                obj.state_episodes.filter(closed_at__isnull=True)
                .select_related('state__group', 'opened_by', 'closed_by')
            )
        episodes = sorted(
            episodes,
            key=lambda item: (
                item.state.group.order,
                0 if item.state.system_key == 'needs_fix' else 1,
                item.state.order,
                item.state.name.casefold(),
            ),
        )
        return DocumentStateEpisodeSerializer(episodes, many=True).data

    def get_content_excerpt(self, obj):
        """First ~500 chars of the markdown, cut at the last complete line.

        Feeds the gallery mini-preview so the list payload stays small; the
        frontend closes any dangling code fence before rendering it.
        """
        markdown = obj.content_markdown or ''
        if len(markdown) <= self.EXCERPT_MAX_CHARS:
            return markdown
        cut = markdown[:self.EXCERPT_MAX_CHARS]
        last_newline = cut.rfind('\n')
        if last_newline > 0:
            cut = cut[:last_newline]
        return cut


class DocumentBrowseSerializer(DocumentListSerializer):
    """Document-manager row without state history, notes or audit actors."""

    def get_active_states(self, obj):
        if (
            getattr(getattr(obj, 'document_type', None), 'code', None)
            == COLLECTION_ACCOUNT
        ):
            return []
        episodes = getattr(obj, 'prefetched_active_state_episodes', [])
        episodes = sorted(
            episodes,
            key=lambda item: (
                item.state.group.order,
                0 if item.state.system_key == 'needs_fix' else 1,
                item.state.order,
                item.state.name.casefold(),
            ),
        )
        return DocumentBrowseStateEpisodeSerializer(episodes, many=True).data


class DocumentDetailSerializer(
    GeneratedDocumentReadMixin,
    ClientProjectReadMixin,
    DocumentThreadSummaryMixin,
    serializers.ModelSerializer,
):
    """Full serializer for document detail view."""

    folder_name = serializers.CharField(source='folder.name', read_only=True, default=None)
    client = serializers.SerializerMethodField()
    client_display_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source='project.name', read_only=True, default=None)
    # The edit page locks issued cuentas; both fields feed that branch.
    document_type_code = serializers.CharField(
        source='document_type.code', read_only=True, default=None,
    )
    tag_details = _TagSummarySerializer(source='tags', many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        source='tags', many=True, read_only=True,
    )
    archived_cause = serializers.SerializerMethodField()
    active_states = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()
    display_state = serializers.SerializerMethodField()
    is_generated_snapshot = serializers.SerializerMethodField()
    is_contract_mirror = serializers.SerializerMethodField()
    source_proposal_id = serializers.IntegerField(read_only=True)
    billing_notes = serializers.CharField(source='notes', read_only=True)
    collection_account_observations = serializers.CharField(
        source='collection_account.observations', read_only=True, default='',
    )
    thread_summary = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = (
            'id', 'uuid', 'title', 'slug', 'status', 'is_client_visible',
            'content_markdown', 'content_json',
            'client_name', 'client', 'client_display_name',
            'client_email_subject', 'client_email_body',
            'client_whatsapp_message', 'client_custom_notes',
            'project', 'project_name',
            'document_type_code', 'commercial_status',
            'display_state', 'is_generated_snapshot', 'is_contract_mirror',
            'source_proposal_id', 'source_version',
            'public_number', 'issue_date', 'due_date', 'currency', 'total',
            'billing_notes', 'collection_account_observations',
            'language', 'cover_type', 'template_style',
            'include_portada', 'include_subportada', 'include_contraportada',
            'folder', 'folder_name', 'tag_ids', 'tag_details',
            'active_states', 'notes', 'thread_summary',
            'created_at', 'updated_at',
            'is_archived', 'archived_at', 'archived_cause',
        )

    def get_archived_cause(self, obj):
        return _archived_cause(obj)

    def get_notes(self, obj):
        notes = getattr(obj, '_active_document_notes', None)
        if notes is None:
            notes = obj.document_notes.filter(
                deleted_at__isnull=True,
            ).select_related('created_by', 'resolved_by', 'deleted_by')
        return DocumentNoteSerializer(notes, many=True).data

    def get_active_states(self, obj):
        return DocumentListSerializer().get_active_states(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('is_contract_mirror'):
            # The row stores a pointer; readers get the contract itself.
            from content.services.contract_mirror_service import mirror_markdown
            data['content_markdown'] = mirror_markdown() or ''
        return data


class DocumentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating documents."""

    folder_id = serializers.PrimaryKeyRelatedField(
        source='folder', queryset=DocumentFolder.objects.all(),
        required=False, allow_null=True,
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=DocumentTag.objects.all(), many=True, required=False,
    )
    # Sin acotar por cliente a propósito: un queryset de campo no ve el valor
    # de su hermano, así que la regla de pertenencia vive en validate().
    client = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(), required=False, allow_null=True,
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True,
    )
    # Bandera de la pregunta que hace el gestor al mover un documento a la
    # carpeta de OTRO cliente. No es un campo del modelo: se consume en
    # validate() y nunca llega a validated_data.
    adopt_folder_client = serializers.BooleanField(required=False, write_only=True)
    client_custom_notes = ClientCustomNotesField(required=False)

    class Meta:
        model = Document
        fields = (
            'title', 'client_name', 'language', 'cover_type', 'template_style',
            'client_email_subject', 'client_email_body',
            'client_whatsapp_message', 'client_custom_notes',
            'include_portada', 'include_subportada', 'include_contraportada',
            'status', 'is_client_visible', 'content_markdown', 'content_json',
            'folder_id', 'tag_ids', 'client', 'project', 'adopt_folder_client',
        )
        extra_kwargs = {
            'title': {'required': True},
            'content_markdown': {'required': False},
            'content_json': {'required': False},
        }

    def validate(self, attrs):
        """Guarda de carpeta archivada + resolución de la asociación.

        Ambas van a nivel de objeto y no de campo porque dependen del estado
        de la propia instancia: mover un documento YA archivado entre carpetas
        es un caso soportado, y la pertenencia proyecto→cliente compara campos
        hermanos.
        """
        adopt = attrs.pop('adopt_folder_client', False)
        if 'folder' in attrs:
            if attrs['folder'] and attrs['folder'].is_system_managed:
                raise serializers.ValidationError({
                    'folder_id': (
                        'Esta carpeta pertenece al archivado automático y sólo '
                        'recibe documentos generados por el sistema.'
                    ),
                })
            try:
                ensure_active_target(
                    attrs['folder'],
                    moving_archived=bool(self.instance and self.instance.is_archived),
                )
            except DocumentArchiveError as exc:
                raise serializers.ValidationError({'folder_id': str(exc)}) from exc
            _inherit_from_folder(attrs, self.instance, adopt=adopt)
        return apply_client_project_association(attrs, self.instance)

    @historical_write
    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        document = super().create(validated_data)
        if tag_ids is not None:
            document.tags.set(tag_ids)
        return document

    @historical_write
    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        document = super().update(instance, validated_data)
        if tag_ids is not None:
            document.tags.set(tag_ids)
        return document


class DocumentFromMarkdownSerializer(serializers.Serializer):
    """Serializer for creating a document from markdown input."""

    title = serializers.CharField(max_length=255)
    markdown = serializers.CharField(required=True)
    client_name = serializers.CharField(max_length=255, required=False, default='')
    client_email_subject = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default='',
    )
    client_email_body = serializers.CharField(
        required=False, allow_blank=True, default='',
    )
    client_whatsapp_message = serializers.CharField(
        required=False, allow_blank=True, default='',
    )
    client_custom_notes = ClientCustomNotesField(required=False, default=list)
    language = serializers.ChoiceField(
        choices=Document.Language.choices, required=False, default='es',
    )
    cover_type = serializers.ChoiceField(
        choices=Document.CoverType.choices, required=False, default='generic',
    )
    template_style = serializers.ChoiceField(
        choices=Document.TemplateStyle.choices, required=False,
        default='professional',
    )
    include_portada = serializers.BooleanField(required=False, default=True)
    include_subportada = serializers.BooleanField(required=False, default=True)
    include_contraportada = serializers.BooleanField(required=False, default=True)
    folder_id = serializers.PrimaryKeyRelatedField(
        queryset=DocumentFolder.objects.all(), required=False, allow_null=True,
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=DocumentTag.objects.all(), many=True, required=False,
    )
    client = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(), required=False, allow_null=True,
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True,
    )

    def validate_folder_id(self, value):
        """Un documento nuevo nace activo: su carpeta tiene que estarlo también."""
        if value and value.is_system_managed:
            raise serializers.ValidationError(
                'Esta carpeta pertenece al archivado automático y sólo '
                'recibe documentos generados por el sistema.'
            )
        try:
            ensure_active_target(value)
        except DocumentArchiveError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    def validate(self, attrs):
        return apply_client_project_association(attrs)


class ClientDocumentRowSerializer(serializers.ModelSerializer):
    """Fila ligera para la sección Documentos de la ficha del cliente.

    Sin excerpt ni tags a propósito: la ficha lista para reconocer y saltar,
    no para leer — el payload del detalle de cliente ya es grande.
    """

    project_name = serializers.CharField(
        source='project.name', read_only=True, default=None,
    )
    folder_name = serializers.CharField(
        source='folder.name', read_only=True, default=None,
    )

    class Meta:
        model = Document
        fields = (
            'id', 'title', 'status', 'project', 'project_name',
            'folder_name', 'created_at',
        )
