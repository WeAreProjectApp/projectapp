# Historial por registro

## Alcance aprobado

Cada registro ofrece un historial interno con fecha, autor, campos modificados y
versiones completas. Se abre desde su detalle, carga veinte eventos por página y
ordena primero el más reciente; el operador puede invertir el orden, consultar
una versión, compararla con la anterior o seleccionar dos versiones cualesquiera.
No permite restaurar, editar ni eliminar versiones.

| Módulo | Información conservada | Entrada |
|---|---|---|
| Documentos | Contenido, título, carpeta, etiquetas, cliente, proyecto, estados, notas, datos de cobro, ítems, medios de pago y archivos emitidos | Pestaña Historial del editor |
| Propuestas | Precio, descuento, alcance/secciones, condiciones, módulos y mensaje preparado; marca y PDF exactos del último envío confirmado | Pestaña Historial del editor |
| Proyectos | Datos generales, URLs, usuarios de administración, contraseñas por ambiente, notas y estados | Historial del detalle de accesos |
| Clientes | Nombre, correo, teléfono, empresa, documento de identidad y datos de facturación | Tarjeta expandida del cliente |
| Contable | Ingresos, gastos, hostings/ciclos, bolsillo, recurrentes, publicidad, saldos de tarjetas, tarjetas, extractos, transacciones, aliases, destinatarios y configuración | Entrada «Detalle e historial» del menú de tres puntos de cada fila (en Ingresos y Cuentas de cobro abre su modal de detalle, que incluye el historial) |

Las cuentas de cobro usan el historial del documento que las representa; no se
duplica la misma identidad. El historial general de Contable sigue disponible y
sus eventos permiten consultar también el historial de un registro eliminado.
Comunicaciones queda como candidato para una ficha posterior.

## Permisos y valores protegidos

La API de lectura exige sesión de administrador. Contable conserva su restricción
a superusuarios, incluida la entrada `collection_account`. Los endpoints no se
exponen al portal del cliente ni usan su cliente JWT.

Las contraseñas y el contenido de las notas de acceso del proyecto se conservan
cifrados con la clave existente `PROJECT_ACCESS_CIPHER_KEY`. Los listados,
versiones y comparaciones entregan máscaras, nunca el texto ni los tokens
cifrados. Revelar exige una acción explícita y un POST con sesión/CSRF; su
respuesta lleva `Cache-Control: no-store`. El visor mantiene ese texto únicamente
en memoria y lo borra al cambiar de versión o cerrar el historial.

La retención no vence y las versiones sobreviven a la eliminación del registro.
Las referencias al autor y al objeto son instantáneas, independientes de sus filas
actuales. Los PDFs reemplazados, retirados o de registros eliminados permanecen
en el almacenamiento. La copia de seguridad debe conservar tanto la base de
datos como los archivos y la clave de cifrado; una rotación debe contemplar
también los tokens históricos. No se reconstruyen documentos anteriores desde
plantillas actuales.

## Escritura y consistencia

`EntityHistory` identifica el agregado por tipo e ID. `EntityRevision` guarda
versiones inmutables, diferencias, resumen de campos, autor, origen y correlación
con evidencias previas. No tiene FK al registro vivo.

`history_operation` agrupa una operación lógica en una transacción. La captura
bloquea el agregado y su cabecera, lee el estado anterior y agrega una sola versión
por agregado al terminar. Un guardado sin cambios no agrega eventos. Los
servicios se agrupan con `historical_write`; HTTP y MCP aportan la identidad del
actor. Los procesos automáticos sin usuario se identifican como Sistema.

El middleware agrupa las escrituras de API y administración. Una excepción no
controlada revierte la operación; una respuesta de error deliberada conserva las
escrituras que el servicio haya confirmado, como el diagnóstico de un correo
fallido. El código HTTP por sí solo no decide el rollback.
Se respeta `transaction.non_atomic_requests` en las vistas que requieren
resultados parciales por elemento: las evaluaciones masivas de solicitudes de
cambio y bugs, cuyos modelos no forman parte de este histórico.

`HistoryTrackedModel` y `HistoryQuerySet` cubren save, delete, update,
bulk_create y bulk_update. En MySQL, las inserciones masivas usan inserciones
individuales del compilador ORM para recuperar cada PK sin disparar señales de
save. Los upserts masivos ambiguos se rechazan: usar `update_or_create` dentro de
la operación. Los escritores nuevos deben usar los servicios o este límite ORM;
SQL directo, `_raw_delete` y manipulaciones externas de tablas no son interfaces
de escritura admitidas. Cambios de relaciones M2M y de `auth.User` deben formar
parte de `history_operation`, como sucede en HTTP y los servicios existentes.

Se excluye telemetría de lectura, seguimiento de correo y autenticación. Markdown
es el contenido canónico del documento; se conserva JSON cuando no hay Markdown.
Las relaciones contienen el ID y una etiqueta del momento del cambio. Las notas
del documento y sus notas de facturación se conservan por separado.

Antes de enviar una propuesta se guarda una preparación privada con su contenido
y PDF exactos. Solo un envío confirmado agrega `sent_version`; una preparación
fallida no aparece como enviada ni es consultable en el historial público de la
API interna. El envío repetido de la misma preparación no duplica esa marca.

## Inicialización y despliegue

Las migraciones `0250_entityhistory_entityrevision` y
`0251_entityrevision_changed_fields` crean las tablas y el resumen liviano de
campos. `0252_merge_history_and_branding` une esta cadena con las migraciones de
marca y Linktrees, sin operaciones adicionales. Las aplica el deploy; no ejecutar migraciones ni la
inicialización desde un worktree enlazado a una base real.

Después de las migraciones, en el entorno de despliegue autorizado:

```bash
DJANGO_SETTINGS_MODULE=projectapp.settings_prod venv/bin/python manage.py initialize_entity_history --batch-size 100
```

También admite `--entity-type document` (o cualquier tipo del registro). Procesa
lotes reanudables, importa las evidencias disponibles de AccountingChangeLog,
ProposalChangeLog y eventos de estados, y crea una versión inicial del estado
actual si todavía falta. Repetir el comando no duplica evidencias ni versiones.
Cada evento antiguo conserva su fecha y autor disponibles, se marca sin versión
completa y no se puede comparar. No se inventan contenidos anteriores.

Sin inicialización previa, el primer cambio de un registro existente conserva
automáticamente su estado anterior como versión inicial. La inicialización sigue
siendo necesaria para incorporar la evidencia antigua y los registros sin cambios.

## Contrato de consulta

Prefijo: `/api/entity-history/<entity_type>/<object_id>/`.

| Ruta | Uso |
|---|---|
| GET raíz, `page`, `order=recent\|oldest` | Lista paginada de resúmenes, último cambio y último envío |
| GET `versions/<revision_id>/` | Instantánea completa, diferencias y campos protegidos disponibles |
| GET `compare/?from=<id>&to=<id>` | Diferencias entre versiones del mismo registro |
| POST `versions/<revision_id>/reveal/`, `{ "field": "…" }` | Revelación explícita de un valor protegido |
| GET `versions/<revision_id>/file/` | Bytes del PDF conservado, incluso si el registro ya no existe |

El listado excluye instantáneas, secretos y diferencias completas de su consulta.
El visor se monta al abrir Historial y descarta respuestas tardías de consultas
anteriores. El diff textual adicional se limita a contenidos acotados; los valores
completos antes/después siguen disponibles.

La validación focal incluye permisos, CSRF, aislamiento entre registros, escrituras
masivas, rollback, ausencia de cambios, importación repetida, PDFs, propuesta enviada,
presupuesto de queries del listado, reintentos y respuestas fuera de orden. Los
cinco flujos de UI se registran por separado en `frontend/e2e/flows/`.
