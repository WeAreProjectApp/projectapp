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
   sucios y limpios, un alcance, aplicar y deshacer.
5. Si cambia lo que el catálogo promete, subir `CATALOG_VERSION`.

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
