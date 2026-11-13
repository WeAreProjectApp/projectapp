# Entrega PA-250 / PA-259 / PA-260-D1 / PA-252

Fecha: 2026-11-12. Rol confirmado: Implementación. Base inicial: main `295b65ef`.
Rama: `fix/12112026-pa250-259-260-252`. La entrega se identifica por el SHA y CI del PR;
este documento no concede turno, DEV LISTO ni aceptación manual.

## Alcance

- PA-250: control Saltar recorrido de Driver con texto/superficie del tema en normal,
  foco inicial, hover y pulsación. El CSS 1.10.2 de Driver asigna #2d2d2d en
  focus-visible; el selector local de mayor especificidad conserva los tokens
  incluso cuando la hoja del proveedor se carga después. Sin cambios al progreso.
- PA-259: borrador/emitida/pagada según commercial_status, número o aviso de no
  asignación, importes conservados. Borrador usa «Fecha del documento»; emitida/pagada,
  «Fecha de emisión», nunca una fecha de pago inferida. Sin fecha no se imprime el
  rótulo; sin cuenta no hay bloque. Estado desconocido: mensaje neutral.
- PA-260/D1: al cerrar la aprobación con mouse se recupera el disparador disponible;
  si desapareció, enlace de la misma propuesta, encabezado del cliente o encabezado
  del editor, con foco visible. Una navegación o un diálogo nuevo impiden robar foco.
  D2 reutiliza PA-259. D3 y los criterios originales/antecedentes conservan sus fichas.
- PA-252: conserva el tratamiento de denegación ya integrado por #569/#572 y añade
  mensajes traducidos y regresión de acceso directo/retorno propio. No se atribuye
  aquí una nueva falla de autorización ni una causa común de las observaciones históricas.

Sin migraciones ni cambios de autorización, emisión, números o datos financieros.
No se ejecutan pruebas/builds localmente: la evidencia automatizada es el CI del PR.
No se amplía el barrido de temas ni los modales de PA-234.

## Matriz para la dupla — datos nuevos, copia aislada

Solicitar a Backlog un único responsable de QA y DevQA para el PR completo. No se
localizó projectapp-qa/devqa-mensajes/backlog-reparto-qa-vigente.md en este host;
las búsquedas públicas de Slack no localizaron la ficha ni el reparto. El traspaso
queda preparado aquí; no se declara un mensaje enviado, asignación ni turno concedido.

| Caso | Preparación y pasos | Esperado / cotejo |
|---|---|---|
| PA-250 general | Cliente ficticio nuevo, perfil completo/verificado, sin progreso. Abrir Proyectos en oscuro y luego claro | Primer paso automático; contraste calculado >=4.5:1 de Saltar en foco inicial, normal, hover y pulsación |
| PA-250 proyecto | Otro cliente nuevo o general ya terminado; primer proyecto propio con guía elegible | Mismo contraste en el primer paso automático de proyecto; IDs actor/proyecto/guía registrados |
| PA-250 terminales | Saltar una guía; completar otra; recargar; repetir desde Ayuda | skipped/completed reales, no relanzamiento automático y repetición manual disponible, sin tocar vistos ajenos |
| PA-259 | Ingresos → Agrupado/Esperados por cobrar → Acciones → Detalle e historial: borrador con fecha y número vacío, emitida, pagada y sin cuenta | Estado/rótulo/importe correctos; misma relación documental, estado, número y fecha de actualización antes/después. Sólo lectura, no emitir/abrir PDF/liquidar |
| PA-260/D1 | Propuesta ficticia nueva, pendiente de Revisar; preparar nuevo cliente/proyecto y confirmar una sola vez con mouse | Se conserva aprobación, dirección, IDs y archivos; desaparece Revisar y foco visible en el enlace del mismo registro. Cancelar devuelve foco al disparador conservado |
| PA-252 | Dos clientes nuevos con un proyecto propio cada uno. Abrir ID ajeno en ambos sentidos; regresar al listado y al propio | Correlacionar el mismo GET 403 con resultado visible sin loader persistente ni datos ajenos; cuenta/idioma conservados; cero escrituras |
| Regresión | 404 de proyecto, error recuperable controlado, acceso propio y respuestas fuera de orden en CI | Mensaje según estado, recuperación útil, sin datos de un proyecto anterior |

Tamaños CSS: 412×915, 835×1195, 1195×835, 1440×900, 2560×1440; ambos temas.
Añadir lectura contable a 1528×732. Registrar los tamaños realmente comprobados:
los de CI no acreditan responsive manual. Sin casos dedicados de teclado; las
pruebas históricas existentes se conservan. No reutilizar ni reiniciar A13/B19,
proyectos 49/55, aprobación 5691011 ni otros terminales sellados para completar evidencia.

## Cobertura automatizada preparada

- Driver real: primera apertura general/proyecto, cinco perfiles y ambos temas,
  contraste calculado en los estados del control; skipped, recarga y repetición manual.
  Se conservan los casos existentes de completed y no relanzamiento.
- Modal de ingreso: los estados comerciales, número vacío, fecha ausente, cuenta
  ausente y traducción. E2E abre Acciones → Detalle e historial sin escrituras.
  Contrato REST parametrizado verifica estado/fecha/número/updated_at conservados.
- Retorno de foco: disparador vigente, eliminado, oculto o deshabilitado; navegación,
  diálogo nuevo y reapertura. E2E confirma una aprobación nueva y cancela otra con mouse.
- Proyecto: 403/404/500/loading, idioma y recuperación; dos actores y cinco perfiles
  en ambos temas con regreso al proyecto propio; conservación del descarte de respuestas
  tardías que ya cubre platform-projects.test.js.

Los mocks de frontera de Playwright no acreditan permisos reales del backend.
DevQA debe correlacionar el evento manual real sin repetir las operaciones selladas.

## Gestión MCP — verificación pendiente sobre el SHA servido

El código reutiliza el contrato de lectura: Contabilidad `get_income` usa el payload
del detalle, incluido collection_account/commercial_status/issue_date. Proyectos
incluye `list_platform_tour_progress`, consulta de guías y políticas de acceso;
Comercial conserva consulta/aprobación de propuestas. No se añade una operación
para cambiar progreso ajeno ni se ejecuta una aprobación para reparar evidencia.

DevQA descubrirá las herramientas realmente expuestas del entorno aislado, registrará
MCP/herramienta/rol/actor/ID/resultado y cotejará el mismo SHA que Chrome. La existencia
de código REST/MCP no acredita que el conector esté disponible ni su autorización.
Si falta una operación necesaria, devolver el punto con esa evidencia a Implementación.
Contraste y foco requieren navegador; MCP aporta estado y conservación de datos.

## Estado de entrega

Pendientes de adjuntar en el PR: SHA final, enlace y resultados CI. Aceptación manual,
DEV LISTO y cobertura MCP real pendientes de asignación/entorno de la dupla. Sin
transferir dictámenes de PR567/PR569/PR572 o de los SHA históricos.
