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
