### FLOW: `admin-requirement-package-examples`

- **Módulo:** projects
- **Rol:** admin
- **Prioridad:** P2
- **Ruta:** `/panel/requirement-packages`
- **Interacción:** Publicar ejemplos con motivo, consultar historial y restaurar el genérico al vaciar una talla propia.
- **Éxito:** La operación conserva su resultado y actualiza la vista correspondiente.
- **Error:** Entradas inválidas, permisos o versión obsoleta no dejan efectos parciales.
- **Fallo:** El servicio muestra un error recuperable y conserva el trabajo pendiente.
- **Presentación:** El recorrido comienza en la navegación correspondiente y usa datos ficticios identificables.
- **Cobertura:** Pendiente de ejecución CI; escenarios en `frontend/e2e/admin/admin-requirement-packages.spec.js`. El registro no acredita recorrido Chrome.
