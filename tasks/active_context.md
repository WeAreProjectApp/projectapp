
> **Enlaces seguros y listas exploratorias — 2026-10-09:** las acciones de fila
> pasan a un kebab inicial sin encabezado que abre un modal
> (`BaseExploratoryList` con `row-actions-layout="menu-start"` +
> `BaseRowActionsModal`, que recibe las mismas entradas que `BaseActionMenu`) en
> Enlaces seguros, Blog, Portfolio, Paquetes de horas, LinkedIn, Linktrees y
> Tarjetas QR. Enlaces seguros activa «Actualizar datos», deja una sola opción de
> editar (contenido, también desde la fila) y renombra el título en línea con un
> PATCH sólo de `title`; la página pública ya no ofrece el atajo `mailto:`.
> Sin cambios de backend ni migraciones. Fuera de alcance: el resto de tablas
> `inline-end` (PA-102) y filas navegables con URL propia (PA-62).

> **Límite REST/MCP de recursos — 2026-10-07:** preservado el rol administrativo de Platform frente a los flags Django staff/superuser. Las lecturas, escrituras y descargas del servicio compartido filtran por propietario cuando no existe ese rol; MCP admite su principal técnico únicamente con contexto, actor y credencial coincidentes. Verificados doce rechazos de cliente staff, positivos de admin/cliente y principal MCP sin perfil simulado; gate focal 100 y schema sin drift.
