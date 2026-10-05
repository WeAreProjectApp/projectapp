from accounts.models import Project, UserProfile
from django.db import transaction
from django.db.models.functions import Lower, Trim
from rest_framework import serializers

from content.models import DocumentFolder
from content.models.document_folder import DocumentFolderMutationLock
from content.serializers.document import (
    ClientProjectReadMixin,
    apply_client_project_association,
)
from content.serializers.strict_input import StrictInputMixin
from content.services.document_archive_service import (
    DocumentArchiveError,
    ensure_active_target,
)

FOLDER_WRITE_FIELDS = {'name', 'parent', 'parent_id', 'order', 'client', 'project'}


def validate_folder_input(data):
    if not hasattr(data, 'keys'):
        raise serializers.ValidationError({'detail': 'El payload debe ser un objeto.'})
    unknown = set(data) - FOLDER_WRITE_FIELDS
    if unknown:
        raise serializers.ValidationError({name: [serializers.ErrorDetail('Campo desconocido o de solo lectura.', code='unknown_field')] for name in sorted(unknown)})
    if 'parent' in data and 'parent_id' in data and data['parent'] != data['parent_id']:
        raise serializers.ValidationError({'parent_id': 'parent y parent_id deben coincidir.'})


class DocumentFolderChangeClientSerializer(serializers.Serializer):
    """Payload del apply de cambio de cliente.

    `mode` va sin default a propósito: el operador elige cada vez qué pasa con
    el contenido. Las dos listas de ids son el token de staleness — el plan que
    corre es el que se mostró en el preview, o no corre nada.
    """

    client_profile_id = serializers.IntegerField()
    mode = serializers.CharField()
    document_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
    )
    folder_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
    )


class DocumentFolderSerializer(StrictInputMixin, ClientProjectReadMixin, serializers.ModelSerializer):
    """Serializer para carpetas de documentos (jerárquicas).

    Los contadores se leen de annotations del queryset cuando el caller las
    provee; de lo contrario caen a un COUNT por carpeta para que las respuestas
    single-object (create/update) sigan incluyendo los campos.

    `document_count`/`children_count` son relativos al estado de la carpeta
    (una activa cuenta contenido activo) y se conservan por compatibilidad. Los
    cuatro `active_*`/`archived_*` son absolutos: sumarlos siempre da el
    contenido real, mientras que sumar los relativos duplicaría el conteo de una
    carpeta archivada. Son además los que permiten a una carpeta activa avisar
    que todavía guarda elementos archivados.
    """

    parent_id = serializers.IntegerField(read_only=True, allow_null=True)
    created_by = serializers.SerializerMethodField()
    creation_source = serializers.CharField(read_only=True)
    document_count = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()
    active_document_count = serializers.SerializerMethodField()
    active_children_count = serializers.SerializerMethodField()
    archived_document_count = serializers.SerializerMethodField()
    archived_children_count = serializers.SerializerMethodField()
    archived_cause = serializers.SerializerMethodField()
    folder_kind = serializers.CharField(read_only=True)
    managed_project_state = serializers.SerializerMethodField()
    is_project_visible = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(
        queryset=DocumentFolder.objects.all(),
        required=False,
        allow_null=True,
    )
    # `client` habla en pk de UserProfile como todo el panel; el modelo
    # persiste `client_user` (auth.User). A diferencia de los documentos —que
    # separan serializer de lectura y de escritura— acá uno solo sirve list,
    # create y update, así que el campo se declara write_only y la lectura la
    # devuelve `to_representation` con el mismo mapeo del mixin.
    # Los dos querysets van sin acotar a propósito: que el proyecto sea del
    # cliente es cosa de validate(), que ve ambos campos a la vez (mismo
    # motivo que en DocumentCreateUpdateSerializer).
    client = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    client_display_name = serializers.SerializerMethodField()
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        allow_null=True,
    )
    project_name = serializers.CharField(
        source='project.name', read_only=True, default=None,
    )
    is_system_managed = serializers.BooleanField(read_only=True)

    class Meta:
        model = DocumentFolder
        fields = (
            'id', 'name', 'slug', 'parent', 'parent_id', 'order',
            'client', 'client_display_name', 'project', 'project_name',
            'managed_project', 'folder_kind', 'managed_project_state',
            'managed_client', 'is_project_visible', 'is_system_managed',
            'document_count', 'children_count',
            'active_document_count', 'active_children_count',
            'archived_document_count', 'archived_children_count',
            'created_at', 'updated_at', 'created_by', 'creation_source', 'creation_operation',
            'is_archived', 'archived_at', 'archived_cause',
        )
        # `is_archived`/`archived_at` son read-only a propósito: update_document_folder
        # usa este mismo serializer para PATCH, y dejarlos escribibles permitiría
        # archivar saltándose la cascada del servicio.
        read_only_fields = (
            'slug', 'created_at', 'updated_at', 'is_archived', 'archived_at',
            'managed_project', 'folder_kind', 'managed_project_state',
            'managed_client', 'is_project_visible',
        )

    def to_internal_value(self, data):
        validate_folder_input(data)
        if isinstance(data, dict) or hasattr(data, 'dict'):
            data = data.copy()
            if 'parent_id' in data:
                data['parent'] = data.pop('parent_id')
                if isinstance(data['parent'], list):
                    data['parent'] = data['parent'][0]
        return super().to_internal_value(data)

    @transaction.atomic
    def save(self, **kwargs):
        # Migration seeds this row; get_or_create also supports migration-free tests.
        DocumentFolderMutationLock.objects.get_or_create(pk=1)
        DocumentFolderMutationLock.objects.select_for_update().get(pk=1)
        if self.instance is not None:
            self.instance.refresh_from_db()
        current = type(self)(self.instance, data=self.initial_data, partial=self.partial, context=self.context)
        current.is_valid(raise_exception=True)
        self.instance = super(DocumentFolderSerializer, current).save(**kwargs)
        return self.instance

    def get_created_by(self, obj):
        if obj.creation_source in ('system', 'mcp'):
            return obj.creation_source
        if obj.created_by_id:
            return {'id': obj.created_by_id, 'username': obj.created_by.get_username()}
        return None

    def create(self, validated_data):
        from content.services.document_folder_provenance import folder_creation_values
        return super().create({
            **validated_data,
            **folder_creation_values(operation=self.context.get('creation_operation', 'create_folder'), request=self.context.get('request')),
        })

    def get_document_count(self, obj):
        attr = 'archived_document_count' if obj.is_archived else 'active_document_count'
        value = getattr(obj, attr, None)
        if isinstance(value, int):
            return value
        # Sin annotation (respuestas single-object) el conteo sigue el mismo
        # scope que la lista: una carpeta activa cuenta documentos activos.
        return obj.documents.filter(is_archived=obj.is_archived).count()

    def get_children_count(self, obj):
        attr = 'archived_children_count' if obj.is_archived else 'active_children_count'
        value = getattr(obj, attr, None)
        if isinstance(value, int):
            return value
        return obj.children.filter(is_archived=obj.is_archived).count()

    def get_active_document_count(self, obj):
        value = getattr(obj, 'active_document_count', None)
        if isinstance(value, int):
            return value
        return obj.documents.filter(is_archived=False).count()

    def get_active_children_count(self, obj):
        value = getattr(obj, 'active_children_count', None)
        if isinstance(value, int):
            return value
        return obj.children.filter(is_archived=False).count()

    def get_archived_document_count(self, obj):
        value = getattr(obj, 'archived_document_count', None)
        if isinstance(value, int):
            return value
        return obj.documents.filter(is_archived=True).count()

    def get_archived_children_count(self, obj):
        value = getattr(obj, 'archived_children_count', None)
        if isinstance(value, int):
            return value
        return obj.children.filter(is_archived=True).count()

    def get_archived_cause(self, obj):
        """'folder' si lo arrastró una carpeta, 'manual' si fue por sí misma."""
        if not obj.is_archived:
            return None
        return 'folder' if obj.archived_via_folder_id else 'manual'

    def get_managed_project_state(self, obj):
        project = getattr(obj, 'managed_project', None)
        state = getattr(project, 'current_state', None) if project else None
        if state is None:
            return None
        return {
            'id': state.pk,
            'name': state.name,
            'system_key': state.system_key,
            'color': state.color,
            'show_in_document_manager': state.show_in_document_manager,
        }

    def get_is_project_visible(self, obj):
        project = getattr(obj, 'managed_project', None)
        # Compatibility field: every canonical project is visible now.
        return bool(project)

    def to_representation(self, instance):
        """Devuelve `client` como pk de UserProfile (el campo es write_only)."""
        data = super().to_representation(instance)
        data['client'] = self.get_client(instance)
        # El modelo persiste auth.User, pero el panel habla en pk de UserProfile
        # en TODA asociación de cliente. Devolver acá el id de usuario obligaría
        # al frontend a manejar dos vocabularios para el mismo concepto.
        managed = getattr(instance, 'managed_client', None)
        profile = getattr(managed, 'profile', None) if managed else None
        data['managed_client'] = profile.id if profile else None
        return data

    def validate(self, attrs):
        if self.instance is not None:
            from content.services.contract_mirror_service import folder_contains_mirror, CONTRACT_MIRROR_MESSAGE
            if set(attrs) - {'order'} and folder_contains_mirror(self.instance):
                raise serializers.ValidationError({'detail': CONTRACT_MIRROR_MESSAGE})
        """Misma regla de asociación que los documentos, sin `client_name`."""
        if self.instance is not None and self.instance.is_system_managed:
            raise serializers.ValidationError({'detail': 'Esta carpeta se administra automáticamente.', 'code': 'system_managed_folder'})
        if self.instance is None or {'name', 'parent'}.intersection(attrs):
            name = attrs.get('name', getattr(self.instance, 'name', '')).strip()
            parent = attrs.get('parent', getattr(self.instance, 'parent', None))
            changed = self.instance is None or (name, getattr(parent, 'pk', None)) != (self.instance.name, self.instance.parent_id)
            if changed:
                matches = DocumentFolder.objects.annotate(normalized_name=Lower(Trim('name'))).filter(
                    parent=parent, normalized_name=name.lower(),
                ).exclude(pk=getattr(self.instance, 'pk', None))
                matching_ids = list(matches.values_list('pk', flat=True))
                if matching_ids:
                    raise serializers.ValidationError({
                        'name': 'Ya existe una carpeta con ese nombre aquí',
                        'code': 'duplicate_folder_name', 'matching_ids': matching_ids,
                    })
        if self.instance is not None and self.instance.managed_project_id:
            protected = {'name', 'parent', 'client', 'project'}
            if protected.intersection(attrs):
                raise serializers.ValidationError({
                    'detail': (
                        'La raíz del proyecto se administra desde el proyecto, '
                        'no desde el Gestor Documental.'
                    ),
                    'code': 'managed_project_folder',
                })

        # La raíz de cliente protege menos que la de proyecto: `project` NO está
        # en el conjunto porque una carpeta de cliente sí puede recibir una
        # asociación de proyecto en su subárbol, y el nombre lo pone el operador
        # —no lo dicta un módulo externo, como sí ocurre con Proyectos—. Lo que
        # no puede cambiar es a quién representa ni dejar de ser raíz.
        if self.instance is not None and self.instance.managed_client_id:
            protected = {'parent', 'client'}
            if protected.intersection(attrs):
                raise serializers.ValidationError({
                    'detail': (
                        'Esta carpeta es el espacio del cliente: no puede '
                        'cambiar de dueño ni dejar de ser raíz.'
                    ),
                    'code': 'managed_client_folder',
                })

        # Crear dentro de una carpeta copia su eje de proyecto/cliente cuando
        # el caller no eligió otro. Esto vuelve efectiva PA-64 también para MCP
        # y otros callers que no pasan los defaults precargados del formulario.
        if self.instance is None:
            parent = attrs.get('parent')
            association_sent = {'client', 'project'}.intersection(self.initial_data)
            if parent is not None and not association_sent:
                profile = getattr(parent.client_user, 'profile', None)
                if profile is not None:
                    attrs['client'] = profile
                if parent.project_id:
                    attrs['project'] = parent.project
        return apply_client_project_association(
            attrs, self.instance, snapshot_client_name=False,
        )

    def validate_parent(self, value):
        """Impide que una carpeta sea su propio padre o descienda de sí misma."""
        if value is None:
            return value
        if value.is_system_managed:
            raise serializers.ValidationError('La carpeta destino se administra automáticamente.')
        instance = self.instance
        if instance is not None:
            if value.pk == instance.pk:
                raise serializers.ValidationError(
                    'Una carpeta no puede ser su propio padre.', code='folder_cycle'
                )
            if value.pk in instance.get_descendant_ids():
                raise serializers.ValidationError(
                    'No se puede mover una carpeta dentro de una de sus subcarpetas.', code='folder_cycle'
                )
        try:
            ensure_active_target(
                value, moving_archived=bool(instance and instance.is_archived),
            )
        except DocumentArchiveError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


class DocumentFolderFilterSerializer(serializers.Serializer):
    parent_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    name = serializers.CharField(required=False, max_length=120)

    def to_internal_value(self, data):
        data = data.copy()
        if data.get('parent_id') in ('null', 'none', ''):
            data['parent_id'] = None
        return super().to_internal_value(data)


def filter_folders(queryset, filters):
    if 'parent_id' in filters:
        queryset = queryset.filter(parent_id=filters['parent_id'])
    if 'name' in filters:
        queryset = queryset.annotate(normalized_name=Lower(Trim('name'))).filter(normalized_name=filters['name'].lower())
    return queryset
