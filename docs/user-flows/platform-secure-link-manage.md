### FLOW: `platform-secure-link-manage`

- **Módulo / rol:** Platform / cliente.
- **Ruta:** `/platform/projects/:id/secure-links`.
- **Display:** Listado y filtros de metadatos; historial con evento, fecha, clase de actor y referencias permitidas.
- **Success:** Cambiar etiqueta, consultar URL explícita, revocar idempotentemente o reactivar un enlace elegible rotando URL y conservando eventos anteriores.
- **Error:** Una revisión obsoleta o estado inválido devuelve error; no hay lectura del secreto, borrado ni edición de contenido en Platform.
- **Failure:** Fallas de listado/historial/operaciones muestran un error recuperable; no se afirma una transición que falló.
- **Cobertura:** pendiente de validación de las pruebas dedicadas del dominio.
