# Integridad de datos

Motor que encuentra datos huérfanos, duplicados e inconsistentes en clientes,
proyectos, documentos, comunicaciones, contabilidad y propuestas, y los corrige con
vista previa, registro y deshacer. Lo usa la skill `data-integrity`
(`.claude/skills/data-integrity/`) a través del conector MCP `projects` (Gestor de
Proyectos), y el panel a través de `/api/projects/data-integrity/`.

## Piezas

| Pieza | Dónde |
|---|---|
| Catálogo de reglas y registro de fixers | `backend/content/services/data_integrity/catalog.py` |
| Reglas por dominio | `backend/content/services/data_integrity/rules/*.py` |
| Alcance (qué ids mira una revisión) | `backend/content/services/data_integrity/scope.py` |
| Motor: escaneo, vista previa, aplicar, deshacer | `backend/content/services/data_integrity/engine.py` |
| Contrato de fixer y escritores compartidos | `backend/content/services/data_integrity/fixes/` |
| Fusiones | `backend/content/services/client_merge*.py`, `backend/content/services/document_folder_merge.py` |
| Registro de operaciones | `content.DataIntegrityOperation` (append-only) |
| API del panel | `backend/content/views/data_integrity.py` |
| Herramientas MCP | `backend/content/mcp/data_integrity_tools.py` (conector `projects`) |
| Inventario de relaciones | `backend/content/services/data_integrity/relation_inventory.py` |
| Comando de sólo lectura | `manage.py audit_data_integrity` (`backend/content/management/commands/`) |
| Qué impide borrar un cliente | `backend/accounts/services/client_deletion.py` |

## Cómo funciona

1. **Detectar.** Cada regla (`@rule`) recibe un `Scope` y devuelve `Finding`s. El
   alcance es un conjunto de ids por modelo: `all` mira todo; `client`, `project`,
   `proposal`, `document` y `thread` limitan. Las reglas de duplicados agrupan sobre
   toda la base y conservan los grupos que tocan el alcance. La agrupación se hace en
   Python con un único normalizador, porque la intercalación `_ci` de MySQL y SQLite
   no coinciden con las tildes.
2. **Fingerprint.** Cada hallazgo se identifica con un hash de regla, versión, sujetos
   y evidencia (nunca etiquetas, fechas ni alcance), así que es el mismo en todos los
   barridos.
3. **Vista previa.** El motor vuelve a detectar, arma el plan de cada fixer sin
   escribir y calcula un `impact_hash` sobre los pasos y los valores actuales de todas
   las filas que se tocarían (incluido `updated_at`). Máximo 20 correcciones y 500
   filas por lote; las fusiones van solas, con su propio tope.
4. **Aplicar.** Idempotente por `request_id`. Bloquea las filas, recalcula la vista
   previa y exige el mismo hash. Cada fixer escribe con los escritores del dominio (los
   mismos servicios y serializers del panel) y el motor guarda antes/después de cada
   campo tocado. Si el hallazgo no desaparece, revierte todo el lote
   (`fix_ineffective`). El historial de entidades se escribe en la misma operación y
   `history_operation_id` lo enlaza.
5. **Deshacer.** Sólo si nada cambió después (`changed_since`), una única vez
   (`already_reverted`) y sin que cambie lo que la corrección dio por hecho
   (`guard_changed`). Ejecuta el `revert` del fixer y luego restaura exactamente cada
   campo que siga distinto; si algo no queda igual, revierte (`undo_not_exact`).

## Invariantes

- Nunca se borran registros para resolver un duplicado: se fusionan y el perdedor
  queda archivado.
- Nunca se escriben filas conservadas de un proyecto eliminado (`retention_context`),
  raíces gestionadas fuera de una fusión, carpetas de sistema ni documentos generados.
- Nunca se reescriben historial, logs ni evidencia.
- Lo que no tiene corrección segura es `report_only`; lo que ya tiene una herramienta
  con su propia vista previa es `existing_tool` y el motor no lo aplica.
- Archivar un cliente no es una acción MCP; la única excepción es el último paso de una
  fusión, cuando el duplicado ya no tiene proyectos (no hay cascada).

## Agregar una regla

1. Elegir el módulo de `rules/` del dominio y un id nuevo (`XX9`). Si la regla cambia
   de significado, subir `version` en vez de reutilizar el id.
2. Escribir `detect(scope)` con lecturas sobre `_base_manager`, filtrando por
   `scope.ids_for(...)`. Textos para el operador en español llano.
3. Si se puede corregir, escribir un `Fixer` (`fixes/base.py`): `plan` sin escribir,
   con `closure` (toda fila que el escritor o sus signals pueden cambiar), `fields`
   registrados, bloqueos en vez de excepciones; `apply` con el escritor del dominio;
   `revert` cuando el escritor deja auditoría.
4. Pruebas en `backend/content/tests/services/test_data_integrity_rules_*.py`: datos
   sucios (fabricados con un `QuerySet.update` crudo, como se cuelan en la vida real) y
   limpios (sin falsos positivos, incluidas las excepciones de negocio), un alcance,
   aplicar y deshacer.
5. Si cambia lo que el catálogo promete, subir `CATALOG_VERSION`.
6. Si la regla mira una relación hacia un ancla, citarla en `relation_inventory.py`.

## Catálogo 1.1.0

Suma 14 reglas de sólo reporte a las 37 de la 1.0.0, y CL4 pasa a su versión 2:

| Regla | Qué detecta |
|---|---|
| CL6 | Cliente sin actividad comercial que conserva registros que impiden su borrado o que quedarían sin cliente |
| PJ8 | Alianza, carpeta de comunicaciones, aviso o evidencia de entrega, o contexto de autoría apuntando al proyecto de otro cliente |
| PJ9 | Fila conservada que el índice de su borrado no lista |
| DC9, DC10 | Documento en una carpeta de otro cliente o de otro proyecto (la carpeta organiza y no es dueña: puede ser intencional) |
| DC11 | Documento activo sin carpeta (los borradores de cuenta de cobro se excluyen: se archivan al emitirse o anularse) |
| DC12 | Número público repetido entre cuentas de cobro |
| CM6 | Adjunto con un documento de otro cliente |
| AC9 | Ingreso con más de una cuenta de cobro sin anular |
| AC10 | Cuenta de cobro con otro proyecto o cliente que su ingreso (la que sólo no tiene el proyecto del ingreso es de PJ1) |
| AC11 | Reparto entre socios que viola `PartnerSplitMixin.clean()` |
| AC12 | Ingreso esperado pagado por encima de su total |
| AC13 | Movimiento del bolsillo que no cuadra con su ingreso o gasto |
| PR9 | Precio histórico de una propuesta sin las claves que leen `save()` y, con descuento, el cálculo del descuento |

**CL4 v2 y la guarda de borrado comparten una sola fuente.**
- `client_deletion.deletion_blockers()` recorre las relaciones que recorre el `Collector`
  de Django al borrar el usuario del cliente: las ocultas (`related_name='+'`) incluidas y
  siguiendo las cadenas CASCADE. Cada PROTECT o RESTRICT que encuentra es un bloqueo, y
  se suma `Project.client`.
- Esa misma fuente usan la guarda (`delete_orphan_client`), el filtro de huérfanos del
  panel y del MCP, `is_orphan`, los conteos por estado y CL4.
- Antes la guarda contaba 6 relaciones de más de 30. Un cliente con una carpeta de
  comunicaciones, una alianza o un proyecto conservado parecía borrable y el borrado
  terminaba en un 500. Además, ese 500 dejaba borrados el avatar y la portada, porque el
  perfil se borraba antes que el usuario.
- **Hoy:**
  - la guarda responde 400 `client_has_protected_references` con las relaciones y sus
    conteos;
  - el borrado es un solo `user.delete()`;
  - si aun así Django rechaza el borrado, la vista y el MCP responden 400 o `ToolError`.

## Inventario de relaciones

`relation_inventory.py` decide, para cada FK, O2O o M2M hacia un ancla (proyecto, cliente,
propuesta, documento, carpeta, hilo, ingreso u hosting), una de tres cosas:
- qué reglas lo miran (`covered`);
- por qué ninguna lo hace (`exempt`: autoría, evidencia inmutable, logs, hijos en
  cascada);
- qué falta (`gap`).

La autoría hacia el cliente se toma de `client_merge_policy.AUTHORSHIP_RELATIONS`. La
prueba `test_data_integrity_relation_inventory.py` falla en tres casos:
- ante una relación sin decisión, así que lo desconocido nunca pasa;
- ante una decisión de una relación que ya no existe;
- ante una regla citada que el catálogo no tiene.

Al agregar un modelo con FK a un ancla hay que decidirla ahí.

## Detección en producción sin MCP

`manage.py audit_data_integrity` corre el mismo catálogo:
- sin `--apply`, sin locks y sin filas de auditoría;
- imprime ids de regla, conteos y `modelo:id`, nunca etiquetas, mensajes ni evidencia;
- `--format json --output <archivo nuevo>` escribe un reporte 0600 y rechaza rutas del
  repositorio, `STATIC_ROOT`, `MEDIA_ROOT` y la media privada;
- `--coverage` agrega el resumen del inventario de relaciones.

Lo corre el operador en el VPS después del deploy; una sesión nunca.

## Fusiones

- **Clientes (CL1-CL3).** Cada relación hacia `auth.User` y `accounts.UserProfile`
  tiene una política en `client_merge_policy.py` (re-vincular, manejar colisión,
  especial, nunca reescribir o bloquear). Una prueba anti-deriva falla si aparece una
  relación nueva sin política: al agregar un modelo con FK a un cliente hay que
  clasificarla ahí.
- **Carpetas documentales (DC4).** Mueve documentos y subcarpetas de la duplicada a la
  que se conserva (fusionando subcarpetas homónimas) y archiva la vacía.
- **Carpetas de comunicaciones.** Sólo se renombran: el modelo no tiene archivo, así
  que una fusión terminaría en un borrado.
