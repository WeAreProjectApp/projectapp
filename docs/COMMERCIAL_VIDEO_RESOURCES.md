# Recursos de video comerciales

## Uso desde el panel

- Células Scrum → Programa → Recursos de video.
- Programa de Alianza → Configuración → Recursos.
- Módulos adicionales → Recursos.
- Propuestas → Configuraciones: video general.
- Editar propuesta → Recursos: video personalizado.

Elegir un MP4 H.264 (audio AAC opcional, hasta 4K/250 MiB), pulsar **Cargar video** o **Sustituir video** y esperar la validación. El archivo anterior permanece vigente hasta que el nuevo se valida. La portada se obtiene del video automáticamente. **Quitar video** deja el recurso vacío; en generales, **Restaurar predeterminado** recupera el incluido con la aplicación.

Los generales se administran por idioma ES/EN y conservan sus interruptores. La bienvenida general de propuestas mantiene las condiciones existentes: propuesta en español, detalle técnico, contrato y ambos controles activos; almacenar un recurso EN no modifica esa regla. Hay un personalizado por propuesta: aparece después de la bienvenida dentro de Vista Ejecutiva y Propuesta Completa, independiente del video general. Sin personalizado no existe esa sección. No entra a PDF, contrato ni técnico y no se copia al duplicar una propuesta.

## Carga desde un entorno externo por MCP

Conectar con credencial Bearer a `/api/mcp/partnership-program/`, `/api/mcp/additional-modules/` o `/api/mcp/proposals/`. Los dos conectores nuevos aparecen inactivos tras la migración; el administrador los activa y crea credenciales desde el gestor MCP habitual.

1. Consultar el video para obtener su `revision` (cero si nunca se administró).
2. `begin_upload({filename, content_type: "video/mp4", size, sha256})` reserva la carga durante una hora y devuelve `asset_id`, `upload_url` y método `PUT`.
3. Enviar **los bytes del archivo** a `upload_url` con `Content-Type: video/mp4`. El cliente debe transmitir desde disco, por ejemplo `curl --request PUT --header 'Content-Type: video/mp4' --upload-file /ruta/video.mp4 "$UPLOAD_URL"`. La URL temporal es una credencial: no se publica ni se incorpora a documentación. Si el cliente sólo ejecuta herramientas MCP, usar `upload_asset_chunk` con bloques de hasta 1 MiB codificados en base64, índice consecutivo y SHA-256 por bloque.
4. `complete_upload({asset_id})` valida tamaño, huella, contenedor y codec.
5. Asignar con la herramienta correspondiente, `asset_id` y la revisión consultada. Sirve **tanto para cargar el primer video como para sustituir el existente**.

| Destino | Consultar | Asignar/cargar/sustituir | Identificador adicional |
|---|---|---|---|
| Alianza | `get_partnership_program_video` | `set_partnership_program_video` | `language`: es/en |
| Módulos adicionales | `get_additional_modules_video` | `set_additional_modules_video` | `language`: es/en |
| Propuestas general | `get_proposal_generic_video` | `set_proposal_generic_video` | `language`: es/en |
| Propuesta personalizada | `get_proposal_personalized_video` | `set_proposal_personalized_video` | `proposal_id` interno |

Ejemplo de argumentos del paso final:

```json
{"proposal_id": 123, "asset_id": "UUID_DEVUELTO_POR_LA_CARGA", "revision": 0}
```

También hay `remove_*_video` (requiere la confirmación MCP habitual), `restore_default_*_video` para generales y `set_*_video_visibility`. No se aceptan rutas locales del cliente ni enlaces de terceros como sustituto de transferir el archivo. Las credenciales restringidas necesitan permitir consulta, begin/chunk/complete/abort y la operación de asignación del destino.

## Contrato y compatibilidad

`GET/POST /api/video-resources/admin/modules/<module>/<language>/` y `/api/video-resources/admin/proposals/<id>/` usan sesión staff y CSRF. POST multipart lleva `action`, `revision` y `file` para upload; remove/restore-default admiten JSON. Los módulos internos son `financing`, `additional-modules`, `proposal` y `building-on-demand`. Células agrega `show_building_on_demand_video` mediante content.0298. Su video predeterminado sólo existe en español; los recursos EN cargados se muestran únicamente en EN.

Las APIs públicas añaden `explainer_video: {mode, video}` y, para propuestas, `personalized_video`. El descriptor de archivo cargado incluye `source: "uploaded"` y usa `src`, `poster`, `durationSeconds`, `width`, `height` y `language`. `default` conserva el video empaquetado del idioma; `none` impide que reaparezca; `uploaded` usa el recurso del servidor. Cada cambio incrementa la revisión y la URL; una revisión vieja devuelve conflicto, sin reemplazar datos.

Los nuevos MCPs reutilizan las operaciones del panel: acuerdos/políticas versionadas en Alianza y categorías/módulos/selecciones/PDF en Módulos adicionales. Retirar, revocar o archivar conserva el historial. Las credenciales comerciales anteriores conservan los 247 nombres de su catálogo `pre_split`; las credenciales nuevas usan Comercial, Nuestra oferta y Programas según la propiedad de cada operación. Los textos fijos de presentación de Alianza no se convierten en CMS. El contrato de datos de desarrollo clasifica estos videos como recursos configurables: no fabrica archivos ni sobrescribe los generales existentes; los tests generan MP4 pequeños y válidos en almacenamiento temporal.

Los archivos permanentes y los temporales MCP de video viven en almacenamiento privado. Las cargas no usan `request.body` ni el adaptador binario que copia todo a RAM. El video personalizado se entrega sólo mientras su propuesta esté activa y vigente (staff puede previsualizarla); las URLs son opacas y deben compartirse sólo con el destinatario. La eliminación de recursos limpia sus archivos después del commit.

## Despliegue y verificación

El deploy aplica la migración `0270_commercial_video_resources`, instala FFmpeg/ffprobe y adapta `scripts/nginx/projectapp.conf` a la raíz real del servidor. La ubicación interna `/_commercial_videos/` debe apuntar a `PRIVATE_MEDIA_ROOT`; recién entonces activar `VIDEO_USE_X_ACCEL_REDIRECT=True`. La ruta de carga acepta 260 MiB para permitir multipart, sin elevar el resto de la API. Mantener el timeout del worker por encima del presupuesto de validación (dos subprocesos de hasta 30 s más escritura); referencia: 120 s. Respaldar también `PRIVATE_MEDIA_ROOT`.

Las sustituciones se reflejan en las APIs inmediatamente y se incorporan al rebuild de prerender existente. El servidor ofrece rangos HTTP para avanzar en el reproductor; sin Nginx interno, Django usa lectura acotada desde disco.

Pruebas focales: `test_video_resources.py` carga/reemplaza mediante los tres MCPs y el panel; `test_video_large_transport.py` transfiere por HTTP real un MP4 de 250 MiB con un átomo ISO BMFF de relleno válido. Pruebas de seguridad, contratos, componentes y navegador completan permisos, errores, estados vacíos y recuperación.

## Células Scrum

El MCP Programas publica `get_building_on_demand_video`, `set_building_on_demand_video`, `remove_building_on_demand_video`, `restore_default_building_on_demand_video` y `set_building_on_demand_video_visibility`, con los mismos uploads y revisiones. El adaptador building-on-demand conserva la identidad anterior durante la compatibilidad. Video y visibilidad no publican revisiones del programa ni alteran el contrato; quitar no reactiva el predeterminado y restaurar no cambia el interruptor.

## Tutoriales de la plataforma del cliente (2026-10-24)

Ayuda en el menú lateral y móvil abre un modal con las piezas disponibles.
El general dura 90 segundos; Appi y reporte por voz, 72 segundos cada uno.
Son demostraciones con datos ficticios, narración colombiana y subtítulos
integrados. La interfaz inglesa los identifica como contenido en español.
Abrir el modal no reproduce el archivo: el cliente debe pulsar reproducir.
Cambiar de pieza, cerrar, navegar u ocultar la pestaña detiene la reproducción.

Los controles global y por cliente pertenecen a Ayuda, compartidos con el
recorrido: ambos deben estar encendidos. No activan las funciones de IA.
`GET /api/platform/help/videos/` requiere JWT de sesión, perfil de cliente
activo y onboarding completo; conserva el general ante indisponibilidad de IA
y filtra los clips por `chatbot.available` y `voice_reporting.available`.
No realiza consultas a proveedores. El contrato devuelve `topic`, `module`,
`language` y `resource: {mode, video}`; los predeterminados se resuelven desde
el manifiesto de assets del frontend, con sus URLs versionadas.

El panel `/panel/platform/help` administra las tres piezas. Reutiliza
`/api/video-resources/admin/modules/<module>/es/` con sesión staff y CSRF.
Los módulos son `platform-overview`, `platform-chatbot` y
`platform-voice-reporting`; esta primera edición admite exclusivamente ES.
Retirar conserva `none` hasta una restauración explícita. Las sustituciones
requieren revisión vigente y mantienen el recurso anterior si el MP4 falla
validación. Un recurso cargado debe incluir los subtítulos visibles.

El MCP **Proyectos** expone `get_platform_help_video`,
`set_platform_help_video`, `remove_platform_help_video` y
`restore_default_platform_help_video`, con `topic` (`general`, `chatbot`,
`voice-reporting`), `language: es` y `revision` para escritura. Set consume
un `asset_id` MP4 completado; remove usa la confirmación habitual. Se reutilizan
los mismos servicios, validación, auditoría y permisos del panel. Los
interruptores se consultan y actualizan con las herramientas compartidas
`get/update_platform_help_settings`, `list_platform_help_clients` y
`get/update_platform_help_client`. Cambiar recursos no cambia esos controles.

El equipo ProjectApp revisa las piezas al modificar un flujo y regenera solo
las afectadas. Fuentes, guiones, tiempos y procedimiento están versionados
en `explainers/brag-v2/platform-overview/README.md`.
