---
trigger: model_decision
description: Project intelligence and lessons learned. Reference for project-specific patterns, preferences, and key insights discovered during development.
---

# Lessons Learned — ProjectApp

This file captures important patterns, preferences, and project intelligence that help work more effectively with this codebase. Updated as new insights are discovered.

> **Lección verificada 2026-09-04 — una capa flotante pertenece al overlay que
> la abre:** un tooltip con `position: fixed` y un número de `z-index` mayor no
> puede superar por sí solo un modal que vive en otro stacking context. La
> solución estable es teletransportarlo al floating root del diálogo mediante
> contexto, conservando `body` como fallback para usos independientes. Y cuando
> dos listados comparten semántica de agrupación, conviene reutilizar la tabla y
> proyectar grupos con funciones puras; persistir una preferencia sólo debe
> ocurrir si el producto lo exige explícitamente.

> **Lección verificada 2026-09-04 — dos controles visibles deben seguir siendo
> dos decisiones de dominio:** que un nivel de confianza haga más probable una
> inclusión no autoriza a persistirla. Serializer, MCP, formulario, tabla y mocks
> deben preservar el campo que el usuario no tocó. La representación también
> necesita un dueño único: un círculo semántico reutilizable evita que lista,
> modal y detalle diverjan, y su estado neutro comunica ausencia de clasificación
> sin confundirla con riesgo bajo. Las copias de registros reinician estado
> operativo; el histórico se conserva salvo una decisión explícita de migración.

> **Lección 2026-09-04 — una entrega y sus destinatarios tienen cardinalidades
> distintas:** SMTP necesita una sola envolvente visible para To/CC, mientras la
> auditoría necesita estado, cliente y rol por dirección. Duplicar el envío como
> solución de persistencia altera privacidad, métricas y semántica. La frontera
> estable es un `delivery_id` compartido, una fila por dirección y una proyección
> agrupada para listados; el snapshot conserva los encabezados originales para
> que el reenvío exacto no dependa de una fila representante. La validación y el
> límite deben vivir también en backend, aunque todos los compositores reutilicen
> el mismo picker frontend.

> **Lección verificada 2026-09-04 — desactivar efectos no debe romper el
> contrato del composable:** una rama como preview puede omitir analytics,
> storage, watchers y lifecycle hooks, pero sus consumidores deben seguir
> recibiendo la misma forma pública. Un objeto neutral con `refs` vacíos y
> operaciones no-op mantiene la página renderizable y hace explícito qué se
> desactiva, sin obligar a cada consumidor a defenderse de `undefined`.

> **Lección verificada 2026-09-03 — una política comercial editable necesita
> identidad temporal:** topes, porcentajes, mora y calendario forman parte del
> significado legal de un otrosí. Una fila mutable sirve para preferencias, no
> para reglas contractuales. La revisión inmutable, el `PROTECT`, la tasa USD
> congelada y la adopción opt-in de borradores permiten actualizar la oferta sin
> reescribir acuerdos históricos ni confundir lo vigente con lo pactado.

> **Lección 2026-09-03 — una previsión humana necesita dos ejes y un dueño de
> cierre:** estar en la lista y la confianza estimada no son el mismo dato; unirlos
> impediría conservar candidatos aún no clasificados o retirar temporalmente uno
> sin borrar el juicio anterior. El KPI también debe nombrar qué suma: aquí es el
> valor original de seleccionados verdes, mientras el modal separa abonado y saldo.
> La deselección automática pertenece a los caminos que cierran el ingreso
> (liquidación, pérdida o cambio de ledger), no a una consulta que esconda estado
> inválido sin corregirlo. Los fixtures de gráficos deben contener al menos una
> serie no nula cuando el resultado esperado es un canvas y no el empty state.

> **Lección verificada 2026-09-02 — paridad MCP es un contrato, no una lista
> de tools:** sumar handlers aislados deja módulos con reglas y riesgos
> diferentes. La unidad mantenible es un manifiesto que relaciona operación del
> Panel, servicio compartido, esquema, riesgo, permiso, auditoría y compatibilidad.
> Una edición documental existente puede parecer ausente cuando el catálogo no
> explica editabilidad, bloqueos y nombre canónico del campo.

> **Lección validada 2026-09-03 — lo comercial y lo contractual comparten
> reglas, no exposición:** la condición de mora y el beneficio del segundo ciclo
> deben nacer del mismo dominio, pero sólo su explicación general es pública.
> Identidad, valores, calendario, borradores poblados y documentos firmados
> pertenecen a endpoints administrativos y a snapshots auditables.

> **Lección 2026-09-02 — una oferta informativa necesita una sola fuente
> comercial:** JSON público, vista de distribución y PDF deben proyectar el
> mismo contenido canónico; duplicar copy entre capas convertiría una condición
> legal en tres versiones distintas. Los acordeones reservan el detalle para las
> reglas de juego y la primera lectura explica valor, alternativas e impacto.
> Cuando una condición depende de un catálogo vivo, el fallback debe mantener la
> página disponible y declarar la desincronización al operador. Las acciones
> flotantes también deben reservar espacio entre sí: que ambas sean visibles no
> garantiza que ambas sean clickeables.

> **Lección 2026-09-02 — entregar contenido no equivale a observar atención:**
> un `GET` sólo demuestra que el servidor respondió; no que el documento quedó
> visible ni que el lector interactuó. La evidencia comercial necesita umbral
> explícito, validación completa e idempotencia por sesión. Y una tarea encolada
> no es una notificación entregada: su estado debe persistir antes del broker,
> reconciliar reclamos estancados y separar el éxito SMTP del enriquecimiento
> diagnóstico posterior para no convertir observabilidad en duplicados.

> **Lección 2026-09-02 — una tarea asíncrona debe colorear el evento, no el
> objeto vivo:** una entidad como Bolsillo admite entrada y salida, de modo que
> su tipo por sí solo no basta y consultar el registro cuando Huey ejecuta puede
> leer una edición posterior o no encontrarlo. La dirección que afecta la
> presentación debe viajar como snapshot inmutable en la auditoría. Los
> históricos sólo se completan cuando el diff aporta evidencia; lo desconocido
> permanece neutral en vez de inferirse desde el presente.

> **Lección 2026-09-02 — ordenar una fecha visible exige una sola proyección:**
> si activos y archivados muestran fechas distintas, el servidor debe construir
> una clave por fila con esa misma semántica y ordenar antes de paginar; ordenar
> el arreglo del navegador sólo reacomodaría la página actual. El estado de una
> vista compartida debe propagarse explícitamente para no filtrarse a otros
> consumidores del store. Y una dirección solicitada no es todavía una dirección
> activa: ante un fallo de recarga se conservan datos, URL y affordance previos.

> **Lección 2026-09-02 — carpeta y entidad pueden ser un mismo recorrido:**
> no toda carpeta manual representa un cambio hacia Carpetas propias. La
> pertenencia real (`folder.project`/`folder.client`) decide si el eje activo se
> conserva; `folder_kind` describe gestión, no contexto de navegación. El clic
> interceptado y el `href` deben consumir la misma función pura, porque cualquier
> divergencia degrada también el origen que luego restaura un editor.

> **Lección 2026-09-01 — una reacción caricaturesca pertenece al glifo, no al
> perímetro:** mover pocos píxeles el contenido comunica presión y aterrizaje sin
> desplazar el layout ni competir con el foco accesible. El resultado de una
> acción es otra capa: copiar puede mostrar un check sólo después de verificar la
> escritura, mientras fallo conserva el affordance original para reintentar.

> **Lección 2026-09-01 — paridad no implica reintroducir el shell:** una vista
> pública puede compartir capacidades con propuestas —tema, guía, compartir y
> PDF— sin volver a montar su encabezado ni copiar su composición completa. Las
> acciones deben compartir contrato, pero el contenido y la persistencia de la
> guía pertenecen al dominio. Un modal teletransportado necesita recibir el tema
> explícitamente; y una acción de compartir debe leer la URL actual, no
> reconstruirla, porque el identificador de selección forma parte del alcance.

> **Lección 2026-09-01 — una historia documental merece una entidad propia:**
> carpeta, cliente y proyecto describen ubicación o pertenencia; no deben
> reutilizarse para representar secuencia. Un contenedor de hilo más una
> membresía única protegida expresa la regla “máximo un hilo”, permite cruzar
> scopes sin mover archivos y hace explícito el bloqueo de borrado. La fecha de
> negocio y la posición estable deben vivir en la membresía, no inferirse en
> cada lectura, porque el orden es parte de la historia editable.

> **Lección 2026-09-01 — una respuesta asíncrona pertenece a su intención:**
> stores, modales y probes de archivos necesitan un identificador de generación,
> no sólo un booleano loading. Cuando cambia documento, búsqueda o fuente, una
> respuesta anterior puede ser correcta para su request y aun así ser incorrecta
> para la pantalla actual. El consumidor sólo aplica el resultado si la
> generación sigue vigente; al extraer componentes usados fuera de Nuxt, sus
> dependencias también deben importarse explícitamente para que el contrato sea
> verificable en aislamiento.

> **Lección 2026-09-01 — el orden del modal también expresa responsabilidad:**
> contexto persistente, validación corregible y fallo de una acción no deben
> competir junto al CTA. El contexto amarillo permanece cerca del encabezado;
> el requisito rojo pertenece al control que puede resolverlo; y el error del
> servidor pertenece al paso que lo produjo. Una sola fuente puede seguir
> bloqueando Confirmar sin duplicarse visualmente en el footer. En responsive,
> la prueba debe entrar por la acción que el usuario realmente ve —drawer en
> tarjetas, acción de fila en tabla— antes de evaluar el modal compartido.

> **Lección 2026-09-01 — identidad visible y trazabilidad son contratos por
> destinatario:** `UserProfile` no expone `full_name`; cualquier comunicación
> que nombre a un cliente debe reutilizar `build_client_display_name` y cargar
> su `user` sin N+1. En un digest consolidado no basta probar el primer log: cada
> destinatario necesita los mismos targets para diagnosticar tanto una entrega
> exitosa como un fallo, y la cadencia nunca debe avanzar si el transporte no
> aceptó el mensaje.

> **Lección 2026-09-01 — excluir previews en la frontera de escritura:** una
> vista interna debe reconocerse por una credencial verificable —la sesión
> Django staff— y detener toda mutación antes de crear eventos, incrementar
> contadores o completar datos del destinatario. IP, navegador o URL no prueban
> identidad; si el equipo abre el enlace sin sesión, el sistema debe contarlo
> como externo. Centralizar la regla evita que catálogo, propuesta y diagnóstico
> diverjan, y conservar el histórico evita inventar una reclasificación que los
> datos anteriores no pueden sostener.

> **Lección 2026-08-31 — editar un borrador no debe borrar su historia:** la
> mutabilidad previa al envío y la trazabilidad no son opuestas. La operación
> conserva la identidad del mensaje, bloquea la fila, valida el estado final y
> escribe diff, documentos y actividad en una sola transacción. Exponer esa
> edición por MCP debe reutilizar el mismo servicio del panel y mantener separada
> la persistencia del hecho de cualquier transporte externo.

> **Lección 2026-08-31 — corregible e inmutable necesitan superficies
> distintas:** un requisito incompleto o un error de serializer pertenece al
> campo, aparece después del intento y se limpia cuando cambia ese valor. Una
> restricción permanente no debe fingir ser validación del formulario: conserva
> el control deshabilitado y una explicación accesible. En componentes
> compartidos, esta distinción puede aplicarse por dominio sin alterar el contrato
> vigente del otro catálogo.

> **Lección 2026-08-31 — activación, proceso y resultado son estados distintos:**
> un pulso inmediato sólo confirma la entrada; no debe fingir que una operación
> asíncrona terminó. El primitive visual cubre botones y enlaces icon-only, el
> loading pertenece a la tarea y el resultado sólo se presenta cuando existe
> evidencia. En particular, copiar se considera exitoso al resolver Clipboard
> API, no al invocarla. Mantener el glifo estable preserva reconocimiento; el
> tooltip temporal y la región viva comunican éxito o fallo. Un guard transversal
> es necesario porque corregir únicamente el icono donde se detectó el problema
> deja que el mismo defecto reaparezca en otras superficies. Al hacer más
> expresiva una reacción compartida, el movimiento debe aislarse del transform
> del control: animar un wrapper interno evita desplazar botones posicionados o
> pelear con escalas hover. Alternar el nombre del keyframe permite que clics
> rápidos reinicien el pulso sin remount ni manipulación imperativa del DOM.

> **Lección 2026-08-30 — catálogo, ubicación y archivo son dimensiones
> distintas:** una migración de esquema no equivale a adoptar datos históricos,
> y una entidad sin contenido todavía pertenece al catálogo. La inclusión del
> proyecto es canónica y compartida por módulos; su grupo activo/archivado se
> deriva del efecto operativo, sin archivar documentos. La raíz se identifica
> con la relación única `managed_project`, no con otro booleano. La ubicación
> física sólo cambia mediante un manifiesto revisado, respaldado y protegido
> contra drift; una rama histórica relacionada sólo se anida con una directiva
> explícita. Ciclo de proyecto y archivo de contenido también son ejes distintos:
> dos toggles independientes deben nombrarlos, y ocultar una opción seleccionada
> exige volver a un destino visible. En la interfaz, proyecto, cliente y carpeta
> propia son ejes excluyentes, pero una carpeta descendiente asociada pertenece
> al mismo recorrido que su entidad: sólo cambiar a Carpetas propias o a una
> entidad distinta debe limpiar el contexto, no acumular una intersección
> invisible.

> **Lección 2026-08-30 — una directiva explícita completa la autoridad del
> manifiesto:** los documentos sueltos no deben inferirse por nombre. Una pareja
> documento→proyecto revisada puede ser autoridad sólo si el registro sigue sin
> carpeta/proyecto y el cliente es compatible; la ruta final se calcula con las
> reglas canónicas y el inverso conserva tanto FKs previas como carpetas creadas.

> **Lección 2026-08-30 — wrap según semántica del tooltip:** una explicación
> extensa necesita cortes seguros, pero un rótulo breve de acción necesita una
> sola línea. El primitive debe ofrecer una política por defecto y dejar que el
> consumidor elija; aplicar `overflow-wrap:anywhere` indiscriminadamente puede
> convertir el ancho intrínseco en una columna de letras.

> **Lección 2026-08-30 — preferencias vs. filtros:** la preferencia personal
> aporta el fallback de una visita limpia; una URL o vista guardada debe seguir
> reproduciendo exactamente el recorte explícito y ganar precedencia. Migrar una
> clave local sólo al crear el perfil evita que un navegador viejo sobrescriba
> preferencias ya sincronizadas desde otro dispositivo.

> **Lección 2026-08-30 — idioma y presentación son preferencias distintas:**
> el locale gobierna los datos que entrega el servidor y la vista sólo gobierna
> cómo se recorren. Un enlace compartido puede proponer el idioma inicial sin
> bloquear al lector; tarjetas/lista/acordeón deben consumir el mismo detalle y
> persistirse por ámbito para que el panel no altere la experiencia pública.

> **Lección 2026-08-29 — el error pertenece al campo:** un formulario no debe
> resumir junto al CTA lo que puede señalar exactamente en el control. La misma
> fuente del mensaje debe gobernar borde, relación ARIA y limpieza al editar;
> el footer conserva sólo acciones y, si hiciera falta, un conteo sin repetir
> nombres. “Opcional” no se escribe cuando el asterisco ya define la convención.

> **Lección 2026-08-29 — factory tabs y vistas propias:** compartir una tira no
> significa compartir propiedad. Las definiciones de fábrica viven en código y
> sus filas persistidas guardan sólo orden/visibilidad; las vistas propias son
> datos del usuario. Sembrar y restablecer debe desplazar/renumerar, nunca borrar,
> estas últimas. Los conteos se calculan en una consulta separada sobre el dataset
> completo para que el filtro activo no se convierta en un filtro implícito de
> todos los demás.

> **Lección 2026-08-29 — una relación canónica y un vacío diagnosticable:**
> `Document.project` no sustituye la ubicación estructural que el sidebar
> representa. Si la raíz gestionada es la fuente de verdad, todo filing
> automático debe colgar de ella y toda adopción histórica debe atravesar el
> mismo manifiesto revisado. Un endpoint pequeño de readiness puede conservar el
> diagnóstico operativo sin convertir detalles de migración en un aviso para el
> usuario final.

> **Lección 2026-08-29 — telemetría visible:** un tab abierto no equivale a
> atención. Todo heartbeat de engagement debe obedecer Page Visibility, cerrar
> una sola vez al ocultarse y protegerse contra requests concurrentes; de lo
> contrario degrada analytics y carga backend al mismo tiempo.

> **Decisión consolidada — 2026-08-28:** un historial probatorio captura la
> evidencia antes del envío, nunca desde el documento vivo. El snapshot se
> comparte entre destinatario principal y copias, y una brecha legada se declara
> en lugar de llenarse con una suposición.

> **Lección 2026-08-28 — catálogo adicional:** un enlace comercial debe fijar
> qué módulos se eligieron, no duplicar su contenido. Así la selección permanece
> estable mientras las correcciones editoriales llegan a todos los clientes. La
> migración semilla crea el inventario una sola vez; los enlaces nunca heredan
> precios ni datos de una propuesta, y las URLs seleccionadas usan `noindex`
> aunque el catálogo canónico sí sirva para captación.

> **Lección 2026-08-31 — descubribilidad comercial:** que una capacidad exista
> dentro de un modal no la vuelve operable. La URL canónica y el PDF completo
> deben ser visibles antes de seleccionar módulos; la personalización y el
> tracking son un segundo camino explícito. Etiquetar ambos evita prometer
> seguimiento sobre una URL indexable o compartir todo cuando se quería curar
> una selección.

---

## 1. Architecture Patterns

### Content Storage: Structured JSON over CMS
- Proposal sections, portfolio works, and blog posts use Django `JSONField` for content
- Each proposal section's `content_json` maps directly to a Vue component's props schema
- Blog supports dual format: structured JSON (preferred) with HTML fallback via `v-html`
- This avoids the need for a full CMS while keeping content rich and structured

### Single Django App: `content`
- All models, views, serializers, and services live in the `content` app
- This works for now but may need splitting if scope grows significantly
- Models are already split into individual files under `content/models/`

### Service Layer Pattern
- Business logic lives in `content/services/`, not in views
- Views are thin FBV wrappers that call service methods
- Services (30 modules): `ProposalService`, `ProposalEmailService`, `ProposalPdfService`, `ContractPdfService`, `EmailTemplateRegistry`, `PdfUtils`, `DocumentPdfService`, `MarkdownParser`, `CollectionAccountService`, `CollectionAccountPdfService`, `TechnicalDocumentPdf`, `TechnicalDocumentFilter`, `PlatformOnboardingPdf`, `LinkedInService`, `DiagnosticService`, `DiagnosticEmailService`, `DiagnosticPdfService`, `DiagnosticDocumentsService`, `AccountingService`, `AccountingExportService`, `AccountingEmailService`, `AccountingCardReminderService`
- MCP tool servers live in `content/mcp/` (`protocol`, `actor`, `tools` + per-domain connector modules), not in `services/` — they wrap existing service/ORM calls behind a token-authed JSON-RPC surface for claude.ai

### Editable labels need immutable operational meaning

- A user-managed status name cannot safely drive billing, reminders or closure.
- `DocumentState` is shared across domains through `catalog`; project behavior keys
  off `operational_effect`, while names/descriptions/colors remain editable.
- Help for an administrable business label needs two layers: user-owned copy says
  what the team means by the state, while system-owned copy derived from
  `operational_effect` states what the application will do. Never let editable help
  redefine billing, reminders or closure behavior.
- Two catalog states may intentionally share one operational effect. **Activo** and
  **En evolución** remain distinct reporting meanings but both preserve operation
  and billing, avoiding a combinatorial multi-state model for this bounded case.
- Removing an operational project state is a data migration, not only a choices
  edit: migrate the canonical state, compatibility mirror and every historical
  episode together, record the merge fact, and apply the target state's financial
  consequences. The former **Pausado** meaning was therefore consolidated into
  **Suspendido**, which is now the only reversible stop.
- Financially consequential transitions use preview + token + atomic revalidation.
  This prevents a confirmation made against stale income/payment data from applying.
- Ambiguous migrated rows fail closed for money and stay explicitly reviewable; a
  migration must not invent whether a legacy archive was a good close or a shutdown.

### External API Integration Pattern (LinkedIn)
- External OAuth integrations follow the singleton model + service module pattern
- `LinkedInToken` (singleton, pk=1) stores Fernet-encrypted access/refresh tokens in the DB; encryption key from `LINKEDIN_ENCRYPTION_KEY` env var
- `linkedin_service.py` encapsulates the full OAuth flow + API calls — views stay thin
- Follow this pattern for any future third-party OAuth integration (e.g., Twitter/X, Instagram)

### PDF Generation Layer
- `pdf_utils.py` is the shared utility layer — fonts, colors, layout helpers, reusable drawing functions
- `proposal_pdf_service.py`, `contract_pdf_service.py`, and `document_pdf_service.py` all depend on `PdfUtils`
- Never duplicate PDF primitives across services — add to `pdf_utils.py` and import from there
- All PDF services use ReportLab directly (no external PDF library abstraction)

---

## 2. Code Style & Conventions

### Backend: Function-Based Views (FBV)
- **All** DRF views use `@api_view` decorators, not class-based views
- Never convert to CBV unless explicitly requested
- The proposal views module is very large — be careful with edits and prefer localized changes

### Frontend: Pinia Options API
- **All** Pinia stores use Options API pattern: `{ state, getters, actions }`
- Do NOT use Composition API (`setup()`) style for stores
- HTTP requests go through `stores/services/request_http` centralized service

### Bilingual Content Pattern
- Models have paired fields: `title_en`/`title_es`, `content_json_en`/`content_json_es`, etc.
- Frontend reads the appropriate field based on current locale
- Proposals have a `language` field (`es`/`en`) that determines which default content to use

### Naming Conventions
- Backend: snake_case for everything (Python standard)
- Frontend stores: snake_case file names (`portfolio_works.js`, `proposals.js`)
- Frontend components: PascalCase (`BusinessProposal/Greeting.vue`)
- Frontend composables: camelCase with `use` prefix (`useExpirationTimer.js`)

---

## 3. Development Workflow

### Backend Commands Always Need venv
```bash
source venv/bin/activate && <command>
# or
venv/bin/python <command>
```

### Huey Immediate Mode in Development
- When `DJANGO_ENV != 'production'`, Huey tasks execute synchronously
- No need to run Redis or Huey worker for development
- Tasks still need to be importable and functional

### Frontend Dev Proxy
- Nuxt proxies `/api`, `/admin`, `/static`, `/media` to Django at `127.0.0.1:8000`
- Both servers must be running simultaneously for full functionality
- In production, everything goes through Django (no separate Nuxt server)

### Test Execution Rules
- Never run the full test suite — always specify files
- Backend: `pytest backend/content/tests/<specific_file> -v`
- Frontend: `npm test -- <specific_file>`
- E2E: max 2 files per `npx playwright test` invocation
- Use `E2E_REUSE_SERVER=1` when dev server is already running

---

## 4. Production Deployment

### Build Flow
1. Frontend: `npm run build:django` → generates `backend/static/frontend/`
2. Backend: `python manage.py collectstatic` → copies to `backend/staticfiles/`
3. Restart: `sudo systemctl restart projectapp && sudo systemctl restart projectapp-huey`

### Django Serves Nuxt Pages
- The `serve_nuxt` catch-all view in `projectapp/views.py` serves pre-rendered Nuxt pages
- This is the LAST URL pattern — all other routes take priority
- CDN URL for assets configurable via `NUXT_APP_CDN_URL`

---

## 5. Email System

### Template Registry Pattern
- All emails defined in `EmailTemplateRegistry` with default content
- Admin can override content via `EmailTemplateConfig` model
- Admin can disable specific emails via `is_active` flag
- Preview rendering available for all templates

### 24h Cooldown Rule
- `last_automated_email_at` field on `BusinessProposal` tracks last automated email
- All automated email tasks check this before sending
- Manual sends (admin clicks "Send") bypass the cooldown

### Composed Email Pattern (Branded + Proposal)
- Shared `_send_composed_email()` method reads templates from registry (not hardcoded paths)
- `send_branded_email()` — thin wrapper, no side effects beyond email + log
- `send_proposal_email()` — creates `ProposalChangeLog(EMAIL_SENT)` + updates `last_activity_at`
- Rate limited: 1 email per minute per template_key per proposal via `EmailLog` query
- `EmailLog.metadata` JSONField stores greeting, sections, footer, attachment_names for history
- View layer: shared `_parse_composed_email()` returns `(data, error_response)` tuple; 3 handler helpers (`_send_composed_email_view`, `_get_email_defaults_view`, `_list_emails_view`) serve 6 thin public views
- Frontend: single `ProposalEmailsTab.vue` with `mode` prop ('branded'/'proposal') + computed `basePath`

### Automations Pause
- `automations_paused` flag on `BusinessProposal` stops all automated emails
- Each Huey task checks this flag early and returns if paused

### Structured `email_delivery` Result, Not Silent Bool
- `ProposalEmailService.send_proposal_to_client` returns `{ ok, reason, detail }` (built via the module-local `_delivery()` helper). Reasons: `sent`, `placeholder_email`, `template_disabled`, `send_failed`, `unexpected_error`.
- `ProposalService.send_proposal`, `resend_proposal`, and `_send_initial_email` propagate this dict — they never swallow failures into `logger.exception` alone.
- The admin views (`send_proposal`, `update_proposal_status`, `resend_proposal`) attach `email_delivery` to the response via the local `_proposal_admin_response()` helper in `views/proposal.py`. The status change still returns 200 (status DID change) but the body tells the truth about the email.
- Frontend stores read `response.data.email_delivery` and the panel toast surfaces the failure reason instead of a generic success. If you add a new email side effect, follow this pattern — never return a bool that the view ignores.

### Defense-in-Depth on Status Transitions That Trigger Emails
- Multiple UI paths can trigger the same transition (`draft → sent` exists in: dedicated "Enviar al Cliente" button, actions modal, and the inline status dropdown).
- Every endpoint that performs the transition must trigger the same side effects. `update_proposal_status` delegates `draft → sent` to `ProposalService.send_proposal` rather than re-implementing the save+email+schedule. If a future endpoint exposes the same transition, route it through the service — never duplicate the save-only path.

---

## 6. Proposal System Specifics

### Proposal creation automation must preserve runtime decisions
- Generate from `ProposalService.get_default_sections()`, then validate through `ProposalFromJSONSerializer` and create through `build_proposal_from_json`; hardcoded templates miss admin-edited defaults.
- `BusinessProposal.total_investment` is the base. The effective client total adds each selected calculator module after per-module rounding, so a quoted all-inclusive total must first be converted into a base that reproduces it.
- Persist `selected_modules` and a `calc_confirmed` change log even when the confirmed selection is empty; otherwise default-selected modules can silently re-enter scope.
- Hosting numbers live on `BusinessProposal`, while `investment.hostingPlan` is presentation. Setting only the JSON is insufficient because public/PDF serializers normalize from the model.

### Section Types Are Fixed
- 18 section types defined in `ProposalSection.SectionType` choices
- Each maps to a specific Vue component in `components/BusinessProposal/`
- Unique together constraint: `(proposal, section_type)` — one of each per proposal

### Heat Score (1-10)
- Pre-computed and cached in `cached_heat_score` field
- Updated by tracking endpoint and periodic task (`refresh_all_heat_scores`)
- Based on: view count, section time, recency, engagement patterns

### Change Log Types
- 20+ change types in `ProposalChangeLog.ChangeType`
- Includes: created, updated, sent, viewed, accepted, rejected, resent, expired, duplicated, commented, negotiating, reengagement, call, meeting, followup, note, calc_confirmed, calc_abandoned, auto_archived, status_change, cond_accepted, calc_followup, email_sent, req_clicked

---

## 7. Contract System Patterns

### Contract PDF Generation
- `ContractPdfService` generates PDFs via ReportLab using Helvetica font for consistent cross-platform rendering
- **Draft mode**: `is_draft=True` suppresses the contractor signature block — use for review cycles
- **Final mode**: includes full contractor signature block with name, date, and signature line
- Clickable Table of Contents generated at PDF start with anchor links to each section heading
- Template parameter substitution: `{{client_name}}`, `{{company_name}}`, etc. replaced at render time using `CompanySettings` + proposal data

### Data Model Entity Patterns
- `DataModelEntity` stores a reusable JSON schema (field definitions, types, constraints) independent of any project
- `ProjectDataModelEntity` associates an entity with a project and optionally overrides its schema
- Technical requirements sync: syncs project `Requirement` entries from the linked data model entity's schema fields
- JSON upload via API endpoint allows bulk creation of entity schemas from external tools
- Platform UI: `/platform/projects/:id/data-model` tab shows linked entities and allows sync actions

## 8. Platform / Accounts App Patterns

### Dual Auth Strategy
- `/panel/` admin uses Django session + CSRF (same as before)
- `/platform/` uses JWT via SimpleJWT (access + refresh tokens)
- Platform stores use `composables/usePlatformApi.js` (axios instance with JWT interceptors)
- Content stores use `stores/services/request_http` (axios with CSRF)
- **Never mix these two HTTP clients**

### Platform Store Naming
- Platform stores use kebab-case: `platform-auth.js`, `platform-clients.js`, `platform-projects.js`, `platform-requirements.js`
- Content stores use snake_case: `portfolio_works.js`, `proposals.js`

### Accounts Services (19 modules)
- `services/onboarding.py` — profile completion flow
- `services/tokens.py` — JWT token generation/refresh
- `services/verification.py` — OTP code generation and validation (login + email validation purposes)
- `services/password_reset.py` — password-reset OTP flow
- `services/client_flow_notifications.py` — best-effort team milestone alerts (first login / email validated / document signed); never raises
- `services/technical_requirements_sync.py` — mirrors accepted-proposal FR groups into `ProjectScopeItem` + `Requirement` rows (respects `content_overridden`)
- `services/hosting_billing.py` + `services/payment_notifications.py` + `services/project_phases.py` — hosting multi-phase billing/proration + payment alerts
- `services/impersonation.py` — panel→platform admin impersonation exchange
- `services/image_utils.py` — avatar processing
- `services/credential_cipher.py` — generic Fernet encrypt/decrypt for project passwords and note bodies; `_get_cipher()` is `@lru_cache(maxsize=1)` so the key is read once; pytest supplies an isolated key and clears the cache per test
- `services/project_access.py` — serializes the non-secret detail, encrypts writes and performs conflict-safe legacy classification for production/staging

### Encrypted Project Access Pattern
- `ProjectAdminAccess` owns one credential set per project/environment; a
  database constraint prevents a second production or staging row.
- `ProjectAccessNote` normalizes multiple title/content notes. Every body is
  encrypted, not only notes marked sensitive; the flag controls presentation.
- Plaintext passwords and sensitive note bodies leave the backend only through
  dedicated reveal endpoints. All detail and reveal responses are `no-store`.
- General project serializers expose at most `has_admin_password`; the legacy
  list no longer returns usernames/passwords, and MCP explicitly excludes both
  sensitive models plus legacy credential fields.
- Panel and Platform reuse one Vue editor and one API adapter, but preserve the
  authentication boundary: `request_http` for session/CSRF and
  `usePlatformApi` for JWT.
- Frontend plaintext stays in ephemeral refs/reactive entries and is cleared on
  hide, save, deletion and unmount; it is never stored in Pinia or localStorage.
- Legacy values are auto-moved only for one exact hostname match. Ambiguity is a
  first-class state: the UI asks for production/staging, and a transactional
  conflict guard refuses to overwrite populated destination fields.

### Platform Layout
- `layouts/platform.vue` with collapsible sidebar, mobile drawer, theme toggle
- Role-based navigation: admin sees all, client sees own projects only
- Dark mode support via `usePlatformTheme` composable

---

## 9. Testing Insights

### Backend conftest.py
- Custom coverage report with Unicode progress bars replaces default pytest-cov output
- `api_client` fixture provides unauthenticated DRF APIClient
- Content tests have their own `conftest.py` with model-specific fixtures

### E2E Flow Definitions
- Every navigation flow must be registered in `docs/USER_FLOW_MAP.md` and `frontend/e2e/flow-definitions.json`
- E2E tests must reflect real user integrations
- Follow quality standards from `docs/TESTING_QUALITY_STANDARDS.md`

### CI Sharding
- Playwright E2E tests are sharded into 5 parallel jobs
- Blob reports are merged after all shards complete
- Test quality gate runs after all test suites pass

### Known Test Issues
- `usePlatformApi.test.js` has 4 failing tests due to `window.location.href` assertions in JSDOM
- JSDOM doesn't support real navigation; `window.location.href` stays as `http://localhost/` after assignment
- Fix: use `delete window.location` + `Object.defineProperty` or mock `window.location` properly

### Playwright + Nuxt Dev Server Patterns
- **Never use `networkidle`** with Vite/Nuxt dev server — HMR WebSocket keeps connection alive, causing infinite hang
- Use `{ waitUntil: 'domcontentloaded' }` in `page.goto()` + explicit element waits (`getByRole('heading').waitFor()`)
- **Always add `test.setTimeout(60_000)`** to describe blocks for SPA routes — first visit triggers Vite on-demand compilation
- **Strict mode violations** are common when sidebar navigation duplicates page content text. Fix patterns:
  - Scope to `page.locator('main')` for page-specific content
  - Use `getByRole('heading', { name: '...' })` instead of `getByText('...')`
  - Use `{ exact: true }` when substring matching causes ambiguity (e.g., 'Activo' vs 'Activos')
- **i18n prefix strategy** adds locale prefix to all `<NuxtLink>` hrefs — use regex in `toHaveAttribute('href', /\/platform\/...$/)`
- **`<label>` without `for` attribute**: `getByLabel()` won't work. Use `page.locator('input[type="date"]')` or `page.locator('select').first()`
- **HTML5 validation bypass**: For testing custom validators, add `novalidate` via `page.evaluate(() => document.querySelector('form').setAttribute('novalidate', ''))`
- **Port conflicts**: Use `E2E_PORT=3001 E2E_REUSE_SERVER=1` when port 3000 is occupied

---

## 10. Cross-Language Shared Logic

### Technical Fragment Content Check (Python ↔ JavaScript)
- `_technical_fragment_has_content()` in `backend/content/views/proposal.py` and `technicalFragmentHasContent()` in `frontend/utils/technicalProposalPanels.js` implement the **same logic** in two languages
- Both determine whether a technical document fragment has real content based on the `content_json` structure
- **If the technical document schema changes** (new fragments, renamed keys, new fields), **both files must be updated together**
- The Python version is used by the analytics funnel to decide which fragments to show; the JS version is used by the client-facing proposal viewer to decide which panels to render

### Stage Time Formatter (Python ↔ JavaScript)
- `ProposalStageTracker.format_remaining_time(days)` in `backend/content/services/proposal_stage_tracker.py` and `useStageStatus.formatRemainingTime(days)` in `frontend/composables/useStageStatus.js` implement the **same** Spanish duration formatter (`"hoy"`, `"1 día"`, `"1 semana 5 días"`, `"2 semanas"`)
- Used by the warning + overdue email subjects on the backend AND the badge labels in the Cronograma admin tab on the frontend
- Both have parallel test suites covering the same case table (0, 1, 2, 6, 7, 8, 12, 14, 15, 21, -12 days). Update both test suites together if you change the format.

---

## 11. Pinia Reactivity (Vue 3 + Options API stores)

### In-place mutation, not spread + reassign

When updating nested arrays inside `currentProposal` (or any other top-level state), **mutate by index** — do not create a new array and reassign the parent:

```js
// ✅ Correct — matches the established pattern in proposals.js
const idx = this.currentProposal.sections.findIndex((s) => s.id === sectionId);
if (idx !== -1) {
  this.currentProposal.sections[idx] = response.data;
}

// ❌ Wrong — silently fails to propagate through computed → prop chains
this.currentProposal = {
  ...this.currentProposal,
  sections: this.currentProposal.sections.map((s) =>
    s.id === sectionId ? response.data : s,
  ),
};
```

**Why**: Components that read via `computed(() => store.currentProposal)` track Vue's reactivity through the computed dependency. The spread+reassign pattern creates a new object reference at the parent level, but the chain through `props.proposal.project_stages` doesn't always re-fire reliably (especially with deep nested arrays). In-place index assignment works because Vue 3's `reactive()` tracks individual array indices.

**Established sites to mirror**:
- `frontend/stores/proposals.js:updateSection`
- `frontend/stores/proposals.js:applySync`
- `frontend/stores/proposals.js:reorderSections`
- `frontend/stores/proposals.js:_mergeProjectStage` (added Apr 9 2026 after fixing ERR-006)

### Components: read from the store, not deep-watch the prop

When a component already imports the store, prefer reading directly from `proposalStore.currentProposal?.field` via a computed instead of receiving the data via prop and deep-watching it. Deep watchers are doubly bad: (a) they fire on every unrelated proposal mutation, and (b) they can clobber in-progress form edits if you re-snapshot form state on every change.

If a deep watcher feels needed, ask: is the watch on the right subset (`() => proposal.project_stages`, not `() => proposal`)? Can the form state stay decoupled and only sync once on mount?

### Reference-based prop watchers do not see `push`/`splice`

When a child component receives a Pinia state array as a prop and watches it with `watch(() => props.list, ...)` (no `deep: true`), in-place mutations like `this.folders.push(...)` or `splice(...)` from the store action will **not** re-run the watcher — the array reference is unchanged. The store's own subscribers (and templates iterating directly) re-render because Pinia's reactivity tracks indices, but a derived `localList` synced via the watcher will go stale.

After a CRUD modal emits `@changed`, parent pages that pass store arrays into children **must** also call `store.fetchX()`. The fetch replaces the array reference (`this.folders = response.data`), which triggers ref-based watchers everywhere downstream.

**Established sites**:
- `frontend/pages/panel/documents/index.vue:handleFoldersChanged` and `handleMoved` — both refresh `documentStore.fetchDocuments()` AND `folderStore.fetchFolders()` in parallel.
- `frontend/components/panel/documents/FolderSidebar.vue` — uses `watch(() => props.folders, ...)` to populate a draggable mirror; depends on the parent calling `fetchFolders()` to see new entries.

This supersedes the earlier rule "stores self-maintain state after CRUD, parents need only refresh the document list" — that was true for templates reading `store.folders` directly, but not for ref-based watchers.

---

## 12. Notification recipients vs universal outbound copies

Every outbound message uses `EmailDeliveryGateway`. Its audience classification
(`client`, `internal`, `security`) remains explicit for traceability, but no
classification bypasses the configured copy rule. The stable key must exist in
`OUTBOUND_EMAIL_CHANNELS`; unknown channels fail before SMTP so a future sender
cannot silently escape the inventory.

The recipient catalogs are separate by design. Operational notifications use
`NotificationRecipient` and legacy `NOTIFICATION_EMAIL(S)` consumers; universal
copies use `EmailCopyRecipient` and its family selection. Never infer one list
from the other — volume, privacy and responsibility differ. Deduplicate copy
addresses against the complete original envelope so overlap never sends twice.

`EmailLog` contains every gateway delivery, including security traffic and its
full body by explicit product decision. It stores original recipients as
`primary` and each independent BCC attempt as `copy` (or `skipped` when already
addressed). Readers that calculate deliverability, cooldowns, contact counts or
retries must filter to `primary`; history readers nest copy rows through their
shared `delivery_id`.

---

## 13. Single Source of Truth for Small Catalogs

Action iconography follows the same rule as business catalogs: semantic identity belongs in one executable map, while handlers and runtime state stay with the consumer. A component may override contextual copy such as “Copiar URL”, but not the glyph assigned to the canonical `copy` action.

When you have a small enum-like catalog (e.g., the two project stages `design` + `development`), put the canonical list in **one place** and have all consumers delegate to it.

For project stages, that place is `ProposalStageTracker` in `backend/content/services/proposal_stage_tracker.py`:

```python
class ProposalStageTracker:
    STAGE_DEFINITIONS = (
        ('design', 0),
        ('development', 1),
    )

    @classmethod
    def ensure_stages(cls, proposal): ...

    @classmethod
    def get_or_create_stage(cls, proposal, stage_key): ...
```

Backed by the model's `TextChoices`:

```python
class ProposalProjectStage(models.Model):
    class StageKey(models.TextChoices):
        DESIGN = 'design', 'Diseño'
        DEVELOPMENT = 'development', 'Desarrollo'
```

**Anti-pattern**: duplicating the `('design', 0)` tuple in the views file (`_STAGE_DEFAULT_ORDER`), the onboarding service, the migration, the frontend component, AND the test file. The first time you have to add a third stage, you'll have to chase six places.

**Migrations are the one exception**: data migrations are frozen in time and should NOT import from current code, so a migration may legitimately re-declare the catalog locally.

---

## 14. Bogotá Timezone Arithmetic

All day-level arithmetic (e.g., "is the stage overdue today?") must use Bogotá time, not Django's default UTC.

**Helpers in `backend/content/utils.py`**:
- `now_bogota()` — current `datetime` in `America/Bogota`
- `today_bogota()` — current calendar `date` in `America/Bogota`
- `to_bogota_date(dt)` — convert any datetime (naive or aware) to its Bogotá calendar date
- `format_bogota_date(d)` — render `"8 de abril, 2026"` (accepts both `date` and `datetime`)
- `format_bogota_datetime(dt)` — render `"8 de abril, 2026 — 14:30"`

**Anti-pattern**: `date.today()` (returns UTC date on a UTC-configured Django) or `timezone.now().date()` (also UTC). Both will give wrong answers around midnight Bogotá local time.

**Why it works**: Bogotá is fixed UTC-5 with **no daylight saving time**. The offset is stable year-round, so we can hard-code it via `ZoneInfo('America/Bogota')` without worrying about DST transitions.

**Cron schedules**: Huey `crontab(...)` is evaluated in UTC (since `TIME_ZONE='UTC'` and Huey has no `tz` override). To run a daily task at 08:30 Bogotá, use `crontab(hour='13', minute='30')` and add a comment explaining the offset.

---

## 15. Internal-Only Model Fields in Shared Serializers

When a model is internal-only by design (e.g., `ProposalProjectStage` per its docstring: "internal-only and never rendered to the client"), the corresponding field on a shared serializer must be **gated by admin context**, not exposed via plain nested-model rendering.

### Pattern

```python
class ProposalDetailSerializer(serializers.ModelSerializer):
    project_stages = serializers.SerializerMethodField()

    def get_project_stages(self, obj):
        if not self.context.get('is_admin', False):
            return []
        return ProposalProjectStageSerializer(obj.project_stages.all(), many=True).data
```

The view sets `context={'request': request, 'is_admin': True}` for admin endpoints. Public proposal views never set `is_admin`, so they get an empty list — the internal data leaks nowhere.

### Anti-pattern

```python
# ❌ Always exposed, including via the public /proposal/{uuid}/ endpoint
project_stages = ProposalProjectStageSerializer(many=True, read_only=True)
```

### Performance

Don't forget to `prefetch_related('project_stages')` in the admin queryset, otherwise the SerializerMethodField triggers an extra SELECT per detail load.

A tab can be slow with **zero network involved** — measure DOM-node delta and long tasks before blaming the backend. Det. técnico (2026-08) rendered an O(requirements × commercial-items) checkbox matrix ≈38k nodes while the whole optimized page was ~610; the cure was the ProposalSectionsTab pattern (sections collapsed by default, bodies mounted on expand via Set + `v-if`) plus a per-row disclosure for the grids, taking the warm tab switch from 2.9s to 155ms.

`list(qs)[:50]` materializes the entire table before slicing. Slice the queryset instead (`qs[:50]`): a warm prefetch cache still serves it in memory, and cold paths emit `LIMIT 50` SQL. The change-log table grows unboundedly with proposal age, so this class of bug gets worse silently.

Never pre-mount a `v-show`-hidden panel to "warm" it: `v-auto-resize` measures `scrollHeight=0` under `display:none` and its `updated` hook is value-memoized, so textareas stay permanently mis-sized. Warm the async **chunk** (share the loader between `defineAsyncComponent` and a `requestIdleCallback` call), not the mount.

---

## 16. Methodology Maintenance

### Memory Bank Source
- Methodology rules based on [rules_template](https://github.com/Bhartendu-Kumar/rules_template)
- Original format is Cursor `.mdc` files; must be adapted to Windsurf `.md` format
- Key adaptation: replace `mdc:` prefix links with standard paths, `.mdc` → `.md` references, `src/` → `backend/`+`frontend/`
- `directory-structure.md` must be customized per project (the template uses generic `src/`, `test/`, etc.)

### When to Refresh Memory Files
- After adding a new Django app or major feature module
- After significant changes to test infrastructure or counts
- When file counts drift by >10% from documented values
- After methodology rule updates from upstream template

**Last full refresh: 2026-07-16** (previous: 2026-07-04). The 2026-07-04 pass had found drift far exceeding the >10% trigger (migrations documented at `0087` vs actual `0137`; test files 124/77/131 vs 199/290/191) because the Accounting, MCP-connector, and client-signing waves shipped without a memory-bank pass. The 2026-07-16 pass caught another 12-day wave (accounting statements/cards/pocket-sync/income-liquidation, proposal + document PDF redesign, panel dashboard command center): migrations 0137 → 0163, test files 199/290/191 → 250/334/206. Lesson: run `/methodology-setup` at the end of a feature *wave*, not just per-feature — the >10% rule only helps if something actually checks it.

---

## Real-Entity FK + Write-Through Snapshot Pattern

When upgrading a denormalized field set into a real foreign key (e.g., `BusinessProposal.client` → `accounts.UserProfile`), keep the original snapshot columns and treat them as a frozen audit trail. **Do not drop them in the same PR** — the rewrite would touch every email/PDF/log path that reads `proposal.client_name` and bloat the diff dangerously, AND it would lose the ability to know what the client was *called at the time of send* if the profile is later edited.

**Pattern applied in this repo (`backend/accounts/services/proposal_client_service.py`)**:

1. **FK with `on_delete=PROTECT`** — accidental client deletion can never cascade and lose proposal history. Combined with the orphan-only delete guard in the service (zero proposals + zero projects), there is no path that loses data.

2. **Snapshot fields kept** — `client_name`, `client_email`, `client_phone` stay on `BusinessProposal` and are synced via `proposal_client_service.sync_snapshot(proposal)` after every FK assignment. Email sends, PDFs, and audit logs read from the snapshot; the FK is the source of truth for *current* identity.

3. **Single resolver in the service**, called from both serializer overrides AND raw view code so the JSON-flow path and the form path share one implementation. `ProposalCreateUpdateSerializer.create()`/`update()` and `create_proposal_from_json()`/`update_proposal_from_json()` all route through `get_or_create_client_for_proposal()`.

4. **Cascade updates via bulk update** — `update_client_profile()` cascades changes to all linked proposals via a single `BusinessProposal.objects.filter(client=profile).update(...)`. Bumping `updated_at=timezone.now()` manually is mandatory because `.update()` bypasses `auto_now`.

5. **Service is the silent twin of an existing service** — `proposal_client_service` mirrors `accounts/services/onboarding.create_client` but **never sends invitation emails**. This lets the proposal admin panel create / reuse client rows without triggering platform onboarding, which is reserved for the proposal-acceptance flow.

### Placeholder Email Skip Pattern (linked technique)

When a feature lets users create rows quickly without committing real contact details (typical for sales test/draft flows), use a **canonical placeholder domain** to mark unsendable rows so automations skip them silently:

1. **Single canonical constant** — `UserProfile.PLACEHOLDER_EMAIL_DOMAIN = '@temp.example.com'` (RFC 2606 reserved TLD, never resolves to a real recipient). Imported by `proposal_client_service`, `proposal_email_service`, and `tasks.py` — never duplicated as a literal string. Migrations may keep their own frozen copy because migration code is supposed to be self-contained.

2. **Two-step save for id-embedded placeholders** — to generate `cliente_<profile_id>@temp.example.com` you have to know the id, which only exists after save. Solution: save with a temp uuid-based username/email first, then rewrite both fields with the real id and save again. See `_create_placeholder_profile()` in `proposal_client_service.py`.

3. **Single helper in the email service** — `_is_unsendable_client_email(email)` returns `True` for empty strings and any address ending in `UserProfile.PLACEHOLDER_EMAIL_DOMAIN`. Every client-facing send method (currently 13 in `ProposalEmailService`) calls this helper as its first guard. Huey tasks import the same helper so the gate is applied consistently across sync and async paths.

4. **Querysets that select candidates exclude placeholders directly** — `BusinessProposal.objects.filter(...).exclude(client_email__iendswith=UserProfile.PLACEHOLDER_EMAIL_DOMAIN)` instead of iterating then skipping. Avoids wasted DB rows in cron task scans.

5. **A model property `is_email_placeholder`** — exposed to the frontend via the serializer so the UI can render a "placeholder, automations paused" badge inline.

6. **MX validator whitelists the placeholder domain** — `validate_email_domain_mx()` in `backend/content/utils.py` short-circuits with `True` when `domain == _PLACEHOLDER_EMAIL_DOMAIN`, before any DNS lookup. This prevents the "El dominio de este correo no puede recibir emails (sin registros MX)." error when an admin manually types a `@temp.example.com` address. The constant `_PLACEHOLDER_EMAIL_DOMAIN = 'temp.example.com'` is local to `utils.py`; it does **not** import from `accounts/models.py` to avoid a cross-app import cycle.

**Why this matters**: vendors creating test/draft proposals at speed never accidentally email real recipients (because the address is a reserved TLD), AND multiple placeholder rows never collapse into a single dedup'd row (because each placeholder is keyed on a unique profile id). The model also exposes `is_email_placeholder` so the UI can warn the user that they need to enter a real email before automations resume.

**Reference implementation**:
- `backend/accounts/models.py` — `PLACEHOLDER_EMAIL_DOMAIN` constant + `is_email_placeholder` property on `UserProfile`
- `backend/accounts/services/proposal_client_service.py` — get-or-create + 2-step placeholder save + cascade update
- `backend/content/services/proposal_email_service.py` — `_is_unsendable_client_email` helper + 13 client-facing methods gated
- `backend/content/tasks.py` — 4 huey task gates + 2 candidate-queryset excludes
- `backend/content/migrations/0079_add_business_proposal_client_fk.py` + `0080_backfill_proposal_clients.py` — schema + dedup backfill
- `backend/content/utils.py:validate_email_domain_mx` — domain whitelist so manually-typed placeholder addresses pass MX validation

---

## 17. Frontend Admin UX Patterns

### Bidirectional Date / Duration Input Sync

When two inputs must stay in sync (e.g., a `datetime-local` + a "number of days" field), use two separate `watch()` calls rather than a single computed getter/setter. The key invariant is:

- **Date → Days**: compute `Math.round(diff / 86_400_000)`, always safe to recalculate.
- **Days → Date**: rebuild from `Date.now() + safeDays × 86_400_000` **but preserve the existing time component** (`form.expires_at.slice(11, 16)`) so a user who set a specific hour does not lose it when they only intend to adjust the day count.

```js
// Days watcher — preserves user's chosen time
watch(expiryDaysInput, (days) => {
  const safeDays = Number.isInteger(days) && days > 0 ? days : DEFAULT_EXPIRATION_DAYS;
  const expiry = new Date(Date.now() + safeDays * 24 * 60 * 60 * 1000);
  const dateStr = `${expiry.getFullYear()}-${pad(expiry.getMonth() + 1)}-${pad(expiry.getDate())}`;
  const timeStr = form.expires_at ? form.expires_at.slice(11, 16)
                                  : `${pad(expiry.getHours())}:${pad(expiry.getMinutes())}`;
  form.expires_at = `${dateStr}T${timeStr}`;
});
```

Vue reactivity short-circuits when `expiryDaysInput` produces the same integer twice in a row, so the two-watcher pattern does not create an infinite loop.

**Implemented in**: `create.vue` + `[id]/edit.vue` for the proposal expiration date field.

### Toast Notifications for Admin Save Feedback

The standard UX pattern for save confirmation in the admin edit page is a **fixed bottom-right toast** (not an inline div inside the form, which may be scrolled out of view at submission time).

**Template pattern**:
```html
<Teleport to="body">
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    leave-active-class="transition-all duration-200 ease-in"
    enter-from-class="opacity-0 translate-y-4"
    leave-to-class="opacity-0 translate-y-4"
  >
    <div v-if="updateMsg" class="fixed bottom-6 right-6 z-[9999] ...">
      {{ updateMsg.text }}
      <button @click="updateMsg = null">✕</button>
    </div>
  </Transition>
</Teleport>
```

**Auto-dismiss without timer stacking** — store the timer id and `clearTimeout` before scheduling:
```js
const updateMsgTimer = ref(null);
clearTimeout(updateMsgTimer.value);
updateMsgTimer.value = setTimeout(() => { updateMsg.value = null; }, 5000);
```

Use `<Teleport to="body">` so the toast renders above all panel layout layers (sticky headers, sidebars) without z-index conflicts. Use Tailwind `transition-all` classes inline on `<Transition>` to avoid a separate `<style>` block.

**Also clear on unmount.** Any `setTimeout` that mutates a reactive ref must be tracked in a module-scoped binding and cleared in `onUnmounted` — otherwise a click-then-navigate flips state on a gone component. Applies to every clipboard-feedback flag (`urlCopied`, `jsonCopied`) and toast timer. See `frontend/pages/panel/diagnostics/[id]/edit.vue` — both copy helpers capture their timer and the unmount hook clears all three (toast + url + json).

**Implemented in**: `frontend/pages/panel/proposals/[id]/edit.vue`, `frontend/pages/panel/diagnostics/[id]/edit.vue`.

**Preferred path for new admin pages**: import `usePanelToast` from `~/composables/usePanelToast` + mount `<PanelToast />` once in the template. The composable already encapsulates the timer + `clearTimeout` ceremony and a single `<PanelToast />` Teleport renders the bottom-right card. No need to re-implement `updateMsg`/`updateMsgTimer`/`setTimeout` pairs in each page — that pattern is reserved for legacy edit pages that already had inline toasts. New pages: `frontend/pages/panel/diagnostics/defaults.vue` (Apr 18, 2026) follows the composable path.

### Generic Modal Reuse via `endpoint` Prop (not `resourceId`)

When a modal performs an HTTP action whose target (proposal vs. diagnostic vs. document) varies across callers, accept a relative `endpoint: String` prop instead of a typed `proposalId` / `diagnosticId`. Each caller constructs the path (`diagnostics/${id}/email/markdown-attachment/`); the modal prepends `/api/` and calls the endpoint without knowing the resource type.

**Pattern**: `MarkdownAttachmentModal.vue` (`components/MarkdownAttachmentModal.vue`) — moved from `BusinessProposal/admin/` to `components/` root when it gained a second consumer (`DiagnosticEmailsTab`). Any future email-composing attachment modal should start here rather than as a copy inside the feature folder.

**Anti-pattern**: `proposalId: [Number, String]` — forced the modal to hardcode the URL template, preventing reuse across resource types.

### Shared Backend View Helpers for Identical Response Bodies

When two or more views produce an identical response body (same validation, same service call, same error codes), extract the logic into a module-level helper in a dedicated file rather than duplicating 40 lines each time.

**Pattern**: `backend/content/views/_email_attachment.py`:
- `inline_pdf_response(pdf_bytes, filename)` — builds `HttpResponse` with `Content-Disposition: inline`.
- `render_markdown_pdf_response(request, *, client_name)` — validates `title`/`markdown`, calls `DocumentPdfService.generate_from_markdown()`, returns the PDF response or a typed 400/500 error.

Both markdown-attachment views (proposal + diagnostic) import these and are 3 lines each. The underscore prefix (`_email_attachment.py`) signals that the module is a helper, not a standalone view router.

### `coerce_bool` vs. Inline `_bool()` for DRF Request Data

DRF's `request.data` delivers form-submitted booleans as strings (`"true"`, `"false"`, `"1"`, `"0"`). Inline helpers that call `request.data.get(key, default)` accidentally return the *string* `"True"` when the key is missing — because the fallback is passed through unchanged.

**Safe pattern**: `coerce_bool(value, default=True)` in `content/utils.py` — handles `None → return default`, `bool → return as-is`, `str → lowercase compare against DRF's BooleanField.TRUE_VALUES`. Never stringify the default.

### Reusing Existing Transition Infrastructure for New Navigation Events

Before adding a new CSS transition, check whether an existing overlay/transition already covers the visual effect you need. The `switch-mode-overlay` in `proposal/[uuid]/index.vue` was designed for gateway → mode transitions but works equally well for mode → gateway by adding a new sentinel value (`'gateway'`) to the icon/heading/subtitle ternary chain. No new CSS needed — the bouncy-scale enter/leave keyframes are reused as-is.

**Pattern**: add a new `v-else-if` case to the overlay template, update `handleBackToGateway` to set `switchOverlayMode = 'gateway'` and `switchOverlayVisible = true` before resetting state, then mirror the timing of the existing `handleViewModeSelect` function (1 s hold → state reset → 1.2 s overlay hide).

## 18. Adding a New `ProposalSection.SectionType`

These three lessons surfaced together while shipping `roi_projection`; treat them as a single checklist for the next person adding a section type.

### Migration backfill: don't trust `ProposalService.get_default_sections` from inside the migration

`ProposalDefaultConfig` is a DB-backed override of the hardcoded `DEFAULT_SECTIONS` list. When the migration calls `ProposalService.get_default_sections(language)` and the DB row exists with the OLD section list (no entry for the new type), `cfg = _defaults_index(language).get('roi_projection')` returns `None` and the row creation **silently no-ops** — the migration reports success but no rows are created. The order-bump step still runs, leaving a permanent gap at `order=4`.

**Fix pattern**: import the canonical hardcoded list directly inside the migration, not via the service:

```python
from content.services.proposal_service import DEFAULT_SECTIONS, DEFAULT_SECTIONS_EN
cfg = next((s for s in (DEFAULT_SECTIONS_EN if lang == 'en' else DEFAULT_SECTIONS)
            if s['section_type'] == 'roi_projection'), None)
```

After running the migration, also update `ProposalDefaultConfig.sections_json` for each language so future proposals (created via `/panel/defaults` or the panel UI) include the new section by default.

### Frontend dispatcher: components expecting `{ content }` need a named branch

`getSectionProps(section, currentIndex)` in `pages/proposal/[uuid]/index.vue` flat-spreads `content_json` keys as top-level props for any section type without a named `if` branch. Components like `ProposalSummary.vue` and `RoiProjection.vue` that `defineProps({ content: { type: Object } })` will mount but bind `undefined` everywhere.

**Fix pattern**: every new section component that uses the single-`content` prop pattern must add a named branch:

```js
if (section.section_type === 'roi_projection') {
  return { content: { ...content, index: paddedIndex } };
}
```

Symptom in browser: section element renders (correct CSS class) but inner h2/cards are empty. Symptom in Playwright: snapshot shows the section but `getByText(...)` for inner content times out.

### Web-only sections: skip from PDF *including* the TOC

Sections without an entry in `SECTION_RENDERERS` (`proposal_pdf_service.py`) silently skip content rendering, but historically the section loop **still appended a TOC entry** for them — leaving orphan TOC links pointing at the next section. After fixing this for `roi_projection`, the loop now `continue`s before appending the TOC entry when both `is_paste=False` and `renderer is None`. The same guard now also drops `proposal_summary` and `process_methodology` from the TOC (they were always content-less in the PDF anyway).

**Pattern**: web-only sections need only one explicit code change — *not* registering them in `SECTION_RENDERERS`. The TOC behavior is consistent because of the loop guard.

### Schema dead-code check before reusing existing components

Before deciding "I'll just add a `kpis` array to `proposal_summary` instead of building a new section", grep the public component:

```bash
grep -nE "v-html|v-for|content\.kpis" frontend/components/BusinessProposal/ProposalSummary.vue
```

`ProposalSummary.vue` defines a `kpis` field in its admin form and seller prompt but the public template only iterates `cards[]`. The `kpis` array is dead schema. Always verify the data path is wired end-to-end (admin form → JSON → backend serializer → public component) before adding fields to an existing section.

## 19. Build-time prerender must bypass production nginx (rate limit / TLS)

A build step that prerenders pages by fetching the app's **own public API** is, from nginx's perspective, just another external client — it inherits production's rate limiting, WAF rules, and TLS redirects. This silently broke blog prerender (ERR-015): `build:django` fetched all 114 blog routes from `https://projectapp.co`, tripped `limit_req zone=api` (5 r/s) → 429 → ~100 posts rendered as 500 → build shipped the SPA shell with no per-post HTML/OG tags. It worked when the blog was small and degraded as it grew past the burst window.

### Rules of thumb
- **Prerender/SSR-at-build against the app server on loopback, never the public hostname.** The build script (`frontend/update-django-template.js`) starts a throwaway Django on a free `127.0.0.1` port and points `PRERENDER_API_ORIGIN` at it.
- **Don't assume `127.0.0.1:8000` works.** Production gunicorn binds `unix:/run/projectapp.sock`, not a TCP port — there is nothing on :8000. The build brings up its own server instead.
- **A loopback build server needs a no-TLS settings module.** `settings_prod` forces `SECURE_SSL_REDIRECT=True`, which 301s plain-HTTP loopback fetches to `https://127.0.0.1` and breaks them. `backend/projectapp/settings_build.py` extends prod (real DB/content) but disables SSL redirect / HSTS / secure cookies. It exists only for the build server.
- **Put the fix at the single build chokepoint.** Both `/deploy-and-check` and the on-publish `run_frontend_rebuild` task call `npm run build:django`, so fixing it there covers every path. Keep a graceful fallback (env-provided origin) for environments with no backend (CI/dev).
- **Make a dropped prerender loud, not silent.** Set `PRERENDER_REQUIRE_BLOG=1` once the build can reliably reach the API, so a regression fails the build instead of silently shipping un-prerendered SEO pages.

---

## 20. Panel Modules Wave — MCP, Accounting, Client Signing (Jul 2026)

### MCP connector security (claude.ai remote connectors)
- The connector token is a **capability URL**: shown in full exactly once at generation, then only its **SHA-256 hash** is stored (`McpConnector`). Regenerating rotates the hash and instantly 404s the old URL.
- The MCP endpoint (`content/views/mcp_blog.py`) validates **Origin** (DNS-rebinding defense) + token + active-state on every JSON-RPC call, and logs `handshake/tool_call/auth_error/origin_rejected` to `McpRequestLog` (the panel's connection-activity feed reads this).
- Rate limits for a multi-connector client must be keyed by **IP + registered connector slug**, not IP alone: Codex starts its connectors concurrently, so a shared IP bucket turns legitimate sibling startups into HTTP 429 failures. Unknown slugs must collapse into one defensive bucket; using arbitrary path text would make the throttle bypassable.
- MCP tools wrap existing services/ORM — they are **not** a new business layer. Guardrails live in the tool module (e.g. Documents connector only exposes MARKDOWN docs, refuses to delete published docs). The machine-facing endpoint is integration-tested in pytest, not E2E.
- Administrative parity should expose **domain verbs**, not writable lifecycle
  flags. A connector may list archive/status fields as read-only while
  `close_thread`, `archive_thread` or `void_message` route through the same
  guarded service as the panel. This keeps conversational administration useful
  without creating a lower-level bypass around transition and audit rules.
- **MCP drift fails silently.** Omitting a newly stored field still produces a valid
  response, so uptime cannot reveal that the assistant sees an incomplete domain.
  Every change to an MCP-exposed model, serializer, service, relation or lifecycle
  must review that module's tools, schemas, precise descriptions, field contract and
  validation script in the same delivery. `content/mcp/contracts.py` forces every
  concrete field into read-only, read-write or an exclusion with a reason;
  `docs/MCP_VALIDATION_RUNBOOK.md` preserves the behavioral create/read/update/error
  check. Share panel services instead of recreating their rules in a tool handler.

### Accounting partner-split invariant
- `PartnerSplitMixin.clean()` is the single source of truth for the money rule: no negative amounts, `gustavo + carlos ≤ total`, and a **personal-ledger record must be 100% the owning partner's** (other partner = 0). `company_amount` is a derived property, never stored. Keep validation in `clean()` so both the API and the admin enforce it; don't re-implement in serializers.
- `source_ref` is an idempotency key (`import:<hash>` / `fake:<tag>`) — dedups re-imports and fake-data reseeds.

### Client document signing
- Two independent gates before a signature is accepted: the document must be `requires_signature`, and the client's email must be **verified via OTP** (`UserProfile.email_verified`). The sign button is disabled client-side and the endpoint returns 403 server-side — test both.
- Signing is **idempotent** (re-sign returns the signed doc, doesn't re-notify). Milestone team notifications are best-effort and must never raise into the client flow (`client_flow_notifications` swallows errors).

### E2E flow tags must be array literals, not bare constants
- The flow-definitions sync checker (`scripts/lib/e2e-flow-refs.mjs`) only detects `@flow:` references inside `tag: [ ... ]` **array literals**. A spec that applies `{ tag: PLATFORM_PASSWORD_RESET }` (bare imported constant) is invisible to it — its coverage silently doesn't count. Always spread: `{ tag: [...PLATFORM_PASSWORD_RESET] }` / `{ tag: [...CONST, '@role:client'] }`. This stayed hidden until the flow was registered in `flow-definitions.json` (an unregistered flow trips neither the "unknown-in-specs" nor the "required-but-unreferenced" check).
- **Verify at the served-HTML layer, not just HTTP 200.** A Nuxt SPA shell returns 200 with no article content. Confirm `<article>` + per-post `og:title` + JSON-LD are present in `curl` output, and spot-check a real browser render.

---

## 21. Test Quality Gate: CI runs DEFAULT mode — `--strict` SUPPRESSES semantic rules

The gate has two semantic-rules modes and they are **not** a superset relationship. The CI job (`.github/workflows/test-quality-gate.yml`) invokes `scripts/test_quality_gate.py` **without** `--semantic-rules strict` — i.e. DEFAULT mode. DEFAULT enables rules that strict mode suppresses: PR #113 went red in CI on the `forbidden_token` rule (the word "batch" in a test name) and the `no_assertions` rule, even though a local `--semantic-rules strict` run was clean.

### Rules of thumb
- **Validate pre-push in DEFAULT mode** — the exact CI invocation is `python3 scripts/test_quality_gate.py --repo-root . --report-path <out>.json --frontend-unit-dir test --verbose`. Do not add `--strict`/`--semantic-rules strict` when the goal is predicting CI.
- **Any ERROR fails the gate** regardless of the overall score; warnings/info only lower the score (score ≥80 green, ≥60 yellow).
- **File-scoped runs** use `--include-file <path>` — cheap way to gate only the specs touched in a batch.
- Watch for `forbidden_token` in test **names** (not just bodies) and `no_assertions` on tests whose assertion lives inside a helper — use plain asserts in the test body.

## 22. Test-audit (Round 8, 2026-07-24): `duplicate_coverage` is a naming signal, not a merge signal; the backend gate is `content`-only

The first whole-corpus `test-audit` (report: `docs/audits/test-audit-2026-07-24.md`) produced two findings worth keeping. Note this corpus is literally the one behind the `test-audit` skill's example table (301 no-interaction E2E / 72 junk-only flows / 146 duplicate unit / 164 weak assertions — measured identically here).

### `duplicate_coverage` findings are overwhelmingly false-positives-for-merge
The `duplicate_coverage` detector matches on **test name + structural shape**, blind to the enclosing `describe` block. All 147 findings here were unmergeable:
- **115 same-file** were the *same generic name* (`"handles error"`, `"sets error on failure"`, `"does nothing when el is null"`) reused across **different** `describe` blocks — i.e. different store actions / different composables (`useDiagnosticCommercialPrompt` vs `useDiagnosticTechnicalPrompt`). Merging deletes real coverage of a distinct subject. The correct fix is **rename to a single-purpose name** (prefix with the action), never merge.
- **32 cross-file** were structurally identical tests for **different components** (`DiagnosticPricingForm` vs `DiagnosticRadiographyForm`, `PrivacyPolicy` vs `TermsAndConditions`) — parallel coverage, **keep**.

Rule of thumb: before actioning any `duplicate_coverage` finding, resolve each test's enclosing `describe`; only two tests in the **same** describe with identical bodies are a true duplicate. Same name + different describe = rename; same shape + different SUT = keep (or `test.each` if truly one subject with a value table).

### The quality gate's backend suite scans only the `content` app
`.testquality.yml` sets `backend_app_name: content`, and CI (`test-quality-gate.yml`) runs the gate with no `--backend-app` override, so **`accounts`, `projectapp`, and top-level `backend/tests/` are ungated in CI**. The audit found 72 error-level findings in `accounts` (67 `misplaced_file` — test files outside the `models/services/views/...` folders `py_allowed_folders` expects) that CI has never seen. To audit the full backend, run the gate once per app: `python3 scripts/test_quality_gate.py --suite backend --backend-app accounts` (repeat for `projectapp`).

## 23. A pre-deploy SPA session survives every deploy — "the feature doesn't work" starts with a hard reload

The panel is a static Nuxt SPA: `serve_nuxt` sends the entry HTML with `Cache-Control: no-cache`, but a browser tab opened before a deploy never refetches it — client-side navigation keeps running the old bundle indefinitely, and old hashed assets stay servable (`staticfiles/frontend/_nuxt` accumulates every deploy's files under a 30d immutable cache; 9,693 files as of Aug 2026), so the stale app never even breaks on its own. Real incident (2026-08-03): "Solo esperados" filtered identically to "Todos los esperados" in the operator's session — the pre-Aug-1 bundle had no `paymentStatus` matcher, so the tab's filter key was silently inert; the shipped feature was fine and a reload fixed it. Diagnosis order for "the deployed feature doesn't show": (1) hard-reload the tab; (2) confirm the served build (`backend/staticfiles/frontend` mtime + grep the new symbol in `_nuxt/`); (3) only then suspect code or data. Purging old `_nuxt` bundles would force stale tabs to break loudly on their next navigation — a possible future chore, deliberately not done yet.

## 24. Gross-income deductions: utility must stay asymmetric

Under the gross convention (operator decision 2026-08-03) an expected income keeps its invoiced total; fees discounted at origin become linked deduction expenses that credit it as payment (`paid = liquid children + linked deductions`, via `ExpenseRecord.source_income`). The utility formulas CANNOT subtract deductions on both sides: **expected** utility subtracts them (gross projection minus known fees) but **liquid** utility subtracts only operational spending, because the liquid total is cash that already arrived net of every fee — subtracting the fee there counts the same loss twice. The same asymmetry holds in `monthly_breakdown`, and any new aggregate should follow it. Corollary: editing or deleting a deduction expense mutates its income's payment state through the credit — they are one bookkeeping unit, which is why manual writes can neither set nor clear `deduction_type` (settlement context only) and a deduction never gains a pocket movement.

## 25. A new required field may not be demanded where it cannot be filled in

PA-51 made the covered period mandatory on hosting incomes, and the rule landed in `IncomeRecordCreateUpdateSerializer.validate` — a serializer every write path shares, not just the panel form that grew the fields. From then on **no hosting income could be settled at all**: `accounting_settlement_service` builds its children (the liquid payment, the rescheduled balance, each abono allocation) through that same serializer, copying the parent's `origin` but nothing else, so the check fired on records nobody could complete from where they stood — the modal has no period fields, and the child is new, so it cannot read the parent's window either. Both a legacy income and one with a perfect window failed identically; the flow was dead for two weeks with no test noticing, because not one test settled a hosting income.

**The rule.** When a field becomes required, walk EVERY path that writes that record — panel form, MCP tool, bulk action, and the services that derive records from other records — and decide for each one: *asked for*, *deferred*, or *not applicable*. A path that cannot show the field must never be the one refused. Concretely in this codebase:

- **Derived records inherit the exemption.** A record a service builds out of another describes nothing on its own, so the rules meant for a person describing something do not reach it. `origin`, `deduction_type` and now the covered period all take the same `context={'settlement': True}` escape — when a fourth one appears, it belongs on that list, not on a new mechanism.
- **Watch for fields whose validation also DERIVES other fields.** The period block rewrites `period_date` from `period_start`. Handing the window to a settlement child would have been the obvious fix and would have silently moved the collected money to the month the window opens, instead of the day it came in.
- **Money is never held for a descriptive field.** Registering that the money arrived and describing what it covers are different acts; the missing description is completed where it shows up (the Liquidar modal offers the window when the hosting charge has none) and, left empty, the settlement goes through all the same.
- **The test that would have caught it** is the one that runs the *derived* path, not the one that runs the form. Any new required field deserves at least one test per writing path — see `content/tests/views/test_settlement_hosting_period.py`.

## 26. Commercial catalogs and contractual snapshots need an explicit time boundary

Replacing an offered periodicity is not a global string substitution. The proposal document, its public view and its PDF may be contractual history, while a project or subscription created today is an operational record governed by the current catalog. In the 2026-08-20 annual→nine-month change, using one unconditional normalizer either rewrote accepted proposals or leaked annual terms into new projects.

The stable pattern is:

- Define “current” once (proposal activity/status or operational record state).
- Preserve stored JSON and paid ledger rows for terminal history; label legacy enum values as historical instead of deleting their read maps.
- Let new-write serializers expose only the current enum while permitting an unchanged legacy value during unrelated edits.
- Give operational conversions an explicit call-site override (`force_current_terms=True`) rather than changing a public/PDF helper's default semantics.
- Put payment-provider state ahead of mutation: abort a data migration before touching any subscription whose pending charge is processing or linked externally.
- Test both sides of the boundary in the same change: historical display stays old, new operational creation becomes current.

## 27. Client-facing copy belongs beside the document, not inside the deliverable

A report and the message used to deliver it have different audiences and lifecycles.
Putting email/WhatsApp copy in the markdown would leak internal working text into the
PDF and client portal; keeping it only in terminal output makes a delayed delivery
easy to lose. The durable boundary is optional private metadata on `Document`, read
and written only by the admin detail surface and the Documents MCP. Free-form notes
follow the same boundary as an ordered JSON collection of small `{title, content}`
objects; a shared normalizer keeps REST and MCP writes consistent without coupling
them to the report markdown schema.

One workflow must own the words. `client-report` creates the report and its canonical
subject/email/WhatsApp triple; `client-message`, when it requests a report, reuses the
same bytes instead of composing an equivalent second message. An omitted MCP field
means “preserve” during partial updates, while an explicit empty string means “clear”.
Duplicating a document deliberately clears all fixed and custom notes because the
metadata is specific to one concrete handoff. Test this boundary from both sides:
internal CRUD round-trips the notes in insertion order, and platform serializers
never expose them.

## 28. Parallel Django migrations converge through an explicit merge node

Two feature branches can both create `0204_*` from the same `0203` parent and merge
without a textual Git conflict because the filenames differ. Django still has two
leaf nodes and will refuse every `migrate` until the graph is reunified.

The safe repair is a new, empty migration whose dependencies are both leaves. Do not
rename either shared migration and do not make one depend retroactively on the other:
either action rewrites published history and can produce inconsistent migration state
across environments. Verify the repair at graph level (`detect_conflicts()` is empty
and the app has one leaf), then run `makemigrations --check --dry-run` and the system
check. This graph check belongs before production deploys because Git alone cannot
detect the condition.

## 29. Responsive card grids need an inner-width acceptance threshold

A desktop breakpoint does not guarantee readable columns. `FinalNote` looked spacious
at the viewport level while `max-w-6xl`, large container padding, the grid gap and card
padding left roughly 460 px per column. Measure the element the user reads, not the
screen: at 1366 px the commitment and kickoff cards must each retain more than 520 px,
and below that capacity the layout should stack. The same rule applies within rows:
allow a descriptive payment label to wrap, but reserve an indivisible column for the
amount, currency and tax suffix.

## 30. Generated rich text needs exact JSON paths in every prompt surface

“Use bold in introductions” is too ambiguous when multiple prompt surfaces and JSON
field names exist. Keep a canonical field list in both `useSellerPrompt` and backend
`_seller_prompt.bold_formatting`, state the allowed tag (`<b>`), fragment limit and
empty-field behavior, and regression-test every path. When correcting one live
proposal, use an exact-match, reversible data migration so deployment cannot overwrite
copy edited after the correction was prepared.

## 31. A persisted derivative needs one backend owner and an explicit refresh graph

`cop_equivalent` looked like ordinary editable accounting data, so creation initialized
it once and later edits simply carried the stale value forward. Reloading could not help:
the database itself was wrong, and every total faithfully summed that wrong cache. The
repair pattern is broader than this field: declare the source inputs, choose the policy
for time-sensitive inputs, make one backend boundary own the calculation, and trigger
that boundary from every source change. Here the policy is the current manually
configured USD rate; `RecurringPayment.save()` owns row changes and
`AccountingSettings.save()` owns rate-wide synchronization. Client previews may explain
the result, but they never become the source of truth. When introducing the invariant,
ship a data migration and a stale-row regression so old data is brought under the same
rule immediately.

## 32. Responsive contracts need one width vocabulary and compiled-CSS proof

Do not derive breakpoints independently in Vue, Tailwind and Playwright. Keep
the panel bands, `matchMedia` queries and five acceptance viewports in one
configuration, then make shared components own adaptation. A table still needs
an explicit per-column `keep/group/hide` policy: a generic “hide the last
columns” rule cannot know business priority. Likewise, cap the content shell on
wide monitors instead of treating responsiveness as only a small-screen issue.

Framework vocabulary is part of the contract. Tailwind already means
orientation when it sees `portrait:` or `landscape:`, so panel width aliases use
the `panel-*` namespace. Unit tests can prove that a class string exists while
missing a bad media query; every new breakpoint family must also be inspected
in generated CSS and exercised at the boundary viewports.

Those breakpoints are product data, not framework defaults. ProjectApp is
operated on five known screen classes, including the awkward portrait-tablet
middle and a 27-inch monitor. A `md` or `lg` class is not acceptance evidence
by itself: choose navigation from usable content width, cap wide screens, and
measure the element the operator uses instead of inferring success from the
viewport alone.

## 32. Structural responsiveness needs one breakpoint owner and exact-device tests

A two-zone page cannot be made compact by hiding random descendants: that leaves two
focus trees, filters ahead of content and desktop assumptions inside a narrow main
column. Choose the structural branch once
(`useIsMobile(PANEL_BREAKPOINTS.landscape - 1)` here), render exactly
one interactive DOM, and let smaller CSS breakpoints refine only the inside of that
branch. The 835 px portrait tablet is the reason this boundary cannot simply inherit
a library's `md`; the 1195 px landscape tablet is the reason it cannot be treated as
a phone.

Verification must name the real five viewport dimensions. For every module, navigate
through the UI, assert concrete fixture data, exercise its transient zone, check page
overflow and measure the large-screen cap. A generic “mobile” project plus one desktop
project misses both the portrait-tablet failure and the over-stretched 27-inch layout.

## 33. Mobile lists and comparative tables are different interaction problems

A responsive table primitive should not turn every dataset into the same mobile
shape. Transactional and comparative screens need stable column semantics, so
they declare `keep/group/hide` by business priority. Exploratory CRUD screens are
usually scanned one entity at a time, so a single card representation below the
panel breakpoint is clearer. Rendering both versions and hiding one with CSS is
not equivalent: it duplicates links, test IDs and accessibility targets in the
DOM. `BaseExploratoryList` therefore chooses exactly one representation from the
shared media-query source, while `BaseResponsiveTable` retains explicit column
policy.

The lasting control is ownership, not a one-time sweep. Every catalog page must
map to one module script, each module must retain a real tagged E2E, and the same
five profiles run on affected PRs and on a monthly full matrix. A semestral review
checks whether the devices themselves changed; individual pages never move a
breakpoint without changing the shared contract and its evidence together.

## 34. Responsive accounting must preserve business meaning, not table shape

An accounting column cannot be hidden because it happens to be last. Declare a
primary field, retained totals and grouped secondary facts for every table, then
verify the choice against the operation users perform. In Ingresos that means
concept and total survive while collection state, month and origin can share a
compact detail block; grouped client headers stack identity and totals instead
of compressing four meanings into one line.

Some data must change location rather than disappear. Pocket's running balance
is the clearest case: its independent column is too expensive below 1024 px, but
without it the ledger becomes a list of unrelated movements. Relocating the
balance below each retained amount preserves chronology and frees horizontal
space. Apply the same rule to secondary KPIs: show the three ranked decisions,
then disclose the rest on demand. A repeatable matrix needs all twelve routes
and all five real widths; representative Playwright checks pin the breakpoint
semantics while the written 12×5 script preserves business review tab by tab.

## 35. Customer email policy belongs at the transport boundary

Adding a BCC inside every template is not durable: template registries describe
content, while sends also originate in services, views, tasks and both Django
apps. The enforceable boundary is the last abstraction before Django's email
backend. Make that gateway the only permitted mail-I/O owner and require every
caller to declare a stable key plus client/internal/security intent.

The client inventory is executable policy, not documentation alone. A new
customer key must enter that mapping before the gateway accepts it, and a static
test must fail if a future caller bypasses the gateway. Keep operational and
security traffic in the same transport path but outside the customer-copy
audience; otherwise OTPs, temporary passwords or internal digests can leak into
an unrelated inbox.

Failure isolation requires separate envelopes. Deliver the customer message
first, then create one BCC-only envelope per configured copy recipient. Group
those attempts with the primary via a delivery identifier, but give each its own
status row. Reader queries must explicitly select `primary` so a copy neither
inflates contact counts nor triggers cooldowns/retries; history surfaces can
then attach `copy` rows underneath without changing the meaning of existing
metrics.

## 36. List context is route state, not component memory

A detail page cannot implement a reliable “Volver” when the owning list keeps
folder, filters, search, mode or page only in refs/store state. Encode every
meaningful list state in a canonical URL, omit defaults, and let browser history
restore those addresses. Use `replace` for incremental filter edits so typing or
toggling does not manufacture a long stack of nearly identical entries.

An explicit origin query is still untrusted input. Resolve it as an application
route, allowlist the expected localized module path, and reject external,
protocol-relative and cross-module destinations before rendering either the link
or its label. Add an entity focus id to the explicit return so a restored page can
bring the originating row/card back into view; native Back should remain native
and consume the prior URL entry.

## 37. Independent modal saves need a field-scoped dirty baseline

When a modal persists one subsection of a larger editor, a successful request
must not reset the editor's entire unsaved-changes baseline. Doing so makes
unrelated edits look saved even though the server never received them. Rebase
only the fields included in the successful request; keep every other field
dirty until its own save succeeds.

Button language is part of that persistence contract. Use `Guardar cambios`
only when the action reaches durable storage and visibly confirms it. If the
parent entity does not exist yet, name the local action as a draft operation and
state the remaining persistence step both before and after it.

## 38. Reuse infrastructure, not the wrong aggregate

Two features can share clients, projects, documents, authentication and UI
primitives without sharing a persistence model. A `Document` is one editorial
artifact; a client conversation is an aggregate root containing ordered,
bidirectional events. Treating messages as documents would make folders,
editorial states and list filters ambiguous and create an expensive extraction
later. The communications module therefore owns thread/message models inside the
existing `content` app and references Documents through a protected join.

Operational facts also need stable semantics. “Sent” remains stored evidence;
“Respondido” is derived from a valid reply. Delivered events are not silently
rewritten: annulment and business-date corrections append audit context, while
only drafts remain mutable. When project ownership changes, historical threads
stay with the original client and lose only their optional project scope.

## 39. Clipping is measured state, but full-value access must not depend on it

A fixed `title` attribute only repeats short values and still leaves touch users
without a path. Measure the rendered element after layout, text changes and
container-width changes, and again after `document.fonts.ready`; publish one application-owned tooltip only while
`scrollWidth/clientWidth` or `scrollHeight/clientHeight` proves clipping. That
tooltip must portal outside overflow containers, flip/clamp within the viewport
and be the sole notice—never pair it with a native `title`. The disclosure
expands in the same row/card so it cannot require navigation. E2E setup must
await font readiness without dispatching a compensating resize event that
production never receives.

Line clamping is a bundle of display, overflow and WebKit properties, not a
decorative class. If a consumer adds `block`, `flex`, `overflow-*` or another
display utility to the clamped node, CSS ordering can silently disable the
clamp and make the measurement say “complete.” The shared primitive therefore
owns collapsed and expanded display state; consumers may supply typography and
color only. Test both the table and the compact card, because their width and
consumer-class combinations are materially different.

## 40. A floating control belongs to the modal, not its scroll panel

An absolutely positioned results list still participates in the clipping rules
of every ancestor. Increasing one modal's fixed height only moves the defect to
the next short modal. A reusable searchable selector therefore needs a shared
portal target at the modal overlay boundary, plus explicit ownership of focus,
Escape, outside clicks, viewport placement and scrolling.

Teleporting alone is incomplete: a body-level list can escape the focus trap or
outlive the dialog. The modal must register its floating descendants and trap
focus at the dialog boundary. Behavioral tests should assert DOM ownership and
scroll positions, not just that an option exists; otherwise a clipped option
still produces a deceptively green test.

## 41. Text containment is an intrinsic-sizing contract, not a final overflow patch

Putting `overflow-hidden` on the last cell is only a backstop. A user-owned
identifier without spaces can enlarge the min-content contribution of a flex,
grid or table child before that overflow rule has any useful effect. Carry
`min-w-0` through every flexible ancestor, bound the inner content, and use
`overflow-wrap:anywhere` for strings whose shape is not controlled by the UI.
`break-words` is weaker here because its emergency breaks do not reduce the
intrinsic minimum in the same way.

Choose truncation as a product policy, not a CSS shortcut. It is valid only when
the complete value is available by a measured disclosure, native hint or detail
view. Then keep every badge/state/folder that describes the title in an ordered,
wrapping metadata row below it; otherwise each new distinction recreates the
same horizontal competition. Row height may remain natural when metadata is
absent, but that must be explicit.

Regression evidence must use the real longest naming convention and geometry,
not a short lorem string. Exercise values with no spaces at every canonical
viewport and compare bounding boxes against their actual cell/card and adjacent
column. Shared table/list primitives should carry the default policy so new
panel screens are safe without rediscovering the bug.

## 42. Representative fake data is an executable dependency graph

A root-record count is insufficient when child modules depend on a specific
shape. Generate identities first, concentrate load deliberately, and route
cross-module records through the same services used at runtime. In ProjectApp,
accounting must precede Documents so each collection account has one real
`IncomeRecord` origin; Documents must precede Communications so protected
attachments can be selected within the thread's client.

Seed and clock are separate reproducibility inputs. Derive one independent RNG
per module so a harmless random choice in one seeder cannot reshuffle all later
modules, and carry one explicit anchor date so expired/current/future buckets can
be replayed on another machine. Auto-generated primary keys need not match for
the semantic dataset and defect path to match.

Safety must fail closed at every entry point, not only at the root command. A
positive settings capability, hard-false production override, no known default
passwords, a non-additive populated-data guard and one outer transaction prevent
the most expensive outcomes: production mutation, misleading partial graphs and
unrepeatable failures.

Finally, documentation alone does not keep coverage current. Compare a declared
seeded/derived/catalog/exempt inventory with Django's concrete app registry in a
test. A new model then forces its author to decide ownership and fake-data
behavior in the same delivery instead of leaving the gap for a later cleanup.

## 42. A disabled control is an explanation surface

Disabling protects an invalid transition but removes the control from normal
keyboard interaction, so the button itself cannot be the only carrier of its
reason. Put a focusable/touchable proxy around it, connect the explanation with
`aria-describedby`, and repeat resolvable prerequisites as visible copy. When
several conditions fail, derive one array and render all of it; a `canSubmit`
boolean or first-error chain hides the real contract and makes the operator
discover blockers one at a time.

Separate three classes. Busy state is temporary and belongs in `loading` plus
an active verb. Lifecycle, permission and first/last-position boundaries need a
specific tooltip/status explanation but are not form errors. Missing input or
configuration is actionable and needs adjacent copy with a nearby resolution
path. For canonical data required late in a workflow, such as a client's email
before issuing a collection account, repair the source record explicitly inside
the modal and preserve the draft; a local override alone would leave the next
workflow broken in the same way.

## 43. Group summaries need one semantic calculator and layout-aware reuse

Grouped financial tables combine independent questions: which rows belong
together, how money changes by lifecycle state, which status counts overlap and
how groups are prioritized. Centralize those rules in a pure utility and let both
group headers and the filtered footer consume its result. In particular, overdue
can overlap issued while amount buckets remain exclusive; calculating either rule
ad hoc in the template makes totals drift silently.

Reuse the visual contract at the smallest stable boundary. Sharing the summary
band and the grouped-table shell kept Incomes and Cuentas de cobro consistent,
while parameterized labels and metrics preserved their different business
semantics. Row slots could also be shared, but the classic table's absolute
stretched link could not: layout-dependent affordances must be enabled by the
owning view mode. A real pointer-driven E2E is what exposed that boundary.

## 44. A route inventory and a commercial product map answer different questions

The exhaustive view catalog exists to make every route and source reference
findable. A client or operator, however, starts with what the product enables,
not with file paths or framework boundaries. Keep a curated capability taxonomy
as a projection over the canonical inventory: commercial labels, operational
value and functional relationships may evolve independently, while validators
prove that every route and technical section is classified exactly once. Partial
coverage of only the deepest area creates a misleading hierarchy; the first
level should be a small set of understandable product spaces, each deep enough
to expose its principal modules and representative submodules.

Visual exploration should preserve ordinary web semantics. Position real buttons
around an orbit, draw connectors in a non-interactive SVG layer and keep the
selected node in the URL. This provides motion and spatial discovery without
making keyboard access, deep links, reduced-motion preferences or testing depend
on a canvas-only graph library. The spatial rendering is not the information
architecture: the same nodes should become a card grid where the orbit no longer
fits. Technical references can remain available behind an explicit disclosure
after the user understands the capability.

Separate preview, selection and guidance as three states. Hover/focus may replace
the context panel transiently but must not mutate a shareable URL; selection owns
`node`; a guided journey adds an orthogonal `tour` key and removes only that key
on exit. Deriving ordered tour steps from the same main-module taxonomy prevents
a second walkthrough script from drifting away from free navigation.

## 45. Removing a record requires explicit product semantics

“Disappear from the active list” is not one operation. A discarded observation
is evidence that a real issue was considered and not addressed, so it keeps the
row and optional reason. A test, typo or duplicate should be deleted because it
adds no historical value, but recoverability still matters. Name both actions,
explain them at the decision point and make their persisted traces different.

Soft deletion only works when inactivity is a system-wide predicate. Default
querysets, nested serializers, counts, history and MCP reads must all exclude the
tombstone; trash is an explicit scope. Audit records should retain actor and time
without creating a second content snapshot that defeats the cleanup semantics.

Derived workflow state must reconcile in the same locked transaction. Removing
the last pending note may close a state created by notes, never a manual/shared
state. Restoration is the inverse business operation: validate compatibility and
reopen/reuse the state before clearing the tombstone, rolling everything back if
that cannot succeed. Bulk cleanup is one selection and one transaction, not a
loop of partially successful requests.

Finally, native browser dialogs are an architectural escape hatch, not a UI
shortcut. Contextual modals can identify the target, explain consequences,
retain input after an error and expose recovery. A repository-level static gate
is what turns that preference into a durable panel invariant.

## 45. Column order and responsive priority are separate contracts

Moving a high-value field earlier on desktop does not make it survive a
breakpoint. Keep order, width and `keep/group/hide` decisions in one executable
column policy, then make the specialized markup consume that same sequence. A
separate visibility list can otherwise preserve the old priority after the
headers have been rearranged.

Grouping low-value context is different from hiding it. Documents keeps state
as a real landscape column while moving client/project beneath the primary
title cell; compact cards preserve the same facts in secondary metadata. Fixed
business order also avoids a second persistence contract competing with the
existing user preference for title width.

## 46. Solving overlay geometry does not make an empty picker useful

A teleported listbox can be perfectly positioned and still leave the workflow
blank if its data contract only runs after typing. Treat opening readiness as a
separate invariant: when an uncommitted searchable entity field gains focus,
load a deterministic first page and make typing a filter over that catalog.
Primary-decision modals should focus that field explicitly; general forms may
retain their normal first-field order and still gain the catalog on demand.

Progressive loading needs an end-to-end cursor contract, even for offset paging:
stable backend order plus a unique tie-breaker, bounded pages, an explicit total,
generation guards around debounced queries, and de-duplication on append. Keep
the scroll signal in the shared listbox but keep `hasMore` and retry state in the
data-owning picker. This preserves one scrollbar without coupling a generic
overlay primitive to a particular API.

## 47. Nullable uniqueness is already a portable partial-uniqueness primitive

When absence is stored as SQL `NULL`, a plain unique constraint already permits
multiple absent values while rejecting duplicate concrete values. Adding
`condition=field IS NOT NULL` does not strengthen that invariant; on MySQL it
causes Django to skip the complete constraint and emit `models.W036`.

Before choosing a functional or partial index, distinguish `NULL` from an empty
string. Use a plain composite unique constraint for nullable integration keys
such as `(catalog, system_key)`. Reserve `NullIf(field, '')` for domains that
deliberately persist blank strings. Any migration that activates a previously
ignored production invariant must query for duplicates before DDL and stop with
the conflicting business keys instead of failing halfway through deployment.

## 48. A kebab belongs to a fixed control track, not the data-column split

The fact that a table “has actions” is not enough to choose its layout. A single
three-dot menu and a row of independent action icons have different space and
interaction contracts, so the table primitive needs a semantic mode rather
than a blanket reorder. `menu-start` reserves 3.5 rem outside the proportional
data weights; `inline-end` keeps legacy loose-icon rows unchanged until their
actions are deliberately consolidated.

Control order is stable: selection first when present, then actions, then the
identifier/content. The header stays visually empty but retains `aria-label`;
the action cell stops click and auxiliary-click propagation so a navigable row
does not open. It must not cancel pointer/touch movement: a trusted touch-pan E2E
starting on the kebab protects horizontal scrolling while proving that the menu
does not open accidentally.

## 48. A recurring definition is not yet a ledger transaction

Recurring rows answer “what do we normally pay?”; expenses and pocket movements
answer “what did we actually pay?”. Adding pause/archive/duplicate behavior to the
definition must not silently cross that boundary. Keep lifecycle state in one
service and make every budget consumer use the same positive predicate — here,
`is_active && !is_archived` — rather than teaching each KPI, chart, export and
reminder its own exclusion rule.

Archive and delete also encode different facts. Cancellation preserves a useful
definition and its audit trail, so archive is reversible and forces inactive;
delete is only for an archived mistake and needs a stronger confirmation. Restore
must not reactivate a cancelled service implicitly. Bulk lifecycle writes lock the
whole selection and validate missing/conflicting ids before the first mutation,
otherwise a stale browser selection creates an unexplainable partial budget.

Duplication is another boundary test: return a non-persisted form draft, inherit
only editable definition fields, and recompute schedule state from the next
occurrence. Copying reminder cadence, archive state or historical links turns a
convenience action into hidden data creation. When recurring payments eventually
originate real expenses, design an idempotent period key, pocket transaction and
charge-history relation explicitly; do not smuggle them into lifecycle endpoints.

## 49. A dense ledger needs a structural breakpoint, not narrower columns

Eight financial columns can satisfy an explicit `keep/group` policy and still be
unusable at 412 px: action, concept, amount and badges compete before grouped
metadata can help. At that point, use one mobile card per source row and preserve
every fact as an ordered label/value pair. Keep a single table branch above the
structural breakpoint so the DOM never contains duplicate actions or accessible
names.

Presentation must not fork behavior. The same leading 44 px kebab and modal should
serve cards, classic tables and grouped tables; atomic badges own word integrity.
Running figures need their own written contract too: **Saldo después** is the normal
chronological ledger, **Acumulado filtrado** starts with the visible cut, and the
headline balance remains global. Geometry tests should pin all three properties:
no document/inner overflow, no action/content intersection and a concrete value
from the fixture.

## 50. A generated SPA fallback is a deployment contract, not a file check

A static build can complete, produce `200.html`, and return HTTP 200 for every
private route while the application is completely unavailable. After the Nuxt
4/i18n 10 upgrade, browser-language detection converted the unprefixed fallback
into a 101-byte meta refresh to `/en-us/200.html`. Django then used that same
fallback for the target path, so the browser looped without creating a server
error or failing the API health check.

Locale ownership must be singular: Django chooses the locale for `/` from the
manual cookie and nginx country header, while Nuxt keeps prefix routing without
browser detection. More importantly, the publication chokepoint must inspect the
generated artifact before touching the live directory. A usable fallback is
non-empty, contains the `#__nuxt` mount, and cannot redirect. Validate those
properties before the atomic swap, and monitor one real SPA deep route by content;
file existence and status 200 prove neither hydration nor availability.

## 51. Cross-cutting commercial scope is a mutable contract, not boilerplate

A fourth card improves the proposal only when it owns a real semantic boundary.
Screens, components and business-specific actions answer *what this product
does*; responsive behavior, accessibility, usability, performance, security,
privacy and browser support describe qualities that can affect several of those
surfaces. Mixing both categories creates duplication and makes technical
traceability ambiguous.

Keep the `cross_cutting_features` container and its position stable, but treat
its items as a context-dependent catalog. Preserve item ids when copy changes,
require technical links for every retained commercial item, and qualify targets
instead of inventing certification levels, browser matrices or performance
guarantees. When evolving stored proposal JSON, update live defaults and editable
drafts while leaving sent or inactive snapshots intact; commercial documents are
history, not caches to be silently normalized.

## 52. A visual tooltip and an accessible name serve different readers

An icon-only row action may need a contextual accessible name such as **Acciones
de Contrato de Servicios**, but repeating that string in a hover hint adds no
value when the document title is already visible. Keep the application tooltip
short and canonical, keep row context in `aria-label`, and let touch users reach
the same action through the button itself rather than depending on hover help.

Tooltip ownership must be singular at the rendered DOM boundary. Wrapping a
button in an application tooltip while also forwarding `title` creates two
competing notices. In Vue, removing an explicit `:title` binding is not enough
when `$attrs` can still fall through automatically: the owning primitive must
filter `title` deliberately while preserving `aria-*`, `data-*` and link
semantics. Test the rendered attribute and the visible `role="tooltip"`
separately; each protects a different half of the contract.

## 53. A primary selection catalog is modal content, not a dropdown

Fixing a dropdown's clipping can expose a second problem: reserving enough room
for a click-triggered overlay leaves the dialog inexplicably empty before the
click. If choosing among records is the modal's main task, those records are not
supplementary disclosure. Render them permanently in flow and let the search
field filter them; keep floating listboxes for secondary choices in forms.

Do not fork the data behavior to get two layouts. One selector should own query
generation guards, selection, paging, retry and creation while a shared results
renderer supplies either a floating or in-flow surface. The consumer opts into
the permanent presentation explicitly, supplies any persistence key and remains
responsible for the review/action context around it.

Ordering is part of catalog usability. Start with a stable server order and an
id tie-break, expose the direction in the column header with `aria-sort`, carry
the same order through filtering and every progressive page, and persist only
the small user preference locally. Geometry tests must prove at least five full
rows, one list-owned scrollbar, a stationary modal, visible review content and
the full-screen compact contract; a screenshot of an open dropdown proves none
of those boundaries.

## 54. Outbound delivery evidence belongs before the SMTP boundary

Logging a filename or regenerating a document later answers what the system has
*now*, not what the recipient received. Build the MIME message first, persist the
decoded attachment bytes, recognition metadata, body and user-facing links, and
only then call the external mail backend. A storage failure must stop delivery;
otherwise the system knowingly creates an unauditable success.

The primary recipient and internal BCC attempts belong to one delivery snapshot,
while their outcomes remain separate log rows. Resending creates a new delivery
and lineage but reads subject, body and attachments from the retained snapshot;
only the recipient is editable. When old rows lack evidence, use explicit
`legacy_partial`/`legacy_unknown` states—never substitute the current Document.
Keep the live Document relation for navigation and deletion protection, while
the attachment filename, type name, hash and bytes remain historical fields.

## 55. Semantic association and lifecycle ownership need separate fields

A folder may point at a project without being the project's system-owned root.
Reusing the ordinary `project` relation for both meanings makes every descendant
look immutable and leaves no reliable way to distinguish a hand-made hierarchy
from the canonical entry point. Keep semantic inheritance on `project`/`client`
and represent lifecycle ownership with a separate one-to-one relation whose
invariants are enforced in the database and every mutation surface.

Historical name matching is evidence, not authorization. A safe reconciliation
first emits a stable inventory with proposed actions, impacts and conflicts; a
human decides every pending row; apply revalidates both the plan digest and the
database fingerprint inside one transaction. This makes ambiguous client/project
names visible before documents move and prevents an approved proposal from being
silently applied to a later database state. Preserve an inverse snapshot even when
the write is atomic: rollback of data classification is an operational procedure,
not just a transaction primitive.

## 56. A generated document is an artifact, not another editable projection

When a system both generates and sends a PDF, regenerating it later is not an
archive: templates, source data and fonts may have changed. Render once before
the outbound boundary, persist those exact bytes with source/version/hash, and
attach that same byte sequence. Generation failure must stop the send before
any lifecycle transition; delivery failure may retain the prepared artifact and
mark the operational problem without rewriting it.

Location is another derived fact. Use stable server-owned folder keys for
project/client/type/year/month identity, not display-name matching, and create
the path idempotently inside the business transaction. Protect that structure
at every mutation surface (REST, MCP and drag/drop), while leaving orthogonal
administrative observations editable. For legacy data, a dry-run-first backfill
should touch only records still lacking a destination, preserve manual choices
and refuse to invent the business date that defines the archive.

## 57. KPI density and KPI geometry are separate contracts

Equal card heights require a stable internal grid, not copy of equal length.
Reserve label, value and optional support rows in the shared primitive so missing
support text cannot shrink one card. Keep help as its own sibling control and
make the primary surface a button only when it performs an explicit action.

That geometric fix does not solve a header with too many questions. Expanded
layouts can show non-zero details in business order and group different question
families separately. Compact layouts should summarize by question family and
put the lossless detail in a focus-managed drawer. A summary total must combine
like units: for heterogeneous operational facts, count active categories rather
than adding clients, records and review rows into a misleading grand total.

## 58. A thread filter is a correlated event question, not independent joins

A conversation can contain many messages, so applying channel, direction and
status as separate relation joins answers the wrong question: one email can
satisfy channel while an unrelated incoming WhatsApp satisfies direction. Build
one message predicate and apply it through one correlated `Exists`; use OR for
multiple values inside a dimension and AND across dimensions. REST, MCP and
facet counts must consume that same read service or they will disagree while
each appears locally correct.

URL and saved-view state add a separate reactivity boundary. Vue reactive arrays
are proxies and cannot be passed blindly to `structuredClone`; normalize them to
plain, validated values before snapshotting, comparing, writing route queries or
saving a view. A real-browser direct-link case is essential here because a unit
mock can miss the browser's `DataCloneError` and leave the route rendered but
non-interactive.

## 59. Preserve long evidence, index its fixed-size identity

A field's character limit is not its index cost. Under MySQL `utf8mb4`, a
2048-character URL can consume 8192 key bytes before the neighboring foreign key
is counted, so a composite unique constraint can pass SQLite CI and still stop a
production migration at InnoDB's 3072-byte limit. Do not shorten historical
evidence merely to satisfy an index. Store the full value and enforce scoped
uniqueness through a fixed-size SHA-256 fingerprint.

The fingerprint must have one writer. A model `save()` hook is ineffective when
the service uses `bulk_create`, so either populate the derived field explicitly
at every bulk boundary or use the ordinary save path when row counts are small.
Backfill before changing the field to non-null, detect duplicate fingerprints
before DDL, and pin the worst-case production key width in a focused schema test.

MySQL adds a second deployment concern: failed DDL may remain even when Django
does not record the migration. Recovery belongs at the failing migration's entry
only when it can recognize the exact residue. Count every new table and live
reference first; clean only an entirely empty partial state and abort on any
data. A generic `DROP IF EXISTS` or blind `--fake` turns an index bug into silent
history loss. If that recovery itself issues DDL, its `RunPython` must also set
`atomic=False`; otherwise Django opens `transaction.atomic()` around the
operation and MySQL rejects the cleanup before its safety checks can help.

## 60. Validation is field state, not footer content

An actionable validation message has one owner: the field that can resolve it.
That owner must render the copy, expose it as an alert, mark the actual control
invalid and clear the relationship when the value changes. A disabled submit
plus a distant list hides the first useful interaction and duplicates content;
submitting an incomplete form can instead reveal every local correction while
leaving the action row stable.

The same economy applies to labels and help. Choose one required-field marker,
let its absence mean optional, and remove default explanations when the default
is already visibly selected. Inline creation is part of a selector's capability
contract, so it must remain discoverable before the empty or error state and be
opted into only by consumers that can complete the creation flow.

## 61. Search copy and query semantics are one public contract

A placeholder that names client, project, subject and content is not decorative
copy: it defines what the operator can reasonably expect the server to search.
When REST and MCP share a query service, a missing relation in that predicate
creates the same silent false negative in both interfaces even if the navigation
picker still finds the entity locally.

Keep the searchable entity inventory in the shared read boundary and mirror it
in public tool descriptions. Pin relational matches with backend tests that also
inspect the returned facets; add a browser assertion that the existing search
control sends the same query. This proves both halves of the contract without
duplicating business filtering in Vue.

## 62. A list card is an index, not a second detail view

List identity and detail evidence have different jobs. A thread index should
answer whether to open the record through title, ownership, scope, state,
channel, count, recency and pending work. Copying the complete latest message
into that index destroys density and introduces nested reading interactions.

Start with title and operational metadata only. A message preview belongs in an
index only after an explicit recognition need outweighs the lost density; the
Communications operator chose no preview. Keep the complete body on the routed
detail surface. When the responsive structure differs, let the owning page
decide the breakpoint once and pass that capability to the list component; this
avoids duplicate media-query state.

Remembering order is a separate navigation contract. Resolve it predictably as
explicit URL, then active saved view, then validated browser preference, then
the product default. Persist only the small allow-listed token, never the whole
reactive filter object.

## 63. Compact density requires in-flow control geometry

Removing unused rows reduces a card's height, but it also removes the empty
space that used to mask absolutely positioned controls. A help target placed at
an edge may then overlap the label or escape a narrow card even when the main
content grid itself is valid.

Model compact indicators as explicit tracks: flexible identity, atomic
value/action and a fixed help column. Keep the main action and help as sibling
buttons, preserve a 44 px target, and measure containment plus intersection in
the real browser at every expanded reference width. The stacked layout remains
the right default when support needs more than one line; a bounded single line
can coexist with the compact layout when browser geometry confirms the same
height. Two groups that promise equal cards must also share the column count,
not only the component.

## 64. Bilingual content and presentation mode are orthogonal state

The active locale chooses the server projection and the PDF language; it must
not be inferred from whether the content arrived through the canonical catalog
or a shared link. A share can supply an author-selected default while still
letting the reader request the other locale from the same immutable selection.

Cards, list and accordion are projections over one detail contract, not three
content stores. Persist only an allow-listed mode and namespace it by surface so
an operator's dense panel preference cannot surprise a public visitor. For
Nuxt E2E, treat an enabled interactive control as the hydration boundary before
clicking links that rely on client-side routing.

## 65. A lifecycle artifact needs one byte source after issuance

A renderable aggregate and an issued artifact are different facts. Before
issuance, relational rows are the editable source and an ephemeral preview may
render them repeatedly. At issuance, render once, validate and persist the exact
bytes with a hash; every viewer, downloader and sender must read that file. If a
stored reference loses its object, surface corruption instead of constructing a
plausible but historically false replacement.

Database rollback cannot undo object storage. The lifecycle owner therefore
keeps a compensation handle until the outer transaction commits, while preview
flows opt out of persistence before forcing rollback. Historical repair follows
an evidence hierarchy: exact retained delivery attachment first, reconstruction
only when evidence is absent, and explicit provenance for both. Fake-data
generators must obey the same boundary: anything visible in the PDF is set before
the snapshot and never edited afterward.

The UI should project that domain honestly. An artifact gets a PDF viewer and
read-only facts, not an empty Markdown editor; orthogonal observations, archive
state and relationships can remain mutable. Preview geometry is also part of the
contract: constrain short content near document width/height and reserve internal
scroll for long content instead of stretching every viewer to its container.

## 66. Draft completeness and action eligibility are different contracts

Allowing an incomplete draft is useful; allowing an irreversible or external
action to silently repair it is not. Store optional work-in-progress as-is, but
validate every required fact at the service boundary immediately before
snapshots, transitions, timers or network delivery. UI blockers explain how to
resolve the problem, while backend validation keeps every caller equivalent.

Generated and manual content should converge on one persisted field. Keep the
artifact path, REST/MCP path and editor path explicit, then render from that
field without fallback copy. When a future edit is valid but history matters,
snapshot the rendered output at send time: the live aggregate owns the next
delivery, and the snapshot owns the previous one.

## 67. A `<col>` is a column even when its cells are hidden

Hiding cells with CSS removes them from the layout, but a `<col>` in the
`<colgroup>` still creates a track, and percentages computed over every column
still promise space to the hidden ones. In a `table-layout: fixed` table that
promise becomes a blank band beside the visible columns — and content quietly
overlapped inside it, so "no horizontal scroll" checks kept passing. Share the
width per viewport profile among the columns that profile shows, emit `<col>`
only for control tracks, and assert geometry (the visible headers add up to
the table width) rather than overflow alone.

Fixed layout also cannot respect content. Where a table must fit a phone,
prefer auto layout with unconstrained data columns: atomic values keep their
width and the wrapping primary column takes the rest. Percentage widths on
every data column turn the fixed control tracks into the only place auto layout
can put the slack, which is why a kebab track once grew in auto layout.

## 68. Close the menu before opening what it chose

BaseModal's focus trap and scroll lock react to their own `modelValue`, and
Vue patches sibling components in template order. A menu that emits its action
and its close in the same tick lets the next dialog open first when it sits
earlier in the template (or in the parent): it saves the menu item as its focus
return target and then the menu's close unlocks the page underneath it. Emit
`close`, await `nextTick`, then hand the choice over — or keep the menu as the
first modal of the page. Nested menus (a row menu inside the client emails
modal) must also leave the scroll lock to the outer modal and tell it to stop
answering the global Esc listener while they are open.
