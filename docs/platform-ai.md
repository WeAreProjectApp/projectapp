# IA de Plataforma y reportes por voz

## Operación

En **Plataforma → Configuración de IA** (`/panel/platform/ai`) el equipo administra
activación global y por cliente, proveedores, plantillas ES/EN y consumo. Las dos
funciones empiezan apagadas; un apagado global prevalece. El chatbot tiene su
propio frente de implementación y consume los contratos compartidos descritos aquí.

El redactor se elige por función: `claude-haiku-5-5` inicialmente, o `gpt-6-luna`.
No se cambia de proveedor automáticamente ante errores. La transcripción usa
`gpt-transcribe`, así que necesita clave de OpenAI aunque Haiku redacte el reporte.
Jev se configura en el mismo almacén; su uso corresponde al chatbot.

Una nota admite WebM, MP4 o WAV, hasta 10 MB y 60 segundos. El navegador recomienda
30 segundos pero acepta grabaciones más breves. FFmpeg decodifica con límite de
tiempo y valida duración/silencio antes de enviar bytes al proveedor. Es necesario
tener `ffmpeg` disponible en desarrollo y producción.

## Claves

Las claves se guardan desde el panel o MCP, cifradas con Fernet. Su lectura sólo
devuelve presencia, versión y última comprobación. No se incluyen secretos en el
historial de cambios, errores, previsualizaciones ni argumentos de confirmación MCP.

La llave de cifrado es independiente de las credenciales de proyectos. Se acepta
`AI_CREDENTIALS_CIPHER_KEY`, o un archivo privado señalado por
`AI_CREDENTIALS_CIPHER_KEY_FILE`; el default es
`PRIVATE_MEDIA_ROOT/runtime-secrets/platform-ai.key`. Debe pertenecer al usuario
del servicio o a root, con permisos 0600 y fuera de media pública.

El deploy provisiona ese archivo una sola vez mediante el management command
`initialize_platform_ai_key` con los settings del entorno correspondiente. No
escribe la base de datos, no imprime el secreto y no reemplaza una llave existente.
Una llave perdida con credenciales existentes se restaura desde backup; no se
regenera. El backup privado debe incluirla separadamente de la base de datos.

## Cupo compartido

El default conservador coordinado con Appi es **20 solicitudes por cliente en una
ventana móvil de 300 minutos**. `ai_request_limit` y `ai_window_minutes` se pueden
editar globalmente o definir juntos para un cliente. Ambos overrides en null
heredan la política global. Cambiar la política nunca borra consumo anterior.

Cada pregunta nueva del chatbot y cada grabación de reporte enviada a transcribir
ocupan una unidad. La transcripción y la pregunta dictada comparten la misma
reserva: el envío del chatbot la canjea una sola vez. Reintentos con el mismo
`request_id` no duplican el consumo; un identificador no se puede reutilizar con
otra entrada. Si la transcripción se canjea después de su ventana, la misma reserva
se incorpora a la ventana actual sólo si hay cupo; no permite acumular consultas
gratuitas para después. Respuestas desde caché y declinaciones nuevas también cuentan.
Un fallo técnico sin transcripción/respuesta útil devuelve una reserva pendiente;
descartar un resultado ya obtenido no la devuelve.

El marcador expone usadas, disponibles y **próxima liberación de cupo**, no un
reinicio total simultáneo. Si un administrador baja el límite, se calcula cuántas
reservas deben expirar antes de permitir otra solicitud. Agotar el cupo devuelve
429 y `Retry-After`. Leer historial, capacidades o el marcador no gasta unidades.

Como protecciones adicionales, hay un máximo inicial compartido de 1000 notas
mensuales, 20 por usuario/día y un trabajo activo por usuario. La generación de
borradores tiene un límite diario de tres veces el máximo diario de notas. Estas
protecciones no crean una segunda cuenta visible del cupo compartido.

## Revisión, conservación y caché

El audio se guarda exclusivamente en almacenamiento privado mientras se procesa.
Se elimina después de transcribir o al finalizar con error. Una tarea cada diez
minutos retira trabajos abandonados desde los cincuenta minutos; un borrado del
usuario o proyecto también elimina el audio de sus trabajos.

La transcripción y la propuesta son borradores privados recuperables por el autor
durante 24 horas. Descartar borra su contenido. El historial oficial sigue siendo
el bug, la solicitud de cambio o el mensaje de la entrega enviado por el cliente.
Aceptar la propuesta sólo llena el formulario; nunca envía el reporte ni aprueba
o rechaza una etapa. El servidor vuelve a validar propiedad y contexto.

Las plantillas de voz incluyen instrucciones comunes, bug, cambio y observación.
Las del chatbot contienen escenarios y marcadores finitos. Editar o restaurar
crea una versión nueva; la seguridad y las autorizaciones no son texto editable.
Los datos desconocidos quedan vacíos o como puntos por aclarar.

La caché exacta se separa por actor, proyecto, contexto, idioma, modelo, versión de
credenciales y plantillas y época de invalidación. Su vigencia máxima es 24 horas.
Nunca evita los permisos actuales. Los prefijos estables aprovechan la caché del
proveedor cuando son elegibles; no se agregan tokens de relleno ni calentamientos.
La invalidación por función conserva la caché de la otra; invalidar ambas cambia
la época global. No elimina borradores recuperables. El historial completo de
reportes no se reenvía al modelo. Métricas de tokens,
audio, latencia y costo estimado no incluyen mensajes ni grabaciones.

## Contratos de integración

- `GET /api/platform/ai/capabilities/`: JWT de sesión completa; disponibilidad y
  `quota` compartida. `chatbot.voice_available` añade la clave OpenAI sin depender
  del interruptor de reportes por voz.
- `POST /api/platform/ai/transcriptions/`: multipart, `audio`, `purpose`,
  `request_id` y `project_id`; el proyecto sólo es omitible para chatbot.
- `GET/DELETE /api/platform/ai/transcriptions/{id}/`: lectura o descarte del
  trabajo propio. GET de la colección lista borradores recientes propios.
- `POST /api/platform/ai/projects/{id}/report-drafts/`: texto revisado, transcripción
  propia, escenario e IDs de contexto autorizados. Devuelve un trabajo asíncrono.
- Las rutas `admin/` son de sesión Django + CSRF y requieren staff; la Plataforma
  usa exclusivamente JWT. Las claves nunca pasan al cliente HTTP de Plataforma.

`platform_ai_quota.reserve/consume/refund/snapshot` implementan el contador común.
`redeem_chat_audio(actor, transcription_id, request_id, project_id=...)` verifica
autor, propósito, trabajo listo, contexto y canje persistente sin cobrar otra vez.
La clave de caché de cada canal incorpora `platform_ai.cache_version(purpose, config)`.
El redactor del chatbot utiliza `platform_ai_providers.generate_text`; su política
de alcance, fuentes y Jev sigue siendo responsabilidad de Appi.

El conector MCP existente **projects** administra configuración, clientes,
credenciales write-only, comprobación de conexión, plantillas, versiones,
restauración, consumo e invalidación. Usa los mismos servicios que el panel y
confirmaciones sensibles con versiones vigentes. Los trabajos privados y sus
reservas no se exponen como recursos administrativos editables.

## Activación

Aplicar las migraciones mediante el deploy, provisionar la llave privada y cargar
credenciales desde el panel. Validar primero en desarrollo y después con un cliente
piloto; habilitar global y cliente explícitamente. Verificar el flujo completo,
los casos sin permisos y el marcador antes de ampliar la activación. Las pruebas
automáticas usan settings_test y fronteras de proveedor simuladas, sin costo de API.

## Referencias de adaptadores

Verificados el 24 de octubre de 2026: [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [GPT-Transcribe](https://developers.openai.com/api/docs/models/gpt-transcribe), [transcripción de archivos](https://developers.openai.com/api/docs/guides/speech-to-text) y [Haiku 5.5](https://platform.claude.com/docs/en/models/haiku-5-5/overview). Los costos mostrados son estimaciones con las tarifas base; la factura y el acceso efectivo dependen del proveedor y de la cuenta.
