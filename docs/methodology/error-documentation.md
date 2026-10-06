## IVA mostrado como dinero en notificaciones (2026-10-06)

El formateador del historial trataba todos los campos Decimal como importes COP,
incluida la tasa de IVA. La tasa ahora se formatea por su campo antes de la rama
monetaria. Las lecturas normalizan únicamente el patrón antiguo conocido del IVA,
sin modificar registros históricos ni correos ya enviados.

## 2026-10-02 — MySQL rechaza el UUID de contexto durante el ensayo

`accounts/0067` agregaba una FK UUID a una tabla histórica cuyo DEFAULT era
`utf8mb4_0900_ai_ci`; el contexto nuevo heredaba `utf8mb4_unicode_ci` de la
base. MySQL exige collations compatibles en las dos columnas y devolvió 3780.
SQLite no detecta esta condición. El reemplazo `0067_delivery_context_mysql_compat`
ajusta sólo el DEFAULT antes de ejecutar las operaciones publicadas, sin
`CONVERT TO`, cambios de datos ni cambios de collation en columnas existentes.
Las instalaciones que ya aplicaron la original no repiten sus operaciones.
La regresión MySQL usa un servicio efímero de CI con datos inventados y sin
settings ni credenciales de producción; pytest mantiene su aislamiento SQLite.
Referencia: [reemplazos de migraciones en Django](https://docs.djangoproject.com/en/6.1/topics/migrations/#squashing-migrations).

## 2026-10-02 — Prefijo de idioma duplicado en enlaces de carpetas

`folderToFor` volvía a localizar `route.path`, que ya incluía el idioma, y
publicaba direcciones como `/en-us/en-us/panel/documents?folder=9`. El clic
simple usaba el store y ocultaba el defecto; abrir el enlace aparte lo exponía.
La corrección localiza `/panel/documents` una sola vez y conserva la query.
El E2E valida la dirección completa y la carpeta mostrada en español e inglés;
buscar sólo `folder=9` admitía la dirección inválida.

## 2026-10-01 — Compatibilidad del seguimiento contractual

Las tarjetas Kanban, `ProjectScopeItem`, comentarios e historial de tarjetas se
retiran mediante la purga autorizada; no equivalen a conformidades históricas.
Los consumidores deben usar etapa → fase de entrega → alcance → contrato y las
rutas nuevas. Una guía cambiada exige otra publicación antes de recibir resultados;
un conflicto de versión exige actualizar el seguimiento. Las conformidades
aprobadas y los PDF capturados no se sobrescriben. El reset fake debe limpiar
el grafo protegido antes de sus fuentes, bajo la capacidad explícita de pruebas.
Reglas y errores de dominio: [PLATFORM_DELIVERY](../PLATFORM_DELIVERY.md).

## 2026-09-29 — Anexos con contenido distinto a la propuesta revisada

- **Causa:** la formalización proyectaba campos permitidos, renombraba secciones,
  recalculaba importes y omitía partes de las condiciones comerciales y técnicas.
- **Corrección:** usar los generadores originales. El comercial sólo elimina
  seis secciones completas; el técnico conserva el contenido original. Markdown
  extrae el texto del PDF y el correo congela esos mismos anexos al prepararlos.
- **Validación:** comparación del texto completo de PDFs reales, exclusiones
  explícitas, secciones deshabilitadas, selección, condiciones, copia y adjuntos.
  Las preparaciones anteriores requieren nueva revisión sin sobrescribir archivos.

---

## 2026-09-29 — PDFs vencidos desde el panel

La pestaña General usaba la descarga pública por UUID, que devuelve 410 al
vencer la propuesta, también para personal autenticado. Los PDFs comercial y
técnico comparten ese control previo a la generación. La ruta administrativa
por ID permite obtener los mismos documentos mediante `IsAdminUser`; la pública
conserva el bloqueo con `proposal_expired`. El control flotante y el cierre
muestran el motivo o permiten reintentar errores de servidor/red. Los anexos
formales de Documentos tienen otro generador y no se cambian en esta corrección.

trigger: model_decision
description: Error documentation and known issues tracking. Reference when debugging, fixing bugs, or encountering recurring issues.
---

# Error Documentation — ProjectApp

This file tracks known errors, their context, and resolutions. When a reusable fix or correction is found during development, document it here to avoid repeating the same mistake.

> **Resuelto 2026-09-04 — la ayuda de pendientes por cobrar aparecía detrás
> del modal y sus candidatos no podían agruparse:** el tooltip se
> teletransportaba siempre a `body`, cuyo `z-index` quedaba fuera del stacking
> context del overlay del diálogo. Ahora usa el floating root provisto por
> `BaseModal`, con fallback global sólo cuando no tiene modal dueño. Gestionar
> candidatos reutiliza la tabla agrupada de Ingresos, calcula grupos y totales
> después de buscar, ofrece Cliente/Proyecto y Clásico, y reinicia la vista a
> Agrupado/Cliente en cada apertura.

> **Resuelto 2026-09-04 — elegir un color activaba la previsión sin consentimiento:**
> el serializer interpretaba `collection_confidence` como una selección implícita,
> aunque nivel de riesgo e inclusión son decisiones distintas. Ahora cada PATCH
> preserva el otro campo, el formulario los envía explícitamente y el interruptor
> sólo cambia desde su control. Un componente único dibuja círculo y estado neutro
> en todas las superficies; las duplicaciones empiezan limpias y no se reescriben
> filas históricas. El acceso rápido contable también dejó de priorizar Ads y
> dirige a Cuentas de cobro.

> **Resuelto 2026-09-04 — una propuesta podía enviarse sin explicar qué
> resolvía:** `email_intro` era opcional, vivía fuera del flujo de correo y el
> renderer sustituía su ausencia con copy genérico. **Correos** es ahora el
> dueño visible del mensaje; todos los límites de envío validan el texto antes
> de efectos, JSON/MCP/skills comparten el campo y cada entrega conserva su
> snapshot aunque el mensaje se edite después.

> **Resuelto 2026-09-04 — los compositores sólo permitían un destinatario y el
> historial duplicaría un envío múltiple:** cada superficie mantenía un string
> local y el modelo de trazabilidad no distinguía Para, CC y BCC. Un servicio
> compartido valida ahora los grupos y su límite antes del SMTP; el gateway
> conserva una fila por dirección bajo el mismo `delivery_id` y el historial
> elige una representante estable para contar, filtrar y paginar una sola vez.
> El snapshot guarda los encabezados visibles, por lo que el reenvío exacto los
> restaura sin inferirlos desde metadata ni confundir CC visible con la copia BCC
> automática.

> **Resuelto 2026-09-03 — cambios comerciales podían reinterpretar borradores
> y contratos anteriores:** guardar topes y porcentajes en una configuración
> mutable habría cambiado retroactivamente su validación y su texto. Las reglas
> viven ahora en revisiones append-only; cada otrosí congela política y tasa de
> conversión, y sólo un borrador puede adoptar manualmente la versión vigente.
> La adopción revalida montos, reconstruye el calendario y registra el cambio de
> versión dentro de una transacción.

> **Resuelto 2026-09-03 — previsión automática y hero contable poco legible:**
> “Pendiente por cobrar” dependía del mes corriente aunque la probabilidad real
> sólo la conoce el equipo, y el hero estiraba su columna alrededor de una
> gráfica dejando un vacío grande; varios textos de ApexCharts además heredaban
> colores ilegibles en dark mode. La previsión ahora es global y manual con
> selección + semáforo auditables, la analítica completa ocupa el hero en un
> acordeón y las opciones de tema se aplican en los nodos que ApexCharts consume.
> Un fixture E2E con doce utilidades en cero también se corrigió: el componente
> mostraba correctamente su empty state, por lo que no debía esperarse un canvas.

> **Resuelto 2026-09-02 — paridad MCP desigual:** `update_document` ya editaba
> Markdown correctamente, pero la capacidad era difícil de descubrir y los
> módulos no compartían contratos de riesgo, concurrencia, credenciales ni
> auditoría. Proyectos y varias superficies comerciales/de contenido carecían
> de conector, mientras Contabilidad concentraba un catálogo demasiado amplio.
> La plataforma común ahora agrupa las áreas, declara riesgo y resultados,
> limita credenciales por herramienta, confirma efectos sensibles y reutiliza
> las vistas, serializers y servicios del Panel en vez de abrir escrituras ORM
> paralelas. La regresión contractual deja propagar errores inesperados de
> resolución de rutas para evitar falsos verdes.

> **Resuelto 2026-09-03 — contratos firmados fuera de media pública:** el
> workspace de financiación no reutiliza el storage servido por `/media/`.
> `PRIVATE_MEDIA_ROOT` mantiene los archivos firmados fuera de Nginx y una vista
> autenticada para administradores controla cada descarga.

> **Resuelto 2026-09-02 — Compartir quedaba debajo del WhatsApp global:** las
> acciones flotantes del módulo de financiación y el acceso global ocupaban la
> misma esquina inferior derecha. Ambos se veían, pero WhatsApp interceptaba el
> puntero y hacía imposible compartir. El grupo PDF/Compartir reserva ahora una
> columna separada; el recorrido E2E verifica un clic real y la URL localizada
> escrita en el portapapeles.

> **Resuelto 2026-09-02 — abrir el documento no probaba una vista y los fallos
> de alerta eran invisibles:** el `GET` público incrementaba contador, primera
> vista y estado antes de que Vue confirmara que la página permaneció visible;
> además, encolar Huey era best-effort y no dejaba estado recuperable. Ahora la
> primera evidencia es un heartbeat validado tras cinco segundos visibles, toda
> su persistencia es atómica y el email mantiene estado, intentos, error y
> reconciliación durable. Analítica permite observar y reintentar un fallo; las
> vistas históricas quedan `legacy_unverified` para no inventar ni reenviar
> eventos. Un error de logging después de SMTP tampoco dispara correo duplicado.

> **Resuelto 2026-09-02 — un egreso creado llegaba verde por correo:** la
> plantilla de cambios contables elegía color por acción (`created` verde) y
> pintaba todo valor nuevo de verde, sin mirar la dirección financiera. Ahora
> el servicio clasifica ingreso/egreso/neutral; Bolsillo persiste su dirección
> en el evento para tareas y reintentos, y el template usa naranja para salidas,
> gastos y deuda. Los valores anteriores siguen rojos y el panel no cambia.

> **Resuelto 2026-09-02 — Creado no permitía ordenar el Gestor Documental:** el
> encabezado era estático y el backend sólo interpretaba `order=oldest` dentro
> de Archivados. La fecha visible ahora es también la clave canónica de orden,
> el icono alterna ambos sentidos en tabla y el control compacto conserva esa
> capacidad en Galería/móvil. Un refresh fallido no confirma ni la dirección ni
> la URL solicitadas.

> **Resuelto 2026-09-02 — una subcarpeta de proyecto encendía «Todos»:** el clic
> simple clasificaba cualquier subcarpeta como carpeta independiente y borraba
> `project`/`client`, aunque el usuario seguía dentro de esa entidad. Carpeta y
> entidad ahora se conservan juntas cuando su asociación coincide; sólo
> Carpetas propias o ajenas limpian los ejes, y el regreso del editor reutiliza
> ese origen completo.

> **Resuelto 2026-09-01 — la reacción de iconos se percibía como un borde:**
> el refinamiento previo dependía de un halo expansivo y sólo escalaba el glifo,
> por lo que no expresaba el pequeño salto solicitado. El primitive ahora anima
> presión, ascenso y aterrizaje exclusivamente sobre el contenido; el clic de
> puntero no pinta foco y reduced motion usa contraste estático. Copiar cambia a
> check únicamente después de que Clipboard API confirma la escritura.

> **Resuelto 2026-09-01 — vacío superior tras retirar el encabezado:** la vista
> pública ocultó correctamente el Navbar, pero conservó el padding que reservaba
> su altura. El catálogo ahora usa un ritmo superior propio, deja espacio sólo
> para su contenido y distribuye las acciones persistentes fuera del área útil
> del móvil. La regresión se cubre en los cinco anchos canónicos.

> **Resuelto 2026-09-01 — visor PDF extraído no resolvía en montaje aislado:**
> `PdfPreviewModal` confiaba en el auto-registro de componentes de Nuxt, por lo
> que Jest montaba el modal sin `PdfPreviewPane` y ocultaba iframe, error y probe.
> La dependencia ahora se importa explícitamente; los cuatro escenarios del
> modal y los cuatro del pane pasan. Los probes y cargas del workspace también
> descartan respuestas obsoletas para impedir que un documento anterior repinte
> la selección vigente.

> **Resuelto 2026-09-01 — avisos bajo Confirmar cambio:** el modal de transición
> acumulaba requisitos corregibles debajo del CTA y mezclaba contenido, impacto
> y acciones. Ahora los mensajes viven bajo estado, decisión de ingreso o nota;
> el preview conserva sus fallos en Revisar consecuencias, la confirmación los
> muestra con el impacto y el footer sólo contiene las dos acciones finales.

> **Resuelto 2026-09-01 — vistas internas y defaults del catálogo:** las
> aperturas del propio equipo podían contaminar las señales comerciales, el
> idioma inicial heredaba el locale del panel y el catálogo público conservaba
> el Navbar flotante. La corrección centraliza la detección de sesión staff en
> el backend, omite por completo esas escrituras en catálogo, propuestas y
> diagnósticos, fija español como punto de partida y oculta el Navbar en todas
> las rutas públicas de módulos adicionales. No se alteraron registros previos;
> un navegador sin sesión sigue siendo indistinguible de un cliente y se cuenta.

> **Prevención verificada 2026-08-31 — edición MCP de borradores:** no se abrió
> un incidente de producción. La herramienta rechaza mensajes enviados,
> recibidos, fallidos, anulados o entrantes antes de escribir; documentos de
> otro cliente y respuestas de otro hilo revierten toda la transacción y no
> generan una revisión engañosa.

> **Prevención verificada 2026-08-30 — preferencias de Comunicaciones:** la carga
> de preferencias no es una dependencia dura del listado; los defaults vigentes
> siguen disponibles si la API falla, un guardado fallido conserva el borrador y
> la navegación con cambios pendientes exige guardar, descartar o continuar.

> **Revisión 2026-08-29 — filtros prediseñados de Comunicaciones:** no se abrió
> un incidente de producción. La implementación evita tres regresiones conocidas
> del patrón: los ceros no se omiten, el conteo de una pestaña no hereda el corte
> activo y restablecer los builtins no elimina las vistas propias. Una respuesta
> anulada tampoco convierte un envío en respondido.

> **Resuelto 2026-08-29:** una propuesta abierta en una pestaña oculta seguía
> enviando snapshots cada 30 segundos y contabilizando tiempo no atendido. El
> tracker ahora finaliza una vez al ocultarse, pausa el intervalo, evita flushes
> solapados y sólo reanuda con un segmento nuevo al volver a ser visible.

> **Resuelto 2026-08-28:** los envíos nuevos archivan evidencia completa antes
> del SMTP. Los registros previos conservan honestamente su estado parcial o
> desconocido y nunca ofrecen un archivo regenerado como si fuera el original.

> **Revisión 2026-08-30 — catálogo adicional:** no se abrió un incidente. La
> ampliación conserva semilla por migración nueva, proyección bilingüe validada,
> PDF sin precios y preferencias locales acotadas. Los flujos esperan la
> hidratación de Nuxt y calientan rutas localizadas para no confundir una carga
> inicial lenta con una navegación rota.

---

## Format

```
### [ERROR-NNN] Short description
- **Date**: YYYY-MM-DD
- **Context**: Where/when this error occurs
- **Root Cause**: Why it happens
- **Resolution**: How to fix it
- **Files Affected**: List of files
```

---

## Known Issues

_Reviewed 2026-07-22 during the QA-campaign methodology refresh (fase 1): no new production incidents from the accounting-correctness / display-standards wave (#113–#116). KNOWN-001 and KNOWN-002 remain open (not re-verified this pass). The quality-gate DEFAULT-vs-strict mode pitfall surfaced by PR #113's red CI is a workflow lesson, captured in `lessons-learned.md` §21, not a runtime incident. Previous review: 2026-07-04._

### [KNOWN-001] kore_project Next.js server occupies port 3000
- **Date**: 2025-07-07
- **Context**: A Windsurf terminal runs `npm run dev --port 3000` for `kore_project`, which respawns after being killed
- **Impact**: Nuxt dev server can't bind port 3000; E2E tests fail intermittently
- **Workaround**: Run Nuxt on port 3001 with `E2E_PORT=3001`
- **Permanent fix**: Close the kore_project terminal in Windsurf IDE

### [KNOWN-002] usePlatformApi.test.js has 4 failing tests in JSDOM
- **Date**: 2026-04-03
- **Context**: `frontend/test/composables/usePlatformApi.test.js` — tests that assert `window.location.href` has changed after a redirect call
- **Root Cause**: JSDOM doesn't support real navigation; `window.location.href` stays as `http://localhost/` even after assignment
- **Impact**: 4 tests permanently fail in Jest/JSDOM environment; does not affect runtime behavior
- **Workaround**: Tests are known failures; excluded from quality gate pass/fail criteria
- **Permanent fix**: Mock `window.location` using `delete window.location` + `Object.defineProperty(window, 'location', { value: { href: '' }, writable: true })` before assertions

---

## Resolved Issues

### [ERR-058] Nuevo documento listaba en rojo lo que faltaba bajo su botón

- **Date**: 2026-09-26
- **Context**: `/panel/documents/create` mostraba «Escribe el título del
  documento.» y «Pega, escribe o carga el contenido Markdown.» como lista roja
  bajo **Crear Documento**, en cabecera y pie. La lista subía el botón y dejaba
  Cancelar centrado contra el bloque. El catálogo `/panel/documents/statuses`
  repetía el patrón en crear estado, crear grupo, guardar y fusionar.
- **Root Cause**: El barrido del 2026-08-29 (#315) aplicó el contrato de
  formularios a los modales de creación, pero la página Nuevo documento no es
  un modal. #330 dejó a propósito la mitad Documentos de `StateCatalogManager`
  con sus gates visibles. Las guías que aún recomendaban `BaseControlGate` para
  formularios corregibles sostenían la omisión.
- **Resolution**: Crear, guardar y fusionar siguen disponibles; tras el intento,
  `BaseFormField` muestra cada aviso bajo su campo, marca el control y se limpia
  al corregirlo, y el foco va al primer campo pendiente. En el catálogo, cada
  modo valida sólo los campos que pinta: documentos no exige descripción ni
  efecto operativo. `BaseControlGate` queda para la semilla que no se fusiona.
- **Files Affected**: `pages/panel/documents/create.vue`,
  `DocumentEditorContent.vue`, `StateCatalogManager.vue`, sus unitarias, los
  E2E de `admin-document-create` y `admin-document-states-manage`, los flows y
  las guías de `BaseButton`/`BaseControlGate`.
- **Verification**: unitarias focales de catálogo y editor; E2E de ambos flows,
  incluida la alineación de Cancelar/Crear en landscape y portrait.

### [ERR-056] La vista previa pública de una propuesta devolvía 500

- **Date**: 2026-09-04
- **Context**: Desde la edición de cualquier propuesta activa, la acción
  «Vista previa pública» abría `?preview=1` en otra pestaña, pero Nuxt mostraba
  su página de error 500 antes de cargar los datos de la propuesta.
- **Root Cause**: `useProposalTracking` devolvía `undefined` al detectar preview,
  mientras la página pública siempre desestructuraba su método `flush`. El fallo
  era de contrato frontend y no dependía del estado ni del contenido de la
  propuesta.
- **Resolution**: Mantener un objeto de retorno estable en preview con `refs`
  vacíos y un `flush` asíncrono no-op, retornándolo antes de registrar watchers,
  lifecycle hooks, storage o requests de tracking.
- **Files Affected**: composable y pruebas unitarias de tracking, spec E2E del
  modal de acciones, shard y documentación del flow.
- **Verification**: cuatro casos unitarios focales para `preview=1|true`; un
  recorrido Playwright desde el modal hasta el banner público, sin página 500;
  flow P1 cubierto en `display` y `success` y flow-map fresco.

### [ERR-054] La columna Creado no ordenaba el listado documental

- **Date**: 2026-09-02
- **Context**: El Gestor Documental mostraba una fecha por documento, pero el
  encabezado no tenía una acción de orden y `order=oldest` sólo afectaba el
  scope archivado.
- **Root Cause**: La UI trataba el orden como un control exclusivo de Archivados
  y la vista backend elegía la cláusula de orden a partir del scope, no de la
  fecha que la fila realmente exponía.
- **Resolution**: Unificar la semántica en `_display_sort_date`, aceptar
  `recent|oldest` en todos los scopes, propagar el estado explícitamente por las
  recargas del gestor y ofrecer controles accesibles en tabla y compacto. La UI
  sólo confirma el nuevo estado después de que la consulta termina bien.
- **Files Affected**: vista REST y pruebas de documentos, store/composable del
  gestor, página, `DocumentsTable`, specs unitarias/E2E y registro de flujos.
- **Verification**: 9 pruebas backend, 13 unitarias y 4 escenarios E2E focales;
  `admin-document-list` cubre `display`, `success` y `failure`, sin brechas.

### [ERR-055] Una carpeta asociada perdía el proyecto al navegar y volver

- **Date**: 2026-09-02
- **Context**: En el Gestor Documental, después de elegir un proyecto como
  Vástago, abrir una subcarpeta resaltaba «Todos». El origen incompleto se
  propagaba al editor y reaparecía al usar «Volver».
- **Root Cause**: El clic simple llamaba `manualFolderFilters` para todas las
  carpetas. Esa decisión borraba los ejes de entidad basándose en el tipo de
  interacción, sin comprobar que la carpeta destino seguía asociada al proyecto
  o cliente seleccionado; además divergía del `href` navegable de la fila.
- **Resolution**: Centralizar la decisión en `contextualFolderFilters`, conservar
  la entidad sólo cuando coincide con la asociación real de la carpeta y usar el
  mismo resultado para el estado y el enlace. Las Carpetas propias y las ajenas
  conservan la limpieza anterior.
- **Files Affected**: `frontend/utils/documentNavigationFilters.js`,
  `frontend/pages/panel/documents/index.vue` y sus pruebas focales.
- **Verification**: 20 pruebas unitarias, los 12 escenarios E2E de navegación y
  el build Nuxt pasan; el flujo P1 conserva cobertura `display`, `success` y
  `failure`.

### [ERR-056] Una cuenta de cobro emitida aparecía como un documento vacío

- **Date**: 2026-09-02
- **Context**: Liquidar una cuenta creaba correctamente el `Document` y su ruta,
  pero al abrirlo desde el Gestor Documental se mostraba el editor Markdown sin
  contenido.
- **Root Cause**: La cuenta se modela con snapshots contables y se renderizaba a
  PDF bajo demanda; nunca tuvo `content_markdown`. El gestor interpretaba la
  ausencia de `generated_file` como un documento editable ordinario y cada
  descarga podía volver a renderizar datos o plantillas posteriores.
- **Resolution**: Archivar un PDF con hash en la misma transacción de emisión y
  convertirlo en la única fuente para vista previa, descarga y correos. El
  editor reconoce el artefacto, muestra sus datos y conserva sólo las funciones
  ortogonales. Un backfill prioriza el adjunto exacto del historial de correo.
  También se acotó la geometría de los visores y se añadió navegación por la
  jerarquía de carpetas bajo el título.
- **Files Affected**: servicios/vistas de cuentas de cobro y Documentos,
  `collection_account_snapshot_service.py`, comando de backfill y editor Nuxt.
- **Verification**: pruebas focales backend/MCP/unit/E2E, build, contratos
  visuales, Django check y migración dry-run en verde.

### [ERR-053] El catálogo público conservaba el hueco del encabezado eliminado

- **Date**: 2026-09-01
- **Context**: Las rutas pública canónica y seleccionada ya no renderizaban el
  Navbar global, pero el índice comenzaba demasiado abajo, especialmente en
  celular.
- **Root Cause**: `CatalogView` conservó `pt-28 sm:pt-36`, espaciado heredado de
  la composición con encabezado, aunque ese elemento ya no existía.
- **Resolution**: Reducir el ritmo superior a `pt-12 sm:pt-16`, reservar espacio
  inferior para las acciones flotantes y verificar que el título empiece dentro
  de los primeros 150 px. Los controles usan áreas seguras y no reintroducen un
  shell global.
- **Files Affected**: `frontend/components/AdditionalModules/CatalogView.vue`,
  `frontend/e2e/public/additional-modules.spec.js` y
  `frontend/e2e/responsive/public.spec.js`.
- **Verification**: 16 escenarios funcionales y la matriz oficial de 20 casos
  en cinco viewports pasan sin retries.

### [ERR-052] El visor PDF extraído desaparecía fuera del runtime de Nuxt

- **Date**: 2026-09-01
- **Context**: La extracción de `PdfPreviewPane.vue` permitió reutilizar el PDF
  dentro del hilo, pero la regresión aislada de `DocumentPdfPreviewModal` no
  encontraba iframe, error ni llamada `fetch`.
- **Root Cause**: `PdfPreviewModal.vue` dependía únicamente del auto-import de
  componentes de Nuxt; Vue Test Utils no instala ese transform al montar el SFC.
- **Resolution**: Importar `PdfPreviewPane` explícitamente desde el modal y
  mantener tokens de generación en sus probes para ignorar resultados tardíos.
- **Files Affected**: `frontend/components/base/PdfPreviewModal.vue`,
  `frontend/components/base/PdfPreviewPane.vue` y sus pruebas focales.
- **Verification**: 8 pruebas de visor/pane y build Nuxt en verde.

### [ERR-051] El modal de cambio de estado acumulaba avisos bajo la confirmación
- **Date**: 2026-09-01
- **Context**: Panel de Proyectos, al revisar o intentar una transición con estado, decisiones de ingresos o nota pendientes.
- **Root Cause**: `applyBlockReasons` se renderizaba como un bloque rojo global dentro del footer, aunque cada razón pertenecía a un control distinto.
- **Resolution**: Mantener una única fuente de razones de bloqueo, proyectar cada mensaje mediante `BaseFormField`, separar errores de preview/aplicación y reservar `BaseModalActions` para Cancelar/Confirmar.
- **Files Affected**: `frontend/components/panel/projects/ProjectStateTransitionModal.vue`, sus pruebas unitarias y el flujo E2E `admin-project-lifecycle-states`.

### [ERR-050] El digest mostraba la representación técnica del cliente
- **Date**: 2026-09-01
- **Context**: Las líneas de ingresos esperados intentaban leer `full_name`
  directamente de `UserProfile`.
- **Root Cause**: Ese atributo no existe; el fallback `str(profile)` podía
  producir correo y rol en lugar del nombre que usa el resto del sistema.
- **Resolution**: Cargar `client__user` y resolver el texto mediante
  `build_client_display_name`, que prioriza nombre, empresa y correo.
- **Files Affected**:
  `backend/content/services/accounting_payment_calendar_service.py`,
  `backend/content/tests/services/test_accounting_payment_calendar_service.py`.

### [ERR-049] El catálogo de estados presentaba requisitos como una lista roja

- **Date**: 2026-08-31
- **Context**: En `/panel/projects/statuses`, crear, editar y fusionar mostraban
  bloqueos agrupados junto a la acción, lejos del campo que debía corregirse.
- **Root Cause**: `StateCatalogManager` usaba `BaseControlGate` tanto para datos
  incompletos y corregibles como para restricciones permanentes del catálogo.
  No mantenía estado de intento ni errores de serializer por campo.
- **Resolution**: El modo Proyectos usa `BaseFormField` para nombre, descripción,
  efecto operativo y destino de fusión; muestra validación local/API sólo tras el
  intento y la limpia al editar. Los estados semilla conservan un gate accesible
  porque su restricción no se resuelve completando el formulario. El modo
  Documentos permanece sin cambios.
- **Verification**: 6 pruebas unitarias, 14 escenarios Playwright del archivo
  afectado, guard de controles, build Nuxt y auditoría de flujos en verde.

### [ERR-048] Los iconos clicables no confirmaban la activación

- **Date**: 2026-08-31
- **Context**: Acciones icon-only, detectado inicialmente al copiar, podían
  ejecutarse sin una señal visible de que el clic se había registrado.
- **Root Cause**: Muchos controles usaban botones o enlaces crudos y los estados
  transitorios se implementaban por pantalla; no existía un primitive común que
  separara activación, trabajo pendiente y resultado.
- **Resolution**: Los controles migraron a `BaseButton`/`BaseActionButton`, con
  reacción inmediata, paridad táctil/teclado y reduced motion. Copiar usa
  `useClipboardFeedback` y sólo confirma éxito al resolver Clipboard API; el
  fallo presenta tono visible y conserva la notificación accionable.
- **Refinement (2026-09-01)**: La reacción común usa un ciclo de 420 ms con
  presión, salto vertical contenido y aterrizaje sobre un wrapper interno, sin
  desplazar el control ni animar su borde. Cada clic reinicia el ciclo,
  `focus-visible` reserva el anillo al teclado y reduced motion conserva sólo
  un cambio estático de contraste. Tras copiar con éxito, el glifo cambia
  temporalmente a check; ante fallo permanece en copiar para permitir reintento.
- **Verification**: 27 pruebas unitarias focales, dos escenarios Playwright de
  éxito/fallo, build Nuxt, parseo de 536 SFC y ambos guards de iconos en verde.
- **Refinement verification (2026-09-01)**: 19 pruebas unitarias focales del
  primitive, la acción canónica y clipboard; tres escenarios Playwright
  (éxito, fallo y reduced motion) sin reintentos; build Nuxt, tres guards
  estáticos, flow audit y registry en verde.

### [ERR-047] Los proyectos suspendidos ignoraban el control de archivados

- **Date**: 2026-08-30
- **Context**: Candle aparecía en el Gestor Documental al entrar aunque el
  interruptor visible estuviera apagado; ese mismo interruptor controlaba en
  realidad carpetas/documentos archivados, no el ciclo del proyecto.
- **Root Cause**: El grupo no operativo se renderizaba siempre y la interfaz
  presentaba un solo control para dos dimensiones independientes.
- **Resolution**: El catálogo incorpora «Ver proyectos no activos», local a la
  visita, apagado por defecto e inclusivo. «Ver archivados» conserva el scope de
  contenido y se mueve junto a Carpetas propias. Ocultar el grupo restablece a
  Todos si la selección dejaría de ser visible.
- **Verification**: pruebas unitarias cubren ambos ejes y la posición; el flujo
  E2E entra desde Panel, comprueba el default, revela Candle sin ocultar activos
  y valida el restablecimiento.

### [ERR-046] Los tooltips breves de acciones se partían letra por letra

- **Date**: 2026-08-30
- **Context**: Los rótulos de los iconos de acción aparecían como una columna
  vertical y dejaban de ser legibles.
- **Root Cause**: El tooltip compartido combinaba ancho intrínseco con
  `overflow-wrap:anywhere`; ese permiso de corte también reducía el ancho
  mínimo calculado para textos breves.
- **Resolution**: `BaseTooltip` conserva el wrap seguro como política por
  defecto y expone `contentClass`. Las acciones de carpeta migraron al único
  `BaseActionButton`, que selecciona una sola línea horizontal, teleporta al
  viewport y desactiva el `title` nativo; eliminar ya no expone dos tooltips.
- **Verification**: prueba unitaria de clases y escenario Playwright que comprueba
  `white-space: nowrap`, geometría horizontal y contención en viewport.

### [ERR-045] El catálogo documental mezclaba adopción histórica con visibilidad

- **Date**: 2026-08-30
- **Context**: Tras incorporar Proyectos y Clientes al Gestor Documental,
  algunas entidades aparecían duplicadas como carpetas manuales, otras no
  aparecían y seleccionar después una carpeta podía conservar filtros previos.
  Vástago parecía vacío aunque sus raíces históricas conservaban 10 carpetas y 58
  documentos en producción.
- **Root Cause**: La migración de esquema no adoptó las raíces existentes. El
  catálogo se reducía a entidades con contenido ya relacionado, la visibilidad
  dependía de metadata editable del estado y una señal podía provisionar una
  raíz histórica al guardar un proyecto. En el navegador, proyecto, cliente y
  carpeta manual no se trataban como ejes excluyentes.
- **Resolution**: Todo `Project` pertenece al mismo catálogo de Documentos y
  Comunicaciones; no existe un opt-out por módulo. El ciclo sólo decide el grupo
  activo/archivado. `DocumentFolder.managed_project` identifica la única raíz
  canónica. La adopción histórica usa un manifiesto v5 con conversiones,
  anidamiento explícito de Germán→Kore y asignaciones revisadas de documentos
  sueltos; Carlos y Gustavo permanecen intactos. Conserva huella completa,
  respaldo obligatorio y snapshot inverso. Las
  selecciones limpian siempre los otros ejes, y Carpetas propias muestra sólo
  raíces sin proyecto ni cliente. PRUEBA permanece visible para pruebas y Candle
  se presenta archivado por ciclo sin archivar sus documentos. El aviso técnico
  PA-108 se retiró del sidebar.
- **Files Affected**: modelos/serializadores/señales de proyectos, servicios y
  comando de conciliación documental, sidebar/filtros de Documentos, pruebas,
  mapa de flujos y runbook de producción.
- **Verification**: pruebas focales de servicios, endpoints, manifiesto y UI;
  la mutación de datos productivos queda separada tras despliegue, respaldo y
  revisión humana del plan.

### [ERR-044] Los avisos de creación competían con las acciones y no identificaban su campo

- **Date**: 2026-08-29
- **Context**: El modal Nuevo proyecto agrupaba nombre y cliente como una lista
  roja junto a Guardar; el estado ocupaba media fila pese a ser el único control
  y su ayuda contradecía el valor En desarrollo ya seleccionado. Otros modales
  repetían pies con bloqueos, etiquetas “(opcional)” y errores generales.
- **Root Cause**: La validación pertenecía al contenedor y a
  `BaseControlGate`, no al campo. Los controles no compartían un contrato para
  enlazar mensajes locales/API, y la creación de cliente en el autocomplete se
  mostraba sólo como resultado vacío.
- **Resolution**: `BaseFormField` conecta validación nativa o explícita mediante
  `role="alert"`, `aria-invalid` y `aria-describedby`; los formularios envían el
  intento y presentan cada error bajo su control. Proyecto usa una columna
  completa, estado inicial seleccionado sin ayuda redundante, creación al vuelo
  persistente y un footer exclusivo de acciones. Los modales de creación del
  panel adoptan el mismo patrón y la convención única de asterisco.
- **Files Affected**: primitivas `BaseFormField`/inputs,
  `ClientAutocomplete`, `ProjectFormModal`, páginas de Proyectos y modales de
  creación de Clientes, Tareas, Documentos, Contabilidad y contenido del panel.

### [ERR-043] Thread cards duplicated the complete latest message

- **Date**: 2026-08-29
- **Context**: `/panel/communications` rendered the latest message inside every
  list row, allowing long content to dominate the viewport and require an inner
  horizontal scroll before the operator could choose a thread.
- **Root Cause**: The generic responsive table remained the only list
  projection below landscape, and its scroll container combined a truncating
  identity cell with an unbounded two-line message body. The repeated **Hilo**
  label also spent compact height without distinguishing records.
- **Resolution**: Added a dedicated compact card projection with identity
  metadata, bounded overflow and no redundant label. Operator feedback then
  removed the remaining excerpt from both projections: **Asunto** now contains
  only the thread title, while message bodies remain exclusively in the
  workspace detail. The selected order stays validated and persisted with
  URL/saved-view precedence.
- **Files Affected**: communications list component, focused Jest and Playwright
  coverage, methodology and flow documentation.
- **Verification**: All 7 focused component tests and all 13 communications E2E
  scenarios pass; the subject-only 412×915 scenario passed on its first run and
  proves multiple visible cards with zero page overflow. The timeline scenario
  needed one unrelated cold-start retry before passing.

### [ERR-042] Proyectos estaba vacío aunque los documentos tenían proyecto

- **Date**: 2026-08-29
- **Context**: El Gestor Documental mostraba cero carpetas y documentos en
  Proyectos, mientras Carpetas contenía 39 raíces y el listado incluía
  documentos con proyecto asignado.
- **Root Cause**: La migración de esquema estaba aplicada, pero la conciliación
  de datos PA-108 nunca se ejecutó: producción tenía ocho proyectos y cero
  raíces `managed_project`. El sidebar lee esa raíz, no `Document.project`.
  Además, el filing generado conservaba un árbol físico paralelo que podía
  volver a dividir ambas relaciones. El filtro por nombres de estado no era la
  causa: siete proyectos pasaban el opt-out temporal que entonces existía.
- **Resolution**: Unificar el filing bajo la raíz gestionada, compartir claves
  estables para Cuentas de cobro/Propuestas, ampliar el manifiesto revisado para
  documentos elegibles y conflictos, impedir que el backfill cree raíces sin
  revisión, y conservar un diagnóstico interno que diferencia conciliación de
  un vacío real. Ninguna carpeta de producción se convierte durante el deploy ni
  desde el panel. ERR-045 retiró después el opt-out y el aviso técnico del
  sidebar.
- **Files Affected**: servicios y comando de carpetas/filing, endpoint de
  readiness, pruebas y registro E2E histórico.
- **Verification**: slices backend de servicio, comando, vistas, backfill y
  snapshots; la cobertura vigente del catálogo vive en los flows de navegación.
- **Lesson**: Una migración de esquema aplicada no demuestra que una migración
  de datos revisable haya ocurrido. Los vacíos operativos deben informar qué
  relación falta en lugar de parecer un estado normal.

### [ERR-041] Django wrapped the MySQL snapshot recovery in a transaction

- **Date**: 2026-08-29
- **Context**: After the URL-index hotfix reached `main`, the next
  `$deploy-and-check` stopped again at `content.0223_email_delivery_snapshots`
  while its recovery tried to remove the previously verified empty residue.
  The exception occurred before the first cleanup statement; service restarts
  were skipped and the existing runtime remained healthy.
- **Root Cause**: A migration is atomic by default. On a backend whose schema
  editor cannot roll DDL back, Django therefore wrapped the recovery
  `RunPython` in `transaction.atomic()`. MySQL correctly rejected its first DDL
  statement with `TransactionManagementError`.
- **Resolution**: Mark only the recovery `RunPython` as `atomic=False`. The
  following schema operations retain Django's normal migration semantics, and
  the existing fail-closed checks still prove that every artifact is empty
  before any cleanup.
- **Files Affected**: migration `0223`, its focused recovery tests and Memory
  Bank documentation.
- **Verification**: A behavioral regression applies the recovery operation with
  a non-transactional schema editor and proves that Django does not enter
  `transaction.atomic()`.
- **Lesson**: Recovery code that executes MySQL DDL must declare its own
  transaction boundary; checking that the data is safe is necessary but does
  not make the DDL transaction-compatible.

### [ERR-040] MySQL rejected the email-link snapshot index

- **Date**: 2026-08-29
- **Context**: `$deploy-and-check` fast-forwarded production `main`, installed
  requirements and stopped while applying `content.0223_email_delivery_snapshots`.
  The frontend build, `collectstatic` and service restarts were skipped, so the
  previous runtime stayed active and `/api/health/` continued returning 200.
- **Root Cause**: `EmailLinkSnapshot.url` permits 2048 characters and the migration
  declared a unique key on `(snapshot, url)`. With MySQL `utf8mb4`, the URL alone
  can require 8192 index bytes, above InnoDB's 3072-byte maximum. MySQL DDL is not
  transactional, so the failed migration remained unrecorded after creating the
  three empty snapshot tables, adding `EmailLog.snapshot_id` and earlier indexes.
- **Resolution**: Preserve the full URL as evidence, derive a 64-character SHA-256
  fingerprint on every model save and enforce `(snapshot, url_sha256)` in new
  migration `0228`. The link writer now uses the model save path. The start of
  `0223` detects the exact MySQL partial state and removes it only after proving
  all snapshot tables and references are empty; otherwise it aborts without DDL.
- **Files Affected**: email snapshot model/service, migrations `0223` and `0228`,
  focused model/migration tests, and Memory Bank documentation.
- **Verification**: A fresh test database applies the complete migration graph;
  8 focused model/recovery cases and 3 gateway regressions pass. The schema test
  pins the worst-case composite key below 3072 bytes.
- **Lesson**: Size indexed text by the production charset, not by character count.
  When MySQL can leave non-atomic DDL, recovery must recognize one known state,
  prove it contains no data and fail closed for every other state.

### [ERR-038] El historial de correos no conservaba los archivos enviados

- **Date**: 2026-08-28
- **Context**: El módulo Emails mostraba destinatario, asunto, estado y cuerpo,
  pero sólo algunas rutas dejaban nombres de adjuntos en metadata. No era posible
  demostrar qué bytes recibió el cliente, calcular el peso real ni reenviar con
  la misma evidencia.
- **Root Cause**: Los logs se escribían después del intento SMTP y no existía un
  modelo común para cuerpo, adjuntos, enlaces y procedencia documental. Consultar
  el `Document` o regenerar un PDF devolvía estado actual, no estado histórico.
- **Resolution**: El gateway captura un snapshot obligatorio antes del SMTP,
  conserva cada archivo con hash/tipo/tamaño, extrae enlaces y comparte la
  evidencia entre logs primarios y BCC. El historial diferencia captura exacta,
  evidencia legada parcial y ausencia desconocida; sólo lo capturado permite
  descarga, visor o reenvío. Los Documentos quedan enlazados y protegidos.
- **Files Affected**: modelos/migración de snapshots, gateway y servicios de
  historial/reenvío, APIs de Emails y Documentos, stores/páginas/modales, fake
  data, tests y registro E2E.
- **Verification**: 18 casos del historial backend, contratos del gateway,
  pruebas unitarias del store/modal/visor, build Nuxt y 7 escenarios Playwright
  focales pasan; el mapa está fresco y la auditoría reporta 0 flows missing.
- **Lesson**: La evidencia de una entrega se captura antes de cruzar el límite
  externo. Una versión actual o regenerada puede ser útil, pero no es historia.

### [ERR-039] Document titles and row actions emitted competing browser hints

- **Date**: 2026-08-28
- **Context**: A clipped document title needed its complete value without
  opening the editor, while the adjacent action control already combined a
  custom tooltip with a browser-native `title`. Native hints could be clipped by
  the table, were not controllable on touch and made actions show two notices.
- **Root Cause**: `BaseOverflowText` and `BaseActionButton` each delegated part
  of the contract to the browser instead of sharing one overlay owner;
  `BaseTooltip` remained absolutely positioned inside overflow containers. The
  first clipping measurement could also become stale after web fonts loaded.
- **Resolution**: Give `BaseTooltip` an opt-in teleported placement mode that
  flips and clamps inside the viewport; use it conditionally from measured
  document titles and unconditionally from catalog actions; suppress the native
  `BaseButton` title for those shared-tooltip owners. Repeat the measurement
  after `document.fonts.ready`, keep **Ver completo** as the explicit
  coarse-pointer path and preserve the generic persisted table resize contract
  at the inventory-backed 520 px maximum. The shared separator also publishes
  its accessible label as a discoverability hint.
- **Files Affected**: `BaseTooltip.vue`, `BaseOverflowText.vue`,
  `BaseActionButton.vue`, `BaseButton.vue`, `DocumentsTable.vue`, focused
  unit/E2E coverage and the document-title flow registry.
- **Verification**: Unit coverage checks clipping, single-tooltip ownership,
  viewport placement and teardown; Playwright checks clipped/complete titles,
  the action notice, touch expansion, persisted/reset widths, the current
  inventory boundary, font-ready remeasurement and fixed Estados/Acciones
  tracks.
- **Lesson**: A browser `title` is not a fallback for an application tooltip.
  One primitive must own placement and semantics, and every hover path needs a
  separate explicit touch path. Clipping must be rechecked after asynchronous
  font layout changes rather than papered over with a synthetic resize in E2E.

### [ERR-037] Panel action buttons rendered two competing tooltips

- **Date**: 2026-08-28
- **Context**: Hovering the three-dot action button in Documents showed the
  application tooltip and the browser-native tooltip at the same time. The
  application copy inherited the full accessible label, such as “Acciones de
  Contrato de Servicios”, and collapsed into an unreadably narrow box.
- **Root Cause**: `BaseActionButton` wrapped the control in `BaseTooltip` while
  also forwarding the same text as the button's native `title`. Its visual
  tooltip fell back to the contextual accessible name and had no intrinsic
  content width. Vue fallthrough attributes also meant that simply removing a
  template binding did not reliably suppress `title` at the rendered root.
- **Resolution**: Make `BaseActionButton` the only tooltip owner. Its visual copy
  now defaults to the short catalog label, its contextual `label` remains the
  `aria-label`, and `BaseButton.nativeTitle=false` filters `title` while
  forwarding every other consumer attribute. The tooltip uses intrinsic width
  with a bounded maximum.
- **Files Affected**: `frontend/components/base/BaseActionButton.vue`,
  `frontend/components/base/BaseButton.vue`, focused component tests and the
  Documents list/gallery E2E specs.
- **Verification**: Component coverage proves that no native `title` is emitted,
  focus exposes one tooltip named **Acciones**, contextual accessible names stay
  intact and explicit visual copy still wins. The list and gallery Playwright
  scenarios verify the same contract before opening their action menus; flow-map
  freshness and the qualifying-flow audit pass.
- **Lesson**: Visual help and accessible naming are separate contracts. A
  tooltip-owning primitive must also own native-title suppression, including
  Vue's automatic attribute fallthrough.

### [ERR-036] El catálogo inicial dejaba un modal alto y vacío

- **Date**: 2026-08-28
- **Context**: La asignación masiva ya cargaba clientes sin escribir y evitaba
  el recorte original, pero seguía presentándolos como un desplegable. Al abrir,
  el modal reservaba la altura necesaria para esa capa y mostraba un vacío hasta
  que el buscador recibía foco; al desplegarla, la información aparecía en el
  espacio que ya estaba reservado.
- **Root Cause**: El selector primario de una decisión masiva se modeló como un
  autocomplete flotante y el consumidor compensó su geometría con una altura
  mínima fija. Un overlay activado por foco no puede ser a la vez el contenido
  permanente que explica la decisión.
- **Resolution**: Añadir a `ClientAutocomplete` una presentación `catalog`
  explícita y en flujo, reutilizando el mismo motor de búsqueda, selección,
  paginación, vacío y errores. `BulkAssignModal` la activa sólo para clientes y
  elimina la altura reservada. El catálogo abre A-Z, permite alternar A-Z/Z-A,
  conserva el criterio en `localStorage`, muestra nombre/empresa/correo y deja su
  propia lista como único scroll; los demás selectores siguen flotando.
- **Files Affected**: endpoint/store de búsqueda de clientes,
  `ClientAutocomplete`, `ClientAutocompleteResults`, `BulkAssignModal` y sus
  pruebas backend/frontend/E2E.
- **Verification**: casos focales de orden y fallback del endpoint, contrato del
  store, siete estados del catálogo, modal y tres escenarios Playwright: cinco
  filas completas con revisión visible, persistencia entre aperturas y pantalla
  compacta 412×915 sin scroll del panel.
- **Lesson**: Cuando una lista es el contenido principal de una decisión, debe
  vivir en el flujo del modal; un desplegable sólo corresponde a información
  secundaria que el usuario decide invocar.

### [ERR-035] Cross-cutting proposal qualities were mixed into specific features

- **Date**: 2026-08-28
- **Context**: The public functional-requirements overview had only three core
  cards. Responsive design lived inside `features`, while other quality concerns
  had no explicit commercial container and could be repeated as generic
  boilerplate by proposal-generation prompts.
- **Root Cause**: The JSON contract modeled screens, components and specific
  behavior, but did not distinguish qualities that span multiple views and flows.
  The seller and technical prompts therefore had no stable id or traceability
  rule for contextual cross-cutting scope.
- **Resolution**: Added the bilingual `cross_cutting_features` group immediately
  after `features`, moved responsive design into it, made its starter items
  explicitly adaptable, protected only the container from deletion, and aligned
  commercial/technical prompt rules and item links. Migration `content.0222`
  updates defaults and active drafts while preserving historical snapshots.
- **Files Affected**: Proposal defaults/service, JSON template and generation
  prompts, functional-requirements editor, data migration, public/admin flow
  definitions and focused backend/frontend/E2E tests.
- **Verification**: Focused backend and frontend unit suites pass; both affected
  Playwright flows pass and remain fully covered in the flow audit.
- **Lesson**: A reusable quality catalog needs a stable structural boundary and
  contextual content rules; otherwise “generic” quickly becomes an unsupported
  promise copied into every proposal.
### [ERR-034] Nuxt generated a self-referential SPA fallback

- **Date**: 2026-08-28
- **Context**: Every non-prerendered panel route returned HTTP 200 but the browser
  never mounted the application. The generated `200.html` contained only a meta
  refresh to `/en-us/200.html`; Django served that same fallback for the target,
  creating an infinite redirect loop in the tab.
- **Root Cause**: After the Nuxt/i18n upgrade, browser-language detection with
  `redirectOn: 'no prefix'` also transformed Nitro's unprefixed `/200.html`
  fallback. Existing deployment checks proved only that the file existed and the
  route returned 200, not that the artifact was a usable Nuxt shell.
- **Resolution**: Keep browser-language detection disabled because Django owns
  the bare-root locale decision. `build:django` now validates `200.html` before
  its atomic swap and rejects empty output, meta refreshes, or documents without
  the `#__nuxt` mount point.
- **Files Affected**: `frontend/nuxt.config.ts`,
  `frontend/update-django-template.js`, `frontend/utils/spaFallback.js`, and its
  focused Jest regression tests.
- **Verification**: Four validator cases and the three panel fallback view cases
  pass. Both `nuxi generate` and the complete `build:django` path emit and accept
  an 8,235-byte SPA shell; production closure still requires merge and deploy.
- **Lesson**: A generated fallback is a deployment contract. Validate its
  behavior before publication instead of treating file existence or HTTP 200 as
  proof of frontend availability.

### [ERR-033] MySQL ignored DocumentState system-key uniqueness

- **Date**: 2026-08-27
- **Context**: `manage.py check --database default` emitted `models.W036` for
  `unique_state_system_key_per_catalog`; production had no physical constraint
  even though the model declared one.
- **Root Cause**: The composite unique constraint added a redundant
  `condition=Q(system_key__isnull=False)`. Django correctly skips conditional
  unique constraints on MySQL, so the predicate disabled the entire database
  invariant instead of only excluding `NULL`.
- **Resolution**: Use a plain unique constraint on `(catalog, system_key)`.
  Standard SQL/MySQL uniqueness already permits multiple `NULL` values. Migration
  `content.0218` checks every non-null pair for duplicates before replacing the
  state constraint, then creates the real MySQL unique key.
- **Files Affected**: `backend/content/models/document_state.py`, migration
  `0218_documentstate_mysql_unique_system_key.py`, focused model tests and Memory
  Bank documentation.
- **Verification**: Production data had zero duplicate pairs; `sqlmigrate` emits
  the expected MySQL `ALTER TABLE ... UNIQUE`; `manage.py check --database
  default` reports zero issues; constraint tests pass 4/4 and MCP contracts 19/19.
- **Lesson**: If absence is stored as `NULL`, first use the backend-portable
  nullable unique semantics. A partial unique predicate is both redundant and
  unsupported on MySQL.

### [ERR-032] Explorer idle context resolved to the root node

- **Date**: 2026-08-27
- **Context**: Opening any selected Explorer space or feature showed its orbit and breadcrumb correctly, but the new context panel displayed **Ecosistema ProjectApp** until a node received hover or focus. The guided-tour entry and technical disclosure were consequently absent.
- **Root Cause**: `findCapabilityNode(null)` intentionally resolves to the catalog root. The preview computed called it even when no transient node existed, so the root was always truthy and shadowed the stable selection.
- **Resolution**: Resolve a preview node only when `activeNodeId` is non-null, then fall back to the selected node. Preview remains ephemeral and URL-neutral.
- **Files Affected**: `frontend/components/views/ViewOperationalExplorer.vue`.
- **Verification**: Focused component cases now cover stable feature details, guided-tour entry and hover restoration; all 16 component cases pass and the Nuxt production build completes.
- **Lesson**: A lookup helper whose empty input means “root” cannot also encode the absence of transient UI state. Guard optional IDs before resolving them.

### [ERR-030] The Explorer preference migration initially left parallel leaves

- **Date**: 2026-08-27
- **Context**: Adding `explorer` to `ViewMapSettings.default_view_mode` required a
  schema-state migration after two independent `0215` merge migrations already
  existed on the integration base.
- **Root Cause**: Depending on only one `0215` node made the new migration a third
  terminal branch instead of converging the complete graph.
- **Resolution**: Migration `0216_viewmapsettings_explorer` depends on both current
  `0215` leaves before altering the field choices. No data migration is required.
- **Verification**: The focused settings API suite passes and
  `makemigrations --check --dry-run` reports no model drift or graph conflict.
- **Lesson**: A new state-only migration must depend on every current leaf when a
  repository already contains parallel merge nodes; sharing a number does not
  imply a shared descendant.

### [ERR-028] Unbroken document titles escaped their cell and covered Cliente
- **Date**: 2026-08-26
- **Context**: `/panel/documents` rendered real underscore/date names such as
  `Levantamiento_Fase_4_Multi-Tenant_24082026` beyond the Título cell. Folder
  metadata also shared the title's flex row, so both strings could paint over
  one another before the title reached Cliente.
- **Root Cause**: The layout relied on ordinary word boundaries and local
  `break-words`. An unbroken string retained a large intrinsic minimum, while
  several flex/table ancestors lacked the full `min-w-0`/bounded-content chain.
  The folder badge was a non-shrinking sibling competing for the same row.
- **Resolution**: Add semantic `wrap`/`truncate`/`atomic` policies to the shared
  table/list primitives; data strings now use `overflow-wrap:anywhere`, while
  bounded values remain atomic. Document titles use a contained one-line
  ellipsis with measured **Ver completo/Contraer** in both rows and cards; the
  expanded value wraps anywhere. Folder is first on its own metadata row, with
  compact Client/Project/State distinctions after it. Desktop rows without a
  folder reserve no blank metadata line. The same containment contract was
  adopted across the other operational panel lists and badges.
- **Files Affected**: `frontend/utils/tableLayout.js`, shared base table/list,
  overflow and badge primitives, Document table/cards, Task/Project/accounting
  list components, and panel list pages.
- **Verification**: Focused Jest slices cover the primitives and representative
  consumers; the full Document Playwright spec passes 11/11 using the three real
  unbroken names at 412×915, 835×1195, 1195×835, 1440×900 and 2560×1440. Nuxt
  build and the responsive/flow/static gates pass.
- **Lesson**: Overflow containment begins at intrinsic sizing, not at the final
  text node. Pair `min-w-0` through every flex/grid boundary with
  `overflow-wrap:anywhere`, and move independent metadata out of a title row.
### [ERR-027] Fake data could be partial, inconsistent and unsafe to replay

- **Date**: 2026-08-26
- **Context**: Seeders had drifted independently as Documents, accounting,
  hosting and Communications evolved. Some list modules had only a handful of
  rows, documents/accounts did not share their real origin graph, clocks and RNGs
  differed, and the root command swallowed child failures while creating a known
  `admin/admin` credential.
- **Root Cause**: There was no shared execution contract, explicit per-entity
  target, concrete-model inventory or positive environment capability. The
  orchestrator optimized for leaving any partial data behind instead of an
  internally valid graph.
- **Resolution**: Centralize guard/seed/anchor/model ownership in
  `content.fake_data`; rebuild in dependency order inside one transaction; create
  collection accounts through the income service; add the 60-row skewed volume
  profile, communication extremes and auxiliary modules; remove default
  passwords; make populated additive runs fail and expose explicit `--replace`.
- **Verification**: Focused contract tests cover all 102 concrete models, the
  60/67 client-project distribution, platform pagination targets, accounting and
  document relationships, the 12/36/12 communication distribution, auxiliary
  history, environment refusal and whole-run rollback.
- **Lesson**: Fake data is production-like infrastructure. Safety, clock,
  randomness, dependency order and coverage ownership must be executable
contracts, not conventions repeated in individual commands.

### [ERR-026] A display utility disabled two-line clipping in document cards
- **Date**: 2026-08-25
- **Context**: The desktop document row exposed the conditional full-title control, but the same long title in the portrait-tablet card never showed **Ver completo**.
- **Root Cause**: The card passed Tailwind's `block` utility into the same link that `BaseOverflowText` marked `line-clamp-2`. The competing display rule disabled WebKit line clamping, so the title expanded naturally and the overflow measurement correctly reported no clipping.
- **Resolution**: Make `BaseOverflowText` the sole owner of display state: collapsed content applies the clamp, expanded content applies `block`, and consumers provide typography only.
- **Files Affected**: `frontend/components/base/BaseOverflowText.vue`, `frontend/components/panel/documents/DocumentCard.vue`.
- **Verification**: The five-case Playwright flow passed the clipped-only desktop hint, compact in-place expansion, drag persistence, fixed tracks and double-click reset; focused component tests remain green.
- **Lesson**: A clipping primitive must own every CSS property that establishes clipping. Consumer typography classes cannot include competing display or overflow utilities.

### [ERR-025] A Playwright run reused another worktree's Nuxt server

- **Symptom**: every communications E2E case timed out on the page heading and
  the captured DOM showed Nuxt's `Page not found`.
- **Cause**: local Playwright enables `reuseExistingServer`; port 3001 belonged
  to a parallel worktree whose source tree did not contain the new route.
- **Resolution**: inspect the listening process and run the focused spec with a
  session-unique `E2E_PORT`. Never terminate or reuse another session's server.
- **Prevention**: allocate a unique port per worktree before interpreting a
  route-level 404 as an application regression.

### [ERR-024] Aplicar una nota no la persistía hasta guardar otra vez el documento
- **Date**: 2026-08-25
- **Context**: El modal de notas decía “Aplicar al documento”, cerraba y actualizaba el formulario local, pero el operador todavía debía usar el guardado general de la pantalla para persistir la nota.
- **Root Cause**: El modal sólo emitía datos al formulario padre; no existía una operación de persistencia propia ni una confirmación que distinguiera un cambio aplicado localmente de uno guardado en el servidor.
- **Resolution**: En edición, el modal ejecuta un PATCH exclusivo de los cuatro campos privados, confirma el éxito de forma visible y actualiza sólo su porción de la baseline de cambios. En creación conserva el paso diferido por necesidad —el documento aún no tiene ID—, pero lo nombra “Aplicar al borrador” y avisa explícitamente que falta crear el documento.
- **Files Affected**: `DocumentClientNoteModal.vue`, páginas de creación/edición de documentos y `useUnsavedGuard.js`.
- **Regression coverage**: Unitarias fijan etiquetas, modo borrador, bloqueo durante guardado y baseline parcial; E2E verifica el PATCH mínimo, la confirmación, la conservación de otros cambios pendientes y los estados 4xx/5xx.

### [ERR-023] Document editor exits discarded the originating list context
- **Date**: 2026-08-25
- **Context**: Leaving `/panel/documents/{id}/edit` always opened the Documents root, losing folders, search, archived mode, filters and pagination.
- **Root Cause**: All four editor exits hardcoded the root route, while the list query synchronized only folder, scope, client and project; no complete origin existed to restore.
- **Resolution**: Make the list URL canonical for every meaningful state, carry it in a validated internal `from` query, add `focus` to the explicit return, and route every editor exit through the same contextual target. Keep native browser Back intact and use the localized root only for direct or rejected origins.
- **Files Affected**: `frontend/composables/useDocumentFilterQuery.js`, Documents list/editor pages, `frontend/utils/documentReturnNavigation.js`.
- **Regression coverage**: Unit tests cover query round trips, browser history, validation, labels and focus; Playwright covers explicit return, native Back and an untrusted-origin fallback.

### [ERR-024] Panel action symbols were inconsistent across modules
- **Date**: 2026-08-25
- **Context**: Copy, duplicate, edit, rename, delete, close and other panel actions mixed Heroicons, inline SVG paths and emojis; some distinct actions shared one symbol.
- **Root Cause**: Screens selected glyphs locally and no executable inventory enforced family, semantic uniqueness, tooltip/accessibility or touch geometry.
- **Resolution**: Added an 84-action Heroicons 24 Outline catalog, shared action icon/button primitives, contextual accessible labels with stable feedback glyphs, a visual styleguide inventory and a CI guard covering all panel-reachable modules.
- **Files Affected**: `frontend/config/panelActions.js`, `frontend/components/base/BaseActionIcon.vue`, `BaseActionButton.vue`, panel pages/components, `frontend/scripts/check-panel-action-icons.mjs`, `.github/workflows/ci.yml`.
- **Regression coverage**: Catalog/component unit tests, focused consumer suites and the static guard verify icon uniqueness, copy-vs-duplicate semantics, tooltip/accessibility, stable feedback and panel adoption.

### [ERR-022] Editing a recurring payment left its monthly COP projection stale
- **Date**: 2026-08-22
- **Context**: Chat-GPT was edited from USD 20 to USD 200, but its stored COP equivalent remained 80,000. Reloading preserved the wrong value, which also understated the general and category monthly totals.
- **Root Cause**: `cop_equivalent` was accepted as client input and only defaulted for new COP rows. The edit form resent the old stored USD value, while no model invariant recomputed it from price, currency or the configured rate.
- **Resolution**: Make the field a server-owned cache derived on every model save, resynchronize all rows when the current USD rate changes, remove it from panel/MCP/import inputs, show a live read-only preview, and run migration `0208` to repair historical rows.
- **Files Affected**: `content/models/recurring_payment.py`, `content/models/accounting_settings.py`, accounting serializers/MCP/import paths, `RecurringPaymentFormModal.vue`, recurring panel/settings pages.
- **Regression coverage**: Separate backend, unit and E2E checks cover price-only, currency-only and frequency-only edits; settings tests cover USD-rate resynchronization; the migration test reproduces and repairs stale USD/COP rows.

### [ERR-021] Responsive behavior diverged across modules and breakpoints
- **Date**: 2026-08-22
- **Context**: Panel modules independently used `sm`, `md`, `lg`, JavaScript widths and fixed table minima; Playwright exposed no permanent reference-viewport acceptance matrix.
- **Root Cause**: Responsive behavior lived in individual pages, with no shared pattern declaration, complete view ownership registry or recurring five-width gate.
- **Resolution**: PA-75 through phase 4 centralized the 412/835/1195/1440/2560 profiles in `responsive.js`, moved repeated behavior into base components, assigned all 101 Nuxt pages to 12 module scripts, and added affected-module PR CI, a monthly full run and a semestral standards review.
- **Files Affected**: `frontend/config/responsive.js`, `frontend/config/responsiveAcceptance.js`, `frontend/components/base/`, `frontend/playwright.config.js`, `.github/workflows/responsive-acceptance.yml`, and `docs/methodology/responsive-*.md`.
- **Verification**: Contract reports 101 views, 12 modules and 5 viewports; the view catalog has no orphan, stale, duplicate or invalid entries; all module matrices passed during implementation; the final post-merge Foundation/Documents slice passed 10/10 and the Nuxt production build completed.
- **Lesson**: Responsive acceptance must be executable product policy. A breakpoint or page-specific CSS fix is incomplete until it shares the canonical component, has one accountable module and passes the same five device profiles.

### [ERR-020] Proposal closing columns and payment amounts were visually compressed
- **Date**: 2026-08-21
- **Context**: The public proposal at laptop and desktop widths showed two narrow closing cards despite available screen space, while payment amounts could wrap before `+ IVA` and the legal contract floated without a document boundary.
- **Root Cause**: `FinalNote` combined `max-w-6xl` with 192 px of desktop horizontal padding and enabled two columns at `lg`; the payment list was capped at `max-w-lg` and its amount could shrink; `ContractTermsDocument` rendered directly on the page background.
- **Resolution**: Use a wider container and defer the two-column grid to `xl`, reserve a non-wrapping amount column inside a wider payment list, and contain the contract in a semantic paper surface with a decorative back layer.
- **Files Affected**: `frontend/components/BusinessProposal/FinalNote.vue`, `Investment.vue`, `ContractTermsDocument.vue`
- **Regression coverage**: Playwright measures both closing columns above 520 px and the payment list above 640 px at 1366 px, and verifies each tax-qualified amount occupies one line.

### [ERR-001] defineI18nRoute(false) conflicts with i18n strategy 'prefix'
- **Date**: 2025-07-07
- **Context**: All platform pages had `defineI18nRoute(false)`, but Nuxt i18n uses `strategy: 'prefix'`
- **Root Cause**: Routes returned 404 because the router expected locale-prefixed paths
- **Resolution**: Removed `defineI18nRoute(false)` from all 11 platform page files
- **Files Affected**: `frontend/pages/platform/*.vue`, `frontend/pages/platform/projects/**/*.vue`, `frontend/pages/platform/clients/**/*.vue`

### [ERR-002] platform-auth middleware bypassed by i18n locale prefix (SECURITY)
- **Date**: 2025-07-07
- **Context**: `platform-auth.js` checked `to.path.startsWith('/platform')` but i18n produces `/en-us/platform/login`
- **Root Cause**: Path comparisons didn't strip locale prefix, so all auth guards were bypassed
- **Resolution**: Added `rawPath = to.path.replace(/^\/[a-z]{2}(-[a-z]{2})?(?=\/)/, '')` before path checks
- **Files Affected**: `frontend/middleware/platform-auth.js`

### [ERR-003] Playwright networkidle hangs with Vite HMR WebSocket
- **Date**: 2025-07-07
- **Context**: `page.waitForLoadState('networkidle')` never resolves in Nuxt dev mode
- **Root Cause**: Vite HMR WebSocket keeps persistent connection, preventing networkidle
- **Resolution**: Use `domcontentloaded` + explicit element waits instead
- **Files Affected**: All 14 `frontend/e2e/platform/*.spec.js` files

### [ERR-004] Playwright strict mode violations from sidebar + page content
- **Date**: 2025-07-07
- **Context**: `getByText('Tablero')`, `getByText('Proyectos')`, etc. matched both sidebar links and page headings
- **Resolution**: Scope to `page.locator('main')`, use `getByRole('heading')`, or `{ exact: true }`
- **Files Affected**: Multiple platform E2E spec files

### [ERR-005] format_bogota_date crashed on plain `date` instances
- **Date**: 2026-04-09
- **Context**: New `ProposalProjectStage` model uses `DateField` for `start_date` and `end_date`. The stage email send methods passed `stage.start_date` to `format_bogota_date()`, which expected a `datetime`.
- **Root Cause**: `format_bogota_date()` called `dj_timezone.is_naive(dt)` and `dt.astimezone(_BOGOTA_TZ)` unconditionally — both of which AttributeError on a plain `date` instance.
- **Resolution**: Updated `format_bogota_date()` in `backend/content/utils.py` to check `isinstance(dt, datetime)` first and skip the timezone conversion for `date` instances. The function now accepts both types and returns `''` for unsupported inputs.
- **Files Affected**: `backend/content/utils.py:format_bogota_date`
- **Test coverage**: 9 stage email service tests now exercise this code path with `DateField` values.

### [ERR-006] Vue stage badge didn't update after store action
- **Date**: 2026-04-09
- **Context**: Mark-as-completed E2E test for the new Cronograma tab failed: clicking "Marcar como completada" called the API and returned `completed_at`, but the badge still showed "🟡 Faltan 1 día" instead of "🟢 Completada".
- **Root Cause**: The store helper `_mergeProjectStage` was reassigning `currentProposal` to a new object spread (`this.currentProposal = { ...this.currentProposal, project_stages: stages }`). The component was reading via `props.proposal` which came from a parent `computed(() => proposalStore.currentProposal)`. Vue's reactivity through the computed → prop chain didn't reliably pick up the spread+reassign combination, even though it tracks the top-level ref.
- **Resolution**: Two changes:
  1. Switched `_mergeProjectStage` to in-place index mutation matching the established pattern used by `updateSection`, `applySync`, and `reorderSections` in the same store: `this.currentProposal.project_stages[idx] = stage`.
  2. Refactored `ProjectScheduleEditor.vue` to read stages directly from `proposalStore.currentProposal?.project_stages` via a computed (with `props.proposal` as fallback for tests), instead of maintaining a local `localStages` mirror with a deep prop watcher (which also clobbered in-progress form edits when other parts of the proposal changed).
- **Files Affected**:
  - `frontend/stores/proposals.js:_mergeProjectStage`
  - `frontend/components/BusinessProposal/admin/ProjectScheduleEditor.vue`
- **Lesson**: When updating nested arrays in a Pinia store consumed by Vue components, mutate by index — do not spread + reassign the parent object. See `lessons-learned.md` § Pinia Reactivity for the rule.

### [ERR-007] respond_to_proposal omitía send_acceptance_confirmation
- **Date**: 2026-04-09
- **Context**: The public endpoint `POST /api/proposals/<uuid>/respond/` with `action='accepted'` was not sending the acceptance confirmation email to the client, even though the docstring of `respond_to_proposal` explicitly promised it. Pre-existing test `TestRespondReengagement.test_acceptance_sends_confirmation_email` was already in the working tree but was failing — this surfaced when running the full proposal test slice during Phase A of the real-client-entity feature.
- **Root Cause**: `backend/content/views/proposal.py:respond_to_proposal` had branches for `action == 'rejected'` (sends `send_rejection_thank_you` + schedules re-engagement) and `action == 'negotiating'` (sends `send_negotiation_notification` + `send_negotiation_confirmation`), but **no branch for `accepted`**. The view always called `send_response_notification` (internal team alert) regardless of action, but the client-facing acceptance confirmation was never wired in.
- **Resolution**: Added the missing branch:
  ```python
  elif action == 'accepted':
      ProposalEmailService.send_acceptance_confirmation(proposal)
  ```
  Right after the existing `negotiating` branch in `respond_to_proposal`. Verified by re-running the failing test plus the full `TestRespondReengagement` class (4/4 green).
- **Files Affected**: `backend/content/views/proposal.py:respond_to_proposal`
- **Lesson**: When a docstring describes a side effect, write a test that asserts the side effect AND wire the side effect into the code. Tests-and-docstring drift is the most common silent regression source.

### [ERR-008] DRF APIClient: `content_type='application/json'` with a dict causes KeyError
- **Date**: 2026-04-19
- **Context**: New backend tests for markdown PDF attachment endpoints used `client.post(url, data=dict, content_type='application/json')`. Tests that then accessed `response.data['error']` raised `KeyError` because the response body was a DRF validation error dict with a different shape.
- **Root Cause**: Passing `content_type='application/json'` with a `dict` skips DRF's multipart parsing — the dict is JSON-serialized by Django's test client, but DRF's parser may not decode it as expected when `request.data` is checked. The simpler and correct form is `format='json'` with a plain dict.
- **Resolution**: Replace `client.post(url, data=dict, content_type='application/json')` with `client.post(url, data=dict, format='json')` in all DRF `APIClient` tests. The `format='json'` kwarg sets the content type AND JSON-encodes the body in one step.
- **Files Affected**: `backend/content/tests/views/test_diagnostic_email_attachment.py` (and any test file using manual `content_type='application/json'`)
- **Lesson**: In DRF `APIClient` tests, always use `format='json'` for JSON payloads — never `content_type='application/json'` with a `dict`. The `format` kwarg is the canonical DRF approach.
### [ERR-009] Documents tab hidden for sent proposals and contract actions enabled too early
- **Date**: 2026-04-22
- **Context**: Proposal admin detail only showed the `Documentos` tab for `negotiating/accepted/rejected`, while the intended flow needs it from `sent` onward
- **Root Cause**: Frontend tab visibility was gated by a narrow status list, and the contract row did not distinguish between `sent/viewed` and `negotiating`
- **Resolution**: Show the tab for every non-`draft` proposal and disable contract actions in `sent/viewed` with a tooltip until the proposal reaches `negotiating`
- **Files Affected**: `frontend/pages/panel/proposals/[id]/edit.vue`, `frontend/components/BusinessProposal/admin/ProposalDocumentsTab.vue`, `frontend/e2e/admin/admin-proposal-contract-generate.spec.js`

### [ERR-010] FolderSidebar didn't show new folders until reload
- **Date**: 2026-05-04
- **Context**: On `/panel/documents`, creating a folder via `FolderManagerModal` persisted the folder in backend and updated the modal's list, but `FolderSidebar` only showed the new folder after a full page reload. Same staleness affected rename/delete/document-count after move.
- **Root Cause**: `frontend/pages/panel/documents/index.vue:handleFoldersChanged` only called `documentStore.fetchDocuments()`. `folderStore.createFolder` mutates `this.folders.push(...)` in place; templates reading `folderStore.folders` directly re-rendered, but `FolderSidebar`'s reference-based watcher `watch(() => props.folders, ...)` never re-fired because the array reference didn't change. Its `localFolders` mirror (used by the draggable list) stayed stale.
- **Resolution**: `handleFoldersChanged` now refreshes `folderStore.fetchFolders()` in parallel with `documentStore.fetchDocuments()` (matching `handleMoved`). The fetch reassigns `this.folders = response.data`, changing the reference and re-triggering the watcher.
- **Files Affected**: `frontend/pages/panel/documents/index.vue`
- **Lesson**: When passing a Pinia state array to a child via prop and the child uses `watch(() => props.list, ...)` (no `deep`), parent CRUD handlers must call `store.fetchX()` to swap the reference. See `lessons-learned.md` § 12 "Reference-based prop watchers" for the rule.

### [ERR-011] Deleting a folder with documents silently orphaned them
- **Date**: 2026-05-04
- **Context**: Admins could delete a folder from `FolderManagerModal` even when it contained documents. The DB FK with `on_delete=SET_NULL` left those documents in "Sin carpeta" without a confirmation that explained the side effect, making the action feel destructive and lossy.
- **Root Cause**: Product rule was missing — `delete_document_folder` accepted DELETE unconditionally; the modal warning said "quedarán sin carpeta" but the user expected the operation to be blocked.
- **Resolution**: Backend now returns **HTTP 409** with `{ detail, document_count }` when `folder.documents.exists()`. Modal shows an amber blocking warning ("No se puede eliminar… Primero mueve o elimina sus N documento(s)") with no destructive button when `document_count > 0`. Empty-folder deletion still works (204). DB-level `SET_NULL` is preserved as a safety net for admin/shell removals.
- **Files Affected**: `backend/content/views/document_folder.py:delete_document_folder`, `frontend/components/panel/documents/FolderManagerModal.vue` (computed `deleteVariant`).
- **Lesson**: When the DB cascade and the user expectation differ, encode the user expectation at the API layer — DB constraints are a safety net, not the contract.

### [ERR-012] "Enviar al cliente" reported success while the email had failed silently
- **Date**: 2026-05-04
- **Context**: Admins moved a proposal from `draft` to `sent` (button "Enviar al Cliente" or inline status dropdown) and the panel showed a generic success toast, but the client never received the email. There was no visible error and no way to know the send had failed.
- **Root Cause**: Two compounding issues:
  1. `ProposalEmailService.send_proposal_to_client` returned `bool` and `_send_initial_email` swallowed every failure path (placeholder email, disabled template, render/SMTP exception) into `logger.exception` without propagating to the caller. The `/proposals/<id>/send/` view always returned 200 + serialized proposal regardless of whether the email was actually dispatched.
  2. `update_proposal_status` (the inline dropdown endpoint) only changed the `status` field for the `draft → sent` transition; it never invoked the email service, so moving a proposal to `sent` from the table dropdown never sent a client email at all.
- **Resolution**:
  1. `send_proposal_to_client` now returns a structured result `{ ok, reason, detail }` (`reason ∈ {sent, placeholder_email, template_disabled, send_failed, unexpected_error}`) constructed via the local `_delivery()` helper. `ProposalService.send_proposal`, `resend_proposal`, and `_send_initial_email` propagate this dict.
  2. The three admin views (`send_proposal`, `update_proposal_status`, `resend_proposal`) attach `email_delivery` to the response payload via the new `_proposal_admin_response()` helper. `update_proposal_status` now delegates `draft → sent` to `ProposalService.send_proposal` (defense-in-depth so the dropdown can never silently mark a proposal as `sent` without dispatching the email).
  3. Frontend store actions (`sendProposal`, `updateProposalStatus`, `resendProposal`) propagate `email_delivery` to callers; `pages/panel/proposals/index.vue` shows a red toast with `email_delivery.detail || email_delivery.reason` when `ok === false` instead of a generic success.
- **Files Affected**: `backend/content/services/proposal_email_service.py`, `backend/content/services/proposal_service.py`, `backend/content/views/proposal.py`, `frontend/stores/proposals.js`, `frontend/pages/panel/proposals/index.vue`.
- **Lesson**: Side-effect operations (email, push, webhook) must surface their result to the caller as structured data, not as a silently-logged bool. If a status change and a side-effect both happen in the same endpoint, return both outcomes (e.g. `{ status: 'sent', email_delivery: { ok: false, reason: 'placeholder_email' } }`) so the UI can be honest. Never have two endpoints with overlapping behavior diverge — if one path triggers a side effect and another doesn't, the panel can silently bypass the side effect.

### [ERR-013] Expired proposals could not be re-saved and stayed expired even after extending the date
- **Date**: 2026-05-04
- **Context**: An admin opened a proposal in `expired` status to fix it: editing any field via the form (PATCH `/proposals/:id/update/`) or re-importing JSON (PUT `/proposals/:id/update-from-json/`) failed with `"Expiration date must be in the future."` even when the admin was not changing `expires_at` at all. When they did change the date to a future value, the proposal was saved but `status` stayed `expired` because nothing recomputed it; the admin panel kept showing the proposal as expired forever.
- **Root Cause**: Two compounding issues:
  1. Both `ProposalCreateUpdateSerializer.validate_expires_at` and `ProposalFromJSONSerializer.validate_expires_at` rejected any `value < timezone.now()` unconditionally. On an expired proposal, the form pre-fills `expires_at` with the (already past) stored value; submitting it back — even with no change — tripped the validator. Same for the JSON path: the exported JSON carried the past `expires_at`, so re-importing the same payload was blocked.
  2. Neither `update_proposal` nor `update_proposal_from_json` recomputed `status` after `expires_at` changed. The model's `is_expired` property returns `True` whenever `status == 'expired'` (regardless of date), so once the cron or the public view persisted `'expired'`, only an explicit status change could undo it — and `'expired'` was not in `ALLOWED_TRANSITIONS` as a manual source state.
- **Resolution**:
  1. Both validators now allow the value through unchanged. `ProposalCreateUpdateSerializer.validate_expires_at` reads `self.instance.expires_at`; `ProposalFromJSONSerializer.validate_expires_at` reads `self.context['proposal'].expires_at` (the JSON view passes `context={'proposal': proposal}` when instantiating the serializer). The future-only check still fires when the value is genuinely changing.
  2. New `ProposalService.reopen_if_unexpired(proposal, *, old_status)` mutates `proposal.status` in memory only when `old_status == EXPIRED` and the new `expires_at > now()` — reverting to `viewed` if `proposal.view_count > 0`, else `sent`. `update_proposal_from_json` calls it before `proposal.save()` so the status mutation rides the single save; `update_proposal` calls it after `serializer.save()` and persists with `update_fields=['status']` only when the helper fires. Both views log the auto-reopen via `ProposalChangeLog` with description `'Auto-reopened from expired after expires_at moved to the future (<old> → <new>).'`.
- **Files Affected**: `backend/content/serializers/proposal.py` (both `validate_expires_at` methods), `backend/content/services/proposal_service.py` (new `reopen_if_unexpired`), `backend/content/views/proposal.py` (`update_proposal_from_json` passes context + calls helper before save; `update_proposal` calls helper after `serializer.save()` and reuses tracked-fields loop with description override).
- **Test coverage**: 5 new pytest cases in `backend/content/tests/views/test_proposal_views.py` — `test_update_succeeds_for_expired_proposal_when_expires_at_unchanged`, `test_update_reopens_status_when_expires_at_moved_to_future_no_views`, `test_update_reopens_to_viewed_when_proposal_was_visited`, `test_update_from_json_succeeds_for_expired_proposal_when_expires_at_unchanged`, `test_update_from_json_reopens_status_when_expires_at_moved_to_future`.
- **Lesson**: A serializer validator that compares against an absolute boundary (`< now()`, `> max`, etc.) must skip the check when the new value equals the bound instance's existing value — otherwise the "edit other fields without touching this one" path becomes impossible the moment the existing value drifts past the boundary. Use `self.instance.<field>` for `ModelSerializer` and pass the bound object via `context=` for plain `Serializer`. And when a status field is computed from another field's state (here: `is_expired` from `expires_at`), every mutation of the source field must go through the same recomputation path — otherwise the system can persist a state inconsistent with its own predicate.

### [ERR-014] Migration backfill silently no-op'd because `ProposalDefaultConfig` had stale `sections_json`
- **Date**: 2026-05-05
- **Context**: Migration `0118_roi_projection_section.py` ran successfully on prod (the `AlterField` step took effect, the `RunPython` step reported no errors), but **zero `roi_projection` rows were created** across the 32 existing proposals. The order-bump step (every `order >= 4` shifted `+1`) DID run, leaving a permanent gap at `order=4`.
- **Root Cause**: The backfill function called `ProposalService.get_default_sections(language)` to look up the template for the new section, then `_defaults_index(language).get('roi_projection')` to fetch the row's content. `get_default_sections` reads from `ProposalDefaultConfig` first (DB-backed override) and falls back to the hardcoded `DEFAULT_SECTIONS` list only when no DB row exists. In prod, the `ProposalDefaultConfig (es)` row had been edited via `/panel/defaults` long ago and stored a frozen 16-section list with no `roi_projection`. So the lookup returned `None`, and the migration `continue`d past every proposal without creating rows.
- **Resolution**:
  1. Recovery via Django shell, importing the canonical lists directly from the source module rather than going through the service:
     ```python
     from content.services.proposal_service import DEFAULT_SECTIONS, DEFAULT_SECTIONS_EN
     def cfg_for(lang): return next((s for s in (DEFAULT_SECTIONS_EN if lang == 'en' else DEFAULT_SECTIONS) if s['section_type'] == 'roi_projection'), None)
     for p in BusinessProposal.objects.all().only('id', 'language'):
         if not ProposalSection.objects.filter(proposal_id=p.id, section_type='roi_projection').exists():
             ProposalSection.objects.create(proposal_id=p.id, section_type='roi_projection',
                                            order=4, is_enabled=False,
                                            content_json=deepcopy(cfg_for(p.language or 'es')['content_json']),
                                            title=cfg_for(p.language or 'es')['title'])
     ```
  2. Updated `ProposalDefaultConfig.sections_json` for each language row to include `roi_projection` so future proposals created via the panel pick it up automatically.
- **Files Affected**: `backend/content/migrations/0118_roi_projection_section.py` (the migration itself was idempotent so no fix to ship — the lesson is for the *next* migration). Lessons captured in `docs/methodology/lessons-learned.md` §18.
- **Test coverage**: New `backend/content/tests/test_roi_projection.py` asserts ES + EN defaults include the section at `order=4` (catches the source list being correct but does NOT exercise the migration's DB-override interaction — that path is hard to test without a real `ProposalDefaultConfig` fixture).
- **Lesson**: Inside a migration, if you need a section/template definition, import the canonical hardcoded list directly (`from content.services.proposal_service import DEFAULT_SECTIONS`) rather than going through a service method that may be reading from a DB-backed override. The service layer's "DB first, fallback to hardcoded" behavior is correct for the runtime app but actively wrong inside a migration — the migration's *purpose* is to update both surfaces (data rows + DB config). After the schema change runs, **also update the `ProposalDefaultConfig.sections_json` rows** so the runtime path stays in sync with the new hardcoded list.

### [ERR-015] Blog prerender silently dropped — build self-fetch tripped the nginx API rate limit
- **Date**: 2026-06-24
- **Context**: `npm run build:django` prerenders blog post pages by fetching each post from the API at build time (`blogPrerenderRoutes` in `nuxt.config.ts` → page `pages/blog/[slug].vue` does `$fetch(\`${apiInternalOrigin}/api/blog/<slug>/\`)`). With `PRERENDER_API_ORIGIN` pointing at the public domain (`https://projectapp.co`), a full deploy produced a build **without** prerendered posts: served HTML was the bare SPA shell with only generic OG/meta tags, no per-post `<article>`/`og:title`/JSON-LD. Two failure shapes seen: (a) when `PRERENDER_API_ORIGIN` was unset it defaulted to `http://127.0.0.1:8000` which is NOT listening (gunicorn binds `unix:/run/projectapp.sock`, not a TCP port) → slug fetch failed → silent skip; (b) with the origin set to the live domain, the slug list fetched fine but ~100 of the 114 post-page renders returned `[500]`.
- **Root Cause**: nginx applies `limit_req zone=api ... rate=5r/s` (burst 10) on `/api/`. Prerendering 114 blog routes fires that many `/api/blog/<slug>/` requests rapidly from one IP → after the burst, nginx returns **429** → the page's `$fetch` throws → `useAsyncData` errors → route prerenders as 500. Confirmed empirically: 25 rapid `curl`s to one blog API URL returned `200×14` then a cascade of `429`. The blog had outgrown the rate limit (works with a handful of posts, breaks past ~10–14). Affected **both** build paths — the `/deploy-and-check` raw `npm run build:django` and the on-publish `run_frontend_rebuild` task — because both go through the same `build:django` script.
- **Resolution**: Make the build prerender against Django **directly, bypassing nginx**. `frontend/update-django-template.js` now starts a throwaway Django dev server on a free loopback port, points `PRERENDER_API_ORIGIN` at it, runs `nuxi generate`, and tears it down. It uses a dedicated `backend/projectapp/settings_build.py` (extends `settings_prod` → same MySQL DB and real content, but disables `SECURE_SSL_REDIRECT`/HSTS/secure-cookies so the loopback HTTP server is reachable — production's `SECURE_SSL_REDIRECT=True` would 301 the prerender fetches to https and break them). Falls back to the previous env-driven behavior when no backend (`venv` + `manage.py`) is present, e.g. CI/dev. When the local server is used, `PRERENDER_REQUIRE_BLOG=1` is set so a dropped prerender becomes a hard build failure instead of a silent SEO regression. Verified: 114 blog routes prerendered with 0 errors; live post HTML now carries `<article>` + per-post `og:title` + JSON-LD.
- **Files Affected**: `frontend/update-django-template.js`, `backend/projectapp/settings_build.py` (new). PR #58.
- **Lesson**: A build step that self-fetches the app's own public API will hit production's rate limiting / WAF / TLS-redirect rules — the build is just another client from nginx's view. Prerender/SSR-at-build against the **app server directly on loopback**, not the public hostname. See `docs/methodology/lessons-learned.md` §19.

### [ERR-016] Documento de producción perdido — restaurar sin reabrir la cadena contenedora
- **Date**: 2026-08-12 (fix principal, #166); 2026-08-13 (guardas permanentes)
- **Context**: En el gestor (`/panel/documents`), restaurar un documento cuya carpeta seguía archivada lo dejaba `is_archived=False` con `folder` apuntando a una carpeta archivada. No salía en Archivados (no está archivado) ni en el árbol activo (su carpeta no se lista): **invisible en ambas vistas**. Caso real en producción: 'Requerimiento Mapping' dentro de la carpeta 'temp'.
- **Root Cause**: El `unarchive_document` original no comprobaba el contenedor. El invariante «toda fila activa tiene su cadena de contenedores activa» no estaba modelado en ninguna capa, y ninguna vista contempla el estado activo-bajo-archivado.
- **Resolution**: Tres capas en #166 (`6a29b44d`): (1) `_restore_chain` reabre la cadena de ancestros — y sólo la cadena — en todo unarchive; (2) `ensure_active_target` rechaza mover/crear/duplicar contenido activo hacia carpetas archivadas; (3) la migración one-shot `0186_repair_active_rows_under_archived_folders` reparó las filas ya perdidas (verificado en prod: 'temp' activa con `requirements_mapping` dentro). Ola del 13-ago (`fix/13082026-document-archive-followups`): comando **re-ejecutable** `audit_archive_integrity` (default dry-run; `--repair` aplica la política exacta de 0186 y jamás re-parenta), campos de archivado **readonly en el admin** de Django (el registro pelado de `DocumentFolder` dejaba `is_archived` editable a mano — el vector para recrear el estado tóxico), locks `select_for_update` en archive/unarchive contra el entrelazado unarchive_document × archive_folder, y el **portal del cliente excluye archivados** (decisión del operador).
- **Files Affected**: `backend/content/services/document_archive_service.py`, `backend/content/migrations/0186_repair_active_rows_under_archived_folders.py`, `backend/content/management/commands/audit_archive_integrity.py`, `backend/content/admin.py`, `backend/accounts/document_views.py`.
- **Test coverage**: `content/tests/services/test_document_archive_service.py`, `content/tests/services/test_document_orphan_repair_migration.py`, `content/tests/management/test_audit_archive_integrity.py`, `content/tests/views/test_admin.py`, `accounts/tests/test_client_documents.py`.
- **Lesson**: «Restaurar» es una operación de **ubicación**, no sólo de estado: o se garantiza un destino alcanzable o se degrada explícitamente (raíz / «Sin carpeta»), nunca a un estado invisible. Y un invariante que sólo vive en el servicio queda a merced de toda superficie de escritura que no pasa por él (admin, carreras, scripts): hay que sellarlas (readonly, locks) y darse una auditoría re-ejecutable — la migración corre una sola vez.

### [ERR-017] Concurrent MCP connectors exhausted one shared IP throttle
- **Date**: 2026-08-19
- **Context**: Codex starts the blog, documents, proposals, accounting and LinkedIn connectors concurrently from the same VPS. Some connectors timed out even though their endpoints were healthy in isolation.
- **Root Cause**: `McpEndpointThrottle` inherited DRF's anonymous cache key unchanged, so all connector requests from one client IP consumed the same `mcp` quota.
- **Resolution**: Override `get_cache_key()` with a scope composed from the base scope and a registered connector slug. Unknown slugs deliberately map to one `unknown` scope so arbitrary paths cannot create unlimited buckets. Capability tokens remain excluded from cache keys.
- **Files Affected**: `backend/content/views/mcp_blog.py`, `backend/content/tests/views/test_mcp_blog.py`.
- **Test coverage**: One test exhausts the blog quota and proves documents still responds; another proves three distinct unknown slugs share and exhaust one quota.
- **Lesson**: Rate-limit keys must model the independent consumer boundary. For a multiplexed endpoint, IP-only is too coarse and unvalidated path-only is too permissive.

### [ERR-018] Historical proposal normalization leaked annual terms into new platform projects
- **Date**: 2026-08-20
- **Context**: The hosting migration correctly preserved an accepted proposal's annual JSON for its public/PDF history, but project creation reused the same normalizer and copied that annual tier into a brand-new operational project.
- **Root Cause**: One helper was serving two different temporal contracts: render the terms agreed in a historical document, and produce the catalog offered for a new subscription today.
- **Resolution**: `normalize_hosting_plan` keeps historical preservation as its default and accepts an explicit `force_current_terms=True` only for operational onboarding. Integration tests pin both outcomes: accepted proposal display remains annual; a project created from it receives nine-month/semiannual/quarterly tiers.
- **Files Affected**: `backend/content/services/proposal_service.py`, `backend/accounts/views.py`, proposal serializer and platform project tests.
- **Lesson**: A snapshot renderer and a new operational record do not share the same meaning of “source of truth.” Make the time boundary explicit at the call site instead of weakening historical preservation globally.

### [ERR-019] Production deploy stopped on two `content.0204` migration leaves
- **Date**: 2026-08-21
- **Context**: `$deploy-and-check` fast-forwarded production `main`, installed backend requirements, and then Django refused to migrate with `Conflicting migrations detected`. The frontend build, `collectstatic`, and service restarts were skipped; the previous runtime remained healthy.
- **Root Cause**: The contract-terms and private document-communication features were developed in parallel from `0203_hosting_nine_month_terms`. Each added a distinct `0204` file, so Git merged both cleanly while Django correctly saw two terminal nodes in the same app.
- **Resolution**: Add the empty migration `0205_merge_contract_terms_and_client_communication`, depending on both `0204_businessproposal_contract_terms_mode` and `0204_document_client_communication`. It performs no schema or data operations and preserves both histories.
- **Files Affected**: `backend/content/migrations/0205_merge_contract_terms_and_client_communication.py`.
- **Verification**: `MigrationLoader.detect_conflicts()` returns `{}`, `content` has only the `0205` leaf, `makemigrations --check --dry-run` reports no changes, and Django's system check passes.
- **Lesson**: Distinct migration filenames do not create a Git conflict. Parallel migration branches need a graph-conflict check in CI or pre-deploy, followed by an explicit merge migration after both leaves land; never rename or re-parent migrations already merged.

### [ERR-020] Panel width aliases compiled as orientation queries
- **Date**: 2026-08-22
- **Context**: The first responsive styleguide run hid the compact profile at
  412 px and showed desktop strips according to device orientation instead of
  usable width.
- **Root Cause**: Tailwind reserves `portrait:` and `landscape:` as built-in
  orientation variants. Extending `theme.screens` under those same names did
  not replace their meaning, so the generated CSS used
  `@media (orientation: ...)`.
- **Resolution**: Namespace panel screens as `panel-portrait:`,
  `panel-landscape:`, `panel-desktop:` and `panel-wide:`. Keep profile names in
  JavaScript, but map Tailwind aliases explicitly through `PANEL_SCREENS`.
- **Files Affected**: `frontend/config/responsive.js`,
  `frontend/tailwind.config.js`, shared panel/base components and responsive
  styleguide tests.
- **Verification**: The production bundle contains width media queries at
  640/1024/1280/1920 px and Playwright selects the expected profile at every
  reference viewport.
- **Lesson**: Semantic breakpoint names must be checked against framework
  variants; verify compiled CSS, not only class strings in unit tests.

### [ERR-021] Responsive dependency drifted from the canonical Phase 0 contract
- **Date**: 2026-08-22
- **Context**: The shared responsive components and the Phase 0 standard were developed concurrently. The dependency initially encoded provisional 600/1000 px bands and a 1440 px content cap, while the approved inventory fixed 640/1024 px and 1400 px.
- **Root Cause**: Widths were duplicated in JavaScript, raw component media queries, documentation and E2E viewports before the canonical Phase 0 document landed.
- **Resolution**: Make `frontend/config/responsive.js` the executable source, align every raw media query and reference viewport to 640/1024/1280/1920 and the 1400 px shell, and treat `docs/RESPONSIVE_STANDARD.md` as the decision source. Accounting tests exercise the five exact reference widths, including the 835 px intermediate case and the 2560 px cap.
- **Files Affected**: `frontend/config/responsive.js`, shared base components, accounting compact tables, responsive E2E specs and responsive documentation.
- **Verification**: Vue compilation, focused unit slices, the production Nuxt build and five Playwright viewport scenarios all use the same contract.
- **Lesson**: Parallel foundation and adoption work needs one named decision owner; merge the approved contract first, then mechanically audit all executable copies before accepting downstream behavior.

### [ERR-022] Proposal magic-link email discarded its rendered body
- **Date**: 2026-08-23
- **Context**: While routing every email through the common delivery gateway,
  the magic-link path was reviewed as one of the 23 client channels.
- **Root Cause**: `send_magic_link_email` built its HTML and text bodies, then
  reset both local variables to empty strings immediately before constructing
  `EmailMultiAlternatives`. SMTP therefore received an empty primary body and
  an empty HTML alternative even though rendering had succeeded.
- **Resolution**: Remove the stale reset and pass the already-rendered values to
  both the outbound message and `EmailLog`.
- **Files Affected**: `backend/content/services/proposal_email_service.py`.
- **Verification**: The client-channel inventory includes `magic_link`; focused
  proposal tests and the gateway HTML/body preservation test cover the path.
- **Lesson**: Variables initialized for an exception path must be bound before
  rendering, not reinitialized after rendering. Centralizing transport is a
  useful audit point because every caller's final envelope becomes visible.

### [ERR-027] Los resultados de selectores buscables quedaban recortados por el modal
- **Date**: 2026-08-26
- **Context**: En la asignación masiva de cliente apenas cabía un resultado y
  parte del siguiente; el modal añadía su propia barra para alcanzar el resto y
  ocultaba el alcance que pedía revisar antes de confirmar.
- **Root Cause**: Cada desplegable absoluto se dibujaba dentro del panel con
  `overflow-y-auto`, por lo que su tamaño dependía de la altura corta del modal.
- **Resolution**: Añadir `BaseFloatingListbox` y un root flotante propiedad de
  `BaseModal`; migrar los selectores compartidos de cliente, proyecto, catálogo
  de proyectos e ingreso vinculado. El modal masivo ahora crece con el contenido
  y conserva visibles al menos cinco opciones y cuatro registros de revisión.
- **Files Affected**: `frontend/components/base/BaseModal.vue`,
  `frontend/components/base/BaseFloatingListbox.vue` y consumidores de
  Contable/Documentos.
- **Verification**: Pruebas unitarias de portal, foco, Escape, click exterior,
  giro y límites; E2E de los cinco consumidores; y la asignación masiva verde en
  los cinco viewports responsivos.
- **Lesson**: Un overlay reutilizable debe pertenecer al boundary de overlay,
  no al contenedor desplazable del consumidor.

### [ERR-028] Grouped collection controls were covered by a stretched row link
- **Date**: 2026-08-26
- **Context**: The first Playwright pass rendered the grouped collection headers correctly, but clicking the project criterion was intercepted by a link from the first data row.
- **Root Cause**: `BaseRowLink` kept its classic-table `stretch` overlay while the same row slots were reused inside grouped sections. The absolute overlay escaped the row's intended interaction area and covered controls above it.
- **Resolution**: Keep the shared row/detail slots, but enable `stretch` only in classic mode (`:stretch="!isGrouped"`). Grouped rows retain their normal explicit links and the header controls remain clickable.
- **Files Affected**: `frontend/pages/panel/accounting/collections.vue`.
- **Verification**: Playwright switches to project grouping, confirms persisted settings and reload behavior, and exercises PATCH rollback without pointer interception.
- **Lesson**: A slot can be reusable while one of its layout affordances is not. Absolute stretched-link behavior must be scoped to the container geometry it was designed for.

### [ERR-029] El destinatario interno no recibía copias de los correos salientes
- **Date**: 2026-08-26
- **Context**: `carlos18bp@gmail.com` no recibía los correos que sí salían de la
  plataforma hacia sus destinatarios principales.
- **Root Cause**: La migración de copias estaba aplicada, pero la tabla de
  destinatarios configurados estaba vacía. Además, la primera versión de la
  regla sólo cubría 23 correos dirigidos a clientes y excluía avisos internos y
  seguridad, contrario al alcance universal requerido.
- **Resolution**: Ampliar el gateway a un inventario fail-closed de 56 canales y
  ocho familias, copiar toda audiencia como BCC independiente y exponer
  configuración e historial universal. `content.0225` crea o reactiva a Carlos
  con las ocho familias para que el despliegue no dependa de una alta manual.
- **Files Affected**: `content/services/email_delivery_service.py`,
  `content/services/outbound_email_inventory.py`, `content/models/email_log.py`,
  `content/models/email_copy_recipient.py`, migración `content.0225`, API y panel
  de Emails.
- **Verification**: Inventario exacto canal por canal, guard SMTP estático,
  pruebas del gateway y API, prueba de provisión de Carlos, pruebas unitarias/E2E
  del panel e historial.
- **Lesson**: Una configuración administrable sin fila activa equivale a una
  regla deshabilitada; cuando el destinatario es requisito del producto, el
  rollout debe provisionarlo de forma idempotente y luego conservar su gestión.

### [ERR-030] Los cuadros nativos borraban el contexto de decisiones del panel

- **Date**: 2026-08-26
- **Context**: Descartar observaciones pedía el motivo con `prompt`; cerrar o
  quitar estados, fusionar/retirar el catálogo, eliminar borradores de
  comunicaciones y confirmar Enviado usaban `confirm`. El navegador bloqueaba
  la página y no podía mostrar el registro afectado ni la consecuencia.
- **Root Cause**: Los primeros consumidores resolvieron cada decisión localmente
  con `window.confirm`/`window.prompt`, sin una política transversal ni un gate
  que impidiera nuevas apariciones. En observaciones, además, no existía una
  operación separada para limpiar pruebas o duplicados.
- **Resolution**: Migrar cada flujo alcanzable bajo `/panel` a `BaseModal`,
  `ConfirmModal` o pasos inline; añadir eliminación lógica recuperable de
  observaciones, confirmación con contenido completo, papelera, restauración,
  auditoría sin snapshot y borrado masivo atómico. Retirar el modal huérfano de
  tags y añadir `check-panel-native-dialogs.mjs` al CI.
- **Files Affected**: componentes/páginas de Documentos y Comunicaciones,
  `document_note_service`, APIs/MCP de Documentos, modelos/migración y workflow CI.
- **Verification**: barrido versionado de 14 llamadas alcanzables, guard estático,
  pruebas focales backend/unit/E2E, build Nuxt, contratos MCP y flow-map fresco.
- **Lesson**: Una decisión destructiva necesita identidad, consecuencia y salida
  segura en el mismo contexto visual; el browser dialog no puede expresar ese
  contrato ni ofrecer recuperación.

### [ERR-031] El modal corregido abría con un catálogo de clientes vacío

- **Date**: 2026-08-27
- **Context**: La capa flotante de ERR-027 eliminó el recorte, pero al abrir la
  asignación masiva quedaba todo ese espacio sin contenido hasta que el operador
  adivinaba y escribía una búsqueda.
- **Root Cause**: `ClientAutocomplete` sólo consultaba el endpoint después de
  foco o teclado, y `BulkAssignModal` enfocaba el panel genérico. Además, el
  endpoint recortaba a 20 por fecha de actualización, sin orden estable ni
  contrato para pedir páginas posteriores.
- **Resolution**: Enfocar el picker principal al abrir; consultar `q=''` en ese
  foco; ordenar alfabéticamente con desempate por id; añadir `limit`/`offset` y
  `X-Total-Count`; cargar páginas al final del scroll del listbox; y presentar
  retry, vacío y creación inline sin abandonar el modal.
- **Files Affected**: endpoint/serializer/store de clientes,
  `ClientAutocomplete`, `BaseFloatingListbox`, `BulkAssignModal` y el cambio de
  cliente de carpetas.
- **Verification**: ocho pruebas del endpoint, pruebas focales del store,
  listbox, autocomplete y modal, más el flujo Playwright de asignación masiva y
  el registro E2E regenerado.
- **Lesson**: Resolver el clipping y resolver la disponibilidad inicial son dos
  contratos distintos; un overlay visible sin datos sigue siendo un estado vacío.

### [ERR-032] El libro del bolsillo conservaba ocho columnas en celular

- **Date**: 2026-08-28
- **Context**: A 412 px, los chips de Vinculado/Ingreso/Egreso se partían dentro
  de la palabra, Acciones quedaba cortada y el icono de editar se superponía con
  la fecha. El scroll horizontal no anunciaba la última columna.
- **Root Cause**: La política de columnas seguía intentando comprimir una tabla
  demasiado densa; además, el menú de fila permanecía en el extremo final y
  varios distintivos no consumían el primitive atómico compartido.
- **Resolution**: Cambiar sólo el perfil `<640 px` a una tarjeta por movimiento,
  conservar todos los datos como pares etiqueta/valor y reutilizar un menú inicial
  de 44 px para editar/eliminar. Migrar los distintivos a `BaseBadge` y aplicar el
  mismo menú inicial en las vistas clásica/agrupada de Ingresos y Cuentas de cobro.
  El saldo por fila conserva el total corrido normal y cambia a acumulado de los
  registros visibles al filtrar; el saldo general continúa siendo global.
- **Files Affected**: página y componentes de Bolsillo, páginas de Ingresos y
  Cuentas de cobro, pruebas unitarias/E2E y registro de flows contables.
- **Verification**: 13 unitarios; 13 escenarios de Bolsillo en los cinco anchos;
  cuatro escenarios compactos clásica/agrupada de los tabs vecinos; validación
  de formulario; flow-map fresco y flows afectados sin `junk-only`.
- **Lesson**: Una tabla financiera densa no se vuelve móvil encogiendo tracks.
  Cuando la identidad, el monto y la acción ya compiten, la estructura debe
  cambiar a tarjetas sin perder campos ni bifurcar acciones o semántica de saldo.

### [ERR-035] Las tarjetas de indicadores desalineaban y ocultaban el listado

- **Date**: 2026-08-28
- **Context**: Proyectos mostraba diez indicadores de alturas distintas y, en
  celular, el encabezado desplazaba el primer proyecto fuera de la pantalla.
  Ingresos repetía el problema con siete preguntas de distinta longitud.
- **Root Cause**: Cada página componía tarjetas ad hoc cuya altura dependía del
  texto de apoyo y trasladaba el inventario completo al perfil compacto. Ayuda
  y posibilidad de acción tampoco seguían un contrato uniforme.
- **Resolution**: Crear `BaseIndicatorCard` con tres filas reservadas, ayuda
  consistente y acción explícita; separar ciclo y pendientes en Proyectos; y
  reducir ambos módulos a dos resúmenes compactos con detalle en drawers. Las
  acciones reutilizan los filtros existentes y el detalle conserva ceros.
- **Files Affected**: `frontend/components/base/BaseIndicatorCard.vue`, wrapper
  contable y páginas/pruebas/flujos de Proyectos e Ingresos.
- **Verification**: Unitarios del primitive y wrapper, acciones Playwright y
  geometría/contenido en 412, 835, 1195, 1440 y 2560 px.
- **Lesson**: Reservar altura corrige alineación; reducir preguntas visibles
  corrige prioridad. Son contratos distintos y ambos deben verificarse.

### [ERR-036] Una vista guardada intentaba clonar proxies reactivos

- **Date**: 2026-08-29
- **Context**: Al abrir directamente Comunicaciones con filtros en la URL, la
  página podía dibujarse pero el estado de filtros dejaba de sincronizarse y el
  flujo Playwright terminaba antes de operar la lista.
- **Root Cause**: `snapshot()` pasaba arrays reactivos de Vue directamente a
  `structuredClone`. El navegador rechaza esos proxies con `DataCloneError`.
- **Resolution**: Convertir el estado a valores planos, validados y ordenados con
  `normalizeStoredFilters` antes de compararlo, guardarlo o escribir el query.
- **Files Affected**: `frontend/composables/useCommunicationFilters.js` y el flujo
  E2E de Comunicaciones.
- **Verification**: Los cinco outcomes del flujo y las cinco geometrías
  responsive pasan con entrada directa, cambio de filtros, vista guardada y
  apertura/cierre del detalle.
- **Lesson**: Los snapshots persistibles deben cruzar explícitamente de estado
  reactivo a datos planos; clonar un proxy no es una serialización.

### [ERR-037] La búsqueda de Comunicaciones prometía proyectos pero no los consultaba

- **Date**: 2026-08-29
- **Context**: El campo global indicaba “Buscar cliente, proyecto, asunto o
  texto”, pero escribir el nombre de un proyecto no devolvía sus hilos. La
  búsqueda local del navegador lateral sí encontraba ese proyecto.
- **Root Cause**: El predicado `q` compartido por REST y MCP incluía título del
  hilo, datos del cliente, asunto y contenido del mensaje, pero omitía
  `project__name`.
- **Resolution**: Añadir el nombre del proyecto al mismo predicado OR, actualizar
  la descripción pública del tool MCP y fijar la semántica con regresiones REST,
  MCP y del flujo visible.
- **Files Affected**: servicio de consulta de Comunicaciones, tool y pruebas MCP,
  flujo E2E y documentación del contrato.
- **Verification**: búsqueda por proyecto con facets coherentes en REST, paridad
  MCP, flujo Playwright focal y mapa de flows regenerado.
- **Lesson**: El texto de ayuda de un buscador es parte de su contrato; cada
  entidad nombrada ahí debe aparecer en el predicado compartido y en una
  regresión observable.

### [ERR-038] La ayuda invadía las tarjetas del ciclo de proyectos

- **Date**: 2026-08-30
- **Context**: En los perfiles expandidos, cada estado mostraba apenas nombre,
  conteo y acciones dentro de una tarjeta de hasta 9.5 rem. El botón `?`,
  posicionado de forma absoluta, podía verse superpuesto o salido de la tarjeta.
- **Root Cause**: El único layout de `BaseIndicatorCard` reservaba tres filas,
  incluida una línea de apoyo vacía, y ubicaba ayuda y acción fuera del flujo.
- **Resolution**: Añadir el layout opt-in `compact-horizontal`: una fila de
  72–80 px para identidad y conteo/acción, más una columna propia de 48 px para
  la ayuda. La adopción inicial cubrió el ciclo; ERR-046 extendió la misma
  geometría a Pendientes operativos.
- **Files Affected**: primitive y wrapper de indicadores, página de Proyectos,
  pruebas unitarias/E2E y contrato documentado del flow.
- **Verification**: 19 unitarias; ayuda sin activar el filtro; geometría sin
  solapamiento en 1195, 1440 y 2560 px; flow-map fresco.
- **Lesson**: Un target táctil hermano no debe flotar sobre contenido variable.
  Cuando la ayuda forma parte estable de una tarjeta, necesita un track propio.

### [ERR-045] Los flujos podían actuar antes de que Nuxt montara la aplicación

- **Date**: 2026-08-30; ampliado 2026-09-01
- **Context**: La entrada al catálogo desde el footer podía hacer click sobre el
  HTML ya pintado antes de que Nuxt instalara sus listeners; en frío, el primer
  import de una ruta administrativa también excedía el tiempo esperado. La
  aceptación de enlaces de proyecto reprodujo la variante más temprana: URL y
  `domcontentloaded` correctos, pero `#__nuxt` todavía vacío.
- **Root Cause**: El flujo confundía contenido SSR visible con una aplicación ya
  montada, y el warmup preparaba rutas sin el prefijo de locale vigente ni una
  identidad válida para las superficies privadas.
- **Resolution**: Esperar que el selector de idioma esté habilitado antes de
  navegar desde el footer; para rutas SPA, reutilizar `waitForNuxtApp`, calentar
  las URLs localizadas con autenticación simulada y tratar como error que una
  ruta crítica no llegue a montar.
- **Files Affected**: E2E público de módulos adicionales, aceptación de enlaces
  de proyecto, helper de navegación y `global-setup.js`.
- **Verification**: Tres casos antes inestables y tres referencias contables
  nuevas pasaron dos veces; la regresión completa de 10 casos y el slice final
  de 4 casos pasaron sin retries.
- **Lesson**: En Nuxt, `domcontentloaded` y una URL correcta no implican una app
  montada; el readiness debe observar el árbol de `#__nuxt` y luego el control
  visible propio de la vista. El warmup privado necesita URL canónica e identidad.

### [ERR-046] Pendientes operativos rompía la paridad de los indicadores de Proyectos

- **Date**: 2026-08-31
- **Context**: Ciclo del proyecto ya usaba tarjetas horizontales de 72–80 px,
  mientras Pendientes operativos conservaba tres tarjetas apiladas, más anchas y
  altas, aunque ambas secciones formaban una sola cabecera de indicadores.
- **Root Cause**: La adopción inicial de `compact-horizontal` se limitó al ciclo y
  el grupo operativo mantuvo una grilla distinta para preservar su línea de apoyo.
- **Resolution**: Aplicar el mismo layout y la misma grilla de cuatro/cinco
  columnas a ambos grupos. La ayuda permanece en su track de 48 px y la línea de
  apoyo operativa se limita a una línea sin alterar las dimensiones.
- **Files Affected**: página de Proyectos, regresión responsive, definición del
  flujo y documentación del contrato.
- **Verification**: 19 pruebas unitarias y 17 escenarios funcionales; paridad de
  ancho/alto, ayuda contenida y sin activar la acción principal en 1195, 1440 y
  2560 px; dos resúmenes iguales en 412 y 835 px.
- **Lesson**: Igualar el componente no basta si dos grupos hermanos usan grillas
  distintas; la paridad visual exige compartir layout y tracks de columnas.

### [ERR-057] Una propuesta podía enviarse sin explicar qué resolvía

- **Date**: 2026-09-04
- **Context**: La propuesta tenía un `email_intro` opcional en General, pero el
  correo sustituía el vacío con copy derivado del título. El operador no tenía
  un lugar claro para escribir, revisar o adaptar el mensaje al reenviar.
- **Root Cause**: Persistencia, composición y elegibilidad estaban mezcladas:
  el campo podía quedar vacío, el servicio no lo validaba y el renderer ocultaba
  esa ausencia con un fallback genérico.
- **Resolution**: Mover la autoría visible a **Correos**, conservar el draft
  opcional y hacer obligatorio el texto en todos los límites de envío. JSON,
  MCP y las skills de Codex/Claude transportan el mismo campo; reenvío lo
  precarga y permite editarlo. El renderer ya no inventa copy y las entregas
  conservan snapshots inmutables.
- **Files Affected**: servicios/serializers/vistas/templates de propuestas,
  panel comercial, contratos JSON/MCP, fake data, flows y ambas skills.
- **Verification**: Regresiones focales cubren validación previa a efectos,
  orden HTML/texto, persistencia, reenvío, multi-envío, historial inmutable y
  los outcomes E2E de éxito/error/fallo.
- **Lesson**: Un fallback no debe convertir la ausencia de contenido comercial
  obligatorio en una entrega aparentemente válida.
