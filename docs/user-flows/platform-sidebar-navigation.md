### FLOW: `platform-sidebar-navigation`

- **Módulo:** platform
- **Roles:** platform-admin, platform-client
- **Prioridad:** P2
- **E2E:** `frontend/e2e/platform/platform-sidebar.spec.js`

La navegación conserva los destinos y opciones permitidos por rol, el estado
activo, el cierre del cajón móvil y las acciones de cuenta. Personaliza abre
el selector de apariencia; Configuración navega al perfil.

**PA-258:** las iniciales de escritorio, cajón y encabezado móvil usan blanco
sobre verde de marca con tokens independientes de la paleta personal, en claro
y oscuro. La separación icono/texto de Cuenta y Personaliza es coherente.
Modelo de datos conserva PRONTO y su condición pendiente.

| Resultado | Interacción |
|---|---|
| success | Navegar desde un enlace del menú y conservar el destino permitido. |
| display | Llegar al perfil desde Configuración y comprobar nombre, iniciales y el par de colores con una paleta personal clara. |
| error | No aplica al ajuste de presentación: la denegación por rol sigue en el flujo de destino. |
| failure | No aplica al ajuste: no se añade una petición de guardado o carga. |

La extensión del contrato se valida en CI sobre el SHA del PR. Las fotografías,
los tamaños CSS y las variantes móviles se cotejan también en el turno visual
acordado; la autoría de estos casos no acredita su ejecución manual.
