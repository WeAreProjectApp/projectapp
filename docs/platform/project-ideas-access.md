# Ideas por proyecto y exposición de accesos — P4

Incremento propio sobre la dependencia publicada e inmutable P3 `dea940345fc37c361f8749d30e1a96ac2bba73ee`, absorbida mediante merge en la rama propia. El PR apunta a `main`; P0 fijó el orden P3 → P1 → P2 → P4 → P5. Migración propia `0070_platform_ideas_access` con padre P3 `0067_explicit_delivery_authoring_context` y dependencia del modelo de usuario. P0 reservó la nueva hoja sin operaciones `0075_p4_platform_domains_merge`, aún no creada: sólo se añadirá después de recibir y absorber mediante merge el SHA final publicado de P2. No aplica migraciones ni despliegue. Esta referencia publicada de P3 todavía no constituye su entrega verde/final.

## Acuerdos recibidos directamente del operador

- Oculto por defecto se aplica **sólo a URLs y accesos**. No hay interruptores globales de bugs, hosting, cobros o entregas publicadas.
- Cada dato se habilita explícitamente por proyecto y ambiente; la API aplica los mismos permisos.
- Ideas son texto simple por proyecto. Audio/IA, contratación automática, correo, finanzas y bugs quedan fuera del incremento.
- Cada sesión conserva su rama, worktree y PR. Esta sesión integra únicamente referencias publicadas e inmutables de dependencias bajo la coordenada de P0 dentro de su propia rama; no mergea a main.

## Modelos y decisiones

`ProjectIdea` conserva proyecto, cliente destinatario al registrarla, autor/etiqueta original, fecha, texto, origen cliente/equipo, número de revisión, versión de escritura y archivo reversible. UUID de petición hace el alta idempotente por proyecto/autor. `ProjectIdeaRevision` conserva cada texto con editor y fecha. La versión también cambia al archivar/restaurar para rechazar ediciones obsoletas.

El propietario actual lee sus sugerencias y las del equipo destinadas a su cuenta. Sólo corrige sus ideas activas; el equipo corrige las del equipo y archiva/restaura cualquiera. El archivo conserva texto/versiones y sigue visible. No existen endpoints de borrado. Tras transferir el proyecto, el nuevo cliente no recibe ideas del anterior; el equipo mantiene acceso a ellas.

`ProjectIdeaCollection` y sus items son internos e inmutables. Recopilan una selección ordenada de hasta 100 ideas del **mismo proyecto y cliente propietario actual**, con las versiones elegidas, texto, autor y fecha copiados. Un conflicto aborta toda la colección. Ninguna operación crea contratos, requerimientos, alcances, revisiones de entrega ni aprobaciones. Se permite copiar los textos para evaluación futura. Una edición posterior no modifica la colección.

`ProjectClientAccessPolicy` es una matriz fija de 2 ambientes × 4 datos: producción/QA (`staging`) y URL del sitio, URL Django, usuario Django y contraseña Django. Ausencia de política equivale a ocho permisos falsos. Cada permiso se vincula al cliente y a una huella HMAC de su fuente. `ProjectClientAccessEvent` audita acciones, actor, campos y versión **sin valores**, URLs, tokens ni credenciales.

Las fuentes siguen siendo `Project.production_url/staging_url` y `ProjectAdminAccess`. No se duplican credenciales ni se exponen accesos legacy no clasificados, repositorio o notas internas. URLs con userinfo, query o fragmento no son elegibles. Actualizar visibilidad exige versión vigente y token firmado de fuentes vistas por el administrador, con caducidad de 30 minutos.

## Permisos y secretos

- Panel usa sesión Django + CSRF y exige staff; Platform JWT exige perfil admin para administración o propietario actual para lectura limitada/revelación.
- Listas, detalle normal, previsualización y eventos omiten valores de usuario/contraseña. El detalle normal añade únicamente `can_view_client_access`, calculada para la cuenta propietaria que consulta; el administrador conserva su editor por rol, sin consultar grants ajenos para esa capability.
- Credenciales requieren un POST por ambiente/campo autorizado. Cada revelación/copia vuelve a comprobar propietario, grant y fuente; respuestas de éxito y error llevan `Cache-Control: no-store` y `Pragma: no-cache`.
- Un cifrado ilegible o configuración de cifrado no disponible devuelve 503 controlado, sin detalles internos y sin registrar una revelación exitosa.
- El valor revelado vive sólo en el componente, sin Pinia/storage/historial. Se elimina al ocultar la pestaña, cambiar contexto/sesión, desmontar o cumplir 30 segundos. Copiar es una acción explícita del usuario y el portapapeles del sistema queda bajo su control.
- Cambiar cliente revoca todos los grants. Cambiar/borrar/mover URL o credencial revoca sus campos. Señales cubren saves/deletes ajenos al editor; un receptor propio consume los nombres de campos del historial existente para cubrir `QuerySet.update/bulk_update`, incluso si después se restaura el valor anterior. Las huellas también rechazan fuentes distintas antes de compartir. Escrituras SQL manuales o realizadas con `without_history()` eluden esta frontera y deben revocar grants explícitamente.
- Django Admin bloquea el proyecto original dentro de la transacción y revoca antes de guardar: todo al cambiar cliente, sólo permisos de URL al cambiar producción/QA. Usa el propietario original en el evento; un fallo de guardado revierte grants y auditoría. P2 posee el formulario, la validación, el helper de core/tickets y el guard financiero. Al absorber su referencia publicada, sus guards deben ejecutarse antes del puente P4, sin escrituras ni revocación si rechazan. La regresión conjunta de rechazo financiero queda pendiente de esa absorción bajo la coordenada de P0.
- Sesión JWT impersonada no registra/corrige ideas ni revela credenciales; conserva lectura permitida. El backend verifica la claim firmada; la UI sólo ajusta controles.

## Rutas

Prefijo Platform: `/api/accounts/projects/<project_id>/`. Prefijo Panel: `/api/projects/<project_id>/`.

| Ruta relativa | Métodos | Permiso |
|---|---|---|
| `ideas/` | GET, POST | Propietario o admin; autor derivado de sesión |
| `ideas/<idea_id>/` | GET, PATCH | Lectura del proyecto; corrección según autor/origen |
| `ideas/<idea_id>/revisions/` | GET | Misma frontera de lectura |
| `ideas/<idea_id>/archive/`, `restore/` | POST | Admin, versión obligatoria |
| `idea-collections/`, `<collection_id>/` | GET; POST sólo listado | Admin |
| `access/client-policy/` | GET, PATCH | Admin, versión + token + matriz completa |
| `access/client-policy/preview/`, `events/` | GET | Admin |
| `client-access/` (sólo Platform) | GET | Propietario actual |
| `client-access/environments/<environment>/credentials/<field>/reveal/` (sólo Platform) | POST | Propietario, grant efectivo, sesión personal |

Inputs desconocidos/identidades enviadas por cliente se rechazan; versiones deben ser enteros reales y permisos booleanos. Proyectos/ideas/colecciones ajenos dan 404; privilegios insuficientes 403; datos inválidos 400; conflictos 409. Listados paginan a 20 filas. Texto de idea tiene máximo 10.000 bytes UTF-8; snapshots completos de una recopilación se limitan a 190.000 bytes, con error antes de escribir si se excede. Listado de recopilaciones devuelve resúmenes con cantidad; sus textos se consultan bajo demanda mediante el detalle. La copia recién creada se muestra inmediatamente. Así las listas y detalles respetan el presupuesto de respuesta sin multiplicar los snapshots completos por página.

MCP `projects`: 10 herramientas de ideas/revisiones/archivo/colecciones y 4 de política/preview/auditoría. Sus adaptadores llaman los mismos FBVs Panel. Compartir/revocar política es sensible: previsualización + `confirm_action`, invalidada por cambio de fuente o versión. No hay herramienta MCP de revelación de credenciales. Autor MCP queda como equipo, jamás suplantando autoría del cliente.

## UX y compatibilidad

Ideas se alcanza desde navegación del proyecto Platform y acciones de proyecto Panel. Formularios conservan borrador/selección en errores; correcciones muestran versiones, archivo es reversible y recopilaciones explican su uso futuro. Texto se renderiza escapado, sin HTML.

Accesos muestra al cliente sólo ambientes/datos efectivos. Su enlace aparece con la capability; la URL directa queda disponible como estado vacío sin grant. El equipo mantiene el editor `project_access` y una política adicional en Platform y modal Panel. Guardar no comparte otros datos implícitamente; preview omite secretos y audit muestra únicamente campos/acciones. La semántica antigua de redirigir clientes en `/access` se reemplaza por esta proyección limitada.

## Propiedad e integración

| Bloque compartido reservado a P4 | Cambio mínimo | Dependencia/orden P0 |
|---|---|---|
| `accounts/models.py`, `apps.py` | Imports de modelos propios y registro de hooks | P3 publicado antes; migración propia 0070 sobre 0067, sin hoja merge de otras sesiones |
| `accounts/migrations/0075_p4_platform_domains_merge.py` (reservada, no creada) | Nueva migración con `operations=[]`; padres `0074_p2_platform_billing_merge` y `0070_platform_ideas_access` | Crear únicamente después de recibir y mergear el SHA final publicado de P2, verificando que existe su padre 0074; no editar migraciones anteriores |
| `accounts/urls.py`, `content/urls.py` | Include de rutas de dominio | Modelos/servicios propios |
| `accounts/serializers.py` | Capability de acceso en detalle; conserva redacción previa | Política y fuente existentes |
| `project_access.py`, `project_service.py`, `accounts/admin.py::ProjectAdmin.save_model` | Locks/revocación por edición y transferencia; en Admin compara contra el proyecto original | Orden: proyecto bloqueado → validación/guards financiero y core/tickets P2 sin writes al rechazar → revoke_grants P4 → reasignación/cascada o guardado Admin. P2 conserva formulario, validación y helper; P4 sólo su puente de revocación. P0 coordina el cruce y la regresión financiera |
| MCP `operation_catalogs.py`, `contracts.py` | Registros nombrados del dominio | Rutas Panel y modelos disponibles |
| Sidebar, Panel projects y modal access | Enlaces Ideas y capability; política adicional | Páginas/components propios |
| Agregadores locales, catálogos, responsive y flows | Entradas/secciones de dominio; derivados regenerados | Integrar sin reordenar bloques ajenos |
| Seeds/clasificación/reset, memoria | Invocación de helper propio y documentación de P4 | Sin ejecutar fake data fuera de tests aislados |
| Config Playwright y workflow propio | Excluir harness real del runner mock; job P4 separado | SQLite/settings_test y fuentes efímeras |

Archivos propios: modelos/serializers/services/views/hooks/urls en `accounts` con nombres ideas/client_access/project_collaboration; FBVs/URLs Panel y herramientas MCP dedicados; componentes `projects/ideas`, `projects/client-access`, stores/services/locales y páginas ideas; tests backend/unit/E2E dedicados, harness local y este documento. Contratos/fases/etapas/guías/prompts y componentes/locales Delivery permanecen propiedad P3.

## Aceptación y límites de validación

Deben pasar autoría/revisiones/archivo; idempotencia; recopilación congelada y atomicidad; permisos granulares/default deny; revocación por fuente/propietario; aislamiento de proyectos/clientes; ausencia de secretos en listas/preview/audit; JWT frente a sesión/CSRF; paridad MCP y confirmaciones obsoletas; UI con borradores y revelación efímera; navegación y cinco anchos canónicos.

Las pruebas usan SQLite y settings_test, límites <=20 por lote y <=2 specs E2E. Los locks de producción MySQL conservan el orden proyecto → acceso/política; SQLite no demuestra contención concurrente MySQL. La migración 0070 es nueva, propia y no aplicada. La hoja 0075 permanece reservada hasta absorber el SHA final publicado de P2; entonces unirá 0074 y 0070 sin operaciones. P0 coordina las demás hojas y el orden P3 → P1 → P2 → P4 → P5. P3 revisa diseño central al terminar. PR abierto, CI propio y revisión de integración son la entrega; no self-merge.
