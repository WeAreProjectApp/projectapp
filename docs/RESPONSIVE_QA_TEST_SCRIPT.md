# Guion consolidado de QA responsivo

**Estado:** obligatorio

**Cobertura automatizada:** 118 vistas × 5 perfiles = 590 celdas

**Fuente de verdad:** `frontend/config/viewCatalog.js`, `frontend/config/responsive.js` y `frontend/e2e/responsive/catalog-scenarios.js`

Este documento reúne la aceptación de PA-75 a PA-80 y sustituye los guiones
separados como punto de entrada operativo. Una vista sólo cuenta cuando su
escenario Playwright actúa sobre la interfaz, afirma un resultado concreto y
pasa el gate de calidad de `$qa`.

## Matriz canónica

| Perfil | Viewport | Riesgo principal |
| --- | ---: | --- |
| `compact` | 412 × 915 | orden de lectura, touch y overlays fullscreen |
| `portrait` | 835 × 1195 | tableta vertical y transición móvil/escritorio |
| `landscape` | 1195 × 835 | tabla/sidebar y altura limitada |
| `desktop` | 1440 × 900 | regresión del portátil habitual |
| `wide` | 2560 × 1440 | contenido centrado con máximo de 1400 px |

El catálogo vigente contiene 100 vistas renderizables y 18 redirects. Las
primeras producen 500 resultados visuales; los redirects producen 90 resultados
de compatibilidad y nunca acreditan layout, tablas o modales.

## Preparación determinista

- Usar los mocks del escenario; no depender de datos de producción.
- Las rutas dinámicas deben resolver `:id`, `:slug`, `:uuid`, `:handle` y
  `:deliverableId` con fixtures estables.
- Incluir en listados un nombre de cliente largo, una cadena sin espacios y un
  monto de muchos dígitos.
- Empezar cada caso arriba de la vista, sin overlays abiertos y con zoom 100 %.
- Montar los mocks antes de navegar y esperar `domcontentloaded` más un elemento
  específico; nunca usar `networkidle` ni sleeps arbitrarios.

## Invariantes aplicables a toda vista visual

1. Se muestra el contenido o valor concreto declarado por el escenario.
2. `scrollWidth - clientWidth` del documento es como máximo 1 px.
3. El contenido principal del panel no supera 1401 px en `wide`.
4. La navegación activa, CTA y primer resultado son alcanzables sin scroll lateral.
5. Los controles marcados para touch miden al menos 44 × 44 px.
6. Ninguna acción depende exclusivamente de hover o drag.
7. Texto, montos, badges, etiquetas y botones no se superponen ni pierden palabras.
8. Una tabla conserva, agrupa u oculta columnas según su prioridad declarada;
   nunca corta una columna sobre la vecina.
9. Tabs y filtros mantienen visible el activo, sus conteos y el mecanismo de
   selector/desborde.
10. Los modales respetan su `kind`, apilan el formulario, son fullscreen en
    `compact` y mantienen título, error y acción final alcanzables.

## Inventario por módulo

| Dueño | Vistas | Recorrido obligatorio adicional a la celda de catálogo |
| --- | ---: | --- |
| Foundation | 2 | drawer/sidebar, tabs, filtros, tabla, modal y selección del styleguide |
| Accounting | 12 | doce tabs, indicadores, agrupación, filtros guardados y modales largos |
| Documents | 2 | carpetas, activo/archivado, listado y acciones de fila |
| Clients | 34 | filtros de dos niveles, tarjetas, administración y plataforma autenticada |
| Projects | 3 | listado, crear/editar, cambio guiado de cliente y seguimiento de monitoreo |
| Commercial | 19 | propuestas, diagnósticos, paquetes, módulos adicionales y financiación |
| Emails | 3 | compositor, adjuntos, preview, historial y entregabilidad |
| Communications | 2 | ordenar, abrir hilo, leer estados/adjuntos y registrar mensaje; abrir un enlace seguro y ver su contenido |
| Canvas | 2 | metadata, editor/preview y guard de salida |
| Dashboard | 4 | pulso, radar, tareas, admins, estadísticas y mapa de vistas |
| Content | 11 | blog, LinkedIn, portafolio, QR y linktrees |
| MCP | 1 | expandir conector, actividad/tools, token y activación |
| Public | 23 | marketing, contacto, legales, blog, portafolio, experiencias compartidas y enlaces seguros |

## Contabilidad: decisiones de los doce tabs

| Tab | Resultado que debe permanecer en los cinco perfiles |
| --- | --- |
| Resumen | Utilidad líquida prioritaria; detalle de indicadores alcanzable; Mes y Utilidad se conservan. |
| Bolsillo | En `compact` usa tarjetas con Concepto, Valor y **Saldo después**; en `portrait` vuelve la tabla priorizada y desde `landscape` existe columna independiente de Saldo. Con filtros se lee **Acumulado filtrado**. |
| Ingresos | Concepto y Total permanecen; cliente, tipo, cobro, mes, origen y proyecto se agrupan. Lista/Agrupada conservan una sola acción inicial. |
| Gastos | Concepto y Total permanecen; período, categoría, contabilidad y repartos se agrupan. |
| Hostings | Cliente, Valor/mes y Estado permanecen; dominio y vigencia vuelven desde `landscape`; el menú conserva ciclos, cobro, correos, editar y eliminar. |
| Cuentas de cobro | Número, Total y Estado permanecen; cliente y vencimiento vuelven desde `landscape`; Lista/Agrupada comparten el menú completo. |
| Recurrentes | Nombre y equivalente COP mensual permanecen; encabezado de categoría, subtotal y participación se leen completos. |
| Ads | Plataforma y Valor permanecen; fecha, tarjeta, participación y acumulado se agrupan. |
| Tarjetas | Tarjeta y Deuda permanecen; fecha, disponible, uso y notas se agrupan. |
| Extractos | Cuadrícula mensual 2/3/4 columnas; Comercio y Valor identifican la transacción angosta y el menú móvil conserva todas las acciones. |
| Historial | Cambios y Correos siguen alcanzables; Registro/Acción y Destinatario/Estado mantienen la identidad al expandir. |
| Configuración | Destinatarios, plantillas y tarjetas apilan formularios; las acciones son ancho completo sólo en `compact`. |

Los seis recorridos de formularios largos se abren en los cinco perfiles como
escenarios especiales: nueva cuenta de cobro en dos pasos, liquidar ingreso,
registrar abono múltiple, nuevo ingreso con orígenes/bloques condicionales,
Hosting con alta de cliente inline y Extractos con edición de encabezado más
alta de transacción. La decisión de **Saldo después** se prueba en `compact`;
agrupación y filtros guardados se prueban además en `portrait`, donde cambia el
mecanismo de acceso.

## Recorridos especiales restantes

- **Documentos:** abrir/cerrar drawer, cambiar activo/archivado y operar carpeta
  y documento; en `compact` no existe columna lateral fija.
- **Canvas:** editar metadata, alternar editor/preview y activar el guard de salida.
- **Clientes:** aplicar ambos niveles de filtro sin ocultar el primer cliente y
  abrir su acción/reasignación.
- **Proyectos:** abrir crear/editar y leer la vista previa de impacto antes de
  confirmar un cambio de cliente.
- **Comercial:** buscar/filtrar, usar acción de fila y selección múltiple, abrir
  formulario, preview y confirmación.
- **Emails:** completar destinatario/asunto, adjuntar, abrir preview y volver.
- **Comunicaciones:** cambiar orden, abrir hilo, volver conservando el criterio y
  comprobar asunto, estado y adjuntos.
- **Dashboard/Contenido/MCP:** abrir una acción real de cada capacidad sin hover.
- **Públicas:** usar el CTA principal de landing, linktree, propuesta,
  diagnóstico y catálogo; ningún control flotante puede cubrirlo.

## Redirects

- `/panel/proposals/email-templates` → `/panel/defaults?mode=proposal&tab=emails`
- `/panel/proposals/defaults` → `/panel/defaults?mode=proposal`
- `/panel/diagnostics/defaults` → `/panel/defaults?mode=diagnostic`
- Las doce rutas de compatibilidad de plataforma, incluidas la entrada, el
  callback de impersonación, la cuenta de cobro dinámica y el detalle de
  entregable, no entran en loop. Diez aliases autenticados terminan en
  `/platform/projects`; el detalle de entregable termina en
  `/platform/projects/1/deliverables`; y el callback sin código termina en
  `/platform/login` como rama de error sin sesión.

## Ejecución

```bash
cd frontend
npm run check:responsive-contract
npm run e2e:responsive:batch -- --batch=accounting-visual-1
npm run e2e:responsive:batch -- --batch=accounting-special
npm run e2e:responsive:batch -- --batch=accounting-special-2
npm run e2e:responsive:batch -- --batch=accounting-special-3
npm run e2e:responsive
```

Cada batch de matriz contiene como máximo cuatro vistas y, por tanto, veinte
pruebas (cuatro escenarios × cinco perfiles). Los batches especiales también
se parten al llegar a veinte casos. Todos corren con cero reintentos; CI ejecuta
sólo los batches de los módulos afectados en PR, mientras que el comando
completo y la programación mensual recorren las 590 celdas más los especiales.

## Reporte y criterio de cierre

El reporter responsive emite una fila por `catalogKey × profile` con:

| Categoría | Vista | Perfil | Clase | Resultado | Evidencia |
| --- | --- | --- | --- | --- | --- |
| módulo dueño | archivo/ruta | alias y viewport | visual/redirect | `cumple`, `no cumple` o `cumple distinto` | test, error y artefacto |

Una ejecución completa exige 590 filas únicas, cero omitidas, cero duplicadas,
cero reintentos flaky, cero `draft-unvalidated`, cero junk-only y gate `$qa` limpio. Una variante
funcional se reporta como `cumple distinto` y no se convierte silenciosamente
en el estándar.

Para la campaña en dispositivos físicos, duplicar una fila por categoría y
anotar el equipo real; lo que falle siempre incluye la vista y el ancho útil:

| Categoría | Vista | Equipo / SO | Ancho útil | Resultado | Evidencia / variante |
| --- | --- | --- | ---: | --- | --- |
| Tablas, filtros, modales, navegación, acciones o módulo | ruta recorrida | modelo y versión | px | `cumple`, `no cumple` o `cumple distinto` | paso reproducible y captura |

## Límite de la automatización

Playwright garantiza el contrato de viewport, touch emulado y geometría
observable. No certifica teclado en pantalla, barras del sistema, safe areas o
particularidades de hardware real; esos datos sólo pueden registrarse mediante
una campaña física separada y nunca se infieren de un resultado E2E verde.
