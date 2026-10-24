# Appi: consultas del cliente y guías de uso

Appi informa sobre el estado y la salud de los proyectos propios y explica cómo
utilizar la plataforma. Su catálogo es finito: proyectos, fases publicadas,
entregables compartidos, bugs y copias contractuales visibles. Las guías explican
pasos; el chat no registra reportes, aprueba entregas, firma documentos ni realiza
pagos. La salud se explica con avance registrado, fechas, bugs abiertos y revisiones
pendientes, sin inventar puntajes, causas o compromisos.

El cliente abre Appi desde su lanzador. Puede seleccionar un proyecto o «Todos mis
proyectos», consultar fuentes internas, ver cuándo se verificó una respuesta,
volver a consultar y borrar conversaciones. Las respuestas históricas conservan
su texto original y se marcan como actuales, desactualizadas o no disponibles.
Una consulta nueva crea otra fila; no reescribe lo que se respondió antes.

## Activación y administración

Panel: **Plataforma → Configuración de IA**, ruta `/panel/platform/ai`.

- Chatbot y reportes por voz tienen interruptores independientes, globales y por
  cliente. Comienzan apagados. El apagado global prevalece y oculta el control.
- Jev clasifica las consultas. El redactor es `claude-haiku-5-5` por defecto o
  `gpt-6-luna`, seleccionado por función, sin cambio automático de proveedor.
- El dictado de Appi usa `gpt-transcribe` y necesita clave OpenAI, aunque el redactor
  sea Haiku. Depende del chatbot, no del interruptor de reportes por voz.
- Las claves Jev/Anthropic/OpenAI se administran con el almacén cifrado común.
  La llave de cifrado de IA está fuera de la base de datos. Las APIs de lectura
  no devuelven secretos; tampoco las vistas previas ni la auditoría de MCP.
- Las plantillas se agrupan por función e idioma. Editar, previsualizar,
  versionar y restaurar usa los mismos servicios desde panel y MCP `projects`.
  Las rutas, permisos, escenarios y reglas de seguridad están fuera del texto editable.

Las guías disponibles abarcan proyectos, documentos, firmas, cobros, hosting,
notificaciones, perfil, Ayuda, resumen del proyecto, revisión de entregas,
contratos, ideas, cambios, reporte y seguimiento de bugs, entregables, recursos,
accesos, enlaces seguros, comentarios y notas de voz. Las guías generales funcionan
sin un proyecto asignado. Las guías de proyecto piden seleccionar uno propio y
respetan las capacidades de la cuenta. Ninguna guía revela credenciales.

## Acceso a datos y proveedores

El modelo nunca recibe conexión, credenciales, SQL, herramientas ni acceso directo
a la base de datos. La aplicación autentica al cliente y construye proyecciones
con campos permitidos, comprobando propiedad y visibilidad en el servidor.

1. Una pregunta nueva se clasifica con Jev mediante opciones tipadas de alcance,
   escenario, tema contractual y necesidad de redacción. Se envían la pregunta
   y, para referencias al mensaje anterior, su selección tipada, no el historial.
2. Fuera de alcance se responde con una plantilla educada que recuerda el
   propósito de Appi. Una pregunta mixta, ambigua o con baja confianza pide
   aclaración. Ninguno de esos casos utiliza Anthropic u OpenAI para redactar.
3. Para identificar un bug, fase, entregable o contrato concreto, Jev sólo puede
   seleccionar entre identificadores y títulos autorizados proporcionados por
   la aplicación. No inventa identificadores ni autoriza accesos.
4. Los listados y guías usan plantillas. Una explicación explícita puede pasar
   al redactor una proyección acotada de hechos propios y la pregunta actual.
   Su respuesta debe citar hechos existentes, cumplir el esquema y superar una
   comprobación de respaldo con Jev; si falla, se usa la plantilla con hechos.
5. Se comprueban otra vez permisos, interruptores y dependencias después de las
   llamadas externas. Si cambió la información, se presenta la plantilla con
   datos actualizados; si se perdió autorización, no se entrega una respuesta.

Los contratos incluyen otrosíes visibles y sus fuentes. Una firma exige la copia
firmada conservada: un borrador posterior no la sustituye. Cuando falta evidencia
verificable se indica esa limitación y se remite al documento o al equipo.
La lectura de vigencia del historial compara la fuente sin volver a extraer su
contenido completo. Los enlaces se construyen desde destinos internos conocidos.

La interfaz informa del procesamiento con proveedores de IA y pide no compartir
contraseñas ni información sensible. Se omiten del enrutamiento patrones evidentes
de claves o JWT como minimización adicional. Esto no convierte texto libre en
un depósito seguro de secretos.

## Caché e historial

La coincidencia exacta normaliza Unicode, mayúsculas y espacios. Su contexto
incluye actor, proyecto, idioma, política y selección anterior cuando existe una
referencia como «esa» o «anterior». Puede reutilizar una clasificación ya validada
sin volver a llamar a Jev. Consultas distintas pasan por Jev y sólo comparten una
respuesta si sus parámetros tipados y dependencias son iguales; no se compara
proximidad semántica de textos.

Los índices de respuestas en Redis guardan referencias temporales a consultas privadas. Su duración
es configurable hasta 24 horas; una caída de Redis permite buscar en el historial.
Antes de usar la respuesta referenciada se comprueban autor, proyecto, vencimiento,
fuentes, miembros autorizados, permisos, modelo, plantilla y versión de caché.
Una referencia no omite ninguna de esas verificaciones.

El historial se conserva como máximo 90 días desde la creación de la conversación,
con páginas de 20 mensajes. Las coincidencias históricas aún vigentes pueden
reutilizarse tras revalidación aunque haya vencido el índice Redis. Cambios en
hechos, publicación, firma, plantilla, modelo o política invalidan la respuesta.
Cambios temporales relevantes para salud también forman parte de las dependencias.
Las plantillas pueden actualizar el mensaje sin otra llamada al redactor.
Si se revoca una capacidad necesaria para una guía, su respuesta histórica pasa a
no disponible y deja de exponer sus pasos y enlaces; el registro original no se reescribe.

Los botones de invalidación de voz, chatbot y ambas funciones son independientes.
Appi utiliza `cache_version('chatbot')`; invalidar voz no cambia su versión.
Invalidar no borra conversaciones ni borradores de voz recuperables. Borrar una
conversación elimina sus respuestas reutilizables y no devuelve cupo consumido.

El historial no se expone al MCP administrativo. Sus autores no se reasignan al
fusionar clientes. Al eliminar definitivamente un proyecto deben seleccionarse
explícitamente sus conversaciones y consultas privadas; no se trasladan al archivo
administrativo. La tarea periódica elimina conversaciones vencidas y devuelve
reservas de consultas pendientes que no obtuvieron un resultado a tiempo.

## Cupo compartido y dictado

Por defecto cada cliente dispone de **20 solicitudes en una ventana móvil de
300 minutos**, compartidas entre sus proyectos, dispositivos, Appi y reportes por
voz. El panel/MCP permite cambiar límite y ventana globales o definir ambos para
un cliente. Dejar ambos valores vacíos hereda la política global.

Una pregunta nueva cuenta una unidad, incluso si se responde desde caché o fuera
de alcance. Un reintento técnico del mismo `request_id` no duplica el consumo.
Los accesos al historial y la lectura del marcador no consumen preguntas.
Un fallo sin resultado útil devuelve la reserva; una transcripción completada
ya es un resultado y conserva su consumo aunque el usuario decida descartarla.

El dictado reserva una unidad al transcribir y entrega un texto editable.
Enviar ese texto con `transcription_id` canjea la misma reserva una sola vez y
comprueba actor, propósito y proyecto exactos. Si la reserva salió de la ventana,
su canje necesita cupo actual: la misma fila reentra en la ventana o devuelve 429.
No se pueden acumular audios para evadir el límite posterior.

El marcador muestra usados, restantes, ventana y próxima disponibilidad. Agotar
el cupo bloquea preguntas nuevas y grabaciones, pero permite leer el historial y
usar la plataforma. La API devuelve 429 y `Retry-After` antes de llamar a modelos.
Los topes técnicos de audio son adicionales. El audio es temporal, se borra al
procesarlo y tiene máximo 60 segundos; se recomiendan 30, sin duración mínima.

## Contratos técnicos

API cliente exclusivamente JWT, con respuestas `no-store`:

| Método y ruta bajo `/api/platform/chatbot/` | Resultado |
|---|---|
| `GET quota/` | Cupo compartido actual |
| `GET conversations/` | Conversaciones propias vigentes |
| `POST conversations/` | Crea contexto con `language: es/en` y `project_id` opcional |
| `GET conversations/{id}/?before={turn_id}` | Mensajes propios y vigencia comprobada |
| `DELETE conversations/{id}/` | Borra la conversación propia |
| `POST conversations/{id}/messages/` | `request_id`, `question` de hasta 2.000 caracteres y `transcription_id` opcional; 202 mientras procesa |
| `GET conversations/{id}/messages/{turn_id}/` | Estado de una consulta y cupo actual |

La transcripción reutiliza `/api/platform/ai/transcriptions/` con
`purpose=chatbot`; para guías generales puede omitirse `project_id`.
El procesamiento se ejecuta en Huey, fuera del proceso web. Sólo hay una consulta
activa por actor; los locks siguen el orden del servicio de cuota compartido.

El layout monta Appi y el host de Ayuda sin dependencias inversas. El coordinador
de superficies permite un único chat, tour o video a la vez. Cerrar Appi conserva
el borrador de texto, y un tour suprime sus globos proactivos sin abrir el chat.

Migraciones propias: `0088_appi_private_conversations` y
`0089_appi_client_guides`, posteriores a las migraciones comunes de voz y Ayuda.
La sesión no aplica migraciones ni despliega cambios. Ver configuración y
credenciales compartidas en [platform-ai.md](platform-ai.md).
