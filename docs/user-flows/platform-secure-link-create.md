### FLOW: `platform-secure-link-create`

- **Módulo / rol:** Platform / cliente.
- **Ruta:** `/platform/projects/:id/secure-links`.
- **Display:** El cliente llega desde su proyecto, ve el límite sólo equipo y texto/credenciales, y la vista vacía o metadatos de sus enlaces.
- **Success:** Crear una vez limpia el contenido del formulario; la URL se muestra sólo en el modal y copiar exige un clic.
- **Error:** Campos requeridos bloquean el envío; entrada inválida o UUID con otros datos muestran un error seguro. Replay idéntico no vuelve a entregar URL.
- **Failure:** Catálogo/listado permiten reintentar. Una falla de creación conserva el borrador y su UUID sin mostrar la entrada en el error.
- **Cobertura:** validada en Nuxt local con frontera API aislada; `frontend/e2e/platform/platform-secure-links.spec.js` cubre display/success/error/failure. Las pruebas backend SQLite verifican autorización, cifrado e idempotencia reales.
