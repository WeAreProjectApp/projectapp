# PA-219 — Destinos visibles al abrir desde Ayuda y cambiar de tamaño

Fecha: 7 de noviembre de 2026. Requerimiento PA-219, PR567, misma rama de sesión
`fix/06112026-pa219-platform-help`. Fuente: devolución parcial de QA1/DEVQA-008
sobre `d012f9e833500f21cc87d067a67c340a8c654e60`; no dictamen global.

## Evidencia recibida y alcance

Fuente íntegra del buzón: `qa-projectapp-DEVQA-008-08-anclaje-proyecto-fallo.md`.
Primera versión SHA25664198a11d6259cfcc11c72f4fcbf55b4c0e854284cdf4b4f8b15a6e2562f3afe;
ampliación con caso C SHA25619ea53de03838c6d9e6f2dd8075af1ed851e25144a369d44332da92c0e65e289.
Se revisaron las capturas de carga móvil y tableta; las observaciones y métricas
son de QA, no una ejecución manual de Implementación.

- A: cliente B19, proyecto55/Bugs, guía de proyecto2 ya completada. Carga directa
  412×915 → navegación móvil → Ayuda → Guía del proyecto. La tarjeta Resumen1/7
  aparece, pero el cajón global cubre Resumen y el recorte ilumina Hosting.
- B: con esa guía abierta, 1440×900 → 412×915 → 835×1195, también 2560 → 412 sin
  recarga. El control se mueve y el recorte queda en las coordenadas anteriores.
- C: guía general en Tus proyectos2/8, 1440 → 412. Driver conserva el nodo oculto
  del menú de escritorio, de tamaño cero, y el cajón móvil no se abre.

Los tres corresponden al criterio original de pasos sobre controles visibles;
no duplicar PA-229/PA-250 ni atribuir una regresión/main sin evidencia adicional.
No se agrega una función Pausar, selector de tema o validación dedicada de teclado.

## Causa y corrección en rama

`prepareTarget` restauraba para destinos no globales el estado inicial del cajón.
Al iniciar desde Ayuda móvil ese estado es abierto. Ahora sólo los pasos de
navegación global abren el cajón móvil; los destinos de proyecto/formulario lo
cierran antes de medir. El snapshot se conserva para restaurar la pantalla al salir.

El resize propio de Driver no prepara el menú ni cambia el elemento elegido al
cruzar el breakpoint; tampoco cubre necesariamente las transiciones posteriores
que desplazan el contenido. Durante la guía se observan el contenido y el destino,
resize y fin de transiciones. Las actualizaciones se agrupan por frame, esperan
el render de Vue y preparan el mismo destino lógico; si cambia el nodo visible,
se reasigna ese paso a su nueva instancia; en otro caso se refresca la geometría.
Al finalizar o pausar se liberan observadores/listeners y frames pendientes.

El arreglo no modifica identidad/store, backend, progreso terminal, rutas,
recursos de video, dependencias ni configuración global/cliente. Sin consultas
nuevas por frame ni temporizador permanente; sólo medición mientras la guía existe.

## Regresiones automatizadas, exclusivamente en CI

- Unitario del composable: abrir guía contextual con el cajón de Ayuda abierto
  deja visible el destino al cerrar ese cajón. Se conservan las siete regresiones
  previas de restauración, cancelación y último destino. Otra regresión programa
  una medición y comprueba que cerrar la guía libera el observador y cancela el
  frame pendiente, mediante las fronteras del navegador. Objetivo focal: store11
  + host9 + composable9 (29 unitarios), más 19 E2E.
- E2E de apertura real: Documentos → Proyectos → proyecto propio → Bugs →
  navegación móvil → Ayuda → guía
  completada. El cajón desaparece, el centro de Resumen cae en el hueco real del
  SVG y la tarjeta queda junto al control. Recargar conserva su acuse terminal.
- E2E por transiciones: desktop→compact, wide→compact, compact→portrait,
  compact→landscape y compact→wide. Mismo paso y comprobación de geometría,
  terminal conservado tras recargar. Cubre las cinco medidas del contrato.
- E2E general: Ayuda → Tus proyectos en escritorio → resize a compacto; el destino
  pasa al cajón móvil visible. Avanzar a Documentos y volver a tableta reasigna
  el control al menú visible, sin reiniciar la guía.

La comprobación SVG usa geometría renderizada (`isPointInFill`), no sólo la clase
que Driver asigna al destino. Las APIs son fixtures de frontera, sin DB desplegada.
Antes de medir se esperan los frames del render y las animaciones finitas activas
del contenido/navegación mediante `Animation.finished`. Se excluyen animaciones
pausadas e infinitas y se dejan procesar los frames de refresco posteriores, sin
esperas fijas. Así una coincidencia transitoria antes de terminar el layout no
acredita el anclaje final. Esta precisión responde al cotejo técnico de DevQA
SHA256daabd3e499c32fba8085f23b613e84f8a025a7a537a47377d7fb4110b383c224;
no modifica el código de producto ni cambia la hipótesis temporal del fallo B.
Las pruebas visuales parten de Documentos, entrada autenticada real según login
y middleware, y llegan a Proyectos y Ayuda mediante clics. La excepción de setup
del gate se limita a esa entrada; no elimina navegación ni aserciones. Nuevas
pruebas aún pendientes de resultado del CI del SHA que las publique.
No se ejecutan tests ni builds locales y CI no acredita Chrome manual.

## Reprueba futura sin alterar la ronda vigente

La ronda actual continúa en `d012f9e8`/DEVQA-008-HELP; no servir este fix durante
sus casos. Publicar SHA final y runs exactos en PR567 y acordar la reprueba con
qa-projectapp/dev-qa; Backlog recibe los avances materiales. PA-220 podrá integrar
el commit original por merge en su rama, sin recrear el parche ni cambiar su turno.

Con terminales ya sellados, repetir manualmente desde Ayuda sin reset: comprobar A,
B y C en cinco medidas, carga directa y resize, conservando el paso y los acuses.
La dupla acuerda los registros/copia del nuevo turno; no repetir el primer ingreso
o terminales para fabricar condiciones. Se preservan los ocho grupos originales,
los cotejos previos y la distinción entre fallo parcial y resultado global.

Pausa por mouse: el guion anterior daba por alcanzable una navegación durante
Driver. La aclaración de Implementación3a32d137 reconoce ese límite. El E2E de
retomar parte de estado pausado de frontera; no acredita cómo lo genera el usuario.
QA/Backlog concilian «retomar o repetir» sin PASS por lectura. Appi/voz positivos
siguen condicionados a disponibilidad segura; no activar proveedores ni consumir
servicios reales. Teclado dedicado fuera de alcance por Carlos el 7 de noviembre;
foco con mouse, temas, responsive y controles visibles conservan su alcance.

## Mapas y verificaciones estáticas

Mismos flujos de guía general y de proyecto, sin rutas, vistas ni capacidades
nuevas. Catálogos de vistas conservan identidad y conteos; se revisa el diff
semántico. La auditoría estática del mapa E2E debe registrar las nuevas regresiones
y mantener explícitas las brechas de outcomes ajenas al arreglo.
