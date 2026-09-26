# Contrato ejecutable del estándar responsivo

**Estado:** vigente desde 2026-08-22

**Alcance:** panel interno `/panel/**`. No modifica `/platform/**`, propuestas públicas ni marketing.

**Estándar canónico:** [`docs/RESPONSIVE_STANDARD.md`](../RESPONSIVE_STANDARD.md).
**Fuente ejecutable:** `frontend/config/responsive.js` + `/panel/styleguide`, sección “Fundamentos responsivos”. Este documento describe la implementación compartida y no redefine las decisiones de la Fase 0.

## 1. Equipos y perfiles canónicos

Los breakpoints se ubican entre los cinco viewports de referencia. Los números exactos
son viewports de aceptación; los perfiles son las reglas que usa el producto.

| Perfil | Rango | Viewport de aceptación | Uso esperado |
| --- | ---: | ---: | --- |
| `compact` | `< 640 px` | `412 × 915` | Celular |
| `portrait` | `640–1023 px` | `835 × 1195` | Tableta vertical |
| `landscape` | `1024–1279 px` | `1195 × 835` | Tableta horizontal |
| `desktop` | `1280–1919 px` | `1440 × 900` | Portátil de 15″ |
| `wide` | `≥ 1920 px` | `2560 × 1440` | Monitor de 27″ |

Reglas transversales:

- El contenido general del panel se centra y no supera **1400 px**. Tener más monitor
  añade margen, no separa elementos relacionados.
- `portrait` es un perfil propio, no un celular agrandado ni un escritorio
  apretado. Conserva una columna cuando la tarea necesita lectura y permite dos
  columnas de formulario cuando hay espacio real.
- Las clases Tailwind canónicas son `panel-portrait:`, `panel-landscape:`,
  `panel-desktop:` y `panel-wide:`. El prefijo evita colisionar con los
  variants de orientación `portrait:`/`landscape:` que Tailwind ya reserva.
  `sm/md/lg/xl` siguen disponibles para superficies ajenas al panel y
  compatibilidad, pero un componente responsivo nuevo no inventa su contrato con
  ellas.
- El texto base del panel es 16 px. Metadata/controles usan 12/14 px y títulos
  fluidos con tope; nunca se reduce el texto para hacer caber una pantalla.

## 2. Patrones canónicos

### Tabla

Patrón elegido: **columnas priorizadas con agrupación declarativa**. No se
transforma toda tabla en tarjetas y tampoco se aplica desplazamiento horizontal
indiscriminado.

Cada columna de una tabla adoptada declara por perfil:

- `keep`: columna visible.
- `group`: se muestra como etiqueta/valor bajo la única columna `primary`.
- `hide`: ausencia deliberada.

`BaseResponsiveTable` exige una declaración completa y exactamente una columna
primaria. Una tabla todavía no adoptada conserva el scroll anterior; una mezcla
parcial genera advertencia en desarrollo para impedir decisiones automáticas.

El redimensionado también es una capacidad declarativa de la tabla. Cada
columna informa `columnWidth` con mínimo, default y máximo; la ajustable marca
`resizable`, las invariantes marcan `fixed` y las donantes ordenan
`shrinkPriority`. `BaseResizeHandle` concentra arrastre, teclado y doble clic,
mientras `useResizableTableColumns` distribuye el espacio, persiste por una
clave estable y activa scroll interno sólo después de agotar los mínimos. Los
textos recortables usan `BaseOverflowText`: dos líneas por defecto en títulos
largos, ayuda nativa únicamente si la medición confirma recorte y expansión en
el lugar como alternativa táctil.

### Tabs y filtros

`BaseResponsiveTabs` y `BaseFilterTabs` comparten un solo quiebre:

- `< 1024 px`: selector nativo nombrado y alcanzable.
- `≥ 1024 px`: tira visible con `flex-wrap`; nunca una línea recortada por
  `overflow-hidden`.
- Los filtros guardados se reordenan por drag con demora táctil, por menú o con
  Ctrl/Cmd + flecha. El gesto no es la única vía.

### Modales y formularios

Los anchos se eligen por propósito:

| `kind` | Ancho máximo desde `portrait` | Uso |
| --- | ---: | --- |
| `confirm` | 28 rem | Confirmación breve |
| `form` | 42 rem | Alta/edición habitual |
| `detail` | 64 rem | Detalle con más contexto |
| `workspace` | 90 vw, máximo 100 rem | PDF, diff o paneles paralelos |

Por debajo de 640 px todo `BaseModal` ocupa la pantalla completa. Desde 640 px
se centra, conserva un máximo de 90 vh y redondea. `BaseModalActions` apila las
acciones a ancho completo en compact y las alinea a la derecha en el resto.

`BaseFormRow` apila por debajo de `portrait`; desde 640 px crea las columnas y
comparte las bandas etiqueta/control/ayuda para conservar el orden y la
alineación. El DOM siempre mantiene el orden de lectura.

### Navegación

- `< 1024 px`: topbar + `PanelMobileDrawer`, con focus trap, cierre por Escape,
  bloqueo de scroll y retorno de foco.
- `1024–1279 px`: sidebar visible pero colapsado por defecto.
- `≥ 1280 px`: sidebar expandido por defecto.
- Las migas de pan aparecen desde `landscape`; en menor ancho el título de la
  topbar evita una tercera repetición del mismo dato.
- Tabs de módulo y filtros obedecen el mismo quiebre de navegación.

### Acciones y táctil

- Acciones de fila: `BaseActionMenu`. En Contabilidad, un kebab inicial
  (`AccountingRowActionsButton`) que abre un modal (`AccountingRowActionsModal`)
  con «Detalle e historial» y «Ver nota» primero; nada más va junto al kebab.
- Selección múltiple: `BaseBulkActionBar`, con conteo, elementos fuera del
  filtro, selección total, cancelación y un único menú de acciones.
- `BaseButton` y los ítems de `BaseDropdown` garantizan 44 px cuando
  `pointer: coarse`.
- Hover sólo puede mejorar una pista. Un control atenuado debe aceptar foco y
  llevar `touch-reveal`; un control nativo fuera de `BaseButton` usa
  `touch-target`. Un handle táctil usa `touch-drag-handle`.

## 3. Inventario priorizado de adopción

El inventario está basado en las 49 páginas Vue bajo `pages/panel`, sus
componentes compartidos y la búsqueda de tablas, strips, modales, grids y
acciones dependientes de hover. La sección responsiva del styleguide se valida
en los cinco viewports; las filas “por adoptar” son el worklist de las fases por
módulo y no se declaran corregidas por esta fase base.

| Prioridad | Módulo/superficie | Hallazgo | Estado tras fase base | Adopción siguiente |
| --- | --- | --- | --- | --- |
| P0 | Layout global | Sidebar/topbar usaban 768/1024 y el contenido podía estirarse sin límite | **Resuelto** con perfiles 1024/1280 y `BasePageShell` 1400 | Ninguna por página; retirar topes locales al tocar cada módulo |
| P0 | Tablas: contable (12 páginas) | Muchas columnas y variantes; un ocultamiento automático perdería datos financieros | Primitive listo; `AccountingTable` conserva compatibilidad | Declarar `keep/group/hide` tabla por tabla, empezando ingresos/gastos/hostings |
| P0 | Tablas: propuestas, clientes, proyectos, documentos, diagnósticos, blog, portfolio, QR, linktrees, LinkedIn, paquetes | Tablas nativas o locales sin una política común | Primitive listo, comportamiento anterior preservado | Migrar por impacto y fijar columna primaria/acciones en cada módulo |
| P0 | Modales transversales (87 superficies detectadas) | Anchos `size` y footers locales; compact no tenía fullscreen uniforme | `BaseModal.kind`, fullscreen y `BaseModalActions` listos | Sustituir `size`/footer por propósito en cada módulo; PA-45 queda absorbida |
| P1 | Contabilidad: navegación y filtros | Subnav/filtros podían divergir o recortarse | **Resuelto** mediante selector/tira compartidos | Adoptar políticas de columna; PA-66/70/73 consolidadas |
| P1 | Propuestas y clientes: filtros/tabs | Guardados, tabs del módulo y configuraciones compartían problema con APIs distintas | `BaseFilterTabs`/`BaseResponsiveTabs`; wrappers compatibles | Importar nombres base en cambios futuros; no duplicar lógica |
| P1 | Acciones masivas de contabilidad | Barra podía crecer horizontalmente y competir con el FAB | `BaseBulkActionBar` adoptada por `BulkAssignBar` | Reusar en cualquier listado con selección; PA-69 absorbida |
| P1 | Documentos/carpetas | Acciones/handles aparecían sólo por hover; panel lateral requiere revisión de espacio propia | Descubribilidad y targets táctiles corregidos | Fase de documentos valida geometría del split y PA-61 en los cinco viewports |
| P1 | Formularios: documentos, propuestas, blog, portfolio, diagnósticos, paquetes | Persisten grids de dos columnas escritos a mano; orden/apilado depende de cada archivo | `BaseFormRow` listo y documentado | Migrar formularios por módulo, empezando modales y create/edit de mayor uso |
| P1 | Diagnósticos/defaults | Tabs extensos, formularios densos y varios modales | Contratos base listos | Adoptar tabs/form rows/modal kinds y medir portrait expresamente |
| P2 | Dashboard/tareas/emails/views/MCP | Cards, Kanban, barras o tablas de densidad propia | Shell/navegación/tipografía aplican globalmente | Validar overflow local y mover acciones excedentes a `BaseActionMenu` |
| P2 | Blog/portfolio/QR/linktrees/LinkedIn | CRUD de uso menos frecuente con tablas/forms locales | Shell y modales base disponibles | Adopción posterior por familia CRUD |
| P2 | Monitor wide | Topes locales históricos (`max-w-*`) pueden crear columnas desalineadas | El shell global impide estirar a más de 1400 | Retirar sólo topes que contradigan el shell al migrar el módulo |

## 4. Consolidación de fichas relacionadas

| Ficha | Decisión |
| --- | --- |
| PA-45 | Se resuelve en `BaseModal.kind`, fullscreen compact y `BaseModalActions`; los consumidores se migran por módulo. |
| PA-61 | Se mantiene como adopción de Documentos: la base táctil ya está; falta validar la geometría específica del panel de carpetas. |
| PA-66 | Absorbida por `BaseFilterTabs`: selector bajo 1024 y wrap por encima. |
| PA-69 | Absorbida por `BaseBulkActionBar`, ya usada por la barra contable compartida. |
| PA-70 | Absorbida por reorder con drag táctil, menú, teclado y persistencia a cargo del consumidor. |
| PA-73 | Absorbida por el mismo selector/tira; no se crea otra solución para contabilidad. |

## 5. Definition of Done para una adopción

Una pantalla sólo cuenta como adoptada cuando:

1. Usa las primitives compartidas, sin copiar sus media queries.
2. Toda tabla declara la política de todas sus columnas y una primaria.
3. Formularios conservan orden DOM y no tienen scroll horizontal.
4. Ninguna acción depende exclusivamente de hover o drag.
5. Modal, tabs, filtros, navegación y barra masiva siguen los perfiles canónicos.
6. No hay overflow horizontal del documento a `412`, `835`, `1195`, `1440` ni
   `2560` px.
7. En wide, el contenido general no supera 1400 px; sólo un workspace declarado puede llegar a 1600 px.
8. Hay prueba unitaria del contrato local y E2E etiquetado para el flujo real.

El ejemplo completo y manipulable vive en `/panel/styleguide`. La API detallada
y snippets de adopción están en `frontend/components/base/README.md`.

## 6. Estado vigente después de la auditoría final

Las tablas de las secciones 3 y 4 son el worklist de la fase base y se conservan
como historia. La Fase 5 las concilió contra las cinco fases ya integradas:

- PA-61, PA-66 y PA-73 cumplen técnicamente la solución compartida;
- PA-45 cumple de forma distinta mientras existan overlays locales;
- el breakpoint local de Blog edit y dos acciones dependientes de hover fueron
  corregidos y protegidos por el contrato;
- la certificación en dispositivos físicos y los rediseños de overlays/harness
  permanecen como RSP-F5-01…04.

El informe normativo vigente es
`docs/audits/2026-08-22-responsive-phase-5-final.md`; ninguna fila “por adoptar”
de esta fotografía debe interpretarse por sí sola como estado actual.
