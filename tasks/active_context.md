> **Integridad de datos — 2026-10-09:** motor de reglas de integridad con vista
> previa, registro y deshacer, fusiones de clientes y carpetas, siete herramientas
> en el conector `projects` y la skill `data-integrity`. Pendiente tras el
> deploy: copia de la skill en la carpeta Skills del Gestor Documental y una
> primera corrida de sólo lectura sobre un cliente real. Fuera de alcance: la
> creación de clientes provisionales al guardar propuestas sin correo, que
> alimenta la regla CL2.

# Contratación estatal en el catálogo — verificada (2026-10-09)

El catálogo comercial suma su módulo 26, *Contratación estatal*, en la nueva sexta categoría *Sector público*. El sistema es SECOP II, no «SECOB»: el módulo sigue procesos abiertos de contratación pública, con búsqueda, filtros, búsquedas guardadas, alertas por correo y seguimiento compartido. Perfiles confirmados: proveedores y contratistas y sus equipos comerciales y de licitaciones; constructoras, firmas de ingeniería civil e interventoría; consultoras de servicios profesionales; firmas de abogados que asesoran en contratación pública; y gremios que siguen las oportunidades de su sector. Finanzas y tesorería quedan fuera porque se siguen procesos abiertos, no contratos adjudicados. Se ofrece como módulo único, con alcance definido con el representante comercial en la propuesta. Su núcleo es replicable, pero necesita adaptación por cliente: roles y permisos, identidad de marca y remitente de los correos, horarios de actualización y envío, y quién ve las notas de quién. Entra como migración de datos `content.0286_seed_government_procurement_module`, sobre `0285_merge_platform_manager_retention`, sin cambio de esquema, serializer, MCP ni frontend. La siembra reserva posiciones contando también registros inactivos y respeta las ediciones del panel; una categoría retirada preexistente recibe el módulo retirado; el reverse elimina la categoría sólo si queda vacía. Los tests cubren el copy bilingüe aprobado, los perfiles y promesas delimitados, los requisitos de alcance, la idempotencia, el catálogo vacío y la reversión sin afectar otras fichas. Verificación de esta revisión en SQLite aislado: `test_migration_0286_government_procurement_module.py` más `test_migration_0247_audiovisual_module.py`, 18 pruebas verdes (11 nuevas y 7 de regresión); gate focal con `--junk-severity=error`, 100/100, cero errores y cero advertencias, «Status: ✓ PASSED». Verificación previa: `makemigrations --check --dry-run` con `projectapp.settings_test`, «No changes detected», y lectura del grafo sin conexión a base de datos con única hoja de `content`, `0286_seed_government_procurement_module`.

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

## 2026-10-09 — barrido de modales con campos demasiado anchos

El modal de liquidar un ingreso esperado y otros 30 modales del panel usan el
patrón compacto de ingresos y cuentas de cobro: ancho `form` (42 rem), campos
cortos en filas de dos o tres y un campo corto sin pareja a media fila. A
1440 × 900 liquidar baja de 1024 a 672 px. El patrón queda escrito en
`frontend/components/base/README.md` («Field widths») y
`docs/RESPONSIVE_STANDARD.md`. Las ayudas de campos dentro de filas pasan a la
ayuda de la fila; la de «Plazo de pago» nunca se mostraba. El formulario
compartido de enlaces seguros cambia también en la plataforma y en la página
pública. Sin backend ni migraciones. Verificación: unas 300 pruebas unitarias y
56 E2E con el medidor compartido `e2e/helpers/modal-layout.js` (contratos 20,
liquidar 8, contabilidad 18, prioritarios 10), más tokens de diseño, contrato
responsive y registro de flujos en verde.

> **Límite REST/MCP de recursos — 2026-10-07:** preservado el rol administrativo de Platform frente a los flags Django staff/superuser. Las lecturas, escrituras y descargas del servicio compartido filtran por propietario cuando no existe ese rol; MCP admite su principal técnico únicamente con contexto, actor y credencial coincidentes. Verificados doce rechazos de cliente staff, positivos de admin/cliente y principal MCP sin perfil simulado; gate focal 100 y schema sin drift.
