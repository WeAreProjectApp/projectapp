# Estándar responsivo del panel — Fase 0

**Estado:** aprobado como línea base para implementación

**Fecha:** 2026-08-22

**Alcance:** las 47 superficies renderizables bajo `/panel/**`

**Fuera de alcance de esta fase:** cambios de código de producto

## 1. Resultado de la fase

Este documento fija el contrato responsivo del panel y el inventario contra el
que se ejecutarán las fases siguientes. El censo encontró 50 archivos de página:
47 superficies con UI y 3 rutas que solo redirigen. La deuda queda consolidada
en 16 hallazgos: **1 P0, 11 P1, 4 P2 y 0 P3**.

La decisión principal es separar dos conceptos que antes se confundían:

- Los **cinco anchos reales** son puntos de aceptación obligatorios. Cada cambio
  responsivo debe probarse exactamente en ellos.
- Los **umbrales de comportamiento** se eligen por el espacio que necesita el
  contenido. No se crean media queries de 412, 835 o 1195 px solo para imitar un
  dispositivo, ni se acepta un valor de librería si falla en uno de los cinco
  puntos de aceptación.

La tableta vertical de 835 px es un caso de primera clase, no una versión grande
del celular ni una versión pequeña del escritorio. En el extremo opuesto, el
monitor de 2560 px debe conservar proximidad visual mediante anchos máximos.

## 2. Dispositivos y puntos de quiebre

Las medidas son viewports CSS útiles, sin contar chrome del navegador. Las
alturas fijan una prueba reproducible de modales, barras sticky y scroll; el
ancho es la dimensión que decide el modo.

| Perfil | Viewport de aceptación | Rango de comportamiento | Contrato principal |
|---|---:|---:|---|
| Celular | **412 × 915** | `< 640 px` | Drawer, una columna, select para controles densos, listas exploratorias en tarjetas. |
| Tableta vertical | **835 × 1195** | `640–1023 px` | Drawer, contenido ancho completo, select para tabs/filtros densos, formularios condicionados por ancho real. |
| Tableta horizontal | **1195 × 835** | `1024–1279 px` | Sidebar fija/colapsable, tiras visibles de máximo dos filas, layouts anchos solo si cada panel conserva su mínimo. |
| Portátil | **1440 × 900** | `1280–1919 px` | Modo ancho, densidad normal y contenido centrado cuando llega a su máximo. |
| Monitor de 27 pulgadas | **2560 × 1440** | `≥ 1920 px` | El viewport crece, el contenido no: máximo general de 1400 px y máximo de workspace de 1600 px. |

### 2.1 Umbrales canónicos

El panel tendrá tres cambios funcionales, aunque se verifique en cinco equipos:

1. **Compacto (`< 640`)**: una columna y controles táctiles.
2. **Intermedio (`640–1023`)**: aprovecha el ancho, pero mantiene drawer y
   selectores para navegación de alta cardinalidad.
3. **Ancho (`≥ 1024`)**: habilita sidebar fija, tiras y layouts multipanel solo
   cuando también pasan sus mínimos internos.

Los límites de 1280 y 1920 no introducen por sí solos otra navegación; sirven
para ajustar densidad y aplicar los topes de contenido. Si un componente depende
del ancho de su contenedor —por ejemplo, un formulario dentro de un modal— debe
usar la capacidad real del contenedor, no inferirla únicamente del viewport.

### 2.2 Anchos máximos

- **Página general:** `1400 px`, centrada. El patrón existente es
  `PAGE_MAX_WIDTH` (`max-w-[87.5rem] mx-auto`).
- **Editor, preview o workspace multipanel:** `1600 px`, centrado. Es una
  excepción explícita, no el valor por defecto.
- **Formularios de lectura lineal:** conservan topes menores (`max-w-*`) cuando
  el ancho adicional empeora la lectura.
- Los fondos del shell pueden ocupar todo el viewport; títulos, filtros,
  tablas, formularios y acciones que guardan relación deben compartir el mismo
  contenedor limitado.

## 3. Invariantes globales

Una superficie cumple el estándar solo si satisface todas estas reglas en los
cinco viewports:

1. No existe scroll horizontal en `html`, `body`, el shell ni la página.
2. Ningún control, acción primaria, encabezado de modal o cierre queda fuera del
   viewport.
3. El orden visual y el orden del DOM siguen siendo legibles al apilar.
4. Los objetivos táctiles interactivos conservan al menos 44 × 44 px, salvo
   controles nativos cuyo área accesible equivalente esté demostrada.
5. Texto, importes y estados no se truncan si esa pérdida cambia el significado.
6. El foco visible, el focus trap del modal, Escape y la restauración del foco
   se mantienen en cualquier ancho.
7. Una barra sticky no tapa el último contenido; contempla safe-area y una forma
   visible de cancelar o limpiar la selección.
8. La reducción de movimiento sigue respetando `prefers-reduced-motion`.
9. A 2560 px, dos elementos relacionados no se separan por estirar el layout:
   se aplica el ancho máximo correspondiente.
10. Un cambio de representación —tabla a tarjetas o tira a selector— preserva
    selección, orden, conteos, estado disabled y acciones disponibles.

## 4. Patrones canónicos

Primero se reutiliza el patrón sano que ya existe. “Adoptar y completar” permite
corregir su umbral o accesibilidad; no autoriza crear una segunda variante para
el mismo problema.

| Tipo | Referencia existente | Decisión canónica |
|---|---|---|
| Shell y navegación | `layouts/admin.vue` + `usePanelSidebar` | Drawer hasta 1023 px; sidebar fija/colapsable desde 1024 px. Una preferencia persistida nunca puede forzar sidebar fija en modo intermedio. |
| Contenedor de página | `PAGE_MAX_WIDTH` en contabilidad | Adoptar globalmente el máximo de 1400 px; 1600 px solo para workspaces declarados. |
| Tabla compartida | `AccountingTable` + `tableLayout.js` | Conservar semántica de tabla para comparar; priorizar columnas por rango y usar scroll interno solo como último recurso. |
| Lista exploratoria | Tarjetas móviles de Blog, Portfolio, Paquetes de horas y Documentos | Tabla/lista densa en ancho; tarjetas apiladas en compacto cuando el objetivo es recorrer entidades, no comparar columnas. |
| Tabs de alta cardinalidad | Selector móvil de Contabilidad y `BaseTabs` | Selector durante compacto e intermedio; tira desde 1024 px, máximo dos filas. Si necesita una tercera, agrupar en “Más” o mantener selector. |
| Filtros guardados | `ProposalFilterTabs` | Igual contrato que tabs: selector hasta 1023 px; tira visible desde 1024 px, máximo dos filas, sin cortar opciones. |
| Modal | `BaseModal` | Único overlay canónico: margen exterior de 16 px, máximo 90dvh, body con scroll, encabezado/cierre y footer alcanzables, focus trap y bloqueo de scroll. `fullHeight` queda para workspaces. |
| Fila de formulario | `BaseFormRow` + `BaseFormField` | Una columna por defecto; dos columnas solo cuando cada control conserva al menos 280 px útiles. En modal estrecho se apila aunque el viewport sea ancho. |
| Acciones por fila | Kebab de Documentos + `DocumentActionsSheet`; en Contabilidad `AccountingRowActionsButton` + `AccountingRowActionsModal` | Un solo disparador por fila. En tabla ocupa la primera columna de control, sin rótulo visible y con 56 px fijos; si hay selección, el orden es Casilla → Acciones → Contenido. Dropdown en ancho; hoja/modal de acciones en compacto o cuando hay muchas acciones (Contabilidad usa siempre el modal). «Detalle e historial» y «Ver nota» son entradas del menú, nunca botones junto al kebab. Nunca una hilera de botones que ensanche la tabla. |
| Selección masiva | `BulkAssignBar` | Barra sticky compacta, contador, acción principal y un menú “Acciones”; siempre ofrece limpiar/cancelar. |
| Navegación de calendario | Lista móvil de Blog Calendar | Vista semántica alternativa en compacto/intermedio cuando comprimir la grilla destruye legibilidad. |
| Workspace multipanel | Editores de Documentos | Apilar hasta que cada panel tenga su mínimo; permitir split solo con al menos 480 px por panel; máximo exterior de 1600 px. |

### 4.1 Regla de decisión para tablas

No se elegirá una transformación distinta pantalla por pantalla. Antes de
implementar, la tabla se clasifica así:

| Clase | Ejemplos | Comportamiento en celular/tableta vertical |
|---|---|---|
| Comparativa o transaccional | Propuestas, diagnósticos, movimientos contables | Sigue siendo tabla. Se conserva identidad + estado + valor crítico + acción; columnas secundarias se ocultan por prioridad. Scroll horizontal interno únicamente si ese mínimo aún no cabe. |
| Exploratoria | Blog, portfolio, documentos, linktrees, QR | Tarjetas apiladas con las mismas acciones y estados. La tabla vuelve desde el ancho en que realmente cabe. |
| Matriz o detalle anidado | Detalle de clientes, estados de cuenta | Conserva estructura tabular dentro de una región con contexto/sticky cuando comparar es esencial; si no, grupos de definición apilados. Nunca desplaza el `body`. |

Cuando la acción por fila es un menú de tres puntos, ese menú es un control y no
una columna de datos: se mantiene al inicio en un track fijo de 56 px, fuera del
reparto proporcional, con encabezado visualmente vacío y nombre accesible
**Acciones**. La celda detiene `click`/`auxclick` para no activar una fila
navegable, pero no cancela gestos de movimiento: el wrapper debe conservar el
paneo lateral iniciado sobre el botón. La decisión de producto del 2026-09-26
consolidó así todas las tablas y listas de Contabilidad: el kebab va solo en su
track y abre un modal cuya primera entrada es «Detalle e historial», seguida de
«Ver nota» cuando el registro tiene nota. Las tablas con iconos sueltos fuera de
Contabilidad siguen pendientes de la misma migración.

Como el track del kebab sólo se sostiene con `table-layout: fixed`, una tabla
`menu-start` con política responsive no emite `<col>` para las columnas de
datos (un `<col>` sigue siendo una columna aunque sus celdas estén ocultas).
Por debajo de 1024 px usa layout auto con columnas de datos sin ancho: los
valores atómicos conservan su ancho de contenido y la columna primaria absorbe
el resto. Desde 1024 px usa layout fijo y cada perfil reparte el 100 % entre las
columnas que muestra.

### 4.2 Tabs, filtros y navegación secundaria

- Se considera **alta cardinalidad** cuando hay más de cuatro opciones o cuando
  las etiquetas no caben en una fila a 835 px.
- Alta cardinalidad usa selector en los dos modos inferiores. El selector lleva
  nombre accesible y muestra la opción activa, badges y estado disabled.
- Desde 1024 px puede usar tira. Puede envolver como máximo en dos líneas; la
  tercera línea activa agrupación/overflow o conserva el selector.
- Una tira de baja cardinalidad puede permanecer visible si todas las opciones
  caben sin recortar texto ni acciones.
- Tabs y filtros no se resuelven con `overflow: hidden`; ocultar una opción es
  equivalente a perder navegación.

### 4.3 Modales

- Todo modal nuevo o migrado usa `BaseModal`; no duplica Teleport, backdrop,
  z-index, Escape, focus trap ni scroll lock.
- En 412 px ocupa el ancho disponible menos 32 px. En tableta/desktop respeta el
  tamaño semántico (`sm`…`5xl`) y nunca excede `calc(100vw - 32px)`.
- El panel mide como máximo 90dvh. En formularios largos, header y footer quedan
  visibles y solo el cuerpo scrollea cuando sea necesario.
- Confirmaciones siguen siendo pequeñas. Workspaces pueden usar `fullHeight` y
  `full`, ya topado en 1600 px.
- Los campos internos aplican la regla de 280 px; una grilla de dos columnas no
  se conserva por el solo hecho de cruzar `sm`.

### 4.4 Formularios

- Una columna en celular. En tableta vertical se admiten dos únicamente si el
  contenedor —incluidos padding y gap— deja 280 px útiles por campo.
- Pares cortos y relacionados pueden compartir fila; textarea, uploads,
  markdown, mensajes y campos que dependen del ancho ocupan fila completa.
- Label, control, hint y error pertenecen al mismo campo y no se reordenan.
- `BaseFormRow` es la estructura canónica; `at="md"` o una futura condición por
  contenedor se usa donde el modal no alcanza el mínimo.

## 5. Inventario priorizado

### 5.1 Criterio de prioridad

| Prioridad | Criterio |
|---|---|
| P0 | Impide navegar u operar en un viewport obligatorio; contenido o acción queda inaccesible sin alternativa. |
| P1 | Rompe una tarea principal o se repite transversalmente; exige corrección en la siguiente ola correspondiente. |
| P2 | Degrada claridad/espacio pero conserva una alternativa operable; se corrige después de las bases. |
| P3 | Pulido visual sin pérdida funcional ni relacional. |

### 5.2 Hallazgos

| ID | P | Tipo | Qué se rompe y evidencia | Módulos/rutas | Destino |
|---|---:|---|---|---|---|
| RSP-01 | P0 | Tabs | `BaseTabs` cambia de select a tira en `md`; la tira usa `whitespace-nowrap` sin wrap ni scroll. Los editores con 8–12 tabs pueden ocultar navegación a 835/1195 px mientras el `body` no desborda. | Propuesta edit, Diagnóstico edit, Defaults | Inmediato compartido; absorbe PA-73. |
| RSP-02 | P1 | Navegación | El shell muestra sidebar fija desde `md`. Una preferencia “expandida” persistida puede dejarla en 240 px a 835 px; se midieron solo 547 px útiles para la página. | Todas las superficies con layout admin | Inmediato compartido. |
| RSP-03 | P1 | Monitor | Solo 13 de 47 superficies consumen `PAGE_MAX_WIDTH`. A 2560 px, Propuestas llegó a 2256 px mientras Contabilidad se mantuvo en 1400 px. | Panel transversal, salvo las 12 rutas contables y Proyectos ya limitadas | Fase 1. |
| RSP-04 | P1 | Filtros/tabs | Contabilidad, filtros de propuestas y controles densos abandonan el selector en `md`. La subnav contable ocupó 3 filas/124 px a 835; el estándar permite selector allí y máximo 2 filas desde 1024. | Contabilidad, Propuestas, Clientes/filters guardados | Inmediato compartido; consolida PA-66/73. |
| RSP-05 | P1 | Tablas comparativas | Propuestas (`min-w-[800px]`), Diagnósticos (`min-w-[900px]`) y entregabilidad dependen de scroll horizontal sin una política explícita de columnas prioritarias. | Propuestas, Diagnósticos, Email deliverability | Fase 2. |
| RSP-06 | P1 | Listas exploratorias | QR y Linktrees siguen siendo tablas en compacto, aunque su tarea es recorrer entidades y ya existe el patrón de tarjetas en otros módulos. | QR Cards, Linktrees | Fase 2. |
| RSP-07 | P1 | Modales | Cinco páginas conservan overlays `fixed inset-0` propios; difieren en z-index, scroll, focus y composición. Clientes mezcla z-100 y z-9999; Propuestas repite tres overlays. Tareas y Defaults suman overlays desde componentes hijos. | Propuestas list/create/edit, Clientes, Admins, Blog edit, Tareas y Defaults | Fase 1; absorbe PA-45. |
| RSP-08 | P1 | Formularios | Persisten grillas manuales de dos columnas y filas sin el contrato de ancho mínimo. En el modal de Tareas a 412 px se observó overflow interno de 19 px y campos de 160 px. | Tareas, Admins, formularios/modales heredados | Fase 1; absorbe PA-45. |
| RSP-09 | P1 | Selección masiva | Propuestas y Diagnósticos muestran varias acciones inline en su barra bulk, en vez del contador + acción principal + menú canónico. | Propuestas, Diagnósticos | Fase 2. |
| RSP-10 | P1 | Workspace | Los editores de Documentos habilitan split en `lg`. Con 1195 px y sidebar expandida quedan ~891 px de página: dos paneles resultan de ~437 px, por debajo del mínimo de 480 px. Es una inferencia geométrica que debe fijarse con prueba de layout. | Documentos create/edit y previews multipanel equivalentes | Fase 3. |
| RSP-11 | P1 | Menús de acciones | Blog, Portfolio, Paquetes, LinkedIn, QR y Linktrees conservan varias acciones directas por fila; consumen el ancho que deberían usar los datos. | Listados indicados | Fase 2. |
| RSP-12 | P1 | Tablas anidadas | Clientes contiene seis tablas internas de 500/600 px sin política de prioridad ni representación compacta; los acordeones densos trasladan la carga al scroll. | Clientes | Fase 2. |
| RSP-13 | P2 | Panel de carpetas | Documentos apila correctamente bajo `lg`, pero a 1195 px el panel de carpetas por defecto (384 px) deja ~483 px al listado después del shell/handle. Es operable, pero queda en el límite. | Documentos | Fase 3; seguimiento de PA-61. |
| RSP-14 | P2 | Breakpoints JS/CSS | Conviven cortes JS de 768, 1023 y 1024 con clases `md`/`lg`; el mismo ancho puede recibir decisiones distintas entre CSS, composables y estado persistido. | Shell, Documentos, Blog/LinkedIn y consumidores de `useIsMobile` | Fase 1. |
| RSP-15 | P2 | Encabezados | QR y Linktrees usan headers horizontales que comprimen título y CTA en 412 px; no se pierde la acción, pero baja la jerarquía y aumenta el wrap accidental. | QR Cards, Linktrees | Fase 4. |
| RSP-16 | P2 | Tabla heredada | El overview contable conserva una tabla `min-w-[500px]` fuera del vocabulario de columnas de `AccountingTable`. | Contabilidad overview | Fase 2. |

## 6. Cobertura por módulo y ruta

`OK` significa que el patrón observado se conserva; no significa que la ruta
quede exenta de las deudas transversales del shell o ancho máximo.

| # | Ruta | Estado observado / hallazgos |
|---:|---|---|
| 1 | `/panel/login` | Superficie independiente del shell; sin rotura específica hallada. |
| 2 | `/panel` | RSP-02, RSP-03. |
| 3 | `/panel/views` | RSP-02, RSP-03, RSP-04. |
| 4 | `/panel/styleguide` | RSP-02, RSP-03; debe convertirse en fixture visual del estándar. |
| 5 | `/panel/defaults` | RSP-01, RSP-02, RSP-03, RSP-07, RSP-08. |
| 6 | `/panel/proposals` | RSP-02, RSP-03, RSP-04, RSP-05, RSP-07, RSP-09. |
| 7 | `/panel/proposals/create` | RSP-02, RSP-03, RSP-07, RSP-08. |
| 8 | `/panel/proposals/:id/edit` | RSP-01, RSP-02, RSP-03, RSP-07, RSP-08. |
| 9 | `/panel/proposals/email-deliverability` | RSP-02, RSP-03, RSP-05. |
| 10 | `/panel/clients` | RSP-02, RSP-03, RSP-04, RSP-07, RSP-12. |
| 11 | `/panel/blog` | RSP-02, RSP-03, RSP-11; `OK`: tarjetas compactas. |
| 12 | `/panel/blog/create` | RSP-02; `OK`: ancho de lectura intencional. |
| 13 | `/panel/blog/:id/edit` | RSP-02, RSP-07, RSP-10, RSP-14. |
| 14 | `/panel/blog/calendar` | RSP-02, RSP-03; `OK`: grilla cambia a lista en angosto. |
| 15 | `/panel/linkedin` | RSP-02, RSP-03, RSP-11, RSP-14; `OK`: representación compacta existente. |
| 16 | `/panel/portfolio` | RSP-02, RSP-03, RSP-11; `OK`: tarjetas compactas. |
| 17 | `/panel/portfolio/create` | RSP-02; `OK`: ancho de formulario intencional. |
| 18 | `/panel/portfolio/:id/edit` | RSP-02; `OK`: ancho de formulario intencional. |
| 19 | `/panel/qr-cards` | RSP-02, RSP-03, RSP-06, RSP-11, RSP-15. |
| 20 | `/panel/linktrees` | RSP-02, RSP-03, RSP-06, RSP-11, RSP-15. |
| 21 | `/panel/linktrees/:id/edit` | RSP-02, RSP-03. |
| 22 | `/panel/hour-packages` | RSP-02, RSP-03, RSP-11; `OK`: tarjetas compactas. |
| 23 | `/panel/hour-packages/create` | RSP-02, RSP-08. |
| 24 | `/panel/hour-packages/:id/edit` | RSP-02, RSP-08. |
| 25 | `/panel/documents` | RSP-02, RSP-03, RSP-13; `OK`: tarjetas, panel apilado y action sheet. |
| 26 | `/panel/documents/create` | RSP-02, RSP-03, RSP-10. |
| 27 | `/panel/documents/:id/edit` | RSP-02, RSP-03, RSP-10. |
| 28 | `/panel/admins` | RSP-02, RSP-03, RSP-07, RSP-08, RSP-11. |
| 29 | `/panel/emails` | RSP-02; `OK`: tres tabs y ancho de lectura limitado. |
| 30 | `/panel/diagnostics` | RSP-02, RSP-03, RSP-04, RSP-05, RSP-09. |
| 31 | `/panel/diagnostics/create` | RSP-02; `OK`: ancho de formulario limitado. |
| 32 | `/panel/diagnostics/:id/edit` | RSP-01, RSP-02, RSP-03, RSP-07, RSP-08. |
| 33 | `/panel/tasks` | RSP-02, RSP-03, RSP-07, RSP-08. |
| 34 | `/panel/projects` | RSP-02; `OK`: contenedor y tabla compartida. |
| 35 | `/panel/mcps` | RSP-02, RSP-03; `OK`: acordeones evitan una tabla ancha. |
| 36 | `/panel/accounting` | RSP-02, RSP-04, RSP-16; `OK`: máximo de página. |
| 37 | `/panel/accounting/incomes` | RSP-02, RSP-04; `OK`: tabla y bulk bar compartidas. |
| 38 | `/panel/accounting/expenses` | RSP-02, RSP-04; `OK`: tabla compartida. |
| 39 | `/panel/accounting/hostings` | RSP-02, RSP-04; `OK`: tabla compartida. |
| 40 | `/panel/accounting/collections` | RSP-02, RSP-04; `OK`: tabla compartida. |
| 41 | `/panel/accounting/pocket` | RSP-02, RSP-04; `OK`: tabla compartida. |
| 42 | `/panel/accounting/recurring` | RSP-02, RSP-04; `OK`: tabla compartida. |
| 43 | `/panel/accounting/ads` | RSP-02, RSP-04; `OK`: tabla compartida. |
| 44 | `/panel/accounting/cards` | RSP-02, RSP-04; `OK`: tabla compartida. |
| 45 | `/panel/accounting/statements` | RSP-02, RSP-04; `OK`: tabla compartida. |
| 46 | `/panel/accounting/history` | RSP-02, RSP-04; `OK`: tabla compartida. |
| 47 | `/panel/accounting/settings` | RSP-02, RSP-04; `OK`: máximo de página. |

Rutas sin superficie propia, excluidas del denominador de 47:

- `/panel/proposals/email-templates` → redirige a Defaults.
- `/panel/proposals/defaults` → redirige a Defaults.
- `/panel/diagnostics/defaults` → redirige a Defaults.

## 7. Consolidación de PA-45, PA-61, PA-66 y PA-73

Las fichas se conservan como trazabilidad, pero ninguna recibe una solución
local que compita con este estándar.

| Ficha | Estado técnico encontrado | Decisión |
|---|---|---|
| PA-45 — modales y saltos | El cierre del PR relacionado registró 35 filas migradas y 62 filas manuales restantes; el censo actual confirma que aún hay grillas y overlays divergentes. | **Dentro del plan, Fase 1** mediante RSP-07/08. No se adelanta como parche de un modal. |
| PA-61 — panel de carpetas | Documentos ya apila bajo `lg` y el panel es redimensionable (default 384 px). Pasa 835 px; a 1195 px el panel de contenido queda en el límite (~483 px). | **Dentro del plan, Fase 3** mediante RSP-13 junto con los workspaces. No urgente. |
| PA-66 — tira de filtros | `ProposalFilterTabs` ya envuelve y eliminó el corte funcional previo. El nuevo estándar amplía el selector hasta 1023 px. | La corrección previa se conserva; el ajuste de 835 px entra en el **PR inmediato compartido** RSP-04, no en otra variante. |
| PA-73 — tabs contables móviles | El selector actual resolvió el celular, pero termina en `md`, por lo que 835 px vuelve a una tira de tres filas. | **Adelantar por urgencia** dentro del mismo PR transversal RSP-01/02/04; no como fix exclusivo de Contabilidad. |

Referencias históricas de implementación: PR
[#176](https://github.com/gustavop-dev/projectapp/pull/176),
[#194](https://github.com/gustavop-dev/projectapp/pull/194),
[#210](https://github.com/gustavop-dev/projectapp/pull/210) y
[#219](https://github.com/gustavop-dev/projectapp/pull/219).

## 8. Orden de ejecución

Esta Fase 0 no modifica producto. El trabajo se divide en PRs de responsabilidad
única y todos se evalúan contra este documento.

| Ola | Hallazgos | Entrega |
|---|---|---|
| Inmediata | RSP-01, RSP-02, RSP-04 | Unificar shell y controles densos: drawer/selector hasta 1023 px y tira/sidebar desde 1024 px. Regresión en 412, 835 y 1195. |
| Fase 1 — Fundaciones | RSP-03, RSP-07, RSP-08, RSP-14 | Contenedor global, modal único, filas de formulario y fuente única de umbrales semánticos. |
| Fase 2 — Listas y acciones | RSP-05, RSP-06, RSP-09, RSP-11, RSP-12, RSP-16 | Clasificar tablas, priorizar columnas, adoptar tarjetas/kebab/action sheet y bulk bar canónica. |
| Fase 3 — Workspaces | RSP-10, RSP-13 | Mínimos de panel, reglas de split/stack y panel de carpetas. |
| Fase 4 — Pulido | RSP-15 | Headers y densidad residual después de estabilizar los patrones. |

El PR inmediato es separado de este documento. La urgencia no amplía su alcance:
no incluye migraciones oportunistas de tablas, formularios o modales.

## 9. Definición de terminado para las fases siguientes

Cada lote responsivo debe:

1. Declarar qué IDs RSP cierra y qué patrón canónico aplica.
2. Probar las superficies dueñas en **412×915, 835×1195, 1195×835,
   1440×900 y 2560×1440**.
3. Afirmar programáticamente `scrollWidth <= clientWidth` en documento/shell.
   Si una tabla conserva scroll interno, probar que el scroll pertenece solo a
   ese wrapper y que identidad/acción siguen accesibles.
4. Verificar navegación por teclado, foco, cierre y restauración del foco cuando
   toca modal, selector, dropdown o action sheet.
5. Verificar al menos un nombre largo, un importe largo, estado vacío, loading y
   error relevantes para la superficie.
6. Actualizar los tests E2E dueños del flujo; no crear un flow “responsive”
   separado que duplique la interacción funcional.
7. Ejecutar build y slices focalizados, nunca la suite completa.
8. Actualizar este inventario: cerrar el ID con evidencia o registrar el residual
   explícito. “Se ve bien” no es criterio de aceptación.

## 10. Evidencia de auditoría

### 10.1 Censo estático

- 50 páginas Vue bajo `frontend/pages/panel`; 47 renderizan UI y 3 redirigen.
- 13/47 páginas usan `PAGE_MAX_WIDTH`: las 12 de Contabilidad y Proyectos.
- 11 páginas contienen tablas literales; solo Blog, Portfolio, Paquetes de horas
  y LinkedIn ya ofrecen rama compacta de tarjetas.
- 10 páginas consumen la familia compartida `AccountingTable`.
- 11 páginas usan `BaseModal`; 5 páginas todavía declaran overlays propios.
- Las fuentes del patrón están en `frontend/utils/tableLayout.js`,
  `frontend/components/base/BaseModal.vue`, `BaseTabs.vue`, `BaseFormRow.vue`,
  `frontend/components/accounting/BulkAssignBar.vue` y los componentes de
  Documentos.

### 10.2 Recorrido de navegador

Se ejecutó un recorrido local con Nuxt y APIs simuladas, usando exactamente los
cinco viewports. Resultados reproducibles más relevantes:

| Viewport/superficie | Medición |
|---|---|
| 835, Contabilidad con sidebar expandida persistida | Sidebar 240 px; página 547 px; subnav 3 filas/124 px. |
| 1195, Contabilidad | Página 891 px; subnav 2 filas/80 px. |
| 1440, Contabilidad | Página 1136 px; subnav 2 filas/80 px. |
| 2560, Propuestas vs. Contabilidad | Wrapper de Propuestas 2256 px; raíz contable 1400 px. |
| 412, modal de Tareas | Modal 380 px; contenido interno 399 px; campos de la grilla 160 px. |
| 412, tabla de Propuestas | Wrapper 380 px; tabla 942 px; el documento no desbordó porque el scroll quedó interno. |

El harness local completó los cinco viewports y expuso las diferencias de la
tabla anterior; se hicieron dos repeticiones focales para corregir/confirmar la
instrumentación de 2560 y 1440. Producción
respondió HTTP 200 y no fue mutada. No se navegó el panel autenticado de
producción porque esta sesión no recibió una sesión autorizada; por eso el censo
de las 47 rutas se completó contra el código real y la comprobación visual se
hizo en entorno local simulado.

## 11. Fuente de verdad

Desde esta fase, una solución responsiva es válida si:

- aplica uno de los patrones de la sección 4;
- cierra un hallazgo de la sección 5 sin abrir otro en la matriz de rutas;
- pasa la definición de terminado de la sección 9.

Si aparece un caso no cubierto, se añade primero al estándar y se decide si es
una nueva clase de patrón. No se resuelve de forma aislada dentro del módulo.

## 12. Conciliación final — Fase 5

La auditoría sobre las cinco fases integradas en `main` cerró la contradicción
entre este inventario histórico y el estado actual. El resultado detallado por
criterio y módulo vive en
`docs/audits/2026-08-22-responsive-phase-5-final.md`.

- RSP-01–06 y RSP-08–16 cumplen el patrón canónico.
- RSP-07 cumple de forma distinta: `BaseModal` es canónico y tiene adopción
  mayoritaria, pero todavía existen overlays locales. Su migración queda en
  RSP-F5-03.
- PA-61, PA-66 y PA-73 tienen cierre técnico contra este estándar.
- PA-45 conserva trazabilidad, pero no puede considerarse migrada por completo
  hasta retirar o justificar los overlays residuales.
- La matriz automatizada usa viewports/touch emulados. La certificación exigida
  en hardware físico queda en RSP-F5-01 y no debe inferirse de Playwright.

Esta sección es el estado vigente. Las secciones 5, 6, 8 y 10 conservan la
fotografía de Fase 0 para trazabilidad y no describen deuda abierta actual salvo
los residuales enumerados aquí.
