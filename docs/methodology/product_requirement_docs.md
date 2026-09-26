# Product Requirements Document — ProjectApp

> **Enlaces seguros de un solo uso — 2026-09-26:** el equipo comparte
> contraseñas, llaves, accesos, datos bancarios o comunicados confidenciales con
> enlaces que se abren una sola vez, se pueden revocar y reactivar (mismo
> enlace o uno nuevo) y conservan el contenido cifrado en ProjectApp. La skill
> `client-response` los crea vía MCP con el contenido que dio el operador. Los
> clientes envían información al equipo desde `/secure-link`; esos enlaces sólo
> los abre el equipo y generan un aviso interno sin enlace ni contenido.
> Vigencia 1/3/7/30 días (7 por defecto; públicos hasta 7). Detalle:
> `docs/secure-links.md`.

> **CAPTCHA transversal — 2026-09-23:** el panel y la plataforma exigen
> reCAPTCHA v2 desde el primer intento de login. Si la verificación falla,
> se bloquea el acceso y se permite reintentar. Incluye la contraseña temporal
> del primer acceso; recuperación, activación, refresh y sesiones abiertas
> conservan su comportamiento. No se cuentan intentos para activar CAPTCHA.

> **Historial por registro — 2026-09-22:** el equipo puede consultar quién cambió cada documento y cuándo, ver versiones completas y compararlas. El alcance confirmado incluye Propuestas (precio/alcance y envío exacto), Proyectos (URLs, credenciales y notas), Clientes (contacto/facturación) y cada registro Contable. Retención indefinida, acceso interno y revelación explícita de secretos; sin restauración. Comunicaciones permanece como candidato. Detalle: `docs/ENTITY_HISTORY.md`.

> **PWA interna — 2026-09-19:** el equipo puede instalar ProjectApp desde la
> barra lateral o el menú móvil del panel. La app abre el panel y conserva el
> login Django; ofrece una invitación descartable en el dashboard una vez por sesión y ayuda
> de instalación por navegador en español/inglés. Sin internet muestra un
> aviso con Reintentar; consultar datos y trabajar requiere conexión. Esta
> versión no incluye push, operaciones offline ni publicación en tiendas.

> **Primer alcance — monitoreo operativo 2026-09-19:** centralizar en el Panel
> las observaciones de vps-projectapp-prod y sus tres proyectos activos:
> ProjectApp, Mimittos y Tenndalux. Separar casos de servidor y proyecto,
> agrupar repeticiones y registrar estado manual, notas y autor. La recuperación
> técnica no cierra el seguimiento; una detección posterior al cierre reabre el
> caso. Los reportes informativos son independientes y se conservan 90 días.
> Ingestión estructurada con credenciales acotadas y cola durable; sin importar
> correo, asignaciones ni notificaciones nuevas. Correo actual coexistente,
> inventario explícito y rollout Silk autorizado por etapas. Detalle:
> `docs/monitoring.md`.

> **Entrega 2026-09-04 — orden del listado de ingresos:** el tab Ingresos abre
> ordenado por **Mes**, del más reciente al más antiguo. El encabezado de Mes
> alterna únicamente entre reciente/antiguo; **Total** recorre mayor/menor y,
> en el tercer clic, vuelve al orden predeterminado por Mes. La preferencia se
> conserva entre filtros, tabs, vistas Agrupado/Clásico y visitas posteriores.
> En Agrupado se ordenan las filas dentro de cada cliente, sin cambiar el ranking
> de grupos por facturación ni la posición final de “Sin cliente”.

> **Corrección 2026-09-04 — ayuda y agrupación de pendientes por cobrar:** la
> leyenda del semáforo se muestra siempre por encima del modal que la contiene.
> En **Gestionar candidatos**, el listado abre agrupado por cliente, permite
> reagrupar por proyecto o volver a la lista clásica y presenta cantidad, total
> original, abonado y saldo abierto por grupo. La búsqueda se aplica antes de
> calcular los grupos; la presentación elegida no se persiste y cada reapertura
> restablece Agrupado/Cliente.

> **Entrega 2026-09-04 — varios destinatarios y copia visible:** todos los
> compositores manuales de correo —independiente, propuesta general,
> seguimiento de propuesta, diagnóstico, envío de documento y reenvío exacto—
> admiten uno o más destinatarios en **Para** y cero o más en **CC**. El operador
> puede buscar clientes registrados o escribir direcciones manualmente; no se
> admiten correos inválidos, temporales ni repetidos entre campos y el límite es
> de 10 direcciones únicas combinadas. Cada acción genera un solo mensaje SMTP
> con encabezados visibles, conserva las copias BCC automáticas como entregas
> internas separadas y aparece como un envío agrupado en el historial, con
> estado y atribución por dirección. El reenvío carga los Para/CC originales y
> permite editarlos sin regenerar asunto, cuerpo ni adjuntos.

> **Corrección 2026-09-04 — previsión visual y activación exclusivamente manual:** el monto
> “Pendiente por cobrar” deja de inferirse por mes y representa la suma global
> del valor original de los ingresos esperados abiertos de empresa que el equipo
> seleccionó y clasificó en verde. Selección y confianza son decisiones
> independientes: cambiar el nivel nunca mueve el interruptor y la inclusión se
> activa sólo por una acción manual. Verde significa cobro muy probable, naranja
> cobro incierto y rojo alto riesgo; cada nivel aparece como círculo amable junto
> a su texto completo en el listado, el modal de previsión, el formulario y el
> detalle del ingreso. Sin nivel se muestra un círculo neutro con “Sin clasificar”.
> Duplicar un ingreso reinicia nivel e interruptor, mientras los registros
> existentes conservan su estado sin migración retroactiva. Al cobrar por
> completo, marcar perdido o sacar de empresa, el ingreso se deselecciona y
> conserva su última clasificación.
>
> En los accesos rápidos de Contabilidad, **Cuentas de cobro** ocupa el lugar de
> **Ads** y abre `/panel/accounting/collections`; el módulo Ads continúa
> disponible en la navegación contable interna.
> La analítica de utilidad sustituye la gráfica “Utilidad por mes” dentro del
> resumen como acordeón abierto por defecto y todos los gráficos deben conservar
> contraste legible en modo oscuro.

> **Listo para integrar 2026-09-02 — control operativo por MCP:** todas las
> operaciones del Panel interno, salvo administración de identidades, secretos,
> infraestructura e impersonación, deben poder descubrirse y ejecutarse desde
> conectores MCP agrupados por área. Las lecturas y ediciones reversibles son
> directas; envíos, publicaciones, efectos financieros, cascadas y eliminaciones
> definitivas exigen previsualización y confirmación vinculada al estado leído.
> Los documentos Markdown, incluidos borradores, son editables; los snapshots
> PDF emitidos permanecen inmutables. Los conectores canónicos, credenciales
> acotadas, uploads firmados y auditoría ya implementan este contrato; los
> conectores nuevos quedan inactivos y las credenciales existentes no se rotan
> hasta el corte operativo.

> **Entrega 2026-09-03 — política configurable de financiación:** aplican
> proyectos, fases o conjuntos de fases entre $20.000.000 y $140.000.000 COP,
> ambos inclusive. El análisis externo de riesgo define el primer pago, nunca
> inferior al 20 %, y sólo el saldo restante —máximo 80 %— se financia. La
> mora aumenta 2 % el Hosting vigente por cuota vencida. El Panel publica
> revisiones inmutables de monto, plazo, porcentaje financiable, recargo y
> ventana de pago; cada otrosí congela su revisión y, si usa USD, la tasa
> contable empleada para validar su equivalente en COP. Sólo un borrador puede
> adoptar expresamente una revisión posterior.

> **Entrega 2026-09-03 — financiación contractual:** el programa incorpora una
> quinta condición común de pago dentro de los cinco primeros
> días calendario y aumento permanente, acumulativo y automático del 2 % sobre
> el hosting vigente por cada cuota en mora. La alianza de cinco años habilita
> hasta dos ciclos separados de financiación de doce meses; el segundo exige el
> pago íntegro del primero y una nueva aprobación manual de riesgo, sin reiniciar
> la exclusividad. Panel administra otrosíes poblados, calendarios editables,
> PDF borrador y el ciclo de firma, activación, cierre, cancelación y archivo.

> **Entrega 2026-09-02 — módulo informativo de financiación:** Project App
> dispone de una experiencia comercial bilingüe para presentar alianzas de
> financiación sujetas a evaluación previa. Explica 12 meses para financiar el
> desarrollo o sus fases con 0 % de interés ordinario, la exclusividad y
> custodia responsable del código, una calculadora de requerimientos expresada
> sólo como entrada y resultado comercial, y un paquete de 60 horas que se
> renueva mensualmente. La opción recomendada conserva cinco años de
> exclusividad e incluye el paquete; la alternativa reduce el plazo a tres años
> y lo excluye. El contenido puede consultarse públicamente en español o inglés,
> descargarse como booklet PDF y distribuirse desde Comercial en el Panel. Las
> condiciones exactas siempre se formalizan en propuesta y contrato.

> **Corrección 2026-09-02 — color semántico de avisos contables:** los correos
> internos de cambios contables usan verde para ingresos y entradas de
> Bolsillo, naranja para gastos, salidas, recurrentes, Ads y deuda de tarjetas,
> y azul para entidades administrativas o sin dirección financiera. El color
> aplica al encabezado y a los valores nuevos; los valores anteriores conservan
> rojo. La acción creada/actualizada/eliminada sigue escrita en el mensaje, pero
> ya no decide su color. El panel y los digests contables no cambian.

> **Entrega 2026-09-02 — orden por fecha del Gestor Documental:** la columna
> **Creado** permite alternar entre más nuevos y más antiguos mediante un icono
> accesible. El listado abre con los más nuevos primero; conserva el orden al
> buscar, filtrar, cambiar de carpeta, ámbito o vista durante la navegación, pero
> no lo guarda como preferencia entre visitas. Las filas activas usan creación,
> las archivadas usan archivo con fallback a creación y las listas mixtas ordenan
> por la fecha que cada fila muestra. Galería y móvil ofrecen el mismo control
> compacto; las carpetas permanecen antes de los documentos y ninguna otra
> columna se vuelve ordenable en este alcance.

> **Cierre visual 2026-09-01 — paridad pública de Módulos adicionales:** el
> catálogo canónico y cada selección conservan la experiencia sin encabezado
> global, reducen el espacio superior y mantienen el PDF de la cabecera. Además
> ofrecen controles flotantes de tema y guía a la izquierda, compartir y PDF a
> la derecha, más el WhatsApp global. El tema se recuerda entre visitas, la guía
> propia aparece una vez y puede reiniciarse, y compartir copia la URL exacta
> abierta —incluido el UUID de una selección—. El español sigue siendo el idioma
> inicial y todos los controles respetan anchos móviles y áreas seguras.

> **Corrección 2026-09-01 — cambio de estado de Proyectos:** el modal presenta
> el flujo en orden: nuevo estado, revisión de consecuencias, decisiones de
> impacto y acciones finales. Los avisos amarillos del proyecto se conservan
> como contexto bajo el encabezado; cada requisito corregible rojo aparece
> junto al campo que lo origina y desaparece al resolverlo. La fila final queda
> reservada exclusivamente para Cancelar y Confirmar cambio.

> **Aceptación 2026-09-01 — calendario contable:** ingresos esperados, gastos
> recurrentes y vencimientos de hosting comparten un digest interno diario.
> Ingresos y recurrentes usan hitos a 15 días, 7 días y el día previsto; hosting
> conserva su calendario previo de 15/7 días y repetición cada 5 días. Los
> ingresos vencidos continúan
> semanal o quincenalmente —quincenal por defecto— hasta liquidarse o
> silenciarse; la pausa puede ser indefinida o tener reanudación automática y
> debe verse en la fila. El correo consolida todos los avisos del día y deja
> trazabilidad por destinatario y registro. Los avisos al cliente siguen siendo
> responsabilidad separada de las cuentas de cobro. Para recurrentes se usa la
> próxima fecha proyectada vigente; este alcance no crea pagos históricos por
> ciclo.

> **Seguimiento 2026-09-01 — cierre del catálogo adicional:** las rutas públicas
> del catálogo, tanto canónica como seleccionada, no muestran el encabezado
> global. Todo enlace o PDF nuevo parte en español y conserva el selector ES/EN.
> Una apertura con sesión Django de staff no se registra en módulos adicionales,
> propuestas —incluidos sus enlaces secundarios e interacciones— ni diagnósticos;
> una visita sin esa sesión sí cuenta como externa. Las aperturas históricas se
> conservan sin reclasificación y la política SEO sigue siendo catálogo canónico
> indexable frente a selecciones `noindex`.

> **Refinado — 2026-09-01:** todo icono ejecutable de panel, plataforma y
> superficies públicas confirma de inmediato que recibió el clic mediante un
> salto común y contenido de 420 ms: presión, ascenso máximo de 3 px y aterrizaje
> sin efecto de borde. Touch y teclado conservan la misma señal y reduced motion
> reemplaza el movimiento por un cambio estático de contraste. Las acciones
> asíncronas mantienen su estado de carga. Copiar muestra éxito sólo después de
> escribir realmente al portapapeles: presenta check + “Copiado” temporalmente.
> Si el navegador lo bloquea conserva el icono para reintentar y muestra un
> estado de error visible, además del mensaje accionable de la pantalla.

> **Ajuste 2026-08-31 — acceso comercial visible:** Módulos adicionales abre
> con un centro de acceso rápido que muestra la URL pública canónica, permite
> copiarla o abrirla y descarga el catálogo completo en PDF sin pasar por una
> selección. El dashboard global repite estas entradas y resume módulos activos,
> enlaces seleccionados vigentes, pendientes de apertura y última apertura. Se
> distingue de forma explícita el catálogo canónico, indexable y sin seguimiento,
> de los enlaces seleccionados, `noindex` y con seguimiento comercial.

> **Entregado — 2026-08-30:** Comunicaciones ubica **Configuraciones** junto a
> **Nuevo hilo** y reúne en una superficie propia las preferencias personales de
> agrupación, orden, cantidad por página, ancho lateral, canal inicial y ayuda.
> Las preferencias se guardan por cuenta, admiten restablecimiento y no alteran
> el registro manual ni los contratos de hilos y mensajes.

> **Corrección 2026-08-29 — formularios de creación del panel:** el modal de
> proyecto presenta controles de ancho uniforme, estado inicial visible en
> **En desarrollo**, creación de cliente accesible desde el selector y una fila
> final reservada a Cancelar/Guardar. Los errores requeridos o del API viven
> bajo su campo y lo marcan inválido; el panel usa asterisco sólo para
> obligatorios y omite “(opcional)” en el resto de etiquetas. El mismo contrato
> se aplica a los demás modales de creación alcanzables del panel.

> **Corrección — 2026-08-30:** el listado de Comunicaciones funciona
> como índice: por debajo de landscape muestra tarjetas compactas identificadas
> por asunto, cliente/proyecto, canal, estado, cantidad, fecha y borradores. El
> cuerpo del mensaje no aparece en la tabla ni en las tarjetas; pertenece
> exclusivamente al detalle. El orden activo se ve y se recuerda entre visitas.

> **Corrección 2026-08-29 — engagement real:** el tiempo de lectura de una
> propuesta sólo se acumula mientras la página está visible. Ocultarla cierra y
> envía una única muestra; volver a verla abre un segmento nuevo. Una pestaña
> abandonada no puede seguir inflando actividad ni generando heartbeats.

> **Entregado — 2026-08-28:** el historial universal conserva antes del SMTP
> cuerpo, enlaces y bytes exactos de cada adjunto, con nombre, tipo, tamaño y
> peso total del envío. Permite filtrar, descargar, previsualizar PDF y reenviar
> la evidencia sin regenerarla; enlaza Documentos en ambas direcciones y declara
> de forma explícita la ausencia o la brecha de datos legados. La migración
> `content.0225` habilita `carlos18bp@gmail.com` en la copia BCC configurable y
> ésta sólo se intenta después de que el envío principal fue aceptado.

> **Ampliación 2026-08-30 — implementada:** el catálogo comercial de módulos
> adicionales conserva su dominio administrable y bilingüe separado de las
> propuestas, y crece de 18 a 23 opciones con CRM, agendamiento, membresías,
> autoservicio del cliente y fidelización/referidos. Panel, catálogo público y
> enlaces compartidos exponen un selector ES/EN y permiten leer el mismo
> contenido como tarjetas, lista o acordeón; cada ámbito recuerda su vista por
> separado. El PDF sigue sin precios, usa el idioma activo y, desde el panel,
> puede dirigirse opcionalmente a un cliente o destinatario sin convertir esa
> personalización puntual en datos de proyecto.

## 1. Overview

**ProjectApp** is the full-stack web application for **Project App** (projectapp.co), a custom software development company based in Colombia. The platform serves as:

1. **Company website** — marketing pages, portfolio showcase, blog, and contact form
2. **Business proposal & diagnostic CRM** — create, send, track, and close personalized proposals and web-app diagnostics for prospective clients
3. **Client delivery platform** — post-sale client portal (`/platform/`) for projects, kanban, deliverables, payments/hosting, bug reports, change requests, and click-to-accept document signing
4. **Internal operations** — admin panel for diagnostics + an internal Kanban, a superuser accounting module (personal ledgers, exports, card-debt reminders), and MCP connectors that expose panel modules to claude.ai

The application is bilingual (English / Spanish) and targets two distinct user personas: the **Admin** (company seller/owner) and the **Client** (prospective customer, and — post-sale — platform user).

---

## 2. Problems Solved

| Problem | Solution |
|---------|----------|
| No centralized way to create and send client proposals | Full proposal builder with 18 auto-generated section types plus four client-facing reading modes |
| Proposals sent as static PDFs with no tracking | Interactive fullscreen web experience with engagement analytics |
| No visibility into client interest or behavior | View tracking, section-level time analytics, heat score, engagement signals |
| Manual follow-up prone to human error | Automated email reminders (day 10, day 15, urgency, inactivity, re-engagement) |
| One document status cannot describe concurrent work or preserve what already happened | User-managed cycle/signal states whose open and closed episodes form an attributable timeline |
| The agency had no received copy of customer email | Every client-classified email leaves through one gateway, which sends configurable BCC-only internal copies and links their independent outcomes to the primary history row |
| Manual email composers could address only one person and had no visible copy field | Every manual composer supports registered-client search plus typed addresses in visible To/CC groups, capped at 10 unique recipients and represented as one grouped delivery |
| Email history could not prove which files or links were delivered | A mandatory pre-SMTP snapshot retains the exact attachment bytes and recognition metadata, body links, total MIME size, Document provenance and resend lineage; legacy gaps stay explicit |
| Client conversations were drafted in disposable chats and reconstructed from memory | A client/project communications registry preserves ordered incoming and outgoing messages, manual send state, date corrections and references to existing documents |
| Sparse or incoherent development data hid pagination, filters and edge defects until production | One guarded, deterministic dataset covers every visible module with explicit volume, skewed relationships, temporal buckets and intentional extremes |
| Company portfolio hard to maintain | Admin CRUD panel for portfolio works with bilingual content |
| No blog for SEO/content marketing | Full blog system with structured JSON content, categories, calendar, sitemap |
| Language barrier for international clients | i18n with prefix routing (`/en-us/`, `/es-co/`) for all public pages |

---

## 3. Core Features

### 3.1 Business Proposal System (Flagship)

The proposal system is the most complex and central feature. It allows the admin to:

- **Create proposals** with client name, email, investment amount, currency, expiration date, language, project type, and market type
- **18 section types auto-generated** per proposal: Greeting, Executive Summary, Context & Diagnostic, Conversion Strategy, Design & UX, Creative Support, Development Stages, Process & Methodology, Functional Requirements, Timeline, Investment, Proposal Summary, Final Note, Next Steps, Technical Document, Value Added Modules, ROI Projection, and Commercial Conditions (the last few are order-dependent; some — e.g. `roi_projection`, `value_added_modules`, `proposal_summary` — are web-only and intentionally skip the PDF)
- **Edit section content** — each section stores structured JSON matching a specific Vue component's props schema
- **Contextual functional-requirement scope** — the core catalog distinguishes
  four client-facing cards in order: views, components, project-specific
  features, and `cross_cutting_features`. The fourth card starts from reusable
  quality concerns (responsive design, accessibility, usability, performance,
  security, privacy, and browser compatibility), but its title, description and
  individual items must be adapted to the business, product stage, audience and
  actual proposal scope rather than copied as fixed boilerplate.
- **Choose a reading mode** — the public gateway offers executive, detailed, technical, and **Contrato y condiciones**. The legal mode is a separate, generic document surface rather than another proposal section.
- **Readable proposal presentation** — closing cards use two columns only when each retains a comfortable reading width; payment amounts keep number, currency, and tax suffix together on laptop/desktop screens. Non-empty lead copy below section titles contains one or two short, safe bold fragments for scanability.
- **Send to client** — triggers email with unique UUID link, schedules automated reminders
- **Track qualified engagement** — the document `GET` is read-only for commercial metrics; after five visible seconds a validated heartbeat records view count, first viewed date, per-section or per-contract-clause time, deduplicated session, reading mode, finalization and engagement score (heat score 1-10)
- **Share links** — clients can share proposals with stakeholders, each share link tracked independently
- **PDF generation** — downloadable PDF version via ReportLab
- **Investment calculator** — interactive modal for clients to explore payment options (hosting plans, discounts)
- **Client responses** — accept, reject (with reason/comment), or negotiate proposals directly from the proposal page
- **Manual discount offer** — from the proposal actions menu the seller can send a one-off discount/urgency email (`proposal_urgency` template) after previewing it; shown only when a discount percentage is configured and the client has an email (never auto-sent)

#### Proposal Lifecycle

```
DRAFT → SENT → VIEWED → ACCEPTED
                      → REJECTED (with reason)
                      → NEGOTIATING
                      → EXPIRED (auto, daily cron)
```

- **DRAFT**: Created, not yet sent
- **SENT**: Email dispatched, `sent_at` recorded, reminders queued
- **VIEWED**: Client opened the link (first view tracked)
- **ACCEPTED / REJECTED / NEGOTIATING**: Client or admin status updates
- **EXPIRED**: Auto-set by daily Huey periodic task when `expires_at < now()`

#### Automated Emails

| Email | Trigger | Timing |
|-------|---------|--------|
| Proposal sent (client) | Admin clicks "Send" | Immediate |
| Proposal sent (admin notification) | Admin clicks "Send" | Immediate |
| First qualified view (internal team) | Public proposal remains visible for 5 seconds | Immediate, durable retries |
| Reminder | Proposal still SENT/VIEWED | Day N (configurable, default 10) |
| Urgency / discount | Proposal still SENT/VIEWED | Day N (configurable, default 15) |
| Abandonment | Proposal viewed but no return | After inactivity period |
| Revisit alert (admin) | Client revisits after inactivity | Immediate |
| Investment interest | Client interacts with calculator | After confirmation |
| Stakeholder alert | Share link is opened | Immediate |
| Post-expiration visit | Client visits expired proposal | Immediate |
| Engagement decay | Declining engagement detected | Immediate |
| Stage warning (internal team) | Project stage 70% elapsed (Cronograma) | Daily 08:30 Bogotá, sent once per stage |
| Stage overdue (internal team) | Project stage past `end_date` (Cronograma) | Daily 08:30 Bogotá, repeats every 3 days while uncompleted |

**24h cooldown** enforced between automated client-facing emails per proposal. **Automations can be paused** per proposal (`automations_paused` flag). **Internal team notifications** (stage warning, stage overdue, first view, comment, seller inactivity, etc.) bypass the cooldown. First view uses a durable status/attempt/error state plus reconciliation; other per-event dedup remains on dedicated source fields.

**Internal team recipients** are read from the `NOTIFICATION_EMAIL` env var (CSV-supported). One env var, all internal notifications. To target a different audience for stage tracking specifically, change the env var — there is no per-feature recipient setting.

**Copies of every outbound email** use a separate administrable list under
`/panel/emails` and never reuse `NOTIFICATION_EMAIL`. The starting behavior is
all platform email, with optional segmentation by Propuestas, Diagnósticos,
Documentos/comunicaciones, Cuentas de cobro, Contabilidad, Plataforma, Tareas y
operación, and Seguridad y acceso. This includes customer, supplier, agency,
OTP, invitation, temporary-credential and password-recovery messages. Copies
are sent as separate BCC-only envelopes after the primary delivery succeeds;
their success, skip or failure is nested in the same delivery history. The
authoritative 56-channel inventory is `docs/client-email-copy-inventory.md`.

**Manual visible recipients** are a separate per-send choice. The standalone,
proposal, diagnostic and document composers —plus exact resend— accept one or
more **Para** addresses and optional **CC**, either selected from registered
clients or typed manually. There may be at most 10 unique addresses across both
headers; a repeated, malformed or placeholder address blocks the action. Para
and CC travel in one visible SMTP envelope and one grouped history entry, while
the configurable copies above remain independent BCC-only attempts.

#### Admin Panel — Proposals

- **Dashboard** (`/panel/`): multi-module command center (redesigned 2026-07-16, #110) — one consolidated endpoint aggregates proposal KPIs/heat scores/alerts, accounting year totals, tasks, diagnostics, and module shortcuts
- **Proposals list** (`/panel/proposals/`): table with title, client, status badge, investment, expiry, views, bulk actions
- **Create** (`/panel/proposals/create`): form with all metadata + JSON import option. Client identity is selected via `<ClientAutocomplete>` (searchable dropdown over `accounts.UserProfile` with `role='client'`); typing a brand-new name + email auto-creates a real `UserProfile` row, and an empty email gets a placeholder `cliente_<id>@temp.example.com` that pauses every email automation for that proposal. A top-level switch controls whether the generic contract mode is visible; it defaults on for Spanish proposals and does not enter the imported/exported section JSON.
- **Edit** (`/panel/proposals/{id}/edit`): Tabs depending on proposal status:
  - **General** — metadata + same `<ClientAutocomplete>` picker + write-through snapshot fields + propagate-changes-to-profile checkbox + send button + immediate contract-mode visibility switch
  - **Correos** — personalized initial-message editor from draft onward; sent+ statuses also expose the branded follow-up composer and delivery history
  - **Documentos** (negotiating/accepted/rejected) — contracts + uploaded annexes
  - **Cronograma** (accepted/finished) — project stage scheduling (design + development dates, mark-as-completed, status badges)
  - **Secciones** — section editor (expand/edit JSON per section)
  - **Det. técnico**, **Prompt Proposal**, **JSON**, **Actividad**, **Analytics**
- **Defaults** (`/panel/proposals/defaults`): manage default section templates per language
- **Email templates** (`/panel/proposals/email-templates`): view/edit/preview/reset email content
- **Email deliverability** (`/panel/proposals/email-deliverability`): dashboard tracking email send/delivery/bounce rates
- **Clients list** (`/panel/clients/`): real `UserProfile` (role=client) entities. Status filters (Todos / Activos / Huérfanos / Archivados), live search, and a "+ Nuevo cliente" modal for standalone creation (no invitation email sent — that path is reserved for the platform onboarding flow). The row action is **Archivar** for an active client and **Desarchivar** for an archived client; it uses the same reviewed archive mechanism as the Archivados filter. Orphan clients (zero proposals + zero platform projects) are deletable via a trash icon gated through `requestConfirm`. Each row expands lazily to load the client's full proposal history. Replaced the legacy "synthetic clients grouped by `(name, email)`" implementation on 2026-04-09.

#### Project lifecycle and operational consequences

- `/panel/projects` uses the shared PA-88 state catalog and history engine, scoped
  to `catalog='projects'`; it does not maintain a second status system.
- The six seeded meanings are **En desarrollo**, **Activo**, **En evolución**,
  **Suspendido**, **Completado** and **Dado de baja**. En evolución
  means that a delivered project remains in production while a next version or
  expansion is being developed. Names, descriptions and colors are administrable,
  while `operational_effect` remains the stable business meaning.
- Every project-state surface in the internal panel offers contextual help: the
  editable description explains what the state means and a system-owned message
  explains its billing, reminder, hosting and closure implications. This help is
  available by hover/focus and by tap; the customer portal remains unchanged.
- In the project-state catalog, required create/edit fields are identified in
  their labels. Local and serializer validation appears beside the responsible
  control only after an attempted action and clears when that value changes; it
  is never summarized as a red list beside the CTA. Merge follows the same rule
  for a missing destination, while immutable seed restrictions remain accessible
  help because editing another field cannot resolve them.
- New projects begin En desarrollo. Later changes require a server preview and an
  impact token; direct enum writes and the legacy archive/unarchive endpoints do
  not bypass that flow.
- Suspendido is the single reversible-stop state. It stops new billing/reminders while retaining debt
  already caused. A failed hosting payment may suggest this state, never apply it.
  Completado means a clean close. Dado de baja is definitive, cancels future
  service and requires an explicit keep/write-off decision for caused receivables;
  a direct jump that skips Suspendido also requires a note.
- Every transition opens/closes dated episodes with actor and note. Existing legacy
  archived projects remain **Sin clasificar / Por revisar** instead of receiving an
  invented final state, and money automation fails closed until an operator decides.
- State filters and header counts come from the live catalog. **Clientes sin
  proyecto** remains literal: a client with no `Project` row, regardless of the
  lifecycle state of projects owned by other clients.
- From the landscape profile onward, each non-zero lifecycle state is a compact
  horizontal card no taller than 80 px: state identity stays left, count and
  filter affordance stay right, and contextual help owns a separate 44 px target
  inside the card boundary. Missing support copy reserves no blank row. Compact
  screens retain the two drawer-backed summaries, and operational pending cards
  retain their support line.

#### Project Schedule Tracking (Cronograma)

A new internal-only sub-system that tracks the **execution** of an accepted proposal — distinct from the client-facing `timeline` proposal section (which is sales/marketing copy with free-text durations like "1 semana").

- **Two stages per accepted proposal**: `design` and `development`. Empty rows are auto-created when the proposal becomes `accepted` via the platform onboarding flow.
- **Per-stage fields**: `start_date`, `end_date`, `completed_at`, `warning_sent_at`, `last_overdue_reminder_at`. The model lives at `backend/content/models/proposal_project_stage.py`.
- **Manual date entry**: Admins fill in `start_date` and `end_date` from the new "Cronograma" tab in the proposal edit page (`frontend/components/BusinessProposal/admin/ProjectScheduleEditor.vue`). We do NOT auto-derive dates from the free-text `timeline` section.
- **70%-elapsed warning email**: The daily Huey task `notify_proposal_stage_deadlines` (08:30 Bogotá) sends a warning email when ≥70% of `(end_date - start_date)` has elapsed. Gated per stage by `warning_sent_at`. **Re-fires after date extension**: when the admin updates `end_date` (or `start_date`) and the new timeline drops elapsed% back below 70%, `update_project_stage` calls `ProposalStageTracker.maybe_reset_warning_on_date_change` to clear `warning_sent_at`; the daily task then fires again once the new 70% mark is crossed.
- **Overdue reminders**: When `today > end_date`, sends a reminder email immediately and then repeats every 3 days until the admin marks the stage as completed (gated by `last_overdue_reminder_at`).
- **Mark as completed**: A button per stage in the Cronograma tab. Sets `completed_at = now()` and clears the alert timestamps. Silences all future emails for that stage.
- **Time format**: Both warning and overdue messages format remaining/overdue time as `"hoy"`, `"1 día"`, `"6 días"`, `"1 semana"`, `"1 semana 5 días"`, `"2 semanas"` (semanas if ≥7 days, días if less, mixed when needed). Logic in `ProposalStageTracker.format_remaining_time` (Python) and `useStageStatus.formatRemainingTime` (JS, kept in sync via parallel test cases).
- **Recipients**: Internal team via `NOTIFICATION_EMAIL` CSV (see Automated Emails table above).
- **Internal-only**: `ProposalProjectStage` is gated by `is_admin` context in `ProposalDetailSerializer.get_project_stages` — never exposed to public proposal views.

### 3.2 Portfolio Showcase

- Public listing and detail pages (`/portfolio-works/`, `/portfolio-works/{slug}`)
- Bilingual content (title, excerpt, structured JSON with problem/solution/results)
- Cover image upload or external URL
- SEO metadata (meta title, description, keywords per language)
- Admin CRUD with JSON import/duplicate/publish flow
- Sitemap data endpoint for SEO

### 3.3 Blog System

- Public listing with featured post hero, category filtering, pagination (`/blog/`)
- Detail page with structured JSON rendering or HTML fallback (`/blog/{slug}`)
- Bilingual content with SEO metadata
- Author profiles, read time estimates, cover images with credit attribution
- 17 categories (technology, design, AI, marketing, etc.)
- Admin CRUD with JSON import, duplicate, publish, calendar view
- Sitemap data endpoint
- **LinkedIn Publishing** — admin can connect a LinkedIn account via OAuth 2.0 and publish/unpublish blog post summaries (with cover image) directly to LinkedIn from the panel; OAuth tokens stored encrypted via Fernet (`LinkedInToken` singleton model)

### 3.4 Contact Form

- Public form (`/contact/`) with fields: name, email, phone, project description, budget range
- Budget ranges: 500-5K, 5-10K, 10-20K, 20-30K, >30K
- Submits to API, triggers email notification to admin
- Success page (`/contact-success/`)

### 3.5 Document System

- Generic branded PDF documents separate from proposals
- Above the folder list, the same segmented control as Communications switches
  entity navigation between **Projects** and **Clients**. Each mode lists the
  complete operational catalog, including entities with zero folders/documents,
  and its separate counters include the full descendant inventory exactly once.
  **Show non-active projects** is off on every visit and inclusively reveals
  projects whose operational effect is neither development nor operating; it
  never removes active projects. Turning it off while one of those projects is
  selected returns to **All**. Inactive clients keep their existing secondary
  group. Project lifecycle never archives documents by itself.
- **Show archived** is a different control: it changes the active/archived
  content scope for any project, client or manual folder and sits immediately
  before **Own folders**. Neither toggle changes or persists the other.
- **Without project** and **Without client** are permanent destinations in their
  respective modes. Selecting an entity or unassigned bucket scopes the document
  list; the chosen grouping persists per staff account between visits. Descending
  into a folder owned by that project or client keeps the entity selected and
  represents both coordinates in the URL, so the sidebar never claims **All**
  while the user is still inside the entity's hierarchy.
- **Own folders** remains a separate, always reachable section. It contains
  only manual roots with neither project nor client. Assigning a root to either
  entity removes it from this section without moving its tree. Managed project
  roots remain valid structural parents but do not appear as editable manual
  folders. Opening an own or unrelated root clears both entity filters; a
  descendant with `folder_kind=manual` does not clear them when it still belongs
  to the selected project or client.
- Every project belongs to the Document and Communication catalogs and owns at
  most one managed root, identified by `DocumentFolder.managed_project`. New
  projects provision their standard root at creation; ordinary edits to
  historical projects only synchronize an already adopted root and never create
  a missing one. There is no per-module opt-out that can make the catalogs drift.
  Users may create arbitrary descendants but cannot rename, move, archive or
  delete the managed first level. Deleting a project preserves its former root
  and content as a manual folder instead of cascading document loss.
- A new project root starts with Cuentas de cobro, Propuestas, Entregables and
  QA. Content and subfolders created below it inherit the project and client
  when the caller does not provide an explicit association. Cuentas de cobro
  and Propuestas carry stable system keys: generated records for a project are
  filed below this same managed root, never in a second physical
  `Proyectos / {project}` tree. Generated filing refuses to provision a missing
  historical root: that project must pass the reviewed reconciliation first.
- Existing roots are reconciled only through a review artifact: a dry-run plan
  records every proposed project conversion/creation, explicit nesting of a
  related legacy root, client-root assignment, explicit assignment of a
  folderless/projectless document to a project, document filing, skip and
  conflict. Applying
  requires every decision, the exact plan digest, a verified backup reference,
  an unchanged fingerprint of projects/clients/folders/documents and a separate
  inverse snapshot path. A reviewed `nest_project_root` may place an explicitly
  mapped legacy root under the one canonical project root; a client root remains
  top-level and receives a client. Folderless project documents move only to an
  exact canonical path approved in the artifact. Manifest v5 accepts repeatable
  `--assign-document-project DOCUMENTO:PROYECTO` directives: generated records
  use their keyed canonical path and ordinary documents enter the managed root.
  Placed, already linked or client-conflicting records never move by inference.
- `GET /api/document-folders/project-readiness/` remains a staff-only operational
  diagnostic for an empty catalog or roots pending reconciliation. It reports
  active/archived lifecycle counts independently from document archival, but the
  sidebar no longer exposes PA-108 implementation warnings to end users.
- Client visibility is an independent `is_client_visible` gate. The legacy
  draft/published field remains only during the expand/contract rollout and no
  longer represents the internal workflow.
- **Administrable workflow**: one document may carry one active state from an
  exclusive cycle group plus any number of additive signals. The editable seed
  catalog is Borrador, Enviado, En revisión, Bug atendido, Cerrado and Solucionar
  bug; stable `system_key` values keep integrations working after a rename.
- **Episode history**: activating a state opens an episode; completing or removing
  it closes that episode with a distinct outcome, actor, exact timestamp, optional
  note and append-only event. A state may recur in multiple episodes, and opening
  times can be corrected when an event was recorded late.
- The list and editor show cycle first, then signals, including live duration.
  Solucionar bug has a high-attention treatment. History opens in a short timeline
  with exact and relative times, duration, actors, notes and linked observations.
- States can be created inline with duplicate suggestions, renamed/recolored,
  retired when unused, or merged from the catalog view. The catalog reports active
  document and historical-episode counts and blocks rule changes that would make
  current documents invalid.
- State filters are OR within the dimension, support absence (for example “without
  Cerrado”), and include the recurring presets Algo por solucionar, Enviados sin
  cerrar, Cerrados and Por clasificar.
- Adding an observation may open Solucionar bug. Resolving or discarding the
  final pending observation closes/removes a linked signal created by notes;
  manually opened states are never closed by note reconciliation. Sending a
  standalone document email may open Enviado after explicit confirmation.
- **Discarding is evidence; deletion is cleanup**: discarding preserves the
  observation and its optional reason because it existed and was intentionally
  not addressed. Deletion is available for pending, resolved and discarded
  observations that never should have existed. It removes them from active
  lists/counts but keeps a recoverable trash row.
- Every deletion confirmation shows the complete selected content and warns that
  copies already sent by email or message remain external to ProjectApp. Bulk
  deletion is one atomic operation within one document. Restoring a pending note
  reopens or reuses its compatible note-origin state; conflicts roll back the
  restoration. Audit activity records actor and time without copying content.
- Structured JSON content stored in `content_json` field
- PDF generation via `DocumentPdfService` + `MarkdownParser` + shared `PdfUtils` layer
- Admin CRUD panel (`/panel/documents/`) with create, edit, list and state-catalog management
- **Document threads** relate a linear history without changing folders, clients
  or projects. A document belongs to at most one thread; a new thread takes the
  source document title as its editable name and needs at least two documents.
  Removing members until only one remains dissolves the thread automatically.
- Each membership owns an editable day-level chronology date. It defaults to the
  document `issue_date`, or to the Bogotá date of `created_at` when the document
  has no issue date; a stable position resolves equal dates deterministically.
- The list action drawer and the editor open the same workspace modal. Its
  **Relacionar**, **Detalle** and **Cronología** tabs search across folders and
  organisational scopes, preview markdown/PDF, and show the ordered story.
  List rows and cards expose `Hilo · N` without leaking the relationship into
  folder navigation.
- Archived documents keep their membership and are labelled in the thread.
  Candidate search hides them by default and can include them explicitly.
  Documents already assigned to another thread remain visible but disabled with
  the reason. Deleting a linked document is blocked until it is unlinked;
  duplicating a document never copies its membership.
- Threads stay out of client-facing document payloads, but the Documents MCP
  reads and builds them: five tools cover reading a thread, listing threads,
  creating one, editing its members incrementally and dissolving it. Membership
  edits are `link`/`unlink` rather than a full replacement, so a caller cannot
  destroy a history by omitting a member, and linking is limited to active
  markdown documents.
- **Long-name containment**: list and gallery titles are always bounded by their
  cell/card. The collapsed state uses one line with ellipsis and exposes the same
  measured **Ver completo/Contraer** path for names with spaces or systematic
  underscore/date naming; the expanded state may break anywhere. Folder comes
  first in a separate metadata row below the title. Rows without a folder keep
  natural height.
- **List priority**: desktop columns use the fixed order Actions, Title, States,
  Created/Date/Archived, Client and Project. Actions remains first and only
  Title width is user-persisted. Landscape retains Actions, Title, States and
  Date as columns and groups Client/Project under Title. Compact cards keep
  Title/States primary and order secondary metadata as Date, Client, Project.
  Project stays low priority until PA-55 backfills historical associations.
- **Private notes**: creation and editing keep the email subject, complete email body,
  WhatsApp message, and an ordered collection of custom title/content notes in one
  optional modal. Every non-empty value has an individual 📋 copy action with ✅
  feedback. These administrative fields never render in markdown/PDF and are never
  exposed in the client document portal.
- In an existing document, **Guardar cambios** in the notes modal persists those
  fields immediately and confirms it visibly; no second page-level save remains.
  During creation, **Aplicar al borrador** states that the document still has to be
  created before the notes are stored.
- The Documents MCP can create, read, and partially update all private notes. Every
  report created through `client-report` continues to generate and persist only the
  canonical subject/email/WhatsApp triple; `client-message` reuses that copy without
  producing a second version. Custom notes remain independently managed metadata.
- Bilingual support (es/en)
- **Folders & workflow states**: folders remain the structural hierarchy. The former
  colored document tags were consolidated into additive workflow states instead of
  leaving two overlapping user-facing systems; legacy tag assignments are expanded
  into open episodes with an explicitly unknown opening time during migration.
- **Generated-document filing**: an issued collection account is filed from its
  Bogotá issue date under `Proyectos / {project} / Cuentas de cobro / YYYY /
  MM - Mes`. Without a project it uses `Clientes / {client} / Sin proyecto`;
  without an identifiable client it uses `Sin clasificar`. Missing levels are
  created idempotently. For a project, “Proyectos” is the sidebar section and
  `{project}` is its managed root; the stored tree therefore begins at that
  root. Cancellation moves the same record to `Anuladas`; a
  never-issued cancellation uses `Sin emitir / Anuladas`. Retrying delivery
  keeps the same document; issuing a replacement after cancellation creates a
  new account/number while the annulled original remains in its branch.
- System-owned folders carry a stable `system_key`. They remain navigable but
  cannot be renamed, moved, reordered, archived or targeted by manual document
  creation through the panel, REST or MCP. Issued accounts and generated PDF
  snapshots cannot be dragged out of their canonical branch.
- Account titles follow `YYYY-MM-DD · public number · concept`. Their visible
  state is derived from the commercial lifecycle plus real email delivery
  history, so draft/issued/sent/send-failed/paid/cancelled never depend on a
  loose manual workflow episode and never appear in Por clasificar.
- Issuance stores the collection account as one immutable PDF artifact. The
  exact retained bytes power its Documents preview, every download and both
  initial/retry email attachments; a later template or accounting edit may not
  regenerate or replace them. The document intentionally has no artificial
  Markdown body. Title, associations, canonical folder and accounting facts are
  read-only after issuance; private observations, archive/restore and document
  threads remain available. Corrections use cancel + reissue.
- Historical issued accounts are repaired by a dry-run-first backfill. The
  earliest exact PDF attachment retained in email history wins; current-data
  reconstruction is used only when no attachment evidence exists, and its
  provenance is recorded separately.
- The editor displays a discreet slash-separated path below the title. Root and
  every folder segment are links to that location and expose normal pointer,
  hover and keyboard focus feedback. Inline/full Markdown previews and immutable
  PDF previews are centered at document-like widths, use bounded viewport-aware
  heights and scroll internally for long content.
- Every initial proposal send, resend and multi-send stores the exact PDF bytes
  attached to the email as an immutable `vNN` Document snapshot, named
  `YYYY-MM-DD · Propuesta comercial · title · vNN` and filed under the parallel
  `Propuestas comerciales / YYYY / MM - Month` hierarchy while it has no
  project. Observations remain editable; source data, folder and workflow state
  do not. Acceptance moves every retained version under the managed project's
  canonical `Propuestas / YYYY / MM - Month` branch.
- Historical folderless collection accounts are handled by the dry-run-first
  `backfill_collection_account_filing` command. Applying it uses the same live
  rule, preserves manually classified records and skips rows whose issue date
  cannot be established.
  - Folder deletion is **blocked (HTTP 409)** when the folder contains documents; the admin must move or delete each document first. The DB FK keeps `on_delete=SET_NULL` only as a safety net for non-API removals.
  - Folder mutations from `FolderManagerModal` re-fetch both the documents list and the folder store so the sidebar count and order reflect the change without a page reload.
- **Context-preserving navigation**: the list URL is the canonical representation of
  folder, normal/archived scope, workflow states, client/project, global search,
  ordering, view mode, page and focused document. Every editor exit returns to that validated list
  URL and identifies its destination; browser Back restores the same list state.
  Entity-owned descendant folders therefore preserve both `folder` and the active
  `project`/`client` through the edit-and-return cycle.
  Direct or untrusted editor entries have no valid origin and fall back to the
  localized Documents root.
  - Collection accounts keep their separate commercial lifecycle and are excluded
    from the generic state catalog and legacy-tag expansion.

### 3.5.1 Client Communications Registry

- **Separate product module, shared infrastructure**: communications are not a
  `Document` subtype. They reuse client/project identities, document references,
  session auth, panel primitives and the existing `content` Django app while
  keeping conversation-specific models, API, store and route.
- A client can own multiple simultaneous threads; a thread may optionally be
  scoped to one of that client's projects.
- A thread contains chronologically ordered messages with channel, direction,
  occurred date, exact content and operational state. Incoming messages are
  optional but first-class, so a reply remains readable beside its origin.
- **State semantics**: outgoing messages are draft or sent; incoming messages are
  received. “Respondido” is derived from a valid opposite-direction reply and
  does not overwrite the stored send fact.
- **Document-manager navigation**: the module has a resizable side panel that
  switches between projects and clients, includes aggregate counts and keeps
  threads without a project reachable through an explicit **Sin proyecto**
  entry. The project axis always lists the same canonical `Project` catalog as
  Documents, including zero-thread projects; lifecycle effects group suspended,
  completed, decommissioned or archived projects under **Proyectos archivados**
  without excluding them. On compact screens the same navigation moves into the
  shared drawer.
- **List, not duplicate detail**: below the landscape breakpoint each thread is
  a compact summary card; landscape and larger profiles retain the comparative
  table with **Asunto** as its identity column. Both projections show only the
  thread title in that identity surface; message bodies remain exclusively in
  the detail. The list never exposes message content or an inner horizontal
  scrollbar.
- **Canonical cuts**: navigation, searchable multi-value filters and ordering
  live in the URL. A thread opens in a workspace modal addressed by
  `thread=<id>`, so closing it or using browser Back restores the exact list.
  The shared filter strip starts with the factory cuts **Borradores pendientes**,
  **Enviados sin respuesta**, **Abiertos**, **Cerrados**, **Correo** and
  **WhatsApp**; every option shows its full-dataset count, including zero, and
  the active cut remains reachable. User-named views coexist as visibly distinct
  **Propia** tabs. Both kinds can be reordered, while module reset restores only
  the factory order/visibility and preserves every user view.
  Frequent combinations can be named and restored through the accounting saved
  filter mechanism. Global text search covers the thread title, readable client,
  project name, message subject and message content through the shared REST/MCP
  query service. Order resolution is explicit URL → active saved view → account
  preference → recent.
- **Manual-channel boundary**: recording what the operator sent or received via
  WhatsApp or email is the chosen operating model, not a provisional phase. The
  product never claims that ProjectApp delivered it, and the interface does not
  promise a future automatic-delivery capability.
- The explanatory notice describes that current manual workflow, can be closed
  after it is understood and remains reachable from contextual help.
- **References, never copies**: messages link existing `Document` rows through a
  protected join. Document detail exposes reverse usage, and a referenced
  document cannot be deleted accidentally.
- Delivered messages are immutable: corrections create append-only dated audit
  rows and annulments require a reason. Drafts remain editable and deletable;
  every successful edit preserves its supplied old/new values in an append-only
  revision while keeping the same message identity.
- The decision record, comparison and phased roadmap live in
  `docs/superpowers/specs/2026-08-25-client-communications-registry-design.md`.

### 3.6 Contract System

- Reusable contract templates (`ContractTemplate`) with customizable sections and parameter substitution
- Contract PDFs generated via `ContractPdfService` using ReportLab + shared `PdfUtils`
- **Draft mode**: generate contract PDF without contractor signature block for review
- **Final mode**: include contractor signature block once contract is agreed
- **Public proposal draft**: Spanish proposals may expose the current default template as **Contrato y condiciones**. Its first panel explains the draft at the same usable width as the linked clause index; its second panel renders the full contract vertically inside a bordered, layered paper surface that remains readable in light and dark themes. The dedicated PDF download is available from the persistent floating action, always forces the global template, masks personal data, omits signatures, and applies the `BORRADOR` watermark.
- The public draft is intentionally independent from proposal-specific `ProposalDocument` contracts and from proposal prompt/section JSON. It is current global content, not a per-proposal snapshot.
- Font: Helvetica throughout for consistent cross-platform rendering
- Clickable Table of Contents with anchor links to contract sections
- `ProposalDocument` links a generated contract to a specific proposal
- `CompanySettings` provides company branding data (name, logo, address, tax ID) used in PDF headers

### 3.7 Data Model Entities

- Reusable JSON-schema–defined data models (`DataModelEntity`) for project technical requirements
- `ProjectDataModelEntity` links a data model entity to a specific project, with optional custom schema override
- Technical requirements sync: project requirements can be synchronized from data model entity definitions
- JSON upload endpoint to bulk-import entity schemas
- Accessible via platform project data model tab (`/platform/projects/:id/data-model`)

### 3.8 Web App Diagnostics

A second sales product alongside proposals: a structured **web-app diagnostic** delivered to a prospect via a public UUID link, mirroring the proposal's JSON-section architecture (rewritten Apr 16, 2026).

- **`WebAppDiagnostic` entity** with 8 typed `DiagnosticSection`s (`purpose`, `radiography`, `categories`, `delivery_structure`, `executive_summary`, `cost`, `timeline`, `scope`), each with `visibility` ∈ initial/final/both.
- **Admin** (`/panel/diagnostics/`): create, edit (base + status-gated tabs: General, Correos, Documentos, Secciones, Prompt, JSON, Activity, Analytics), a send-initial → mark-in-analysis → send-final lifecycle, per-language defaults (`/panel/diagnostics/defaults`), and full analytics parity with proposals (engagement score, funnel, device breakdown, sessions).
- **Public view** (`/diagnostic/{uuid}/`): sidebar-indexed sections, PDF download, share, dark-mode toggle, per-section dwell tracking.
- **NDA / confidentiality**: an optional confidentiality PDF can be attached to diagnostic emails.

### 3.9 Platform — Expanded Modules

Building on the base Platform (auth, projects, kanban), these modules extend client collaboration:

#### Bug Reports
- Client and admin can submit, track, and resolve bug reports per project
- Global view (`/platform/bugs`) + per-project view (`/platform/projects/:id/bugs`)

#### Change Requests
- Structured change request workflow per project
- Global view (`/platform/changes`) + per-project view (`/platform/projects/:id/changes`)

#### Deliverables
- Track project deliverables with status and descriptions
- Global view (`/platform/deliverables`) + per-project view (`/platform/projects/:id/deliverables`)

#### Notifications
- In-platform notification center (`/platform/notifications`)
- Centralizes alerts across all platform modules

#### Payments
- Track payment milestones and subscription plans per project
- Global view (`/platform/payments`) + per-project view (`/platform/projects/:id/payments`)
- Linked to proposal investment section (hosting tiers, payment milestones)
- New hosting offers use exactly three prepaid periods: quarterly (10% discount), semiannual (20%), and every 9 months (40%). Monthly and annual remain readable only on historical records.

#### Global Board + Profile
- `/platform/board` — global kanban view across all projects
- `/platform/profile` — user profile management page

### 3.10 Marketing / Landing Pages

- **Home** (`/`): main company page with animations, portfolio highlights, services overview
- **Landing Web Design** (`/landing-web-design`): targeted landing for web design services
- **Landing Software** (`/landing-software`): targeted landing for software development
- **Landing Apps** (`/landing-apps`): targeted landing for mobile app development
- **About Us** (`/about-us`): team and company information
- All pages fully responsive with GSAP animations

### 3.11 Project Detail — URLs, Django Credentials & Notes

Each project has one operational detail for consulting, copying and editing its
product access data. Panel staff open it as a modal from the project list or
card; platform admins open the project-scoped route
`/platform/projects/:id/access`. `/platform/access` remains only as a
compatibility redirect.

- **Product URLs**: production, staging and repository URL.
- **Fixed environments**: production and staging each own a Django admin URL,
  admin username and independently encrypted admin password through
  `ProjectAdminAccess` (one unique row per project/environment).
- **Notes**: `ProjectAccessNote` stores multiple title/content entries. All note
  content is encrypted at rest; a note marked sensitive is masked until an
  explicit reveal or copy action.
- **Interaction**: every value has an icon action for copy; fields save
  individually without closing the detail. Passwords begin masked and use an
  explicit reveal control. Destructive password/note deletion is confirmed.
- **Visibility**: Django staff through the session/CSRF panel API and platform
  users with the admin role through the JWT API. Client-role users cannot see
  the navigation item or access the route/API.
- **Security**: passwords and note bodies use Fernet with
  `PROJECT_ACCESS_CIPHER_KEY`. General project serializers and the deprecated
  access list never return plaintext credentials. Every project-access payload
  is `Cache-Control: no-store`; plaintext is returned only by dedicated reveal
  endpoints and is kept in ephemeral component state. Operational URLs, both
  access models and legacy credential fields are explicitly excluded from MCP.
- **Compatibility migration**: legacy generic admin credentials move
  automatically only when the admin URL hostname matches exactly one of the
  product hostnames. Ambiguous rows remain intact and the detail offers an
  explicit production/staging classification that refuses overwrites.
- **Backend**: the shared handlers in `accounts/project_access_api.py` serve
  equivalent `/api/projects/:id/access/` (panel) and
  `/api/accounts/projects/:id/access/` (platform) contracts for detail, per-field
  update, reveal/delete password, note CRUD/reveal and legacy classification.

### 3.12 Admin Panel Enhancements

- **Panel Login** (`/panel/login`) — dedicated login page for admin panel
- **Panel Admins** (`/panel/admins`) — admin user management (invite, list, manage admin accounts)
- **Internal Kanban Task Board** (`/panel/tasks`) — admin-only Kanban board for managing internal ProjectApp team work. Four columns: TO DO, In Progress, Blocked, Done. Tasks have title, description, status, priority (low/medium/high), assignee (FK to any admin User, optional), and due_date (optional). Cards display priority badge and due_date highlighted in red when overdue. Drag-and-drop between columns and reorder within columns via vuedraggable. Create/edit modal with confirm-guarded delete. Tasks are independent — no FK link to proposals or documents.
- **View Map operational Explorer** (`/panel/views`) — a third presentation mode complements the complete route list and module map with three understandable product spaces: **Panel interno**, **Plataforma de clientes** and **Experiencias públicas**. Each space exposes its main modules and representative submodules with stage, audience, purpose and operational value; the Panel and Platform each provide eight main modules, while the public space connects acquisition, content/proof, additional modules, financing, proposals and diagnostics. Hover and focus update the context without changing the URL, while selection creates a shareable `node` link. Users may navigate freely or start a guided space tour persisted with `tour=<space-id>`; exiting preserves the current module. Compact and portrait profiles use cards, and landscape or wider profiles use the orbital layout with relationships. Search, drag, keyboard rotation, zoom, pause and reduced-motion support remain available. Route names and source files are secondary disclosure, and all context is curated product information rather than live business data.
- **Responsive panel contract** — the internal panel is validated at 412, 835,
  1195, 1440 and 2560 px. Shared primitives own table column priorities,
  tab/filter collapse, modal widths and stacking, navigation, bulk/row actions,
  touch targets, typography and the 1400 px general-content ceiling. The canonical
  fleet standard, project inventory and implementation contract live in
  `docs/RESPONSIVE_STANDARDS.md`, `docs/RESPONSIVE_STANDARD.md` and
  `docs/methodology/responsive-standard.md`, respectively.
- **Responsive operational modules** — Documentos, Clientes and Proyectos preserve their useful information at 412, 835, 1195, 1440 and 2560 px. Below the canonical 1024 px landscape boundary, two-zone/filter-heavy interfaces collapse into one primary content stream plus explicit drawers/selectors, dense rows become labeled cards, every hover/drag action has a touch path, and phone modals use the full viewport. At 1195 px their desktop structures are active. At 2560 px the content column remains capped at 1400 px.
- **Readable document titles** — document names use end truncation by default. A single app-owned, viewport-aware hint exposes the complete name only when rendered measurement proves clipping; it reuses the same `BaseTooltip` primitive as row actions and never adds a duplicate browser `title`. Measurement repeats after web fonts load, and the same clipping condition exposes an in-place **Ver completo/Contraer** path for touch layouts. In list mode, Título is adjustable from 240 to 520 px (320 px default) through a visible labelled separator, remembered per browser and reset by double click. The 520 px maximum is content-backed: the 2026-08-28 production inventory contained 40 titles, its longest had 56 characters and required an estimated 496 px including cell padding and safety. Proyecto, Cliente and Fecha yield space in that order, while Estados and Acciones stay fixed. After donor minima, only the table wrapper scrolls. Middle truncation was evaluated and intentionally deferred because conditional reveal preserves the full value without inventing a second naming rule.
- **Leading three-dot row actions** — every panel table whose row control is a single three-dot menu places it at the start with no visible heading. Selectable tables use Checkbox → Actions → Identity/Content; the action track is fixed at 56 px, does not join the data-width split, and opening it cannot activate row navigation. The adopted surfaces are Documents, Proposals, Diagnostics and both classic/grouped Incomes tables. Tables that still expose several loose action icons, including Collection Accounts, remain outside this contract until their actions are explicitly consolidated into one menu.

### 3.13 Internationalization (i18n)

- Two locales: `en-us` (English, default) and `es-co` (Spanish Colombia)
- Prefix strategy: `/en-us/about-us`, `/es-co/about-us`
- Lazy-loaded translation files
- Geo-locale detection plugin for automatic language suggestion
- Language store with sync plugin

### 3.14 Accounting (Superuser Finance)

Internal double-ledger bookkeeping at `/panel/accounting/*`, restricted to superusers (shipped 2026-07-03).

- **Three ledgers** — company + two partners (Gustavo, Carlos) — with a **partner-split invariant**: a personal-ledger record must be 100% the owning partner's (enforced in `PartnerSplitMixin.clean()`).
- **Sub-ledgers**: incomes, expenses, hosting, recurring payments, ads spend, pocket movements, and weekly card-balance snapshots — each with server-side + client-side filters and modal CRUD.
- **Dashboard & charts** per year; **exports** to CSV/XLSX per section and a full-year multi-sheet workbook.
- **Card-debt reminder**: a weekly Huey task emails the partners every Friday cycle until a card snapshot dated on/after that Friday is registered (re-alerts every 2 days).
- **Income lifecycle** (2026-07-16, #110): incomes carry a kind — *expected* (projection), *liquid* (actually received; a liquidation modal links the settled record to the projection it fulfills via an `expected_income` FK), or *lost* (write-off excluded from projections). The incomes view reports received-% and lost totals; expenses expose a paid/pending state. Liquidation defaults its destination to the ProjectApp pocket, with an optional exact-payment-date toggle (#114); income/expense `period_date` accepts a full date besides YYYY-MM.
- **Collection-account linked income** (2026-08-26): the selector opens on the chosen client's *expected* incomes and resets to that stable default on every open and client change. This is a reversible kind filter, not a restriction: *all* and *liquid* remain selectable. Kind—not payment status—defines the default, so a partially paid expected income remains eligible. An empty result offers a one-click expansion to all kinds while retaining client scope, then to global scope only when that client has no eligible income; the last choice is not remembered.
- **Pocket as entry point** (#103): pocket movements sync bidirectionally with income/expense records. A pocket egreso attributed to a partner mirrors a **company-ledger expense 100% assigned to that partner** — every pocket draw reduces company liquid utility and the partner's participation, never the personal ledger (#114).
- **Display standards** (#115/#116): emails format COP with the millions apostrophe (`format_cop_email`) while the app uses dot grouping; all dates render as "Jue, 16 jul 2026" (abbreviated Spanish weekday + short month) via the backend Bogotá helpers and the frontend `utils/formatDate.js`.
- **Credit-card catalog & statements** (#105/#106): registered cards with quota (debt computed server-side as quota − available), monthly statements with editable transactions + PDF and an 8-day reminder, plus summary cards for card debt and current-month expected income.
- **Recurring COP projections** (2026-08-22): the server owns each recurring payment's COP equivalent. It derives the charge from price + currency + the current manually configured USD rate, then prorates it by frequency for the monthly column. Editing any input or saving a new exchange rate refreshes the row and all dependent totals; a data migration repairs historical stale values.
- **Recurring lifecycle and row actions** (2026-08-27): grouped and classic rows expose one leading three-dot menu for edit, duplicate-as-draft, activate/deactivate, reminder mute and archive. Duplicate inherits the commercial definition but recalculates its next reference date and writes nothing before form confirmation. Active, non-archived rows are the only recurring payments counted by budget totals, participation percentages, charts, dashboard/calendar notices and exports' aggregate metadata. Archive is recoverable and preserves the definition/audit trail; restore always returns inactive, while permanent deletion is restricted to archived mistakes. Current rows support atomic bulk activate, deactivate and archive. Turning a recurring definition into a real expense/pocket movement and browsing its charge history remain a separate feature because that changes the ledger's source-of-truth boundary.
- **Audit trail** (`AccountingChangeLog`) + notification-recipient settings.
- **Responsive accounting workspace** (2026-08-22): the twelve tabs share one navigation contract, saved-filter strips collapse to selectors below 1024 px, KPI groups preserve the three business priorities and disclose secondary values, and every table declares which fields stay, group or hide. Grouped client headers stack their totals in narrow layouts; long workflows use semantic full-screen mobile modals and touch-safe action menus. Pocket never drops the running balance: compact rows relocate it below the movement amount and the independent column returns from landscape width. The repeatable 12-tab × 5-width acceptance script lives in `docs/ACCOUNTING_RESPONSIVE_TEST_SCRIPT.md`.
- **Grouped collection accounts** (2026-08-26): `/panel/accounting/collections` alternates between the classic table and one grouped view, using the same segmented interaction as Incomes. Grouping is one criterion at a time — client or project — and orders groups by pending amount descending, alphabetical ties, with the unassigned group last. Every header shows count, issued, pending, collected and cancelled amounts plus draft/issued/overdue/paid/cancelled counts; overdue intentionally overlaps issued. The footer totals the complete filtered set. Live projects, historical project snapshots (`(histórico)`) and truly missing projects are distinct. View and criterion are global accounting settings, saved immediately and editable from Accounting Settings.

### 3.15 MCP Connectors (claude.ai)

Remote Model-Context-Protocol connectors that expose panel modules to claude.ai custom connectors, managed at `/panel/mcps` (superuser-gated; shipped 2026-07-02/03).

- **Connectors**: blog, documents, proposals, diagnostics, clients, tasks,
  accounting, LinkedIn personal and communications — each a token-authenticated
  JSON-RPC tool server (`content/mcp/*`) grouped by module and exposed through one
  registered slug.
- **Management**: generate/rotate a one-time connector URL (plaintext token shown once, only its SHA-256 hash stored), toggle active, and watch a connection-activity feed (handshake / tool_call / auth_error / origin_rejected).
- **Security**: Origin validation (DNS-rebinding defense), per-connector token, active-state gate.
- **Communications**: exposes the panel's administrative lifecycle through
  fourteen explicit tools. It lists and opens active/archived threads; creates
  and edits manual threads; closes, reopens, archives and restores them; records
  incoming messages and outgoing drafts; edits or deletes eligible drafts;
  confirms external delivery; and annuls or date-corrects historical messages
  with audit evidence. Project/document ownership, immutable client history and
  state rules come from the same serializers and services as the panel. It never
  sends through a provider. Migration `content.0212_seed_communications_mcp`
  creates the connector disabled and tokenless; migration
  `content.0239_expand_communications_mcp_parity` only refreshes its description,
  so activation and existing credentials remain under operator control.
- **Parity**: Documents exposes client, project and workflow states; Accounting
  exposes hosting periods, allocations, partial payments and settlement history.
  `content/mcp/contracts.py`, focused tests and `docs/MCP_VALIDATION_RUNBOOK.md`
  make every exposed model field and repeatable validation scenario explicit.
- The `client-report` skill publishes session change-reports and their canonical
  subject/email/WhatsApp note to the Documents connector; custom notes remain
  available for manual or direct MCP use.

### 3.16 Client Document Portal & Signing

Client-facing document delivery + click-to-accept signing at `/platform/documents` — the landing page for a client after first login.

- Lists the **main contract** (`requires_signature`) first, then annexes; each downloadable as a branded PDF.
- **Email-ownership OTP**: before signing, the client validates their email via a 6-digit code (`email/verify/request` + `/confirm`); `UserProfile.email_verified` gates the sign button.
- **Signing**: click-to-accept with a consent checkbox records `signed_at/signed_by/signature_name/signature_ip/signature_user_agent`; idempotent re-signs.
- **Team milestone notifications** fire (best-effort, in-app + email) on first login, email validated, and document signed.

### 3.17 Representative Development Dataset

Development and test environments have one cross-module dataset contract:

- a default target of 60 root rows where the domain is list-shaped, including a
  60-row heavy project for requirements, deliverables, changes and bugs;
- coherent client → project → income → collection-account and client → thread →
  message relationships, with document creation routed through the production
  service layer;
- deliberately skewed clients, lifecycle states and histories instead of uniform
  random samples;
- past/current/future date buckets and UI-breaking long unbroken labels and large
  amounts;
- isolated random streams plus an explicit business-date anchor for exact replay;
- an atomic, fail-fast refresh guarded by a positive capability that remains hard
  false in production settings;
- an executable model inventory that makes fake-data ownership part of the same
  delivery as every future model.

The canonical counts, commands and exceptions are maintained in
`docs/FAKE_DATA_COVERAGE.md`.

---

## 4. Target Users

### Admin (Seller / Company Owner)
- Creates and manages business proposals
- Tracks client engagement and follows up
- Manages portfolio works and blog content
- Receives notifications via email and WhatsApp

### Client (Prospect)
- Receives unique proposal link via email
- Chooses between executive, detailed, technical, and contract reading modes; the contract itself is a continuous vertical document with clause links
- Can accept, reject, negotiate, or comment on proposals
- Can share proposal with stakeholders
- Can download PDF version

---

## 5. Non-Functional Requirements

- **Explain disabled controls**: A disabled panel control must state why it is
  unavailable. If the operator can resolve the block, every missing prerequisite
  is shown as adjacent text and remains available on hover, keyboard focus and
  touch; lifecycle, permission and positional limits still expose a specific
  reason. A transient operation uses its active status label. The collection
  account flow additionally warns about clients without email in the selector
  and permits an explicit inline repair without losing the draft.
- **Consistent panel actions**: Every operational action rendered with an icon under `/panel/**` must resolve its glyph and default accessible name from one shared Heroicons 24 Outline catalog. Icon-only controls expose exactly one short, readable hover/focus hint, an accessible name and a touch target of at least 44×44 px. Row context belongs in the accessible name, not in the visual hint, and an application tooltip must suppress the duplicate native browser `title`; decorative, status and editable-content symbols are not action glyphs.
- **Text containment**: Every panel table, card and metadata row must contain
  arbitrary user/API strings, including values with no spaces, at every canonical
  viewport. Data-owned prose/identifiers wrap with intrinsic-safe break
  opportunities; truncation is allowed only when the complete value remains
  available through a disclosure, tooltip or detail view. Bounded dates, money and
  numeric values may remain atomic.
- **Responsive acceptance**: Every panel and public view must pass the same five automated reference viewports (phone 412 px, portrait tablet 835 px, landscape tablet 1195 px, laptop 1440 px, large monitor 2560 px), followed by the separately evidenced physical-device pass required for final certification. Shared components own repeated behavior; large-monitor content keeps an explicit readable maximum width.
- **Pocket ledger on mobile**: Below 640 px, each movement is presented as one
  complete card rather than an eight-column table. Concept and signed value lead;
  date, direction, link/allocation state and the running figure remain available
  as labelled facts. Badges never split words, and the same edit/delete action is
  a leading 44 px target. The headline balance remains the all-ledger total;
  filtering changes the per-row figure to the cumulative total of visible rows.
- **Performance**: Hybrid SSR/SPA rendering; SSR for SEO-critical pages (home, landing, portfolio, blog), SPA for admin and proposal views
- **SPA fallback integrity**: Every non-prerendered panel, platform and proposal
  deep link must bootstrap from a generated Nuxt shell. The deployment build must
  reject an empty, redirecting, or mount-less `200.html` before replacing the
  currently served frontend. Django remains the authority for the locale chosen
  from the bare root.
- **Security**: Dual auth — session/CSRF for `/panel/`, JWT (SimpleJWT) for `/platform/`; staff-only admin endpoints; CORS/CSRF trusted origins; Fernet encryption for project admin credentials (`PROJECT_ACCESS_CIPHER_KEY`)
- **SEO**: Server-side rendered public pages, sitemap endpoints, meta tags, Google verification
- **Analytics**: Google Tag Manager, Google Analytics, Facebook Pixel, Microsoft Clarity, Cal.com booking tracker
- **Email**: SMTP via GoDaddy (smtpout.secureserver.net:465 SSL), HTML + text templates
- **Notifications**: WhatsApp via CallMeBot API
- **Backups**: django-dbbackup with configurable storage path, 4 backup retention
- **Monitoring**: Optional Silk profiler for query analysis (gated by env flag)

---

## 6. Business Rules Summary

1. Each proposal gets a unique UUID for public access
2. Proposals auto-expire when `expires_at < now()` (daily Huey cron)
3. 24h cooldown between automated client-facing emails per proposal
4. Automations can be paused per proposal
5. Engagement heat score (1-10) computed from views, section time, recency
6. Proposal sections map 1:1 to Vue components via `section_type` (18 section types; some are web-only and skip the PDF)
7. Default section content is configurable per language (admin-editable)
8. Email templates are editable and resettable via admin panel
9. Share links track independent view counts from main proposal views
10. Change logs record full audit trail of proposal lifecycle events
10a. **Qualified first view**: loading a public proposal does not change commercial metrics. A non-draft, non-staff browser must remain visible for five seconds and submit a valid heartbeat. The `(proposal, session_id)` pair is idempotent; historical views without delivery evidence are never retroactively emailed.
11. **Project stage notifications**: Stage rows are admin-managed (not auto-derived from JSON timeline). Warning fires once at 70% elapsed; overdue alert fires immediately when `today > end_date` and repeats every 3 days until `completed_at` is set. All day-level arithmetic uses Bogotá time (`today_bogota()` from `content/utils.py`). Internal team recipients live in `NOTIFICATION_EMAIL` CSV.
12. **Proposal client identity**: `BusinessProposal.client` is a FK to `accounts.UserProfile` filtered to `role='client'` (`on_delete=PROTECT`). Legacy denormalized fields `client_name` / `client_email` / `client_phone` are kept as write-through snapshots, synced via `proposal_client_service.sync_snapshot()` after every FK assignment. Empty client emails get a placeholder `cliente_<profile_id>@temp.example.com` (RFC 2606 reserved TLD) generated via two-step save. Clients with placeholder emails are excluded from **all 13 client-facing email methods** in `ProposalEmailService` and from the 4 huey reminder/urgency/abandonment tasks via `_is_unsendable_client_email(email)`. Two candidate-selection querysets (`abandonment_candidates`, `interest_candidates`) also exclude placeholders directly via `.exclude(client_email__iendswith=UserProfile.PLACEHOLDER_EMAIL_DOMAIN)`. Shipped 2026-04-09.
13. **Project scope items**: an accepted proposal's functional-requirement groups are mirrored into `ProjectScopeItem` rows (chain Project → ProjectPhase → ProjectScopeItem → Requirement) by `technical_requirements_sync`. Re-sync overwrites proposal-authored content unless an admin took over a card (`Requirement.content_overridden=True`); removed items are archived and re-added ones resurrected.
14. **Client document signing**: a client can only sign a `requires_signature` document after their email is verified via OTP. Signing records name/timestamp/IP/user-agent and is idempotent; it fires best-effort team milestone notifications (first login, email validated, document signed) that never block the client flow.
15. **Accounting partner split**: every accounting record carries a total plus per-partner amounts; a record on a personal ledger (Gustavo/Carlos) must be 100% that partner's (the other partner's amount = 0), enforced at `clean()`. Company amount is derived, not stored.
16. **Manual-only discount offer**: the discount/urgency email from the proposal actions menu is never sent automatically — it requires an explicit send and is only offered when a discount percentage is configured and the client has a real email.
17. **Hosting periodicities**: the current commercial offer is quarterly, semiannual, and every 9 months. The nine-month charge is the discounted effective monthly price multiplied by nine. Public proposal views and PDFs preserve the stored annual snapshot for closed/inactive proposals, while new operational project/subscription records always use the current 9/6/3-month catalog. Paid cycles and payments are immutable history.
18. **Contract proposal mode**: `show_contract_terms` is top-level proposal metadata, defaults to `True`, and only produces a public mode for Spanish proposals. It never changes the proposal prompt or section JSON. Preview and draft-PDF endpoints read the current default `ContractTemplate`, never a proposal-specific contract, and are unavailable when the proposal is inactive, English, or has the flag disabled.
19. **Server-owned derived values**: a persisted derived value is never accepted as independent input. When any source changes, the canonical backend write path refreshes the derivative in the same transaction. For recurring payments, `price + currency + current AccountingSettings.usd_exchange_rate → cop_equivalent`, and `cop_equivalent ÷ frequency_months → monthly_cop_cost`; changing the rate synchronizes every recurring row.
20. **Document workflow state**: active document state is derived only from open
    `DocumentStateEpisode` rows. Exclusive cycle states transition each other;
    additive signals may coexist unless the catalog declares an incompatibility.
    Closing means completed work and removing means the state was inapplicable; both
    remain in history as different outcomes. Non-null integration `system_key`
    values are unique inside each catalog at database level, while custom states
    may continue to share a `NULL` key.
21. **Document migration truthfulness**: legacy Published becomes client visibility,
    not an inferred cycle state. Existing draft/published documents receive no
    invented cycle classification; old tag assignments become additive episodes
    with unknown effective time, and old private note JSON becomes normalized notes
    with an unknown historical creation time.
22. **Communication history is evidence**: changing a project's client detaches
    its historical communication threads from the project instead of moving them
    to the new client. Deleting clients or documents is blocked while historical
    communication references remain.
23. **Project lifecycle meaning outlives its label**: project billing, reminders
    and closure use `DocumentState.operational_effect`, never an editable display
    name. Every transition is previewed, token-bound and recorded as a dated
    episode; legacy unclassified rows fail closed for financial automation.
24. **Searchable selectors inside modals**: secondary selectors render their
    result list in a floating layer owned by the modal, never inside its
    scrollable panel. A selector that is itself the primary decision uses an
    explicit permanent in-flow catalog instead: bulk client assignment opens
    with the rows visible, without click-triggered disclosure or reserved blank
    height. On desktop it exposes at least five complete clients and only a long
    catalog scrolls; the modal remains still, grows with its review content and
    caps at the viewport. On narrow screens it follows the shared full-screen
    contract. The catalog opens in stable A-Z order, its Nombre header toggles
    A-Z/Z-A and remembers that browser-local choice between openings; typing
    filters the visible rows and later pages load progressively. Each row shows
    name, company and email and flags missing email. Empty filters/catalogs offer
    client creation; read failures offer retry. A bulk action must show the
    affected count and record identities before confirmation without requiring
    the operator to scroll the modal.
24. **Observation removal semantics**: discard retains the row and optional
    reason; soft delete removes it from active reads and counts while preserving
    recoverability. Deleting the last pending note reconciles only a linked
    note-origin episode, and the entire bulk selection succeeds or fails together.
25. **No browser-native dialogs in panel flows**: `/panel` confirmations, data
    requests and errors use application-owned modals or inline alerts. Native
    `alert`, `confirm` and `prompt` are prohibited and guarded in CI.
26. **Cross-cutting proposal scope is contextual but structurally stable**:
    `functional_requirements.groups` keeps `cross_cutting_features` immediately
    after `features` and non-empty. Sellers may keep, rewrite, remove or add its
    individual items according to the proposal context, without duplicating
    specific business behavior or promising unsupported compliance targets.
    Default-config snapshots and active drafts receive the new group; sent,
    inactive and otherwise historical proposal snapshots remain unchanged.
27. **Indicator headers preserve content priority**: KPI cards use a fixed
    label/value/reserved-support structure, consistent help and an explicit
    action. Expanded views keep meaningful non-zero indicators in business
    order and separate lifecycle from operational questions. In Proyectos both
    expanded groups share the same compact card geometry and column widths; a
    bounded support line cannot make an operational card taller. Compact project
    and income headers collapse to two actionable summaries whose drawers retain
    the full detail, including zero-valued states, so the first list row remains
    visible in the initial 412×915 viewport.
28. **Proposal send messages are authored evidence, not fallback copy**: every
    proposal stores one editable plain-text `email_intro` in the canonical
    **Correos** tab. It states the client's problem, the proposal's solution and
    the expected business outcome. Drafts may persist it empty, but initial,
    repeated, bulk and multi-proposal sends all fail before side effects while
    any required message is blank. The email keeps its predefined body, inserts
    the message immediately afterward and before commercial blocks, and stores
    the rendered delivery as immutable history. A resend starts from the latest
    saved message and may persist an edit without changing prior deliveries.


## Documentación para formalización

En Documentos de cada propuesta se descargan el contrato final y los anexos comercial/técnico curados. El correo de formalización precarga tres adjuntos seleccionables, admite documentos de la propuesta, Para/CC y secciones ordenables con Markdown seguro. La revisión muestra los archivos que se enviarán. Las secciones de venta, ROI, CTA y evolución futura quedan fuera de los anexos; la curaduría no inventa obligaciones ni criterios. Si falta información estructurada indispensable, se corrige en la propuesta o se desmarca el documento. Una preparación obsoleta o vencida no se puede enviar.

## Programa de Alianza: exclusividad conceptual (2026-09-25)

La opción de cinco años incorpora la renuncia de Project App. a desarrollar
para otros clientes proyectos competidores del mismo sector y nicho que
reproduzcan conceptos, ideas o enfoques específicos del producto acordado.
Rige durante los cinco años originales; un segundo ciclo no la extiende.
Sector, nicho, producto y conceptos se delimitan por escrito en propuesta y
contrato. La modalidad de tres años conserva sus condiciones y excluye este
compromiso adicional. Confidencialidad, propiedad intelectual y competencia
leal siguen siendo obligaciones independientes en ambas modalidades.

La redacción distingue el compromiso contractual de la apropiación de ideas
generales ([Ley 23 de 1982, art. 6](https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=3431))
y de los supuestos legales de imitación desleal
([Ley 256 de 1996, art. 14](https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=38871)).
El otrosí conserva su revisión jurídica previa a firma.

### Organización y lectura de comunicaciones (2026-09-25)

El equipo puede organizar conversaciones completas en carpetas/subcarpetas por cliente/proyecto, identificar documentos e hilos por su ID y encontrarlos mediante búsqueda exacta. El lector permite saltar al inicio/final, plegar la redacción y sus detalles conservando datos, y copiar mensajes directamente. Los hilos madre mantienen su papel de entrada y la organización no modifica el histórico.
