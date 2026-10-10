"""Explicit inputs for the Projects Panel adapters, without registration changes."""

from copy import deepcopy


def _object(properties=None, required=()):
    return {
        'type': 'object',
        'properties': deepcopy(properties or {}),
        'required': list(required),
        'additionalProperties': False,
    }


def _id(description):
    return {'type': 'integer', 'minimum': 1, 'description': description}


def _ids(description):
    return {'type': 'array', 'items': {'type': 'integer', 'minimum': 1},
            'description': description}


def _query(properties=None, required=()):
    return {'query_schema': _object(properties, required)}


def _payload(properties=None, required=()):
    return {'payload_schema': _object(properties, required)}


# These are Panel-only compatibility inputs or keys the Panel always rejects.
# Publishing them as writable would contradict the MCP operation's purpose.
PANEL_ONLY_FIELDS = {
    'change_project_client': {
        'hosting_ids': 'Lista legado del Panel; MCP usa el plan calculado por mode y expected_impact_hash.',
        'income_ids': 'Lista legado del Panel; MCP usa el plan calculado por mode y expected_impact_hash.',
        'communication_thread_ids': 'Lista legado del Panel; MCP usa el plan calculado por mode y expected_impact_hash.',
    },
    'update_project': {
        'client': 'La vista lo rechaza siempre; el cliente se cambia con change_project_client.',
        'client_profile_id': 'La vista lo rechaza siempre; el cliente se cambia con change_project_client.',
        'state_id': 'La vista lo rechaza siempre; el estado requiere preview_project_state_transition.',
        'status': 'La vista rechaza el estado legado; el ciclo se cambia con apply_project_state_transition.',
    },
    'preview_project_delete': {
        'force': 'Sólo el Panel permite previsualizar un borrado forzado; MCP sólo elimina proyectos vacíos.',
    },
    'delete_project': {
        'force': 'El borrado forzado pertenece al Panel; MCP sólo elimina proyectos vacíos.',
        'delete_keys': 'Selección exclusiva del borrado forzado del Panel, fuera del contrato MCP.',
        'confirmation': 'Texto exclusivo del borrado forzado del Panel, fuera del contrato MCP.',
        'impact_token': 'Token exclusivo del borrado forzado del Panel, fuera del contrato MCP.',
    },
}

_PAGE = {'type': 'integer', 'minimum': 1, 'default': 1,
         'description': 'Número de página desde 1; por defecto 1, con 20 resultados por página.'}
_VERSION = {'type': 'integer', 'minimum': 1,
            'description': 'Versión vigente de la idea; entero desde 1 obtenido al consultarla.'}
_REQUEST_UUID = {'type': 'string', 'format': 'uuid',
                 'description': 'UUID estable de la petición para repetirla sin duplicar el registro.'}
_IDEA_TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 10000,
              'description': 'Texto de la idea, sin quedar en blanco; máximo 10.000 caracteres y bytes UTF-8.'}
_REASON = {'type': 'string', 'minLength': 1, 'maxLength': 2000,
           'description': 'Motivo de la operación, obligatorio y sin quedar en blanco; máximo 2.000 caracteres.'}
_REQUEST = {'type': 'string', 'minLength': 1, 'maxLength': 100,
            'description': 'Identificador estable de la petición para reintentos; máximo 100 caracteres.'}
_IMPACT_HASH = {'type': 'string', 'pattern': '^[0-9a-f]{64}$',
               'description': 'Hash de impacto de la vista previa revisada; 64 caracteres hexadecimales en minúsculas.'}
_CATALOG = {'type': 'string', 'enum': ['documents', 'projects'],
            'description': 'Catálogo del estado; esta operación siempre lo fija en projects.'}
_ORDER = {'type': 'integer', 'minimum': 0,
          'description': 'Posición de orden desde 0; por defecto 0 al crear.'}
_ACTIVE = {'type': 'boolean', 'default': True,
           'description': 'Indica si el elemento está activo; por defecto true al crear.'}
_STATE_PROPERTIES = {
    'catalog': _CATALOG,
    'name': {'type': 'string', 'minLength': 1, 'maxLength': 60,
             'description': 'Nombre del estado, sin quedar en blanco; máximo 60 caracteres.'},
    'description': {'type': 'string', 'maxLength': 300,
                    'description': 'Explicación del estado de proyecto, obligatoria sin quedar en blanco; máximo 300 caracteres.'},
    'color': {'type': 'string', 'enum': ['gray', 'emerald', 'blue', 'yellow', 'orange', 'red', 'purple'],
              'default': 'gray', 'description': 'Color del estado; por defecto gray al crear.'},
    'operational_effect': {
        'type': 'string',
        'enum': ['', 'development', 'operating', 'suspended', 'completed', 'decommissioned'],
        'description': 'Efecto operativo del estado; projects exige un valor no vacío y no permite cambiarlo después.',
    },
    'order': _ORDER,
    'group': _id('Id del grupo de proyectos; al crear se usa el primer grupo exclusivo activo si se omite.'),
    'is_active': _ACTIVE,
    'incompatibility_ids': _ids('Ids de estados incompatibles; al crear, por defecto ninguno.'),
}
_ACCESS_FIELDS = _object({
    'site_url': {'type': 'boolean', 'description': 'Permite compartir la URL del sitio.'},
    'admin_url': {'type': 'boolean', 'description': 'Permite compartir la URL de administración.'},
    'admin_username': {'type': 'boolean', 'description': 'Permite al cliente consultar el usuario de administración.'},
    'admin_password': {'type': 'boolean', 'description': 'Permite al cliente revelar la contraseña por la vía autorizada.'},
}, ('site_url', 'admin_url', 'admin_username', 'admin_password'))
_ACCESS_MATRIX = {
    **_object({'production': _ACCESS_FIELDS, 'staging': _ACCESS_FIELDS}, ('production', 'staging')),
    'description': 'Permisos completos por campo para production y staging; cada permiso es true o false.',
}
_SELECTION = {
    **_object({
        'communication_threads': _ids('Ids de hilos conservados que se seleccionan para eliminar.'),
        'communication_folders': _ids('Ids de carpetas de comunicación conservadas que se seleccionan para eliminar.'),
        'document_folders': _ids('Ids de carpetas documentales conservadas que se seleccionan para eliminar.'),
    }),
    'type': ['object', 'null'], 'default': None,
    'description': 'Contenedores conservados seleccionados por tipo; omitido o null revisa todos. Las listas se deduplican.',
}


def _container_query(description):
    return {
        'oneOf': [
            {'type': 'integer', 'minimum': 1},
            {'type': 'array', 'items': {'type': 'integer', 'minimum': 1}},
            {'type': 'string'},
        ],
        'description': description + (
            ' Id, lista de ids o texto separado por comas; sin ninguna selección se revisan todos los tipos, '
            'y con selección se excluyen los tipos omitidos.'
        ),
    }


PROJECTS_BRIDGE_SCHEMAS = {
    'list_projects': _query({
        'client_profile_id': _id('Id del perfil de cliente para filtrar; omitido consulta todos los clientes.'),
        'scope': {'type': 'string', 'enum': ['active', 'archived', 'all'], 'default': 'active',
                  'description': 'Ámbito legado: active, archived o all; por defecto active.'},
    }),
    'get_project': _query(),
    'update_project': _payload({
        'name': {'type': 'string', 'minLength': 1, 'maxLength': 200,
                 'description': 'Nombre del proyecto, sin quedar en blanco; máximo 200 caracteres. Omitido conserva el actual.'},
        'description': {'type': 'string',
                        'description': 'Descripción del proyecto; admite texto vacío. Omitida conserva la actual.'},
    }),
    'preview_project_delete': _query(),
    'delete_project': _payload(),
    'list_project_unlinked_records': _query(),
    'list_project_retention_contexts': _query({
        'client_profile_id': _id('Id del perfil de cliente para filtrar los datos conservados; omitido consulta todos.'),
        'page': _PAGE,
        'integrity': {'type': ['boolean', 'string'], 'default': False,
                      'description': 'Incluye filas conservadas que recuperaron un proyecto con true o "1"; por defecto false.'},
    }),
    'assign_project_unlinked_records': _payload({
        'hosting_ids': {**_ids('Ids de hostings del cliente sin proyecto; por defecto lista vacía.'), 'default': []},
        'income_ids': {**_ids('Ids de ingresos del cliente sin proyecto; por defecto lista vacía.'), 'default': []},
        'document_ids': {**_ids('Ids de documentos del cliente sin proyecto; por defecto lista vacía.'), 'default': []},
        'thread_ids': {**_ids('Ids de hilos conservados del cliente sin proyecto; por defecto lista vacía.'), 'default': []},
        'reason': {'type': 'string', 'maxLength': 2000, 'default': '',
                   'description': 'Motivo opcional del traslado; máximo 2.000 caracteres, por defecto vacío.'},
    }),
    'preview_project_client_change': _query({
        'client_profile_id': _id('Id del perfil del nuevo cliente propietario.'),
    }, ('client_profile_id',)),
    'change_project_client': _payload({
        'client_profile_id': _id('Id del perfil del nuevo cliente propietario.'),
        'mode': {'type': 'string', 'enum': ['move', 'detach'],
                 'description': 'move traslada los registros al nuevo cliente; detach conserva su cliente y los desvincula del proyecto.'},
        'expected_impact_hash': {'type': 'string',
                                 'description': 'impact_hash de preview_project_client_change después de revisar el plan vigente.'},
    }, ('client_profile_id', 'mode', 'expected_impact_hash')),
    'list_project_state_groups': _query(),
    'create_project_state_group': _payload({
        'catalog': _CATALOG,
        'name': {'type': 'string', 'minLength': 1, 'maxLength': 80,
                 'description': 'Nombre del grupo, sin quedar en blanco; máximo 80 caracteres.'},
        'selection_mode': {'type': 'string', 'enum': ['exclusive', 'additive'],
                           'description': 'Modo de selección del grupo; esta operación siempre lo fija en exclusive.'},
        'order': _ORDER,
        'is_active': _ACTIVE,
    }, ('name',)),
    'list_project_states': _query({
        'include_retired': {'type': ['boolean', 'string'], 'default': False,
                            'description': 'Incluye estados retirados con true, "1" o "yes"; por defecto false.'},
    }),
    'create_project_state': _payload({
        **_STATE_PROPERTIES,
        'confirm_similar': {'type': 'boolean', 'default': False,
                            'description': 'Confirma que se revisaron los estados similares; por defecto false.'},
    }, ('name',)),
    'suggest_project_states': _query({
        'q': {'type': 'string', 'default': '',
              'description': 'Nombre o fragmento para buscar estados similares; por defecto vacío.'},
    }),
    'update_project_state': _payload(_STATE_PROPERTIES),
    'retire_project_state': _payload(),
    'merge_project_state': _payload({
        'target_state_id': _id('Id del estado de proyectos que recibe la fusión.'),
    }, ('target_state_id',)),
    'preview_project_state_transition': _payload({
        'state_id': _id('Id del estado de destino del catálogo de proyectos.'),
        'effective_at': {'type': 'string', 'format': 'date-time',
                         'description': 'Fecha y hora ISO 8601 de la transición; omitida se usa la fecha calculada por el servicio.'},
    }, ('state_id',)),
    'apply_project_state_transition': _payload({
        'state_id': _id('Id del estado de destino del catálogo de proyectos.'),
        'effective_at': {'type': 'string', 'format': 'date-time',
                         'description': 'Fecha y hora ISO 8601, igual a la revisada en la vista previa; omitida usa la fecha calculada.'},
        'impact_token': {'type': 'string', 'minLength': 64, 'maxLength': 64,
                         'description': 'Token de impacto vigente de la vista previa; exactamente 64 caracteres.'},
        'note': {'type': 'string', 'maxLength': 500, 'default': '',
                 'description': 'Nota de la transición; máximo 500 caracteres, por defecto vacía.'},
        'resolutions': {
            'type': 'array', 'default': [],
            'items': _object({
                'income_id': _id('Id del ingreso pendiente al que se aplica la decisión.'),
                'action': {'type': 'string', 'enum': ['keep_receivable', 'write_off']},
            }, ('income_id', 'action')),
            'description': 'Decisiones por ingreso pendiente: keep_receivable conserva el saldo, write_off lo descarta; por defecto ninguna.',
        },
    }, ('state_id', 'impact_token')),
    'list_project_state_history': _query(),
    'list_project_commercial_phases': _query(),
    'add_project_commercial_phase': _payload({
        'proposal_id': _id('Id de la propuesta aceptada ya vinculada al proyecto.'),
        'order': {'type': 'integer', 'minimum': 1,
                  'description': 'Posición de la fase desde 1; omitida se agrega al final.'},
    }, ('proposal_id',)),
    'update_project_commercial_phase': _payload({
        'hosting_start_date': {'type': ['string', 'null'], 'format': 'date',
                               'description': 'Fecha de inicio de hosting en formato YYYY-MM-DD; null elimina la fecha.'},
    }, ('hosting_start_date',)),
    'remove_project_commercial_phase': _payload(),
    'reorder_project_commercial_phases': _payload({
        'items': {'type': 'array', 'items': _object({
            'id': _id('Id de la fase comercial.'),
            'order': {'type': 'integer', 'minimum': 1},
        }, ('id', 'order')),
            'description': 'Todas las fases del proyecto, cada id una vez y posiciones consecutivas desde 1.'},
    }, ('items',)),
    'get_project_brand': _query(),
    'upload_project_brand_asset': _payload({
        'title': {'type': 'string', 'minLength': 1, 'maxLength': 200,
                  'description': 'Título del archivo de marca, sin quedar en blanco; máximo 200 caracteres.'},
        'category': {'type': 'string', 'enum': ['branding', 'manual', 'design_system', 'logo', 'other'],
                     'description': 'Categoría del archivo: branding, manual, design_system, logo u other.'},
    }, ('title', 'category')),
    'download_project_brand_asset': _query(),
    'delete_project_brand_asset': _payload(),
    'list_project_ideas': _query({'page': _PAGE}),
    'get_project_idea': _query(),
    'list_project_idea_revisions': _query({'page': _PAGE}),
    'create_project_idea': _payload({'text': _IDEA_TEXT, 'request_id': _REQUEST_UUID}, ('text', 'request_id')),
    'update_project_idea': _payload({'text': _IDEA_TEXT, 'expected_version': _VERSION}, ('text', 'expected_version')),
    'archive_project_idea': _payload({'expected_version': _VERSION}, ('expected_version',)),
    'restore_project_idea': _payload({'expected_version': _VERSION}, ('expected_version',)),
    'list_project_idea_collections': _query({'page': _PAGE}),
    'get_project_idea_collection': _query(),
    'create_project_idea_collection': _payload({
        'title': {'type': 'string', 'minLength': 1, 'maxLength': 255,
                  'description': 'Título de la recopilación, sin quedar en blanco; máximo 255 caracteres.'},
        'request_id': _REQUEST_UUID,
        'items': {'type': 'array', 'minItems': 1, 'maxItems': 100,
                  'items': _object({
                      'idea_id': _id('Id de la idea seleccionada; no se repite en la recopilación.'),
                      'expected_version': _VERSION,
                  }, ('idea_id', 'expected_version')),
                  'description': 'Entre 1 y 100 ideas del proyecto y cliente actual, sin repetir ids, con sus versiones vigentes.'},
    }, ('title', 'items', 'request_id')),
    'get_project_client_access_policy': _query(),
    'set_project_client_access_policy': _payload({
        'expected_version': {'type': 'integer', 'minimum': 0,
                             'description': 'Versión vigente de la política consultada; 0 si todavía no existe.'},
        'source_token': {'type': 'string', 'maxLength': 1000,
                         'description': 'Token de los datos consultados en get_project_client_access_policy; máximo 1.000 caracteres, vigente 30 minutos.'},
        'permissions': _ACCESS_MATRIX,
    }, ('expected_version', 'source_token', 'permissions')),
    'preview_project_client_access': _query(),
    'list_project_client_access_events': _query({'page': _PAGE}),
    'preview_retained_operation_undo': _query(),
    'undo_retained_operation': _payload({
        'reason': _REASON, 'request_id': _REQUEST, 'expected_impact_hash': _IMPACT_HASH,
    }, ('reason', 'request_id', 'expected_impact_hash')),
    'preview_retained_container_cleanup': _query({
        'communication_threads': _container_query('Hilos conservados seleccionados.'),
        'communication_folders': _container_query('Carpetas de comunicación conservadas seleccionadas.'),
        'document_folders': _container_query('Carpetas documentales conservadas seleccionadas.'),
    }),
    'delete_empty_retained_containers': _payload({
        'reason': _REASON, 'request_id': _REQUEST, 'expected_impact_hash': _IMPACT_HASH,
        'selection': _SELECTION,
    }, ('reason', 'request_id', 'expected_impact_hash')),
}
