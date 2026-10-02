# Enlaces seguros propios en Platform — contrato técnico

Decisiones directas del operador: enlaces del cliente sólo para nuestro equipo;
catálogo existente de texto/credenciales, sin archivos, terceros ni importación de
accesos internos. Gestión A: crear, listar metadatos, historial propio, revocar y
reactivar explícitamente rotando token. El cliente no lee secretos guardados,
borra evidencia ni cambia contenido en el mismo enlace. Corregir revoca y crea un
sucesor ligado al anterior; la auditoría y el contenido cifrado anterior permanecen.

## Propiedad y permisos

`owner` referencia el UserProfile cliente, separado de `created_by` (puede ser el
actor administrativo MCP). Cada consulta cliente exige owner=client=perfil,
project=ruta y Project.client=usuario actual; el origen debe ser `platform` y
audience=`team`. Se exige cuenta activa, cliente, onboarding completo y sin archivo.
Una reasignación de proyecto corta el acceso; no se heredan enlaces al nuevo
cliente. Los enlaces legacy no se adoptan por email, client ni project.

Platform usa exclusivamente JWTAuthentication/usePlatformApi. Una sesión Panel
no autentica estos endpoints, y un JWT no otorga administración Panel. La apertura
pública por token sigue exigiendo sesión staff para enlaces de clientes. Panel y
MCP staff conservan la administración existente; la propiedad de un enlace
Platform es inmutable también para ellos. La eliminación staff sigue siendo su
operación administrativa destructiva existente, nunca una capacidad del cliente.

## API JWT

Prefijo `/api/accounts/projects/{project_id}/secure-links/`.

| Ruta | Método | Entrada / resultado |
|---|---|---|
| `types/` | GET | Catálogo actual después de validar proyecto propio |
| raíz | GET | page>=1, status, search; página de 25, count/counts, metadatos |
| raíz | POST | request_id UUID, title, secret_type, fields; language es/en, validity_days 1/3/7 (default 7), replaces opcional |
| `{id}/` | GET | Metadatos y capacidades, sin URL ni secretos |
| `{id}/` | PATCH | title y expected_updated_at |
| `{id}/events/` | GET | page>=1, 25 eventos: id/kind/fecha, actor_kind y referencia de sustitución |
| `{id}/link/` | POST | `{}`; URL explícita del enlace activo, auditada |
| `{id}/revoke/` | POST | `{}`; metadatos, idempotente |
| `{id}/reactivate/` | POST | expected_updated_at y validity_days; metadatos y nueva URL |

Primera creación: 201 `{link, url, replayed:false}`. Repetición idéntica: 200
`{link, replayed:true}`, sin URL. UUID reutilizado con entrada normalizada distinta:
409 `request_id_conflict`. Se compara HMAC-SHA256 con clave del servidor y
SECRET_KEY_FALLBACKS; sólo el MAC se persiste, nunca entrada/contraseña ni hash
sin clave. Una nueva clave sin mantener la anterior como fallback hace fallar la
comparación de solicitudes anteriores (conflicto, sin duplicación ni exposición).

PATCH y reactivación exigen la fecha actual: versión obsoleta=409. No hay
endpoints cliente content/delete/mark-sent ni campos owner/audience/client/origin
editables. Extras en escritura=400, scope ajeno=404, JWT ausente=401, rol no
habilitado=403, límites por usuario=429, cifrado no configurado=503. Creación tiene
10 intentos/hora y URL/reactivación 30/minuto. Todas las respuestas JWT,
incluidos errores de autenticación/validación, llevan no-store y Pragma no-cache.

## Ciclo de vida, idempotencia y carreras

Se reutilizan el cifrado Fernet, token aleatorio de 32 bytes en fragmento URL,
hash SHA256 de consulta, vencimiento calculado y reveal atómico existente. No se
duplica criptografía ni se descifra contenido para comparar solicitudes.

Revoke conserva evidencia y no duplica eventos. Reactivar Platform requiere
enlace consumed/expired/revoked sin sucesor, rota SIEMPRE el token, reinicia vigencia
y guarda reactivated+rotated. La URL anterior queda inválida. Legacy conserva
reactivación opcionalmente sin rotar y vigencia 1/3/7/30.

Una sustitución exige que el anterior ya esté revocado, pertenezca al mismo
owner/proyecto y no tenga sucesor. `replaces` es OneToOne. El formulario de
sustitución comienza sin contenido; si la nueva creación falla o se cancela, el
anterior queda revocado. No se reactiva un enlace ya sustituido.

Escrituras administradas bloquean Project antes de SecureLink. MCP usa el mismo
orden para revalidar etags bajo confirmación. El índice owner/project/fecha y la
restricción única owner/request_id evitan búsquedas completas y duplicados. La
creación usa savepoint y reconsulta bloqueante para resolver carreras del UUID,
incluso entre proyectos diferentes del mismo propietario; la relación OneToOne
también tiene unicidad en DB. Reveal público conserva su bloqueo de fila y
rechazo de segundo consumo. No hay locks de Redis ni envíos externos.

SQLite/settings_test valida resultados, unicidad y revisiones obsoletas; su
select_for_update es inoperante. La exclusión entre transacciones concurrentes de
MySQL queda sin validación ejecutada mientras no exista harness aislado permitido;
no se usan pytest MySQL, la DB real ni .env de producción para verificarla.

## MCP administrativo y privacidad

Conector `communications`: nuevos create_platform_secure_link, list_secure_link_events
y get_secure_link_url. Create exige owner_id(UserProfile), project_id y el payload
JWT de creación; fuerza equipo/origen Platform y usa el mismo servicio/idempotencia.
List_secure_links añade filtro owner_id. Get/list sólo metadatos; history pagina
20 (máximo 50) y omite IP, navegador y detalles crudos.

Get_secure_link_url exige grant explícito independiente de grants generales,
confirmación y etag actual; resultado ephemeral_result, recibo sin URL y replay
sin capacidad de lectura. La lectura de contenido staff sigue siendo
reveal_secure_link_content, con su propio grant y confirmación existente. Update,
revoke, reactivate, mark-sent y delete mantienen handlers administrativos;
reactivate Platform fuerza rotación y omite URL en su recibo persistido; mark-sent
rechaza enlaces cliente. Los logs de estas tools sólo toman IDs enteros
whitelisteados y nunca recorren fields. Catálogo/errores no reflejan claves desconocidas.

## Frontend, datos y compatibilidad

Ruta `/platform/projects/:id/secure-links`, navegación exclusiva cliente.
Componentes Platform dedicados; los campos del catálogo se reutilizan como UI pura,
sin usar el cliente HTTP ni store Panel. Pinia contiene metadatos/catálogo, nunca
contenido, URL, firma del payload o errores Axios crudos. Los secretos de borrador
y URL sólo viven en el componente; se limpian al éxito/cierre/logout/cambio de
proyecto/unmount y se ignoran respuestas tardías. Clipboard requiere un clic.

Secure_links/0004_platform_ownership está reservada por P0: parents secure_links/0003
y accounts/0066. Backfill sólo audience (public=team, panel/mcp=bearer); no infiere
owner, descifra, rota tokens ni reescribe payloads. La semántica staff/public legacy
queda disponible. El filtro de recibidos Panel usa audience team y detecta Platform.
Seed exclusivamente de desarrollo incorpora dos propietarios ficticios y estados
activos/consumidos/vencidos/revocados/sustituidos, sin notificaciones ni URL en salida.

Bloques comunes propios: include accounts.urls; registry/contracts MCP y grant
get_secure_link_url; navegación; namespace i18n platformSecureLinks; catálogos,
responsive owner/flow y shards de flujos propios; secciones de memoria. No se
modifican contratos/prompts/guías, hosting/cobros ni políticas de otros frentes.
P3 revisa diseño; P0 coordina final P3 y orden de integración. Esta sesión entrega
PR a main y no hace merge ni deploy.

Base inicial verificada: `origin/main=cce8e6949b080269cf603b8013a97876604b63a5`.
La base publicada incorporada para el cierre de P5 es P4
`38f65b8016dad055f39354c6e29cd5701d77cfaf`, seguida de P1
`6a95dc933c227ec8777bcb1cd853a6597423eede` y P3
`54b8156b437936848da1fa9c637d88cc336537f7`, mediante merges en la rama propia.
P4 ya incluye P2 `fae1e3610bb38da0da8dd62864c1c763928dd85a` y P3
`cecb5b93d8cfd0b968fec3a71239323c48c7018f`. La hoja accounts es
`0075_p4_platform_domains_merge`, sin operaciones, con padres 0074 P2 y 0070 P4.
`secure_links/0004` conserva sus padres confirmados 0003 y accounts/0066:
no se renumera ni aplica a una base real. Los conflictos de agregadores conservan
las entradas de cada dominio; el mapa se regenera desde los shards y documentos.
Las tres correcciones comunes seleccionadas por P0 pertenecen a su PR separado,
último del tren, y no se incorporan a #461. La QA integrada y el merge de los PR
permanecen bajo P0, separados del cierre original de P5.

## Evidencia de validación

Las pruebas se ejecutaron desde el worktree P5, exclusivamente con
`projectapp.settings_test` y SQLite. El dominio tiene 55 casos: API (16),
idempotencia (11), ciclo de vida (13), ownership (7), MCP (7) y presupuesto de
consultas (1). También pasaron 32 regresiones del servicio/Panel/MCP legacy y
dos verificaciones de contratos/registro MCP. Las ejecuciones focales posteriores
repiten únicamente los casos afectados por cada ajuste.

P0 reservó también la compatibilidad de `accounts/tests/test_delivery_migration.py`:
su corte histórico se deriva del grafo y excluye descendientes de migraciones
accounts posteriores a 0063 en cualquier app, conservando las hojas compatibles
y 0063 como target explícito para que Django revierta el esquema, no sólo el estado.
El finally restaura latest aunque falle la preparación/get_model. Los tres casos
originales de purga y conservación pasaron sin skip/xfail; no se modificó el
esquema ni la migración 0064. El lote combinado de esos tres casos y el backfill
legacy pasó 4/4 en el mismo proceso SQLite, verificando la restauración efectiva.

Después del merge de P3 `dea94034`, el lote focal pasó 13/13: tres casos del
fixture histórico, backfill legacy, siete casos MCP propios y dos verificaciones
del registro/contrato MCP. El pin de catálogo pasó 1/1. Se revalidaron catálogo
(120 páginas), contrato responsive (600 celdas), tokens de diseño, flow-sync
(394 referencias/424 definiciones) y frescura del mapa; los tres flujos P5
siguen covered para display/success/error/failure. No se repitió toda la QA ni
se ejecutaron pruebas contra MySQL.

Después de incorporar P4 38f65b80, P1 6a95dc93 y P3 54b8156b, pasan los 13 casos
focales del cruce: fixture histórico (3), backfill (1), MCP propio (7) y contratos
de campos/herramientas del conector communications (2). El pin unitario pasa 1/1.
Catálogo (124 vistas), responsive (108 visuales + 16 redirects, 620 celdas),
flow-sync (403 referencias/433 definiciones) y registro derivado fresco pasan.
Antes de abrir la DB, el wrapper verificó settings_test, SQLite y todos los
aliases MAILERS en locmem, con guardas fail-closed de DB/red/SMTP. El lote terminó
con cero intentos de red y SMTP. No se repitieron los E2E, la suite original,
el diagnóstico observability ni su reproducción sintética; P0 conserva la QA
única del contenido integrado y las correcciones comunes de su PR separado.

Frontend: 13 pruebas unitarias dedicadas y una verificación del catálogo existente.
Dos casos reprodujeron respuestas tardías de catálogo entre proyectos y pasaron
después de corregir la generación de carga del workspace. Los tres flujos nuevos
declaran display/success/error/failure; el mapa derivado está fresco. La validación
de navegador usa Nuxt real con la frontera HTTP simulada: no demuestra integración
contra una API desplegada. Las pruebas SQLite comprueban el contrato backend real.

Los 15 E2E dedicados se ejecutaron: diez funcionales y cinco perfiles responsive
(412, 835 vertical, 1195, 1440 y 2560). Después de alinear el fixture HTTP con el
catálogo real, nueve funcionales pasaron directamente y creación pasó en retry;
esa creación se revalidó sola y luego dos veces con retries=0/trazas, ambas verdes.
Hubo un timeout local de 60 segundos cuyo artefacto no quedó recuperable: su causa
no está determinada y las revalidaciones no prueban qué lo produjo. El dev Nuxt
tuvo fallos IPC; la repetición final usó el build propio servido en loopback.

El build Nuxt final terminó correctamente. Los guards de catálogo, responsive y
tokens de diseño pasaron; Ruff se ejecutó realmente desde el venv aislado del
worktree. La validación de concurrencia MySQL sigue pendiente del harness aislado
permitido. El piloto de mutación del toolkit no admite este clon no registrado;
no se alteraron sus guards ni projects.yml para hacerlo pasar. El CI del head P5
y el cierre final de P3 se verifican por SHA en el PR, separados de estas pruebas
locales; la referencia P3 publicada anterior ya está absorbida.

QA local: APPROVED. El gate final de los 15 archivos de pruebas/helpers tuvo
0 errores y 0 warnings (7 backend, 4 unitarios, 3 E2E; helper revisado manualmente).
El engine retiró su marker. La auditoría concluyó KEEP para todo el alcance;
el reporte local y las trazas viven fuera de archivos versionados.
