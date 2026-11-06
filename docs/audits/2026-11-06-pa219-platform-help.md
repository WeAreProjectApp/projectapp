# PA-219 — Recorridos y Ayuda: corrección y traspaso

## Causa y alcance

`UserProfileSerializer` devuelve `user_id`, sin `id`. El store de Ayuda
comprobaba `id` y abandonaba antes de consultar el catálogo. El mismo alias
incorrecto impedía detectar cambios de cuenta y guardar o sincronizar el progreso.
Las fixtures unitarias y de navegador incluían ese alias y ocultaban el fallo.

La corrección se limita a Ayuda y sus pruebas. Conserva las APIs JWT, los
interruptores existentes, la publicación de revisiones y el progreso por usuario.
No requiere migraciones ni operaciones sobre la base del servicio.

## Regresión automatizada

Ejecución exclusivamente en CI. Las pruebas de Ayuda usan perfiles con
`user_id` sin `id`; las fixtures compartidas de otros módulos no cambian.

| Interacción | Resultado comprobado por las pruebas |
|---|---|
| Ingresar con un cliente y catálogo publicado | Carga de Ayuda y apertura de la guía general. |
| Entrar al primer proyecto propio | Inicio de su guía contextual. |
| Saltar o completar; recargar | Conserva el acuse y no se inicia automáticamente. |
| Repetir desde Ayuda | Abre la guía manualmente, también en móvil, sin borrar el acuse. |
| Retomar una guía pausada | Abre el último paso guardado y permite completarla. |
| Cambiar de cuenta | Descarta respuestas anteriores y no envía avances ajenos. |
| Fallar carga o guardado | El proyecto sigue utilizable; el descarte pendiente se reintenta. |
| Desactivar capacidades de IA | Omite Appi y voz; con voz disponible espera el formulario real. |
| Publicar otra identidad de recorrido | La novedad aparece una vez, sin reabrir la guía general completada. |

La revisión del mapa de vistas `--apply --diff` conserva las entradas existentes:
ya describen el primer ingreso, el primer proyecto, la repetición desde Ayuda y
las novedades. No se añaden rutas, tipos, capacidades ni conteos.
La auditoría estática de flujos comprueba el registro vigente; sus resultados
no equivalen a pruebas de navegador aprobadas ni a conformidad manual.
El mapa está vigente y no tiene flujos sin pruebas ni pruebas descalificadas
como única evidencia. Conserva brechas declaradas: las guías general y de
proyecto no tienen evidencia E2E separada para `error`/`display`; la de voz no
tiene `error`/`failure`; la administración de disponibilidad carece de `error`
y la edición de recorridos de `failure`. Esta corrección conserva esos controles
y no presenta la auditoría como cobertura completa del módulo.

## Validación manual coordinada con dev-qa

El aviso inicial se envía directamente a la sesión `dev-qa`. Las solicitudes
no conceden un turno: dev-qa confirma el SHA servido, los datos y la disponibilidad
de DEV. La entrega externa identifica PR, SHA exacto, corridas CI y resultado.

Precondiciones: dos clientes activos con perfil completo y sin progreso previo,
proyectos propios, un administrador del panel y variantes con IA disponible o
desactivada. Cliente 17 y proyecto 38 son referencias del ticket; dev-qa confirma
su vigencia y los IDs del segundo cliente. Preparar datos con el generador
canónico; documentar cualquier preparación manual o brecha y vincularla a PA-231.
No compartir contraseñas ni tokens en mensajes o evidencias.

1. Cliente A: iniciar sesión y comprobar la guía general; saltarla, recargar y
   volver a entrar. No debe reiniciarse. Repetirla desde Ayuda.
2. Cliente B: completar la general y entrar a su primer proyecto. Completar o
   saltar la contextual; comprobar el acuse guardado y repetir desde Ayuda.
3. Pausar por navegación y retomar desde Ayuda en el último paso guardado.
4. Desactivar Appi y voz; comprobar que no se ofrecen sus pasos. Con voz
   disponible, abrir voluntariamente un formulario compatible: sólo entonces
   debe ofrecerse su guía, sin grabar, transcribir ni enviar datos.
5. Desde Panel → Plataforma → Ayuda de la plataforma, publicar una novedad con
   identificador nuevo. En el siguiente ingreso o recarga, comprobar que aparece
   una vez y no reinicia la general. Republicar el recorrido anterior conserva
   sus vistos.
6. Revisar acceso y repetición en 412×915, 835×1195, 1195×835, 1440×900 y
   2560×1440, temas claro/oscuro, navegación por Tab y retorno del foco.

Registrar SHA servido, roles, IDs, tamaño CSS, tema, pasos y evidencia por caso.
Los fallos de los criterios vuelven a Implementación; los hallazgos adicionales
se documentan como seguimiento vinculado, conforme al acuerdo de validación.
El cierre de la implementación es PR abierto con CI verde; QA determina el
veredicto del ticket sobre el SHA de `main` que incluya el cambio.
