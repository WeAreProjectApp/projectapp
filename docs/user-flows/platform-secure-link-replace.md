### FLOW: `platform-secure-link-replace`

- **Módulo / rol:** Platform / cliente.
- **Ruta:** `/platform/projects/:id/secure-links`.
- **Display:** El detalle muestra las referencias anterior/sucesor; el modal de confirmación explica que corregir revoca primero y conserva auditoría.
- **Success:** Confirmar revoca, abre formulario sin secreto y crea un sucesor enlazado que entrega su nueva URL una vez.
- **Error:** Contenido faltante, sustitución duplicada/cruzada/no revocada o conflicto del UUID no cambia el contenido anterior.
- **Failure:** Si falla revocar no se abre el formulario. Si falla crear, el anterior permanece revocado y su historial conservado.
- **Cobertura:** validada en Nuxt local con frontera API aislada; `frontend/e2e/platform/platform-secure-links-replace.spec.js` cubre display/success/error/failure. API SQLite verifica unicidad del sucesor, conservación del cifrado anterior y rechazo de asociaciones entre proyectos.
