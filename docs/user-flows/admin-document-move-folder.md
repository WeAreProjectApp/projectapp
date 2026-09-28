### FLOW: `admin-document-move-folder`

- **Módulo:** admin
- **Prioridad:** P1

- **Éxito:** mover un documento o el contrato vigente a una carpeta o a «Sin carpeta».
  El contrato conserva contenido y propietario; la respuesta compacta no vacía el editor.
- **Error:** una carpeta que se vuelve protegida rechaza el movimiento y mantiene el modal.
- **Fallo:** un error del servidor mantiene el modal y muestra el fallo.
- **Visualización:** al abrir «Mover a carpeta», mostrar destinos activos y «Sin carpeta».

Cobertura: `frontend/e2e/admin/admin-document-move-folder.spec.js`.
