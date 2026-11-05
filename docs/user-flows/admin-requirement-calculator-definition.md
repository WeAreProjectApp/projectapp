### FLOW: `admin-requirement-calculator-definition`

- **Module:** commercial
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/requirement-calculator`
- **Description:** El administrador consulta la definición vigente, previsualiza y publica una nueva revisión con motivo. El servidor rechaza parámetros inválidos y revisiones obsoletas; una falla no confirma la publicación.
- **Steps:** Consultar tallas y señales → modificar un parámetro → escribir motivo → previsualizar → confirmar Guardar.
- **Branches:** Parámetros inválidos o If-Match obsoleto muestran calculator-error; un 5xx conserva la edición.
- **Coverage:** ❌ Missing — `display`, `success`, `error`, `failure`.
