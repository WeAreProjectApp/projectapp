### Platform: prompt e importación de JSON

Fuente: editor de importación en `DeliveryWorkspace.vue`.

El administrador copia el prompt, redacta fuera de la aplicación y pega un JSON con `schema_version: 1`. Previsualiza antes de aplicar. Cambiar el texto invalida esa previsualización. La aplicación importa únicamente borradores y rechaza campos de estados, firmas o aprobaciones.

`delivery-authoring.spec.js` prueba JSON inválido y la secuencia previsualizar → aplicar → consultar el borrador persistido. Las reglas de importación atómica y protección se verifican también por API y MCP.
