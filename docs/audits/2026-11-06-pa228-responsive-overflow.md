# PA-228 — Ocho desbordes responsive del Panel

## Corte y responsabilidades

Base y reproducción original: `b01448a2d01a50dfb712f18c14cbc348b875621a`.
Rama `fix/06112026-pa228-responsive-overflow`, base `main`.
Chrome DEV aislado, claro y superusuario ficticio. No cambia el modelo de datos,
los cálculos, la autorización ni las rutas.

Implementación conduce automatizadas **exclusivamente en CI**, sin tests ni
servidores locales. DevQA administra el único DEV y sus datos. Backlog ProjectApp
realiza el recorrido mediante la extensión Chrome después de DEV LISTO,
manteniendo el SHA durante cada caso. Ninguna credencial forma parte del brief.

## Correcciones y aceptación

| Caso original | Corrección | Comprobación concreta |
| --- | --- | --- |
| RESP-R001, Dashboard | Grid acotado, hijos reducibles y gráfico al 100 % con redimensionado. | Chips y seis meses con datos caben en carga directa y escritorio → móvil sin recarga. |
| RESP-R013, Recurrentes | Calendario horizontal bajo 640 px, 32 px por día más 80 px para ejes; columnas desde tableta. Elección explícita del operador. | 31 etiquetas sin intersección, barras e importe del día 10; redimensionado con modal abierto. |
| RESP-R019, Blog | Nombre y URL apilados, acción dentro de su fila y campos reducibles con nombre accesible. | Tres acciones visibles; editar URL y quitar segunda fuente conserva la tercera. |
| RESP-R061, Detalle técnico | Selector acotado y acción apilada en móvil. | Elegir opción extensa, enfocar sin desplazamiento lateral e insertar módulo con el mismo título. |
| RESP-R061, Comunicación | Cabecera apilada, selector completo y acciones en fila propia compacta. | Ver master, cambiar plantilla, recargar iframe y cerrar con botón visible. |
| RESP-R061, Analítica | Títulos completos y metadatos distribuibles en ambos modos. | Doce recuentos y etiquetas «solo detallado»; Técnico conserva cero y «no visto». |
| RESP-R010, Ingresos Clásico | Total agrupado bajo Concepto en compacto; ajuste de importes y texto sin elipsis. | `$987.654.321.012 COP`, importe habitual y acción visibles sin scroll lateral; menú del registro correcto. |
| RESP-R010, indicadores | Una tarjeta por fila móvil y banda del importe expandible. | `$522.238.000 COP` y `$97.542.000 COP` completos al filtrar Perdido; cotejo con detalle. |

Interfaz aditiva: `valueWrap`, booleano default `false`, en `BaseIndicatorCard` y
`AccountingStatCard`. Ingresos lo activa en sus indicadores apilados; no cambia
el comportamiento predeterminado de los demás consumidores.

## Pruebas y revisión de flujos

Matriz **412×915, 835×1195, 1195×835, 1440×900, 2560×1440**. Los fixtures se
inyectan en la frontera HTTP; los componentes y gráficos son reales. Las
aserciones miden cajas y fragmentos de texto para detectar desborde y elipsis.

| Lote CI | Casos propios | Flujos registrados reutilizados |
| --- | ---: | --- |
| dashboard-special-1 | 5 | admin-dashboard |
| content-special-1 | 5 | admin-blog-edit |
| commercial-special-2 | 15 | admin-proposal-edit, admin-proposal-analytics |
| accounting-special-5 | 15 | admin-accounting-recurring, admin-accounting-income-crud |

Revisión `e2e-user-flows-check` acotada al diff: los ocho comportamientos
corresponden a estos seis flujos existentes en los shards y su mapa derivado.
No se añade interacción ni endpoint. Las regresiones se etiquetan `success` o
`display`; no acreditan validación/permisos (`error`) ni fallos del servidor
(`failure`) ajenos al cambio visual. IDs, descubrimiento, gate y ejecución se
validan en CI; resultados dinámicos y Chrome pendientes hasta tener evidencia.

Revisión `view-map-update --apply --diff`: no se agregan páginas, nombres,
propósitos ni capacidades; no corresponde editar catálogos o conteos por estos
ajustes de distribución. Sin nuevo camino de datos, no corresponde perf-pass.

## CI y entrega

PR [#566](https://github.com/WeAreProjectApp/projectapp/pull/566). Las corridas y
sus SHA se registran en el [comentario de validación](https://github.com/WeAreProjectApp/projectapp/pull/566#issuecomment-6692099659).
Contrato verde o job omitido no sustituye la ejecución de los cuatro lotes propios.

El Quality Gate del SHA `8cd97f7ec74bbb0742da65817d748bef4d989928`
[falló](https://github.com/WeAreProjectApp/projectapp/actions/runs/42269944845)
por un único error: `no_user_interaction` en la prueba de redimensionado del
Dashboard. El detector no clasifica `setViewportSize` como interacción. Se
documenta la excepción dentro del caso, conforme a las excepciones del estándar:
la acción reproducida es cambiar el tamaño de una ventana con el gráfico montado,
sin hacer clic ni recargar. Se conservan las aserciones de ancho, chips y meses.
No se modifica código de aplicación por este fallo del gate. Reprueba en CI
pendiente de la siguiente corrida; no acredita todavía ejecución E2E ni Chrome.

El SHA `72968198356e4189d7345d8c2a69fde57bd9bdfd` aprobó el
[Quality Gate](https://github.com/WeAreProjectApp/projectapp/actions/runs/42272273503).
La [corrida responsive](https://github.com/WeAreProjectApp/projectapp/actions/runs/42272273277)
aprobó los 15 casos propios de Contabilidad, los cinco de Blog y los diez de
preview/embudo de Propuestas. Fallaron cinco de Dashboard y cinco de inserción
técnica por expectativas incorrectas: el locale del navegador representa los
meses con punto (`may.`, `oct.`) y el generador existente añade `Alcance ampliado:`
al título. Las trazas acreditan esos textos reales; se corrigen las expectativas
sin cambiar la aplicación ni quitar comprobaciones de geometría. Dashboard pasa
a comprobar los seis meses completos. La espera del título erróneo alcanzó un
refresco posterior en el caso compacto; el título correcto se observa antes.
La nueva ejecución queda pendiente de su propio corte CI.

## Guion y cierre visible

Encargo inicial enviado directamente a dev-qa y preservado en
`projectapp-qa/devqa-mensajes/PA228-implementacion-a-devqa.md`; respuesta esperada
en `PA228-devqa-acuse.md`. DevQA confirmará post/propuesta 1 e ingreso 979 o sus
equivalentes efectivos. Repetir los ocho casos en claro, cinco tamaños, carga
directa y resize con los mismos datos. No enviar correos ni publicar contenido.

La sesión entrega PR abierto con CI verde, sin mergear. QA de rama no cierra el
ticket: `🧪 IN TEST` requiere main integrado y servido. Backlog emite `📦 CLOSE`,
`❌ REJECTED` o bloqueo con pasos, esperado/observado, captura y SHA; confirma
también Estado y carpeta del enlace.
