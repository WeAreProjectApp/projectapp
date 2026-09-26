# Aceptación responsiva y guion de regresión

**Estado:** obligatorio desde 2026-08-22
**Alcance:** panel interno, plataforma autenticada y vistas públicas
**Contrato ejecutable:** `frontend/config/responsive.js` y `frontend/config/responsiveAcceptance.js`

Este documento define la aceptación implementada por PA-75 → fase 4.
Complementa el estándar de componentes de `responsive-standard.md`: ese
documento define cómo responde cada patrón; este define cómo demostrar que una
vista está terminada y cómo evitar que una entrega posterior reconstruya el
problema. La auditoría de Fase 5 y sus límites están en
`docs/audits/2026-08-22-responsive-phase-5-final.md`.

## Estado de implementación

El catálogo vigente deja 118 páginas Nuxt asignadas sin ambigüedad a 13
módulos de aceptación. Comercial, Emails, Comunicaciones, Canvas de Documentos,
Dashboard, Contenido, MCP y Públicas completan la adopción iniciada por
Fundamentos, Contabilidad, Documentos, Clientes y Proyectos. Las listas CRUD de exploración
usan tarjetas debajo de 1024 px mediante `BaseExploratoryList`; las superficies
comparativas usan `BaseResponsiveTable` y declaran la prioridad de cada columna.

Las fichas PA-45, PA-61, PA-66, PA-69, PA-70 y PA-73 dejan de ser variantes
independientes: su criterio de cierre es este contrato y sus primitives
compartidas. La línea base vigente se verifica con 118 escenarios explícitos,
13 módulos, cinco perfiles y 590 celdas catálogo×perfil: 100 vistas visuales
(500 celdas) y 18 redirects de compatibilidad (90 celdas), además del flow-map
funcional sin flows `junk-only` ni `missing`.

Esa línea base es automatizada: Playwright emula viewport y capacidades de
entrada. No prueba por sí sola teclado en pantalla, barras del sistema, safe
areas ni particularidades de hardware. La certificación física obligatoria
permanece abierta como RSP-F5-01.

## Condición de aceptación

Una vista nueva o modificada **no se considera terminada** hasta cumplir todo
lo siguiente en los cinco viewports canónicos:

| Perfil | Viewport | Riesgo que valida |
| --- | ---: | --- |
| `compact` | 412 × 915 | Lectura, orden, targets táctiles y overlays |
| `portrait` | 835 × 1195 | Tableta vertical; transición entre móvil y escritorio |
| `landscape` | 1195 × 835 | Tableta horizontal y altura limitada |
| `desktop` | 1440 × 900 | Portátil de uso diario |
| `wide` | 2560 × 1440 | Relación visual y ancho útil máximo de 1400 px |

La comprobación exige:

1. contenido y acción principal visibles;
2. cero overflow horizontal del documento;
3. tablas con prioridad de negocio declarada, nunca inferida;
4. formularios en orden de lectura y overlays que caben o tienen scroll interno;
5. ninguna acción disponible únicamente por hover o drag;
6. targets táctiles de al menos 44 × 44 px cuando se declaran para aceptación;
7. contenido del panel limitado a 1400 px en `wide`;
8. un E2E de resultado real con tags `@flow:*`, `@responsive:<módulo>`,
   `@responsive-batch:*` y `@viewport:*`.

`npm run check:responsive-contract` falla si una página Nuxt no está en el
catálogo, si una vista no tiene exactamente un escenario, si cambia la matriz
de equipos, si una ruta dinámica queda sin resolver o si un batch supera cuatro
vistas. El workflow de PR determina los módulos afectados y ejecuta cada batch
en los cinco perfiles, con un máximo de veinte pruebas por proceso.

## Guion repetible por módulo

El detalle ejecutable vive junto al código para que CI y documentación no
mantengan listas divergentes. La matriz actual es:

| Módulo | Tag | Recorrido mínimo |
| --- | --- | --- |
| Fundamentos | `@responsive:foundation` | Navegación, tabs/filtros, tabla, modal y acciones compartidas |
| Contabilidad | `@responsive:accounting` | Doce tabs, filtros, fila representativa y modales largos |
| Documentos | `@responsive:documents` | Carpetas, activos/archivados y acciones de documento |
| Clientes | `@responsive:clients` | Estado, filtros, tarjeta/fila y reasignación |
| Proyectos | `@responsive:projects` | Búsqueda, alcance, formulario y cambio de cliente |
| Comercial | `@responsive:commercial` | Propuestas, diagnósticos, selección múltiple y paquetes |
| Emails | `@responsive:emails` | Composición, adjuntos, preview e historial |
| Comunicaciones | `@responsive:communications` | Orden, hilo, mensajes, estado, adjuntos y auditoría |
| Canvas | `@responsive:canvas` | Metadata, editor/preview, guardado y guard de salida |
| Dashboard | `@responsive:dashboard` | Pulso, radar, cifras, estadísticas y acciones rápidas |
| Contenido | `@responsive:content` | Blog, calendario, LinkedIn, portafolio, QR y linktrees |
| MCP | `@responsive:mcp` | Conector, actividad, tools, token y activación |
| Públicas | `@responsive:public` | Marketing, blog, portafolio, linktree, propuesta y diagnóstico |

Para repetirlo localmente:

```bash
cd frontend
npm run check:responsive-contract
npm run e2e:responsive:batch -- --batch=commercial-visual-1
npm run e2e:responsive:batch -- --batch=accounting-special-2
npm run e2e:responsive:changed
```

La segunda orden ejecuta un batch (máximo cuatro vistas) en los cinco perfiles.
La tercera ejecuta un sublote especial de hasta veinte interacciones; la cuarta
resuelve el diff contra `origin/main`. Un cambio transversal ejecuta
todos los batches. Cada perfil se declara en el spec mediante `test.use`, por lo
que los tests no responsive ya no se multiplican mediante projects globales.

El guion completo, incluidos los recorridos especiales y el formato del reporte,
vive en [`docs/RESPONSIVE_QA_TEST_SCRIPT.md`](../RESPONSIVE_QA_TEST_SCRIPT.md).

## Cierre de fichas adelantadas

Una ficha previa de responsividad sólo se cierra cuando:

- su pantalla usa el patrón canónico o documenta por qué el caso es distinto;
- no conserva una media query, selector o modal paralelo que replique la
  primitive compartida;
- el comportamiento coincide con el resto del módulo en `compact`, `portrait`
  y `landscape`, no sólo en celular;
- su flujo representativo queda dentro del tag responsivo del módulo;
- el gate del contrato y el E2E focalizado quedan verdes.

Esto aplica expresamente a PA-45, PA-61, PA-66, PA-69, PA-70 y PA-73. Una
solución adelantada se adapta al estándar; no se convierte en una excepción
por haber llegado primero.

## Automatización y revisión periódica

`.github/workflows/responsive-acceptance.yml` ejecuta la aceptación automática:

- **PR y pushes a `main`/`master` con cambios en las rutas del workflow:** valida
  catálogo/propiedad y ejecuta sólo módulos afectados.
- **Mensual:** el día 1 a las 06:00 UTC ejecuta los trece módulos completos en
  los cinco viewports.
- **Ejecución manual (`workflow_dispatch`):** ejecuta la matriz completa.

La revisión semestral queda a cargo del equipo, sin creación automática de
issues. Debe contrastar los equipos canónicos con analytics y dispositivos
reales, revisar errores de CI por perfil, actualizar breakpoints sólo desde
`responsive.js` y dejar cualquier cambio de patrón en el estándar, el styleguide
y sus pruebas dentro del mismo PR. Cambiar un ancho en CSS sin actualizar esa
fuente no es una revisión válida. El guion manual y la certificación física
complementan las pruebas automáticas.

### Retiro del recordatorio `standards-review` — 2026-09-23

El job se agregó en el [PR #245](https://github.com/gustavop-dev/projectapp/pull/245)
el 2026-08-22 para abrir una issue, no para ejecutar pruebas. Sólo admitía el
cron de febrero/agosto, por lo que se omitía en los PR y en la corrida mensual.
El historial disponible no registra ejecuciones efectivas del job; la corrida
programada del 2026-09-01 también lo omitió. Por decisión del operador se retiran
el job y su cron semestral, conservando la aceptación automática descrita arriba.
En la revisión del 2026-09-23 no había ramas protegidas ni rulesets que exigieran
ese check. Las ejecuciones históricas conservan su estado omitido.

## Certificación física

El cierre automatizado y el cierre físico son evidencias distintas. Para cerrar
RSP-F5-01 se recorre este mismo guion en hardware real y se adjuntan, como
mínimo, navegador/sistema, viewport útil, orientación, teclado abierto donde
haya formularios, barras/safe-area y resultado de touch. La ausencia de
overflow en Chromium emulado no autoriza registrar esa pasada como realizada.
