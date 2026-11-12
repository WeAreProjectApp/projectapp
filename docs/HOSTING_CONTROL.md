# Control visual de hosting · PA-264

## Operación

Panel → Proyectos → Control de hosting, disponible en el encabezado y las
acciones de cada proyecto. El selector busca producciones por nombre/dominio,
incluidas las aún sin vínculo comercial. Se muestra destino y servidor antes
de cambiar. Requiere administrador activo del Panel; usa sesión/CSRF.

Los switches Pantalla de suspensión y Banner de aviso representan un único
modo (`normal`, `suspended`, `banner`). Activar uno sustituye el anterior;
apagar el activo vuelve a normal. Los títulos/textos se guardan por separado,
sin tocar el otro mensaje ni cambiar el modo. Cada operación compara versión
y conserva quién cambió qué y cuándo. Un conflicto conserva el borrador.

La pantalla sustituye documentos y vistas autenticadas. El banner conserva
contenido y funcionamiento. APIs, webhooks y rutas operativas continúan; el
Panel central y su autenticación/MCP siguen accesibles. No cambia estados
comerciales, cobros, permisos de negocio, procesos ni datos.

## Configurado y recibido

Una versión guardada queda pendiente. El receptor del toolkit consulta cada
10 s, valida destino, entorno, orígenes, revisión y huella; escribe localmente
por reemplazo atómico. Cada origen debe servir el estado y un documento con
la misma versión/huella y sus recursos de presentación antes de confirmar.
El navegador consulta el adaptador cada 10 s y al recuperar visibilidad.
Objetivo: aplicación en hasta 30 s para una producción conectada.

La UI distingue sin integrar, pendiente, confirmado, desconectado (sin recibo
reciente durante 45 s), error y servicios suspendidos/retirados. Recibos viejos
o ajenos se rechazan. Un cambio de mensaje invalida la confirmación anterior.
Descargar o guardar el archivo no equivale a aplicación.

La copia local conserva el último estado válido, también tras reiniciar el
receptor. Ante desconexión no se retira una suspensión automáticamente.
Normal retira el aviso al recibirse; la pantalla independiente puede
recuperarse sin iniciar la aplicación. Estado/documentos usan `no-store`.

## API y MCP

- `GET /api/hosting-controls/`: búsqueda, proyecto vinculado y página.
- `GET /api/hosting-controls/<id>/`: mensajes, modo y recibos por destino.
- `PATCH .../<id>/mode/`: `expected_version`, `mode`.
- `PATCH .../<id>/message/`: `expected_version`, `message_mode`, `title`, `text`.
- `GET .../<id>/events/`: historial paginado.
- `GET /api/hosting-runtime/configs/`: sólo destinos de la credencial receptora.
- `POST /api/hosting-runtime/receipts/`: destino, versión, huella y resultado.

MCP Proyectos 5.2.0 publica `list_hosting_controls`, `get_hosting_control`,
`set_hosting_control_mode`, `update_hosting_control_message` y
`list_hosting_control_events`. Las escrituras requieren vista previa y
`confirm_action`, y comparten servicio, permisos y versión con Panel. Las credenciales deben usar el catálogo canónico Proyectos y permitir estas
operaciones; los catálogos heredados y sus permisos no se amplían automáticamente. Secretos
del receptor nunca se consultan ni editan por MCP. PA-263 aporta patrones de
gestión; su disponibilidad por cliente no activa este control por producción.

## Instalación y cobertura

Migración aditiva `hosting_control.0001`; sólo la aplica el deploy autorizado.
`hosting-production-inventory.json` es una instantánea no secreta generada desde
el toolkit. Regenerar al cambiar el roster y revisarla antes de importar con
`configure_hosting_control --manifest <archivo>`. El importador conserva modos
y mensajes; no acepta mover una identidad integrada de origen silenciosamente.
Recursos de monitoreo existentes se reutilizan por su clave estable.

Emitir/revocar credenciales sólo con el comando de configuración. `--issue`
requiere `--targets` y `--token-file` nuevo: crea 0600 y no imprime el token.
No ejecutar desde el worktree conectado a la base de producción. Receptor,
unit y guía de alta: `vps-ops-toolkit/docs/hosting-control.md`.

| Producción | Adaptador preparado | Instalado/comprobado por esta sesión |
|---|---|---|
| ProjectApp | Django y documento Nuxt; Panel excluido | No; pausa vigente |
| Fernando Aragón | Django y React SPA; nginx pasa documentos a Django | No; pausa vigente |
| Gym | Django y Vue SPA; estado excluido de caché PWA | No; pausa vigente |
| Mimittos | Proxy/documento Next Node y estado local compartido | No; pausa vigente |
| Tenndalux | Django y documento Next exportado | No; pausa vigente |
| Kore, Crushme | Inventariados como servicios suspendidos | No; no se reactivan |

Cada alta futura requiere adaptador, inscripción y comprobación de consumo.
El inventario no acredita integración. Los retirados quedan identificados y no
reciben configuración. Ningún archivo, flag, test aislado o PR acredita por sí
solo aplicación en una producción externa.

## Guion de validación pendiente

CI cubre tres estados/transiciones, independencia de textos, versiones,
permisos, transporte limitado, rechazo de recibos, consumo de documentos,
escritura atómica, reinicio/desconexión y recuperación del Panel. Los specs
de navegador usan HTTP ficticio para probar el adaptador y la gestión, con
los cinco perfiles responsivos. No contactan ni modifican producción.

QA manual y servicios siguen pausados. Al levantarlos, DevQA/QA deben fijar
SHA y entorno autorizado con datos ficticios: dos proyectos, ambos mensajes
por Panel/MCP, navegación autenticada/directa, recarga, pestañas abiertas,
móvil/escritorio, transición y retirada, caché y todos los dominios. Registrar
por separado CI, instalación y comprobación real; PA-264 no se declara cerrado
sin la evidencia de recepción de cada integración.
