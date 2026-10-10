"""Explicit inputs for the 36 Documents MCP adapters over Panel views.

Path parameters, ETags and confirmation metadata belong to ``panel_operation``.
These fragments describe only the payloads and query parameters the views read.
"""

from copy import deepcopy


def _closed(properties=None, required=()):
    schema = {
        'type': 'object',
        'properties': deepcopy(properties or {}),
        'additionalProperties': False,
    }
    if required:
        schema['required'] = list(required)
    return schema


def _id(description, *, nullable=False):
    return {
        'type': ['integer', 'null'] if nullable else 'integer',
        'minimum': 1,
        'description': description,
    }


def _ids(description, **constraints):
    return {
        'type': 'array',
        'items': {'type': 'integer', 'minimum': 1},
        'description': description,
        **constraints,
    }


def _query_ids(description, *, selectors=()):
    # The query service reads comma-separated IDs; the bridge encodes arrays
    # as CSV, and also accepts the Panel's existing string representation.
    branches = [
        {'type': 'integer', 'minimum': 1},
        _ids('Identificadores positivos, enviados como una lista separada por comas.'),
        {'type': 'string'},
    ]
    return {
        'anyOf': branches,
        'description': description + (
            f' También admite {", ".join(selectors)}.' if selectors else ''
        ),
        'x-query-encoding': 'csv',
    }


_SCOPE = {
    'type': 'string',
    'enum': ['active', 'archived', 'all'],
    'description': 'Estado del inventario: active, archived o all. Omitido usa active, salvo archived.',
}
_ARCHIVED = {
    'type': ['boolean', 'string'],
    'description': 'Alias de archivados: true, 1, yes u on seleccionan archived si no se indica scope; omitido usa activos.',
}
_ORDER = {
    'type': 'string',
    'enum': ['recent', 'oldest'],
    'default': 'recent',
    'description': 'Orden por fecha: recent muestra primero lo reciente; oldest, lo antiguo. Omitido usa recent.',
}
_SEARCH = {
    'type': 'string',
    'description': 'Texto de búsqueda; se recorta a 200 caracteres y se ignora si está vacío. Omitido no filtra.',
}
_INCLUDE_CONTENT = {
    'type': 'boolean',
    'default': False,
    'description': 'Incluye el Markdown en la respuesta si es true. Omitido usa false.',
}
_CLIENT_POLICY = {
    'type': 'string',
    'enum': ['inherit', 'keep', 'abort_on_conflict'],
    'default': 'abort_on_conflict',
    'description': 'inherit adopta cliente y proyecto; keep conserva y bloquea conflictos; abort_on_conflict hereda sin conflictos y es el valor omitido en MCP.',
}
_PORTAL_POLICY = {
    'type': 'string',
    'enum': ['abort', 'allow', 'hide_new_exposure'],
    'default': 'abort',
    'description': 'abort bloquea nueva audiencia; allow la permite; hide_new_exposure oculta documentos que ganarían acceso. Omitido usa abort en MCP.',
}
_EXPECTED_PLAN_HASH = {
    'type': 'string',
    'pattern': '^[a-f0-9]{64}$',
    'description': 'plan_hash de preview_move, con 64 dígitos hexadecimales en minúsculas. Si se indica, rechaza un plan que haya cambiado.',
}
_DOCUMENT_DECISIONS = {
    'type': 'array',
    'maxItems': 100,
    'description': 'Hasta 100 decisiones por documento: inherit adopta el destino; move elige otra carpeta. Omitido no agrega decisiones.',
    'items': _closed({
        'document_id': _id('ID positivo del documento al que se aplica la decisión.'),
        'action': {
            'type': 'string',
            'enum': ['inherit', 'move'],
            'description': 'inherit adopta el destino principal; move exige destination_folder_id.',
        },
        'destination_folder_id': _id('ID positivo de la carpeta alternativa; obligatorio cuando action es move.'),
    }, ('document_id', 'action')),
}
_FOLDER_FIELDS = {
    'name': {
        'type': 'string', 'minLength': 1, 'maxLength': 120,
        'description': 'Nombre de la carpeta, de 1 a 120 caracteres tras recortar espacios. Omitido conserva el nombre.',
    },
    'parent_id': _id('ID positivo de la carpeta padre; null mueve a la raíz. Alias de parent; omitido conserva el padre.', nullable=True),
    'parent': _id('ID positivo de la carpeta padre; null mueve a la raíz. Si también se indica parent_id, deben coincidir.', nullable=True),
    'order': {
        'type': 'integer', 'minimum': 0,
        'description': 'Posición de la carpeta, como entero desde 0. Omitida conserva el orden.',
    },
    'client': _id('ID positivo del perfil de cliente; null quita la asociación. Omitido conserva el cliente.', nullable=True),
    'project': _id('ID positivo del proyecto; null quita la asociación. Omitido conserva el proyecto.', nullable=True),
    'client_policy': _CLIENT_POLICY,
    'portal_policy': _PORTAL_POLICY,
    'expected_plan_hash': _EXPECTED_PLAN_HASH,
}
_TAG_FIELDS = {
    'name': {
        'type': 'string', 'minLength': 1, 'maxLength': 60,
        'description': 'Nombre único de la etiqueta, de 1 a 60 caracteres tras recortar espacios. Obligatorio al crear; omitido al editar conserva el nombre.',
    },
    'color': {
        'type': 'string',
        'enum': ['gray', 'emerald', 'blue', 'yellow', 'red', 'purple'],
        'description': 'Color de la etiqueta. Omitido al crear usa gray; al editar conserva el color.',
    },
}
_GROUP_FIELDS = {
    'catalog': {
        'type': 'string', 'enum': ['documents', 'projects'],
        'description': 'Catálogo documents o projects. Al crear, la vista fija documents; omitido al editar conserva el catálogo.',
    },
    'name': {
        'type': 'string', 'minLength': 1, 'maxLength': 80,
        'description': 'Nombre del grupo, de 1 a 80 caracteres tras recortar espacios. Obligatorio al crear; omitido al editar conserva el nombre.',
    },
    'selection_mode': {
        'type': 'string', 'enum': ['exclusive', 'additive'],
        'description': 'exclusive permite un estado vigente; additive permite varios. Omitido al crear usa additive; al editar conserva el modo.',
    },
    'order': {
        'type': 'integer', 'minimum': 0,
        'description': 'Orden del grupo, entero desde 0. Omitido al crear usa 0; al editar conserva la posición.',
    },
    'is_active': {
        'type': 'boolean',
        'description': 'Indica si el grupo está activo. Omitido al crear usa true; al editar conserva el valor.',
    },
}
_STATE_FIELDS = {
    'catalog': deepcopy(_GROUP_FIELDS['catalog']),
    'group': _id('ID positivo del grupo. Omitido al crear usa el primer grupo aditivo activo; al editar conserva el grupo.'),
    'name': {
        'type': 'string', 'minLength': 1, 'maxLength': 60,
        'description': 'Nombre del estado, de 1 a 60 caracteres; se normalizan los espacios. Obligatorio al crear; omitido al editar conserva el nombre.',
    },
    'description': {
        'type': 'string', 'maxLength': 300,
        'description': 'Explicación de hasta 300 caracteres; se normalizan los espacios. Omitida al crear usa una cadena vacía; al editar se conserva.',
    },
    'color': {
        'type': 'string',
        'enum': ['gray', 'emerald', 'blue', 'yellow', 'orange', 'red', 'purple'],
        'description': 'Color del estado. Omitido al crear usa gray; al editar conserva el color.',
    },
    'operational_effect': {
        'type': 'string',
        'enum': ['', 'development', 'operating', 'suspended', 'completed', 'decommissioned'],
        'description': 'Efecto operativo del catálogo; los estados documents requieren una cadena vacía. Omitido al crear usa vacío; al editar se conserva.',
    },
    'order': {
        'type': 'integer', 'minimum': 0,
        'description': 'Orden del estado, entero desde 0. Omitido al crear usa 0; al editar conserva la posición.',
    },
    'is_active': {
        'type': 'boolean',
        'description': 'Indica si el estado está activo. Omitido al crear usa true; al editar conserva el valor.',
    },
    'incompatibility_ids': _ids('IDs positivos de estados incompatibles. Omitidos al crear dejan la lista vacía; al editar conservan las incompatibilidades.'),
}


DOCUMENTS_BRIDGE_SCHEMAS = {
    'move_documents': {
        'payload_schema': _closed({
            'document_ids': _ids('Entre 1 y 100 IDs positivos de documentos activos, sin repetir. Se mueven todos o ninguno.', minItems=1, maxItems=100, uniqueItems=True),
            'folder_id': _id('ID positivo de la carpeta destino; null deja los documentos sin carpeta.', nullable=True),
            'include_content': _INCLUDE_CONTENT,
            'client_policy': _CLIENT_POLICY,
            'portal_policy': _PORTAL_POLICY,
            'expected_plan_hash': _EXPECTED_PLAN_HASH,
            'document_decisions': _DOCUMENT_DECISIONS,
        }, ('document_ids', 'folder_id')),
    },
    'browse_documents': {
        'query_schema': _closed({
            'scope': _SCOPE,
            'archived': _ARCHIVED,
            'order': _ORDER,
            'page': {
                'type': 'integer', 'minimum': 1, 'default': 1,
                'description': 'Página solicitada, entero positivo. Omitida usa 1; si excede el total se usa la última página.',
            },
            'page_size': {
                'type': 'integer', 'enum': [10, 12], 'default': 10,
                'description': 'Documentos por página: 10 o 12. Omitido usa 10.',
            },
            'client': _query_ids('ID positivo, lista de IDs o cadena de IDs separados por comas de perfiles de cliente. Omitido no filtra.', selectors=('none (sin cliente)', 'all (todos)')),
            'project': _query_ids('ID positivo, lista de IDs o cadena de IDs separados por comas de proyectos. Omitido no filtra.', selectors=('none (sin proyecto)', 'all (todos)')),
            'folder': {
                'anyOf': [{'type': 'integer', 'minimum': 1}, {'type': 'string'}],
                'description': 'ID positivo de carpeta, también como cadena; none busca sin carpeta, root aplica la raíz visible, all incluye todas. Omitido no filtra.',
            },
            'tags': _query_ids('IDs positivos de etiquetas, como lista o cadena separada por comas. Omitidos no filtran.'),
            'states': _query_ids('IDs positivos de estados vigentes, como lista o cadena separada por comas. Omitidos no filtran.'),
            'without_states': _query_ids('IDs positivos de estados vigentes que se excluyen, como lista o cadena separada por comas. Omitidos no filtran.'),
            'preset': {
                'type': 'string',
                'enum': ['', 'needs_fix', 'sent_not_closed', 'closed', 'unclassified'],
                'description': 'Consulta predefinida: needs_fix, sent_not_closed, closed o unclassified. Omitida o vacía no agrega filtro.',
            },
            'search': _SEARCH,
        }),
    },
    'get_document_counts': {'query_schema': _closed()},
    'get_document_navigation': {'query_schema': _closed()},
    'get_document_communication_usage': {'query_schema': _closed()},
    'get_document_email_usage': {'query_schema': _closed()},
    'render_document_pdf': {
        'query_schema': _closed({
            'inline': {
                'type': 'string',
                'description': 'Cadena no vacía, por ejemplo 1, para mostrar el PDF en línea. Omitida o vacía descarga el archivo.',
            },
            'template': {
                'type': 'string', 'enum': ['professional', 'friendly'],
                'description': 'Estilo professional o friendly para el PDF Markdown. Omitido usa el estilo guardado; los documentos generados mantienen su renderizador.',
            },
        }),
    },
    # These views read include_content in the document_write_options decorator,
    # which the one-hop AST inventory intentionally cannot see.
    'duplicate_document': {'payload_schema': _closed({'include_content': _INCLUDE_CONTENT})},
    'archive_document': {'payload_schema': _closed({'include_content': _INCLUDE_CONTENT})},
    'unarchive_document': {'payload_schema': _closed({'include_content': _INCLUDE_CONTENT})},
    'list_document_folders': {
        'query_schema': _closed({
            'scope': _SCOPE,
            'archived': _ARCHIVED,
            'order': _ORDER,
            'search': _SEARCH,
            'parent_id': {
                'anyOf': [
                    {'type': 'integer', 'minimum': 1},
                    {'type': 'string'},
                ],
                'description': 'ID positivo del padre, también como texto; null o none como texto, o una cadena vacía, filtran raíces. Omitido incluye todos los padres.',
            },
            'name': {
                'type': 'string', 'minLength': 1, 'maxLength': 120,
                'description': 'Nombre exacto de carpeta, hasta 120 caracteres, sin distinguir mayúsculas ni espacios exteriores. Omitido no filtra por nombre.',
            },
        }),
    },
    'get_project_folder_readiness': {'query_schema': _closed()},
    'update_folder': {'payload_schema': _closed(_FOLDER_FIELDS)},
    'delete_folder': {'payload_schema': _closed()},
    'archive_folder': {'payload_schema': _closed()},
    'unarchive_folder': {'payload_schema': _closed()},
    'reorder_folders': {
        'payload_schema': _closed({
            'ids': _ids('IDs positivos de carpetas en el orden deseado. Omitidos usan una lista vacía; las raíces gestionadas se ignoran.'),
        }),
    },
    'preview_folder_client_change': {
        'query_schema': _closed({
            'client_profile_id': _id('ID positivo del perfil de cliente destino, distinto del cliente actual.'),
        }, ('client_profile_id',)),
    },
    'change_folder_client': {
        'payload_schema': _closed({
            'client_profile_id': _id('ID positivo del perfil de cliente destino, distinto del cliente actual.'),
            'mode': {
                'type': 'string', 'enum': ['propagate', 'folder_only'],
                'description': 'propagate cambia la carpeta y su contenido; folder_only cambia sólo la carpeta. Debe elegirse explícitamente.',
            },
            'document_ids': _ids('IDs positivos de todos los documentos revisados en la vista previa; verifican que el conjunto no cambió. Omitidos usan una lista vacía.'),
            'folder_ids': _ids('IDs positivos de todas las subcarpetas revisadas en la vista previa; verifican que el conjunto no cambió. Omitidos usan una lista vacía.'),
            'portal_policy': _PORTAL_POLICY,
        }, ('client_profile_id', 'mode')),
    },
    'list_document_tags': {'query_schema': _closed()},
    'create_document_tag': {'payload_schema': _closed(_TAG_FIELDS, ('name',))},
    'update_document_tag': {'payload_schema': _closed(_TAG_FIELDS)},
    'delete_document_tag': {'payload_schema': _closed()},
    'list_document_state_groups': {'query_schema': _closed()},
    'create_document_state_group': {'payload_schema': _closed(_GROUP_FIELDS, ('name',))},
    'update_document_state_group': {'payload_schema': _closed(_GROUP_FIELDS)},
    'list_document_state_catalog': {
        'query_schema': _closed({
            'include_retired': {
                'type': ['boolean', 'string'],
                'description': 'true, 1 o yes incluyen estados retirados y fusionados. Omitido muestra sólo estados activos sin fusionar.',
            },
        }),
    },
    'create_document_state': {
        # The view supplies an additive group before serializer validation.
        'payload_schema': _closed({
            **_STATE_FIELDS,
            'confirm_similar': {
                'type': 'boolean', 'default': False,
                'description': 'true confirma la creación aunque existan estados parecidos. Omitido usa false y exige revisar las sugerencias.',
            },
        }, ('name',)),
    },
    'suggest_document_states': {
        'query_schema': _closed({
            'q': {
                'type': 'string',
                'description': 'Nombre a comparar con estados existentes; devuelve hasta cinco sugerencias. Omitido o vacío no devuelve sugerencias.',
            },
        }),
    },
    'update_document_state_catalog_item': {'payload_schema': _closed(_STATE_FIELDS)},
    'retire_document_state': {'payload_schema': _closed()},
    'merge_document_state': {
        'payload_schema': _closed({
            'target_state_id': _id('ID positivo del estado destino del catálogo documents, distinto del estado de origen.'),
        }, ('target_state_id',)),
    },
    'correct_document_state_opening': {
        'payload_schema': _closed({
            'opened_at': {
                'type': 'string', 'format': 'date-time',
                'description': 'Nueva fecha y hora de apertura en formato ISO 8601; debe respetar la cronología del episodio.',
            },
        }, ('opened_at',)),
    },
    'list_document_state_history': {'query_schema': _closed()},
    'update_document_note': {
        'payload_schema': _closed({
            'title': {
                'type': 'string', 'maxLength': 120,
                'description': 'Título de la observación, hasta 120 caracteres; vacío lo borra. Omitido conserva el título.',
            },
            'content': {
                'type': 'string', 'minLength': 1,
                'description': 'Contenido no vacío de la observación. Omitido conserva el texto; debe enviarse title o content.',
            },
        }),
    },
    'list_document_note_events': {'query_schema': _closed()},
}
