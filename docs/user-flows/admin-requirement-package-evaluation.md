### FLOW: `admin-requirement-package-evaluation`

- **Módulo:** projects
- **Rol:** admin
- **Prioridad:** P1
- **Ruta:** `/panel/requirement-packages?project=:id`
- **Interacción:** Publicar una propuesta manual de talla y agenda sin consumir; responder objeciones conservando revisiones.
- **Éxito:** La operación conserva su resultado y actualiza la vista correspondiente.
- **Error:** Entradas inválidas, permisos o versión obsoleta no dejan efectos parciales.
- **Fallo:** El servicio muestra un error recuperable y conserva el trabajo pendiente.
- **Presentación:** El recorrido comienza en la navegación correspondiente y usa datos ficticios identificables.
- **Cobertura:** Pendiente de ejecución CI; escenarios en `frontend/e2e/admin/admin-requirement-packages.spec.js`. El registro no acredita recorrido Chrome.
