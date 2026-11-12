# PA-251, PA-253, PA-257, PA-258 y PA-261 · Implementación

## Corte y límites

Trabajo de Implementación en una sola rama de sesión desde `295b65ef` de
`origin/main`, cotejado el 12 de noviembre de 2026. Las referencias de las fichas
son antecedentes históricos: no se declara reproducción en main ni despliegue.
El PR #569 figura mergeado; no se reutiliza su rama ni su evidencia.
Pruebas y builds se ejecutan exclusivamente en CI. Los resultados, SHA y URL de
la corrida se entregan con el PR; esta documentación no acredita QA manual.

No se levantan pausas, se conceden turnos, se preparan servidores ni se repiten
pagos o aprobaciones. No se cambian estados de backlog por escribir código.

## Contratos implementados

### PA-251 · precisión visual

`formatMoney(..., { decimals: 'auto' })` es optativo: muestra dos decimales si
existe fracción y mantiene compactos los enteros. El comportamiento anterior
sigue siendo el predeterminado. Las columnas de tabla pueden declarar
`moneyDecimals`; Ingresos lo usa en las vistas clásica/agrupada y sus detalles
compactos. Los subtotales del listado, el menú y el reparto usan la misma regla.
No se alteran importes, entradas, cálculo de mitades enteras ni payloads.

Casos ficticios: 119,03 con socios 59/59 y remanente 1,03; reparto manual
50,25/60,50 sobre 119 con remanente 8,25. Se conserva el cierre por Cancelar.
Los originales históricos 65, 66 y 87 quedan fuera de la reprueba.

### PA-253 · selección y búsqueda

`BaseChoiceSelect` reutiliza el portal del proyecto (`BaseFloatingListbox`),
conserva el tipo exacto de cada valor y ofrece búsqueda local a partir de diez
opciones, salvo configuración explícita. Tiene etiquetas, estado seleccionado,
opciones deshabilitadas y validación de campo obligatorio sin submit al elegir.
No convierte globalmente `BaseSelect` ni permite destinos o scripts libres.

A: recorrido, contexto y destino de Ayuda; origen, severidad y entorno al reportar
un bug. C: estado, tipo, mercado e idioma en propuesta, y Previsión del listado.
Cambiar estado sigue siendo una intención hasta confirmar: Cancelar no actualiza
el valor guardado. Los formularios de ingreso y el idioma del vídeo no se
presentan como recorridos históricos acreditados.

Ayuda consulta el mismo endpoint paginado al escribir con debounce de 200 ms.
Cada cambio invalida inmediatamente las respuestas anteriores, también durante
el debounce. Carga, resultado, total y página pertenecen a una misma generación.
Cambiar o limpiar vuelve a página 1; Buscar ejecuta inmediatamente. La carga y
los errores de búsqueda son independientes del guardado de configuración.
No se descargan todos los clientes para filtrar en memoria. El servidor mantiene
20 registros por página y su búsqueda actual por fragmento de nombre, apellido
o correo: no se amplía la coincidencia de nombres completos ni PA-243.
El botón de limpiar cliente en propuestas usa traducciones ES/EN disponibles.

### PA-257 · uno o varios requerimientos por elemento

La revisión confirmó que el esquema, el mapa por `linked_item_ids` y el catálogo
adicional ya admitían listas. No se crea una relación paralela ni una migración.
El prompt conserva atomicidad e identificadores, pero elimina porcentajes,
mínimos por categoría y variación artificial. Un elemento simple puede tener
uno; varios comportamientos independientes se desglosan. Las personalizaciones
de prompt guardadas en el navegador no se sobrescriben.

El modal conserva N requerimientos y ahora recibe configuración, flujo de uso
y metadatos editoriales cuando existen. El catálogo adicional ya tenía entradas
desglosadas ES/EN: no se reescribe su contenido por una hipótesis. Su siembra
resuelve los IDs opacos vigentes de los elementos coincidentes y mantiene la
prioridad del contenido manual. Los históricos no se reescriben ni se regeneran.

Corpus ficticio: `docs/fixtures/pa257-requirements.json`. Son fragmentos comerciales
y técnicos representativos ES/EN, no una reproducción ni una propuesta real.
Registro e inicio de sesión están separados; vistas, componente de búsqueda,
funcionalidad con permisos y módulo PWA tienen conteos según su alcance. Los
casos de CI pasan esos fragmentos por importación y edición, verifican que las
listas se conserven y consultan su detalle a través del transporte MCP Comercial.
La generación mediante un proveedor externo no es un paso automático del
producto: la interfaz ofrece prompts para el proceso comercial/técnico en dos
pasos. Este cambio no inventa una llamada a un proveedor.

### PA-258 · presentación de navegación y perfil

Personaliza se declaraba `icon-only` aun mostrando texto: la envoltura interna
del botón agrupaba icono y rótulo fuera del gap de la fila. Se limita esa
propiedad al menú colapsado y se alinea el cajón móvil con las filas de cuenta.
No se atribuye una causa común a los tres síntomas del ticket.

Las iniciales usan blanco sobre el verde de marca #002921 en ambos temas:
contraste calculado 15,68:1. Se conservan las fotografías. Los controles pendientes
se identifican con aria-disabled y una etiqueta legible; Modelo de datos sigue
sin destino habilitado y conserva PRONTO. No cambia la personalización guardada.

### PA-261 · copiar título

La acción junto al lápiz copia `detail.title`, completo y vigente, mediante el
feedback de portapapeles existente. No consulta contenido ni URL, no renombra,
no modifica estados y no necesita una operación de servidor. La copia de enlace
mantiene su acción y feedback independientes. Tras renombrar, se usa el título
confirmado por la respuesta. Un rechazo de Clipboard se muestra y admite reintento.

## Traspaso para validación aislada

Antes de conceder turno, DevQA verificará el SHA servido y el reparto vigente.
El archivo `projectapp-qa/devqa-mensajes/backlog-reparto-qa-vigente.md` no estaba
disponible en este host durante la preparación: no se asigna una dupla por inferencia.

- PA-253: staff autorizado sin SU; cliente propio para Bugs y otro ajeno para
  comprobar denegación. Corpus con más de veinte clientes, fragmentos coincidentes,
  vacío y error de carga. Buscar y elegir no deben publicar guías ni guardar flags.
  La edición de estado con efectos se acuerda aparte; para Cancelar no se repite
  aprobación histórica. Previsión conserva el requisito de acceso financiero.
- PA-257: propuesta ficticia en borrador, permisos de edición de propuestas,
  corpus ES/EN y un perfil sin override de prompt o con el override revisado.
  Comprobar N y sus detalles en cada familia y conservar un histórico sin editar.
- PA-258: usuario ficticio sin foto y otro con foto; escritorio expandido/colapsado,
  cajón móvil y navegación de proyecto en claro y oscuro. Registrar tamaño CSS real.
- PA-251: ingresos ficticios equivalentes, abrir reparto automático/manual y
  cancelar. Cotejar etiquetas y payloads en CI; no confirmar liquidaciones reales.
- PA-261: títulos normal, largo y con tildes/signos; copiar y pegar en un campo de
  prueba, renombrar uno ficticio acordado y repetir. No revelar el contenido secreto.

La matriz visual incluye móvil, tableta vertical y escritorio, con los tamaños
históricos pertinentes (1440×900, 1920×855 y 1536×639 CSS) como referencias de
cada corte. Foco con mouse y nombres accesibles se cotejan; teclado dedicado
permanece excluido. Las capturas históricas no se reciclan como resultados nuevos.

## MCP y conservación

DevQA comprobará las herramientas realmente expuestas, sus permisos y resultados
sobre el mismo SHA y entorno: Proyectos para Ayuda/bugs, Comercial para propuestas,
Contabilidad para ingresos y Comunicaciones para metadatos/renombre de enlaces.
Las operaciones de lectura/búsqueda no acreditan escrituras ni autorizan efectos.
El test de transporte MCP Comercial es evidencia automatizada de ese contrato;
no sustituye la verificación del conector accesible por la dupla.

La presentación de avatar/menús y el portapapeles son capacidades de navegador;
no se añade una escritura MCP para cambiar estilos o copiar localmente. Los
servicios de negocio y permisos existentes siguen siendo la fuente. No se infiere
cobertura MCP de un endpoint REST, del catálogo en código ni de una captura.

## Cobertura y estado de verificación

Pruebas focales de formato y tablas; elección tipada y conservación de intención;
fuentes de bug y previsión; invalidación de búsquedas; copia sin mutaciones y
renombre; listas, detalle editorial e importación de requerimientos. Los E2E
mantienen sus tags existentes y adaptan únicamente los controles convertidos.

Las ejecuciones se registran en CI con su SHA. No se ejecutaron tests, builds,
servidores ni navegadores localmente. Los recorridos visuales y la comprobación
MCP aplicable permanecen pendientes de turno, sin declarar aprobaciones.
