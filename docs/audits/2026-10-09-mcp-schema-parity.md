# Auditoría de paridad MCP — 2026-10-09

Se compararon los nombres, esquemas de entrada y salida, descripción, título y anotaciones publicados por `tools/list` con `describe_capabilities`, además de las versiones de capacidades y `serverInfo` de `initialize` (protocolo `2025-11-25`). La medición ejecutó el registro local con `projectapp.settings_test`, sin base de datos ni contexto MCP, sobre el commit `e8da7b83`; el script, el snapshot y los logs de arranque quedaron en `/tmp/mcp-schema-parity/`.

## Antes

| Conector | tools/list | describe_capabilities | Nombres distintos | Esquemas distintos | serverInfo (initialize) | Versión en capacidades | Raíz sin `additionalProperties: false` | Con `data`/`query` | Combinadores en la raíz |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| accounting | 70 | — | — | — | 1.0.0 | — | 70 | 0 | 0 |
| accounting-billing | 46 | 46 | 0 | 0 | 1.0.0 | 2.0.0 | 32 | 21 | 0 |
| accounting-cards | 38 | 38 | 0 | 0 | 1.0.0 | 2.0.0 | 31 | 12 | 0 |
| accounting-ledger | 56 | 56 | 0 | 0 | 1.0.0 | 2.0.0 | 53 | 15 | 0 |
| additional-modules | 25 | 25 | 0 | 0 | 1.0.0 | 2.0.0 | 13 | 13 | 0 |
| blog | 7 | — | — | — | 1.0.0 | — | 7 | 0 | 0 |
| clients | 6 | — | — | — | 1.0.0 | — | 6 | 0 | 0 |
| commercial | 201 | 201 | 0 | 0 | 1.0.0 | 2.0.0 | 131 | 135 | 5 |
| communications | 50 | 50 | 0 | 0 | 1.0.0 | 2.0.0 | 12 | 12 | 2 |
| content | 60 | 60 | 0 | 0 | 1.0.0 | 2.0.0 | 38 | 24 | 0 |
| diagnostics | 13 | — | — | — | 1.0.0 | — | 13 | 0 | 0 |
| documents | 66 | 66 | 0 | 0 | 3.1.0 | 3.1.0 | 50 | 35 | 0 |
| linkedin-personal | 7 | — | — | — | 1.0.0 | — | 7 | 0 | 0 |
| operations | 4 | 4 | 0 | 0 | 1.0.0 | 2.0.0 | 1 | 1 | 0 |
| partnership-program | 26 | 26 | 0 | 0 | 1.0.0 | 2.0.0 | 14 | 14 | 0 |
| projects | 162 | 162 | 0 | 0 | 2.1.0 | 2.1.0 | 37 | 72 | 1 |
| proposals | 108 | 108 | 0 | 0 | 2.1.0 | 2.1.0 | 48 | 71 | 5 |
| tasks | 20 | 20 | 0 | 0 | 1.0.0 | 2.0.0 | 17 | 0 | 0 |

Los conteos corresponden a herramientas por conector, sin deduplicar herramientas compartidas entre conectores. «Nombres distintos» cuenta nombres presentes en una sola vía; «Esquemas distintos» cuenta herramientas con diferencias en el esquema de entrada o de salida. Las tres últimas columnas examinan únicamente la raíz de `inputSchema`; `data`/`query` cuenta cada herramienta una vez si publica cualquiera de esas propiedades, y los combinadores son `anyOf`, `oneOf` o `allOf`.

### Diferencias por herramienta

Ninguna: donde existe `describe_capabilities`, coincide con `tools/list`.

### Observaciones

- Los 18 conectores publican 965 herramientas en total. Los 13 con `describe_capabilities` reúnen 862 herramientas y coinciden en nombres, `inputSchema`/`input_schema`, `outputSchema`/`output_schema`, descripción, título y anotaciones.
- Cinco conectores carecen de `describe_capabilities`: `accounting`, `blog`, `clients`, `diagnostics` y `linkedin-personal`.
- Diez conectores publican `1.0.0` en `serverInfo` y `2.0.0` en capacidades. Los otros tres con capacidades coinciden: `documents` en `3.1.0`, y `projects` y `proposals` en `2.1.0`.
- 580 herramientas no tienen `additionalProperties: false` en la raíz. Esto ocurre en todas las herramientas de los cinco conectores sin `describe_capabilities` (103 en total).
- 425 herramientas publican `data` o `query` en la raíz, distribuidas entre 12 conectores; `commercial` concentra 135.
- 13 herramientas tienen combinadores en la raíz: cinco en `commercial`, cinco en `proposals`, dos en `communications` y una en `projects`.

Snapshot de regresión: `/tmp/mcp-schema-parity/before.json`, con las 965 herramientas completas y todas las claves ordenadas. No se registraron excepciones ni intentos de acceso a la base de datos. Los logs de arranque se redirigieron a `/tmp/mcp-schema-parity/django-logs/` para evitar crear archivos adicionales dentro del repositorio.

## Después (registro local, settings_test)

Informe generado el 2026-10-09 desde el worktree
`mcp-expected-incomes-parity`, con los diez commits posteriores a `e8da7b83`
(hasta `eacc5206`) y el incremento final de `ConnectorSpec.version`.
Comandos desde `backend/`, sin base de datos ni credenciales reales:

```bash
DJANGO_SETTINGS_MODULE=projectapp.settings_test ../.venv/bin/python manage.py mcp_schema_report --write-fingerprints
DJANGO_SETTINGS_MODULE=projectapp.settings_test ../.venv/bin/python manage.py mcp_schema_report
```

Ambos terminaron con código 0. Tabla emitida por el segundo comando:

| Conector | serverInfo (initialize) | serverInfo (discover) | capabilities | registro | tools/list | describe | nombres distintos | esquemas distintos | genéricas pendientes | abiertos documentados | huella |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| accounting | 1.1.0 | 1.1.0 | 1.1.0 | 1.1.0 | 78 | 78 | 0 | 0 | 0 | 0 | d025370a71f7 |
| accounting-billing | 2.1.0 | 2.1.0 | 2.1.0 | 2.1.0 | 46 | 46 | 0 | 0 | 20 | 0 | fcf670bdefdb |
| accounting-cards | 2.1.0 | 2.1.0 | 2.1.0 | 2.1.0 | 39 | 39 | 0 | 0 | 12 | 0 | 77023134b46f |
| accounting-ledger | 2.1.0 | 2.1.0 | 2.1.0 | 2.1.0 | 61 | 61 | 0 | 0 | 15 | 0 | 4c8edbf1841f |
| additional-modules | 2.1.0 | 2.1.0 | 2.1.0 | 2.1.0 | 25 | 25 | 0 | 0 | 13 | 0 | 35471953f663 |
| blog | 1.1.0 | 1.1.0 | 1.1.0 | 1.1.0 | 10 | 10 | 0 | 0 | 0 | 4 | d5e8cf0df022 |
| clients | 1.1.0 | 1.1.0 | 1.1.0 | 1.1.0 | 9 | 9 | 0 | 0 | 0 | 0 | 9348847c3539 |
| commercial | 2.1.0 | 2.1.0 | 2.1.0 | 2.1.0 | 201 | 201 | 0 | 0 | 101 | 18 | a8d81c600252 |
| communications | 2.1.0 | 2.1.0 | 2.1.0 | 2.1.0 | 50 | 50 | 0 | 0 | 12 | 0 | e49f760eb2a8 |
| content | 2.1.0 | 2.1.0 | 2.1.0 | 2.1.0 | 60 | 60 | 0 | 0 | 24 | 5 | 23238e8e953f |
| diagnostics | 1.1.0 | 1.1.0 | 1.1.0 | 1.1.0 | 16 | 16 | 0 | 0 | 0 | 4 | 20e35450e6b7 |
| documents | 3.2.0 | 3.2.0 | 3.2.0 | 3.2.0 | 66 | 66 | 0 | 0 | 50 | 0 | 524af63b9ea2 |
| linkedin-personal | 1.1.0 | 1.1.0 | 1.1.0 | 1.1.0 | 10 | 10 | 0 | 0 | 0 | 0 | ee941a9ec6f3 |
| operations | 2.1.0 | 2.1.0 | 2.1.0 | 2.1.0 | 4 | 4 | 0 | 0 | 1 | 0 | 68d4589f26ee |
| partnership-program | 2.1.0 | 2.1.0 | 2.1.0 | 2.1.0 | 26 | 26 | 0 | 0 | 14 | 0 | 5ee4f3e70c4f |
| projects | 2.2.0 | 2.2.0 | 2.2.0 | 2.2.0 | 162 | 162 | 0 | 0 | 37 | 0 | 6482297144a6 |
| proposals | 2.2.0 | 2.2.0 | 2.2.0 | 2.2.0 | 108 | 108 | 0 | 0 | 37 | 14 | 28e89762fd1a |
| tasks | 2.1.0 | 2.1.0 | 2.1.0 | 2.1.0 | 20 | 20 | 0 | 0 | 0 | 0 | fed0f09607ab |

El informe terminó con «Diferencias: Ninguna». Las huellas completas y sus
versiones quedan en
[connector_contracts.json](../../backend/content/mcp/connector_contracts.json).
La huella no incluye la versión: este último incremento conserva los SHA-256
del contrato ya implementado y actualiza la versión asociada.

### Backlogs por conector

Conteos de herramientas con deuda vigente en `schema_backlog.py`: raíz genérica;
raíz cerrada con argumentos sin descripción; raíz cerrada con infracciones
estructurales diferidas. Las dos últimas columnas pueden solaparse. Las
herramientas compartidas se cuentan en cada conector donde presentan esa deuda;
no se suman estas filas para obtener nombres únicos.

| Conector | Genéricas | Sin descripción de argumentos | Diferidas |
| --- | ---: | ---: | ---: |
| accounting | 0 | 47 | 0 |
| accounting-billing | 20 | 18 | 0 |
| accounting-cards | 12 | 21 | 0 |
| accounting-ledger | 15 | 23 | 0 |
| additional-modules | 13 | 9 | 0 |
| blog | 0 | 3 | 0 |
| clients | 0 | 3 | 0 |
| commercial | 101 | 78 | 3 |
| communications | 12 | 13 | 0 |
| content | 24 | 14 | 0 |
| diagnostics | 0 | 7 | 0 |
| documents | 50 | 10 | 0 |
| linkedin-personal | 0 | 0 | 0 |
| operations | 1 | 0 | 0 |
| partnership-program | 14 | 9 | 0 |
| projects | 37 | 119 | 4 |
| proposals | 37 | 58 | 3 |
| tasks | 0 | 9 | 0 |

Los tamaños globales sin duplicar nombres son **272 genéricas, 273 sin
descripción y 7 diferidas**. Las pruebas exigen correspondencia con las
excepciones vigentes y que esos backlogs sólo se reduzcan. «Abiertos
documentados» en el informe cuenta nodos de esquema con motivo de apertura,
no herramientas genéricas pendientes.

### Observaciones posteriores

- Hay paridad en los 18 conectores (13 canónicos y 5 de compatibilidad):
  991 herramientas sumadas entre catálogos, sin diferencias de nombres,
  esquemas públicos, descripción, título o anotaciones. Los handshakes
  coinciden en instrucciones e identidad.
- Las versiones de `initialize`, `server/discover`, capacidades y registro
  coinciden. La paridad HTTP de metadata moderna se verifica además con
  `test_mcp_registry_parity.py`; la medición local no pasa por la vista HTTP.
- Fuera de las excepciones genéricas y diferidas no quedan combinadores
  `anyOf`, `oneOf` o `allOf` en la raíz. La política estricta no equivale a
  un validador central de argumentos: en esta rama validan los
  handlers/serializers. `accepted_arguments_schema` permanece privado.
- El barrido de descripciones y contratos de Documentos/Proyectos continúa en
  `feat/09102026-mcp-folder-migration`, junto con su validador central opt-in.
  No se atribuyen a esta entrega las correcciones aún diferidas.
- La publicación plana de propuestas cubre las herramientas nativas actualizadas.
  El puente Panel compartido aún publica `data` en `update_proposal_settings` y
  `review_proposal_approval`, entre otras; su proyección plana está pendiente
  del trabajo paralelo. No se interpreta la paridad como retirada completa
  de todos los sobres publicados.
- Incidencia reportada el 2026-10-09: «Gestor de Contenido» (`content`) falló
  al conectar desde claude.ai con HTTP 405. La hipótesis es conector inactivo
  o token rotado; no se verificó la causa y el estado HTTP por sí solo no la
  confirma. Queda fuera de este cambio y no fue reproducida por la medición local.

### Verificación de cierre local

Las ejecuciones usan `pytest.ini` (`projectapp.settings_test`), sin
`--nomigrations`. Los casos HTTP prepararon la base SQLite de test con las
migraciones que crean las filas de `McpConnector`.

| Archivo | Lotes | Aprobadas | Fallidas |
| --- | --- | ---: | ---: |
| `content/tests/services/test_mcp_connector_registry.py` | Versiones: 18; huellas: 18; resto: 17 | 53 | 0 |
| `content/tests/views/test_mcp_registry_parity.py` | Contabilidad: 16; Documentos/Propuestas: 8; compatibilidad restante: 16; Operaciones/Alianzas/Módulos/Proyectos: 16; Comercial/Comunicaciones/Contenido/Tareas: 16 | 72 | 0 |
| **Total** | Cada lote terminó con un máximo de 18 casos | **125** | **0** |

Un intento del último lote se canceló durante la preparación porque `-k content`
seleccionaba todo el directorio `content`. Se corrigió a `-k '[content]'`,
combinado con los otros tres slugs, y los 16 casos seleccionados pasaron.

También se verificaron las 18 versiones del changelog contra `CONNECTORS`, el
inventario del runbook contra el registro, la tabla anterior contra la salida
del comando y los 32 enlaces locales de los siete documentos actualizados.
`git diff --check` no encontró errores de espacios. El entorno observado fue
Django 6.1.2; no se cambiaron dependencias. No se ejecutó la comprobación remota
post-deploy ni se usaron credenciales reales.

Procedimientos: [runbook de validación](../MCP_VALIDATION_RUNBOOK.md) y
[changelog de versiones y compatibilidad](../changelog/2026-10-09-mcp-connectors-schema-registry.md).
