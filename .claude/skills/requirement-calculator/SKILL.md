---
name: requirement-calculator
description: "Clasifica un requerimiento por talla XS–XL o Proyecto usando la calculadora versionada de ProjectApp, sus parámetros vigentes y las condiciones particulares aprobadas del proyecto. Se utiliza desde el chat mediante MCP; horas, costos y valores unitarios permanecen internos."
---

# Calculadora de requerimientos

La definición y los parámetros se administran en **Comercial → Calculadora de requerimientos**. El documento general es su representación sincronizada. La IA del chat interpreta el requerimiento; ProjectApp conserva configuración, documentos y registros, sin ejecutar un modelo de IA.

## Obtener la definición aplicable

1. Consulta `get_requirement_calculator` en MCP Comercial con el requerimiento y, cuando exista, `project_id`. Usa el esquema publicado por el conector.
2. El contexto devuelve la revisión exacta, su huella, parámetros e instrucciones. Para un proyecto utiliza la versión aprobada. Si no tiene una, comunica el aviso de uso de la general. Usa `project_version_id` sólo si se pidió revisar expresamente ese borrador; nunca lo presentes como aprobado.
3. Sin acceso MCP, el command de lectura `read_requirement_calculator --project-id <id>` ofrece el mismo contexto desde el entorno de ProjectApp explícitamente configurado. No uses una SQLite vacía ni leas el `.env` en el transcript. Si no puedes obtener la fuente, informa la falta de acceso; las tablas históricas de `references/` no sustituyen la definición vigente.

## Clasificar en el chat

- Separa resultados independientes y confirma qué existe y qué se construye. Pregunta por las ambigüedades que cambian la talla; declara supuestos pendientes.
- Aplica las señales y familias de la definición obtenida. Cita identificadores válidos y explica la talla. Los puntos son referencias de magnitud; no se suman como si fueran una fórmula de clasificación.
- XL es una talla válida para una capacidad delimitada. Usa **Proyecto** cuando se cumpla la frontera explícita: no se descuenta como requerimiento del paquete.
- El resultado compartible contiene requerimiento, talla, definición breve, explicación y supuestos. Horas, costo, precio unitario y recargos permanecen internos. La programación se acuerda aparte.
- No alteres parámetros para conseguir una talla deseada ni clasifiques con reglas recordadas de otra versión.

## Registro y calibración

Registra el resultado mediante `record_requirement_estimate` con un `request_id` UUID estable, revisión, huella, proyecto/versión particular cuando apliquen, señales y explicación. Un reintento conserva el mismo identificador y payload. `expected_size` se usa sólo si existe una revisión humana de referencia; no inventes una respuesta esperada.

Cuando el operador aporte un cierre real, usa `record_requirement_actual` con evidencia y esfuerzo confirmado. Las fechas de un PR no equivalen a horas trabajadas. Corregir requiere `supersedes_id` del último cierre y conserva el anterior. `get_requirement_calibration` informa cohortes paginadas y posibles revisiones sin aplicar cambios. Los listados de estimaciones son resúmenes: `get_requirement_estimate` recupera el texto completo y `list_requirement_actuals` pagina toda la evidencia de cierres y correcciones.

## Administración explícitamente solicitada

- General: consulta parámetros, previsualiza y publica con `if_match` y motivo. La publicación crea otra revisión y actualiza el documento y los valores compartidos con Paquetes.
- Proyecto: usa MCP Proyectos para consultar, crear borrador y modificar sus parámetros existentes. Textos, estructura y fórmulas conservan la revisión general de origen.
- Aprobar es una acción explícita del equipo con confirmación MCP: congela documento/PDF y asigna la versión al proyecto. Para cambiar una aprobada crea otro borrador. El envío o publicación al cliente es una operación independiente.
- Nunca edites el cuerpo desde MCP Documentos ni sobrescribas una versión aprobada.

Los documentos de `validation/` conservan casos históricos para revisión de consistencia; sus precios y horas no son una calibración económica vigente. La calibración nueva requiere cierres reales registrados.
