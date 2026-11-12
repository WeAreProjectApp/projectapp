### FLOW: `platform-guided-tour-general`

- **Módulo:** platform
- **Prioridad:** P1
- **Rol:** platform-client
- **E2E:** `frontend/e2e/platform/platform-guided-tour.spec.js`

Orientación general por usuario, descarte persistente, finalización y repetición desde Ayuda. Se omiten destinos sin disponibilidad o sin control visible. Al cambiar de tamaño conserva el paso y selecciona el enlace visible de escritorio o del cajón móvil. El anclaje se conserva en mediciones posteriores sobre el destino visible, tras asentarse la distribución y la tarjeta. La tarjeta queda junto al control al concluir la transición del resaltado.

| Resultado | Interacción y evidencia |
|---|---|
| display | Entrar por Documentos y navegar a Proyectos, abrir la guía desde Ayuda y avanzar hasta Proyectos/Documentos. Redimensionar escritorio→móvil→tableta; comprobar texto, control visible, hueco SVG y tarjeta junto al destino. |
| success | Avanzar, saltar, repetir o guardar desde sus controles; comprobar el resultado visible y persistido. |
| error | Usar permisos o valores no admitidos; no se publica contenido ni se sobrescribe el estado vigente. |
| failure | Fallar una petición de carga o guardado; mostrar el error o conservar el acuse pendiente para reintento. |
