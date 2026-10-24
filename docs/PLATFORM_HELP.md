# Ayuda y recorridos de la plataforma

La plataforma ofrece una guía general y una guía del primer proyecto por cada
usuario. Ambas se pueden saltar y repetir desde **Ayuda**, en el menú lateral
y móvil. El recorrido de voz espera a que la persona abra un formulario que
realmente tenga disponible esa función. Las tarjetas no graban, envían,
generan contenido ni cambian el alcance del proyecto.

## Disponibilidad y estados

`PlatformHelpSettings` guarda los interruptores globales de recorridos y video.
`ClientPlatformHelpSettings` conserva las preferencias del cliente por `user`,
sin agregar campos a la configuración de IA. Los valores iniciales son `true`;
la disponibilidad combina global AND cliente. Un recurso de video o una función
de IA puede seguir sin estar disponible aunque su interruptor esté encendido.

`PlatformTourProgress` es único por usuario y recorrido, independiente del
proyecto que se use como contexto. Completar o saltar es terminal para el inicio
automático; repetir manualmente no borra ese acuse. Las pausas por navegación o
por abrir Appi/video permiten retomar manualmente desde Ayuda. Un acuse que
falla al guardar queda en una cola local separada por usuario hasta sincronizar.

Un fallo de configuración impide el inicio automático. Se revalida al recuperar
foco, cambiar ruta, avanzar y cada 30 segundos durante un recorrido activo.
El menú móvil y el foco se restauran al salir. Driver.js se importa sólo al
iniciar una guía; se respeta la preferencia de movimiento reducido.

El destino actual se registra al seleccionarlo, antes de la animación: cerrar
una tarjeta inmediatamente conserva ese paso. El inicio automático sólo marca
el contexto después de abrir la guía. Si la navegación monta un destino más
tarde, un cambio en los destinos visibles permite reintentarlo; las solicitudes
concurrentes se agrupan y se descartan al desmontar el anfitrión.

## Administración

En **Panel → Plataforma → Ayuda de la plataforma** se gestionan interruptores,
clientes, borradores ES/EN, orden de pasos, publicación e historial. Un borrador
no llega al cliente hasta publicarse como revisión inmutable. Publicar otro
texto del mismo recorrido conserva los vistos; una novedad nueva necesita un
identificador diferente. Desactivar conserva el historial.

Los destinos del editor pertenecen al registro cerrado
`accounts/services/platform_help_targets.py`, compartido con Appi. Sus rutas,
contextos y requisitos de capacidades no son editables. No se admiten scripts,
selectores ni URLs libres. Las tarjetas presentan texto escapado.

## Interfaces

| Interfaz | Acceso y propósito |
|---|---|
| `GET /api/platform/help/` | JWT completo de cliente activo; configuración efectiva, catálogo publicado y progreso propio. `project_id` exige un proyecto propio. |
| `POST /api/platform/help/tours/{id}/progress/` | JWT; estado, revisión, último destino y proyecto cuando corresponda. Reintentos idempotentes. |
| `/api/platform/help/settings/` | Sesión/CSRF de administrador; lectura y PATCH con `expected_version`. |
| `/api/platform/help/clients/` | Sesión de administrador; búsqueda y paginación de controles por cliente. |
| `/api/platform/help/clients/{user_id}/` | Sesión/CSRF de administrador; lectura y PATCH versionado. |
| `/api/platform/help/admin/tours/` | Listar y crear borradores; detalle por ID para consultar o editar. |
| `.../{id}/preview/`, `publish/`, `archive/`, `revisions/` | Vista previa sin alterar vistos, publicación, archivo e historial. |
| `/api/platform/help/admin/progress/` | Consulta paginada por administrador; no marca vistos ajenos. |

El MCP existente **Proyectos** publica estas mismas operaciones: configuración
global y por cliente (`get/update_platform_help_*`, `list_platform_help_clients`),
catálogo (`list_platform_guided_tours`, `get_platform_guided_tour`,
`create_platform_guided_tour`, `update_platform_guided_tour`,
`preview_platform_guided_tour`, `publish_platform_guided_tour`,
`archive_platform_guided_tour` y `list_platform_guided_tour_revisions`) y progreso (`list_platform_tour_progress`).
Panel y MCP comparten validación, control de versión y auditoría. Los cambios de
disponibilidad y publicaciones usan la confirmación sensible del MCP.
La vista previa sólo presenta las tarjetas del borrador guardado; publicar es
un comando versionado independiente. Una prueba MCP verifica que esa lectura
no escriba en ninguna tabla, incluso si una escritura terminara revertida.

## Integración con las otras funciones

`usePlatformHelpSurface` coordina `chat`, `tour` y `video` dentro de la misma app.
Cada productor registra su cierre, solicita su superficie al abrir y la libera
al cerrar. Abrir otra pausa la anterior sin reanudarla automáticamente.
`isTourActive` permite pausar las sugerencias proactivas de Appi.

El layout provee `platformHelp`; el productor de video registra su acción con
`registerVideo(opener, available)`. Ayuda ofrece video sólo si existe un recurso
efectivo, sin autoplay. El tour puede invitar a verlo después de finalizar.
El módulo de video conserva el manifiesto Vite, recursos, modal y API propios.

Los pasos Appi/voz exigen `capabilities.*.available` y un control visible con
`data-tour="platform-appi-launcher"` o `data-tour="voice-report"`. Ayuda no consume
cuota de IA ni registra reservas en su ledger. Los clientes HTTP de plataforma
mantienen JWT; la administración usa el cliente de sesión/CSRF del panel.

## Verificación

Las pruebas de backend usan exclusivamente `projectapp.settings_test` y SQLite
aislado desde el worktree. Las pruebas del navegador simulan las APIs, sin
modificar datos desplegados. Los flujos y el contrato responsive se registran
en sus fuentes declarativas; el cierre exige PR abierto y CI verde.
Las migraciones se aplican mediante el deploy, nunca desde la sesión de trabajo.
