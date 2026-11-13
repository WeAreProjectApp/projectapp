### FLOW: `platform-requirement-packages-request`

- **Módulo:** platform
- **Rol:** platform-client
- **Prioridad:** P1
- **Ruta:** `/platform/projects/:id/packages`
- **Interacción:** Describir un resultado nuevo, enviarlo sin entrega previa obligatoria y consultar su estado.
- **Éxito:** La operación conserva su resultado y actualiza la vista correspondiente.
- **Error:** Entradas inválidas, permisos o versión obsoleta no dejan efectos parciales.
- **Fallo:** El servicio muestra un error recuperable y conserva el trabajo pendiente.
- **Presentación:** El recorrido comienza en la navegación correspondiente y usa datos ficticios identificables.
- **Cobertura:** Pendiente de ejecución CI; escenarios en `frontend/e2e/platform/platform-requirement-packages.spec.js`. El registro no acredita recorrido Chrome.
