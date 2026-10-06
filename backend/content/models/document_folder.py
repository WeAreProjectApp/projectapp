from accounts.retention import RetainedProjectModel
from django.conf import settings
from django.db import models

from content.utils import safe_slug


class DocumentFolder(RetainedProjectModel, models.Model):
    """Carpeta jerárquica para organizar documentos en el panel admin.

    Soporta anidación ilimitada vía la self-FK `parent`: las carpetas sin
    padre son raíces; las demás son subcarpetas.

    La carpeta dice de qué cliente y proyecto es con los MISMOS campos que el
    documento (`client_user` es auth.User, `project` es accounts.Project), así
    que la regla de asociación y el mapeo a UserProfile que habla el panel se
    reusan tal cual desde los serializers de documento. Lo que se hereda hacia
    el contenido se COPIA al crear, nunca se calcula al vuelo: el portal del
    cliente filtra por estos campos y un valor derivado lo dejaría invisible.
    """

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    system_key = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        help_text=(
            'Stable identifier for folders whose structure is managed by the system.'
        ),
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='children',
        null=True,
        blank=True,
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_document_folders',
    )
    creation_source = models.CharField(
        max_length=10, default='system', editable=False,
        choices=[('panel', 'Panel'), ('mcp', 'MCP'), ('system', 'System'), ('migration', 'Migration'), ('unknown', 'Unknown')],
    )

    creation_operation = models.CharField(max_length=160, blank=True, default='', editable=False)

    # Asociación. SET_NULL como en Document: borrar un cliente o un proyecto
    # no puede llevarse por delante la organización del gestor.
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, null=True, blank=True, related_name='document_folders')
    # Sólo las raíces creadas y mantenidas por el ciclo de vida de Project
    # llevan este vínculo. `project` sigue siendo la asociación heredable de
    # PA-64 para CUALQUIER carpeta; separar ambos conceptos evita confundir una
    # carpeta manual asociada a un proyecto con la raíz automática del mismo.
    managed_project = models.OneToOneField('accounts.Project', on_delete=models.PROTECT, null=True, blank=True, related_name='document_root_folder')
    client_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_document_folders',
    )
    # El equivalente de `managed_project` para clientes, con la misma
    # separación: `client_user` es la asociación heredable de CUALQUIER carpeta;
    # esto marca la única raíz que representa al cliente en el gestor.
    #
    # Apunta a auth.User y no a UserProfile a propósito: es lo que permite la
    # CheckConstraint `client_user = F('managed_client')`, la que garantiza en
    # base que la raíz no pueda quedar apuntando a otro cliente que el suyo.
    #
    # A diferencia de las raíces de proyecto, NO se provisiona sola: los
    # proyectos crean la suya en el post_save, pero hay decenas de perfiles de
    # cliente y sólo un puñado con carpeta, así que un signal llenaría el gestor
    # de carpetas vacías. Se adopta explícitamente.
    managed_client = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_document_root_folder',
    )

    # Archivado: saca la carpeta de la vista sin destruirla. A diferencia de
    # borrar, archivar SÍ está permitido con contenido: la cascada arrastra
    # subcarpetas y documentos. `archived_via_folder` guarda la carpeta que
    # causó el archivado (NULL = archivada por sí misma), y es lo que permite
    # desarchivar devolviendo sólo lo que esta carpeta arrastró.
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_via_folder = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='cascade_archived_folders',
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['order', 'name']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(managed_project__isnull=True)
                    | models.Q(parent__isnull=True)
                ),
                name='managed_project_folder_is_root',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(managed_project__isnull=True)
                    | models.Q(project=models.F('managed_project'))
                ),
                name='managed_folder_matches_project',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(managed_project__isnull=True)
                    | models.Q(is_archived=False)
                ),
                name='managed_project_folder_is_active',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(managed_client__isnull=True)
                    | models.Q(parent__isnull=True)
                ),
                name='managed_client_folder_is_root',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(managed_client__isnull=True)
                    | models.Q(client_user=models.F('managed_client'))
                ),
                name='managed_folder_matches_client',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(managed_client__isnull=True)
                    | models.Q(is_archived=False)
                ),
                name='managed_client_folder_is_active',
            ),
            # Una raíz representa a UN espacio. Una carpeta que fuera a la vez
            # la del proyecto y la del cliente heredaría dos asociaciones
            # incompatibles hacia abajo.
            models.CheckConstraint(
                condition=(
                    models.Q(managed_client__isnull=True)
                    | models.Q(managed_project__isnull=True)
                ),
                name='managed_root_is_project_or_client',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def folder_kind(self):
        if self.managed_project_id:
            return 'project'
        if self.managed_client_id:
            return 'client'
        return 'manual'

    @property
    def is_system_managed(self):
        return bool(self.system_key)

    def save(self, *args, **kwargs):
        if self._state.adding and not self.creation_operation:
            self.creation_operation = 'orm.create'
        if not self.slug:
            base = safe_slug(self.name, 'folder')
            slug = base
            index = 2
            while DocumentFolder.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{index}'
                index += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_ancestors(self):
        """Devuelve la cadena de carpetas desde la raíz hasta el padre directo."""
        ancestors = []
        node = self.parent
        visited = set()
        while node is not None and node.pk not in visited:
            visited.add(node.pk)
            ancestors.append(node)
            node = node.parent
        ancestors.reverse()
        return ancestors

    def get_descendant_ids(self):
        """Devuelve el set de IDs de todas las subcarpetas (recursivo)."""
        descendant_ids = set()
        pending = list(self.children.values_list('pk', flat=True))
        while pending:
            child_id = pending.pop()
            if child_id in descendant_ids:
                continue
            descendant_ids.add(child_id)
            pending.extend(
                DocumentFolder.objects.filter(parent_id=child_id)
                .values_list('pk', flat=True)
            )
        return descendant_ids


class DocumentFolderMutationLock(models.Model):
    """One mutex for manual tree writes, including siblings at the root.

    Existing duplicate folders stay intact. Serializing validation with the
    write prevents new collisions and reciprocal reparenting races without a
    uniqueness migration that would fail on legacy names.
    """
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
