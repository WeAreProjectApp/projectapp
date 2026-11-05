### FLOW: `admin-project-requirement-calculator-draft`

- **Module:** projects
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/projects → /panel/requirement-calculator?project=<id>`
- **Description:** Desde Acciones del proyecto, el administrador crea un único borrador desde una revisión general. El resumen carga sólo metadatos y la versión seleccionada carga sus parámetros e historial por separado. Sólo se ajustan parámetros existentes; un segundo borrador, un cambio estructural o una versión obsoleta se rechazan.
- **Steps:** Abrir Acciones → Calculadora de requerimientos → crear borrador con motivo → elegir versión → modificar parámetro → guardar → verificar historial.
- **Branches:** No se permite otro borrador ni modificar textos o estructura. Conflictos y fallos se muestran sin asignar el documento.
- **Coverage:** ❌ Missing — `display`, `success`, `error`, `failure`.
