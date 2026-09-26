# Carpetas y lectura de Comunicaciones — PR #416 (2026-09-25)

Implementado en `feat/25092026-communication-folders-reading`: carpetas independientes por cliente/proyecto, IDs visibles y buscables, lectura del hilo con formulario y detalles plegables, accesos al inicio/final y copia directa. REST y MCP comparten las reglas de contexto, jerarquía y borrado protegido. La navegación de proyecto incluye las carpetas generales de su cliente y conserva la ubicación al crear desde móvil. Migración aditiva `content.0258`; entrega mediante PR #416 a main, sin despliegue ni cambios en datos reales.

# Contrato v8: confidencialidad, propiedad intelectual y literales — en verificación (2026-09-26)

La migración `content.0259` reescribe la cláusula décima (DESARROLLO
ESPECÍFICO del cliente; know-how y componentes reutilizables y estándares de
la industria en parágrafos propios, de ProjectApp aunque se escriban durante
el proyecto; licencia temporal pasa a Parágrafo Quinto) y la décima primera
(confidencialidad recíproca, no uso, sin productos derivados de la oportunidad
revelada, no circunvención de 2 años que incluye equipo y subcontratistas;
sin excepción de portafolio). Todas las enumeraciones pasan a literales en
negrilla, uno por párrafo, y las referencias a "literal": el parser del PDF
unía los `a)` consecutivos y ambos renderizadores renumeraban las listas
`N.`. Un solo grupo atómico: una sección personalizada deja la plantilla
intacta con aviso. Los títulos largos de cláusula ya no se salen del PDF.

**Un solo contrato.** Producción servía la v7 (sin #410/#412 desplegados) y
el Gestor guardaba una copia manual v6 (doc #104). Ahora la plantilla default
es el único texto, de solo lectura en el admin y cambiada sólo por migración.
`ContractTemplate.mirror_document` (0260) enlaza un documento del Gestor que
no guarda copia: panel, PDF, correos y MCP lo sirven en vivo, igual al
borrador público, con descarga PDF/Markdown y sin edición, duplicado,
archivado ni borrado. La 0261 convierte el #104 en esa ventana. La 0262
alinea el párrafo de alcance de las propuestas (otrosí + no renuncia) y el
texto de financiación dice que la cesión opera con el acta tras el pago.
Pendiente del operador tras el despliegue: confirmar en el lector público y
en el #104, y decidir si regenera los PDFs de contratos en negociación.

# Propiedad intelectual y terminación del contrato — en verificación (2026-09-25)

La migración `content.0257` perfecciona la cesión de desarrollos específicos y
reserva know-how, activos reutilizables y licencias de terceros. La salida
unilateral del cliente exige una penalidad del 30 % de las fases restantes,
independiente del precio y sin derecho al código. Solicitarlo posteriormente
requiere completar el 100 % del precio, además de liquidar la penalidad; sólo
se entrega el desarrollo existente al cierre, sin reactivar fases pendientes.
Las cláusulas novena, décima y decimosexta se actualizan como un grupo para
evitar contradicciones si existen ediciones manuales. Se retira el acceso de
solo lectura y se renumera el numeral de hosting posterior y su referencia.
Los contratos particulares y PDF emitidos se preservan. Trabajo aislado en
`contract-ip-termination`; aplicación a producción mediante despliegue.
Consulta de producción verificada mediante el lector público del contrato:
Actividades contiene únicamente los numerales 1 a 6 y no obliga a entregar
videos. No se añadió un numeral 7 ni se tocaron las exclusiones audiovisuales.
Los ocho bloques anteriores de la migración coinciden con la plantilla
publicada. El test de cesión se actualizó a la nueva condición de pago.

# Reajuste del servicio en el contrato — en verificación (2026-09-25)

La migración `content.0255` sustituye el parágrafo tercero de la cláusula
vigésima primera de la plantilla predeterminada. Conserva SMMLV/IPC como base
mínima y remite fecha del primer reajuste, renovaciones, periodicidad de pago
y componentes adicionales al Documento Propuesta Comercial aceptado, sin
imponer un ajuste cada 1 de enero ni duplicarlo por facturación. El reemplazo
es puntual y reversible; las cláusulas personalizadas se conservan con aviso.
PDFs históricos y contratos particulares permanecen intactos. Aplicación a la
base real mediante el despliegue; validación en SQLite aislado del worktree
`contract-service-adjustment`.

# Retiro del recordatorio responsivo — implementado (2026-09-23)

**2026-09-25 — copia Markdown de documentos de propuestas:** implementada en
[PR #408](https://github.com/gustavop-dev/projectapp/pull/408). El contrato
conserva el texto junto a su PDF; los anexos formales comparten contenido
curado y los adjuntos admiten PDF textual, DOCX y XLSX sin OCR. Incluye vista
previa de Office, descarga del original, feedback de portapapeles y mapas
actualizados. Backend: 29 casos focales verificados con almacenamiento y
SQLite temporales. La validación final de navegador y CI se consulta en el PR.
La migración 0255 se aplica durante el deploy.

Por decisión del operador, el PR #405 incorpora el retiro del job
`standards-review` y su cron de febrero/agosto. Sólo creaban una issue semestral;
su omisión en los PR era consecuencia de esa condición. Se conservan contrato,
selección de módulos, E2E por PR/push, matriz mensual y ejecución manual. La
revisión periódica queda a cargo del equipo; las APIs de GitHub no muestran
ramas protegidas ni rulesets que requieran el check. Diagnóstico y política
vigente en `docs/methodology/responsive-acceptance.md`.

# CAPTCHA de login — implementado (2026-09-23)

**2026-09-23 — CAPTCHA de login:** implementación en el worktree de sesión
`login-captcha`, sobre `origin/main`. reCAPTCHA v2 obligatorio en Django Admin
(panel) y Plataforma, verificador compartido que bloquea ante fallas, widget
con expiración/reintento y configuración explícita por ambiente. Validación
focal backend/unit y navegador con Django real en base temporal; entrega como
PR abierto. Activación y claves reales quedan al deploy (`docs/LOGIN_CAPTCHA.md`).
# Plantillas HTML por MCP (Nivel 3) — en verificación (2026-09-23)

El conector `content` suma doce herramientas en `backend/content/mcp/linktree_template_tools.py` para que un asistente diseñe plantillas a medida: contrato de autoría con las variables reales de la tarjeta (perfil, foto/logo, enlaces con etiqueta/URL/icono/tipo, acciones disponibles, contacto, colores y fuente), carga de paquetes por texto/base64/`asset_id`, seguimiento de la validación en Chromium, vista previa con capturas como artefactos, reemplazo de imágenes editables, publicación con confirmación, restablecimiento, compartición y clics agregados. Reutiliza íntegro el servicio del panel: ninguna instantánea se activa sin `status=valid` y perfil vigente. Contratos actualizados (`LinktreeTemplate`/`LinktreeTemplateVersion` en lectura, `is_shared` escribible). Segundo commit: biblioteca de imágenes por Linktree (`LinktreeAsset`, migración 0254) con `upload_linktree_asset`/`list_linktree_assets`/`delete_linktree_asset` y endpoints de panel; la plantilla puede pegar la URL devuelta o usar `data-asset="clave"`, cada versión guarda su copia, y el bloque Apariencia del panel avisa que con plantilla publicada el tema básico sólo es el fallback (los campos se conservan para los linktrees existentes). Rama `feat/23092026-linktree-mcp-tools`, [PR #403](https://github.com/gustavop-dev/projectapp/pull/403); casos nuevos de backend y unitario de frontend en verde localmente. Documentación en [LINKTREE_HTML_TEMPLATES.md](../docs/LINKTREE_HTML_TEMPLATES.md) y el runbook MCP.

# Correcciones de plantillas HTML — en verificación (2026-09-23)

Tras revisar el PR #400 integrado, se corrige la detección de capas fijas de `body` y pseudoelementos, y la densidad real de las variantes de imagen (incluidas las publicaciones existentes). Entrega en [PR #402](https://github.com/gustavop-dev/projectapp/pull/402), rama `fix/23092026-linktree-template-validation`, basada en `main`. Pruebas focales y quality gate aprobados; la ejecución completa de CI se consulta en el PR. También se refuerza el control del despliegue: responder HTML 200 en una ruta nueva de API no constituye un deploy correcto. El acceso al servidor de producción está pendiente de confirmar; no se han ejecutado migraciones ni cambios remotos.

# Plantillas HTML para Linktree — implementadas (2026-09-23)

Nivel 2 sobre `main` actualizado: paquetes ZIP/archivos, Mustache escapado, recursos sanitizados, validación visual aislada, versiones publicadas y biblioteca compartida por cliente. El PR anterior de branding y recursos de proyectos (#396) ya fue integrado. Entrega en [PR #400](https://github.com/gustavop-dev/projectapp/pull/400), rama `feat/23092026-linktree-html-templates`; no se modifica la base de producción. Verificación: 38 casos nuevos de backend, 10 unitarios del frontend y cinco E2E ejecutados en CI; gate focal sin errores y auditoría KEEP. Publicar exige una instantánea validada y la biblioteca comparte por cliente. El worker requiere Chromium y la migración 0253 mediante deploy. [Guía](../docs/LINKTREE_HTML_TEMPLATES.md) y [evidencia QA](../docs/audits/2026-09-23-linktree-templates-qa.md). El estado del CI final se consulta en el PR.

# Historial por registro implementado (2026-09-22)

Se implementó la ficha aprobada para Documentos, Propuestas, Proyectos, Clientes y todo Contable: versiones consultables/comparables, autor, conservación sin vencimiento, PDFs históricos y secretos cifrados. Comunicaciones y restauración quedan fuera. Validación focal: 44 casos backend, 5 del visor y 15 E2E aprobados; regresiones de accesos, propuestas, CRUD contable, correo fallido, PWA, migración de credenciales y eliminación de alias aprobadas, al igual que el contrato de fake data y la compilación Nuxt. El despliegue requiere las migraciones 0250/0251 y el inicializador idempotente descrito en `docs/ENTITY_HISTORY.md`; no se ejecutaron contra una base real.

# Active Context — ProjectApp

**2026-09-25 — videos brag v2:** dos piezas de 45 segundos con voz,
música cálida e identidad ProjectApp para catálogo y Programa de Alianza.
Fuentes v1 conservadas; alcance y validación en `explainers/brag-v2/`.
Pipeline reproducible, clips cacheados por contenido y portada sin parpadeo.
Entrega mediante PR #415; el despliegue queda fuera de esta sesión.

**2026-09-24 — Diseño público en los PDF formales:** el adaptador de formalización
reutiliza los generadores comercial/técnico y sus portadas, tipografía, colores,
índice y componentes. La proyección mantiene alcance, condiciones y exclusiones,
con importes previamente resueltos y sin re-seed de catálogos. Las preparaciones
nuevas versionan la huella para incluir títulos; las existentes conservan sus
bytes revisados. Trabajo en `fix/24092026-formal-pdf-public-design`; sin cambios
de frontend, migraciones ni envíos reales.

**2026-09-23 — ajustes visuales comerciales implementados:** continuación
del PR #391 en `fix/23092026-commercial-visual-polish`. Catálogo, selecciones
y Programa de Alianza distinguen página, tarjeta e interiores en ambos temas;
se retiran separadores decorativos y el corte del brillo del encabezado, y se
corrige el SVG de compartir. Las entradas
de secciones respetan movimiento reducido y contenido recibido tras hidratación.
Las rutas `partnership-program` y redirects existentes se conservan. La validación
focal cubre los cinco perfiles, contraste, controles, modales, errores y rutas;
el fallback del nuevo observer se prueba en unidad. Sin migraciones ni cambios
de API. Entrega mediante PR de sesión; el despliegue queda al operador.

**2026-09-22 — sexta ronda de rendimiento de Plataforma:** continúa en el PR #397.
Los selectores global y por cliente proyectan sólo los campos que publican;
el resumen legacy de accesos calcula presencia de contraseña en SQL sin cargar
accesos ni ciphertext. Se conservan permisos, filtros, orden y tipos, incluidos
el importe cero y la presencia de secretos con espacios. QA cubre consultas con
JWT y materialización en pruebas separadas. Los listados siguen completos: su
caso es conservative y queda pendiente acordar otro contrato para acotar payload
y memoria bajo carga. Sin cambios de esquema, flujo UI ni despliegue.

**2026-09-22 — quinta ronda de rendimiento de Plataforma:** continúa en el PR #397.
El detalle GET de cliente reutiliza los agregados del listado; proyecto carga
agregados independientes y recorre una proyección estrecha de fases una sola vez,
conservando cálculos Decimal, descuentos y vínculo legacy. Entregable comparte
las versiones con su contador y evita cargar campos no publicados de propuestas
y cuentas de cobro. Las mutaciones conservan su ruta y los serializers su fallback.
QA mide peticiones completas con JWT: el objetivo de clientes/proyectos es el
presupuesto estándar; entregables conserva una desviación documentada por sus
colecciones completas. No hay cambios de contrato, esquema, flujo UI ni despliegue.

**2026-09-22 — cuarta ronda de rendimiento de Plataforma:** continúa en el PR #397.
Notificaciones precarga entregables; evaluación masiva carga sólo los IDs del
payload preservando sus errores, duplicados y efectos por elemento; el detalle
GET de requerimientos consume comentarios e historial precargados con sus autores.
Se mantiene el filtro de comentarios internos y el fallback del serializer.
La evaluación masiva de bugs vuelve a notificar por proyecto y bug, como la
individual, sin acceder al campo retirado `deliverable`. QA verifica consultas,
filas materializadas y contratos; el coste JWT del detalle se reporta separado
del presupuesto de datos. Sin cambio de esquema, mapa de vistas ni despliegue.

**2026-09-22 — tercera ronda de rendimiento de Plataforma:** continúa en el PR #397,
en `fix/21092026-perf-platform-lists`. Clientes prepara conteos, actividad y la
suscripción elegida; proyectos usa agregados independientes y precarga sólo los
datos necesarios; fases lee el ID del entregable sin cargarlo. Se conservan los
contratos de listado, orden y permisos, junto a los fallbacks usados por detalle,
panel y MCP. Los guards comparan una fila con cincuenta, con relaciones distintas
y un caso vacío; las regresiones cubren orden, permisos, archivado y consumidores.
El selector de propuesta declara el tipo de PK para combinar fase y vínculo
legacy en Django. Sin cambios de esquema, flujos de frontend ni despliegue.

**2026-09-19 — formalización de propuestas implementada para revisión:** perfil documental
curado (comercial y técnico), contrato final, preparación privada con revisión
exacta de adjuntos y correo configurable desde Documentos. La vista pública y
el estado de la propuesta conservan sus flujos existentes. La validación se
ejecuta en el worktree `proposal-formalization`, sin envíos reales. La matriz de
contenido y el recorrido están en `docs/PROPOSAL_FORMALIZATION.md`. La migración
`content.0249` queda para el despliegue; las preparaciones privadas están
excluidas del MCP y la limpieza diaria conserva las evidencias del historial.

**2026-09-19 — PWA del panel interno:** implementación en la rama de sesión
`feat/19092026-panel-pwa`. Instalación desde navegación de escritorio/móvil,
ayuda bilingüe y pantalla autónoma de desconexión con reintento. La invitación
solo aparece en el dashboard para no desplazar los datos de otros módulos. Sin caché
privada ni cambios de auth. Rutas raíz explícitas en Django y verificación del
build; CI incorpora Chromium contra el frontend generado servido por Django
con settings de test y sin migraciones. El diálogo nativo se simula solo en la
frontera del navegador; la instalación en dispositivos físicos queda como
comprobación manual posterior al despliegue.

## En curso — Monitoreo operativo (2026-09-19)

Módulo interno para administradores: casos por proyecto/servidor, notas, cierre
manual y reportes separados. Primera integración: vps-projectapp-prod y sus
proyectos activos ProjectApp, Mimittos y Tenndalux. Recepción estructurada con
credenciales limitadas, idempotencia y cola durable local; correo coexistente.
Silk se habilitará gradualmente mediante deploy, nunca desde el worktree.

Implementación en `feat/19092026-project-monitoring`, PR #393. Incluye catálogo
de vistas y flows nuevos, pruebas aisladas de permisos/CSRF/idempotencia/orden,
historial manual y presupuesto de consultas/retención. Conectores locales en
el toolkit y exportadores en worktrees independientes de Mimittos/Tenndalux.
Activación, migraciones productivas y rollout Silk quedan al deploy del operador;
la sesión entrega PRs abiertos, no los mergea. Runbook: `docs/monitoring.md`.

## Current State

**2026-09-19 — interfaz pública comercial y URL de Alianza listas para integrar:**
catálogo, selecciones y Programa de Alianza comparten controles flotantes con el
patrón de propuestas; el tema local persistente llega a diálogos, guía y errores,
sin recolorear el panel. Compartir conserva la URL completa y ofrece copiar o
usar el selector nativo con feedback recuperable. El panel vive en
`/panel/partnership-program` (incluidos nuevo y detalle); enlaces anteriores
redirigen por Django y Nuxt conservando idioma, parámetros y destino protegido.
API, datos e identificadores internos de financiación no cambian. Se verificaron
18 casos backend, regresiones unitarias de componentes/middleware, 15 escenarios
de tema y 15 redirects en los cinco perfiles, más compartir, errores, PDF y panel.
Los nueve flujos E2E afectados están cubiertos; el gate focal E2E pasó 100/100.
Mapa de vistas, contrato responsive y registro de flows actualizados. Sin
migraciones, acceso a datos reales ni despliegue desde esta sesión.

**2026-09-04 — módulo de experiencias audiovisuales listo para integrar:** el
catálogo comercial suma su módulo 24 en *Marketing y adquisición*: creación de
contenido audiovisual en lenguaje comercial, como piezas cortas hechas a la
medida de la marca para que una vista se entienda de un vistazo. Se ofrece por
paquetes —los iniciales son de 4, 8 y 16 recursos— y la invitación a consultar
los disponibles con el representante cierra la tarjeta de requisitos, junto a
los recursos que aporta el cliente: identidad de marca, material propio,
mensajes clave y acceso a la plataforma. Entra como migración de datos, sin
cambio de esquema, serializer, contrato MCP ni frontend; por eso los paquetes
viven dentro de los campos existentes y no como bloque propio — si un segundo
módulo se ofrece así, ahí conviene promoverlo a capacidad del catálogo. Un test
blinda que el catálogo nunca nombre la herramienta con la que se produce el
contenido.

**2026-09-04 — orden de ingresos listo para integrar:** el listado abre por Mes
descendente; Mes alterna reciente/antiguo y Total recorre mayor/menor/default.
La selección persiste en el navegador y sobrevive filtros, quick tabs, cambio
Agrupado/Clásico y recarga. En Agrupado se aplica dentro de cada cliente sin
mover el orden financiero de los grupos ni el bucket “Sin cliente”. No hay
cambios backend ni de esquema; composable, encabezado agrupado y flujo E2E
quedaron cubiertos y el mapa P1 conserva todos sus outcomes satisfechos.

**2026-09-05 — detalle seguro de accesos por proyecto listo para integrar:**
Proyectos abre un modal desde tabla, tarjeta o acciones compactas del Panel, y
los administradores de Plataforma usan `/platform/projects/:id/access`; la ruta
global anterior sólo redirige. El editor compartido presenta producción y
staging en columnas desde landscape, URL del repositorio, URL/usuario/password
Django por ambiente y notas múltiples con título/contenido. Cada campo guarda
por separado y se copia con acción iconográfica; passwords y notas sensibles
empiezan ocultos. `ProjectAdminAccess` y `ProjectAccessNote` guardan secretos
Fernet, registran actor/fecha y la migración `accounts.0063` mueve legacy sólo
cuando un hostname identifica un único ambiente; los ambiguos se clasifican con
acción explícita y guard de conflicto. Session/CSRF staff y JWT admin reutilizan
handlers, pero clientes, serializers generales y MCP no ven secretos; todos los
payloads del detalle usan `no-store`. Seeds representativos generan dos
ambientes y notas cifradas con dominios reservados. Verificación focal: 31
backend, 14 unitarias y 15 E2E funcionales, matriz responsive 10/10, build Nuxt,
Django check/migration dry-run/SQL, contratos de flows y quality gates en verde.
El refresh de fake data se omitió porque `projects.yml` clasifica este entorno
como producción.

**2026-09-04 — ayuda y agrupación de pendientes por cobrar listas para
integrar:** el tooltip de la leyenda ahora se monta en la capa flotante del
modal dueño y conserva `body` como fallback fuera de diálogos. Gestionar
candidatos reutiliza la tabla agrupada de Ingresos con Cliente/Proyecto,
totales completos y alternativa Clásico; abre siempre en Agrupado/Cliente y no
guarda la presentación entre visitas. La búsqueda precede al agrupamiento y las
mutaciones inmediatas existentes no cambian. Pasaron 38 pruebas unitarias, 6
E2E funcionales, los 5 perfiles responsive del modal, 10 celdas foundation,
build Nuxt y checks de diseño, responsividad y flow registry. El flujo P1
`admin-accounting-receivables` queda cubierto en display/success/failure.

**2026-09-04 — mensaje personalizado de propuestas listo para integrar:** el
tab **Correos** está disponible desde borrador y guarda de forma independiente
un mensaje en texto plano que conecta problema, solución y resultado. Todos los
caminos de envío lo exigen antes de crear snapshots o cambiar estado; reenvío
lo precarga, permite editarlo y conserva intactas las entregas previas. El mismo
contrato atraviesa creación manual/JSON, MCP, fake data y las skills de creación
de propuestas en Codex y Claude. No hay cambio de modelo, migración ni backfill;
los flows P1/P2 de crear, enviar, reenviar y multi-enviar están cubiertos en sus
outcomes declarados.

**2026-09-04 — destinatarios múltiples y CC listos para integrar:** los
compositores independiente, de propuesta general/seguimiento, diagnóstico y
documento, además del reenvío exacto, admiten selección de clientes y entrada
manual en Para/CC con máximo 10 direcciones únicas. Backend conserva payloads
singulares, valida el contrato completo y envía un solo mensaje visible; el
gateway registra cada dirección bajo una entrega y mantiene aparte las copias
BCC automáticas. Snapshot, historial universal, historiales contextuales,
dashboard, filtros, documentos y MCP proyectan el grupo sin inflar conteos. La
migración `content.0246` hace backfill seguro. Verificación focal: 24 pruebas
backend, 55 unitarias, 11 casos Playwright, build Nuxt, Django/migraciones,
guards de diseño/responsive y auditoría de flows en verde. El refresh de fake
data se omitió porque `projects.yml` clasifica este entorno como producción.

**2026-09-04 — vista previa pública de propuestas lista para integrar:** la
acción del modal de edición vuelve a abrir la propuesta en una pestaña pública
con `preview=1`, sin activar tracking ni devolver el 500 de Nuxt. El composable
de tracking conserva ahora un contrato estable en preview (`refs` vacíos y
`flush` no-op) y sale antes de registrar watchers, lifecycle hooks o requests.
La cobertura focal valida `preview=1|true` y el recorrido real desde el botón
hasta el banner de preview; el flow `admin-proposal-actions-modal` cubre
`display` y `success`, y el mapa quedó fresco.

**2026-09-03 — política de financiación lista para integrar:** la oferta y el
otrosí comparten una política versionada con elegibilidad inclusiva de
$20–140 millones COP, primer pago definido por análisis de riesgo con piso del
20 %, financiación máxima del 80 %, doce meses, pagos entre días 1–5 y recargo
de Hosting del 2 % por mora. Panel permite publicar revisiones y consultar su
historial; cada acuerdo congela política y tasa USD, y sólo un borrador anterior
puede adoptar la vigente mediante acción auditada. JSON/PDF público, contrato,
calendario y formulario son dinámicos. Pasaron 81 pruebas backend, 22 unitarias,
36 E2E y el build; los 11 flujos de financiación están totalmente cubiertos.

**2026-09-04 — previsión visual con interruptor manual lista para integrar:**
cada ingreso esperado abierto de empresa puede entrar o salir de una shortlist
y conservar un semáforo verde/naranja/rojo; elegir color ya no lo selecciona y
cada cambio se persiste sin alterar el otro eje. El interruptor sólo responde a
la acción manual del usuario. El círculo acompaña el texto completo en tabla,
modal, formulario y detalle; lo no clasificado usa un círculo neutro. Alta y
edición guardan ambas decisiones, duplicar las reinicia y los estados históricos
permanecen intactos. El total “Pendiente por cobrar” es global y suma el monto
original únicamente de verdes seleccionados. Un cobro total, ingreso perdido o
cambio fuera del ledger de empresa retira automáticamente el candidato sin
borrar su clasificación. El acceso rápido Ads fue reemplazado por Cuentas de
cobro sin retirar Ads del submenú contable. Esquema `content.0244`, endpoint
REST, herramientas MCP, seeds y mapas E2E permanecen sincronizados sin migración
nueva.

**2026-09-02 — paridad operativa MCP lista para integrar:** los 16 conectores
registrados —10 canónicos y 6 compatibles— exponen el Panel por área con
credenciales acotadas, actor técnico, riesgo explícito, resultados estructurados,
auditoría, ETags, uploads firmados y confirmaciones de un solo uso. Documentos
conserva edición Markdown de borradores y bloquea snapshots inmutables;
Comunicaciones, Comercial, Proyectos, Contenido, Tareas, Operaciones y los tres
dominios contables reutilizan las mismas vistas, serializers y servicios del
Panel. Verificación final: fundamento 25 casos, protocolo 14, contratos de rutas
12, store 8 y E2E MCP 10/10; build Nuxt, Django check y migraciones sin drift en
verde. El flow `admin-mcps` cubre display/success/error/failure. No se activó ni
rotó ninguna credencial de producción; ese corte sigue siendo deliberadamente
posterior al merge y despliegue.

**2026-09-03 — workspace contractual de financiación listo para integrar:** la
penalización por mora queda como condición documental —sin escrituras automáticas
sobre Hosting—, la modalidad de cinco años ofrece un segundo ciclo sujeto a pago
íntegro y nueva aprobación, y `/panel/financing` administra datos reales,
calendario, borrador, PDF firmado privado, auditoría y estados explícitos. El
panel y sus mensajes quedaron disponibles en español e inglés.

**2026-09-02 — módulo de financiación listo para integrar:** la nueva superficie
comercial informa, sin cotizar ni aprobar automáticamente, las condiciones de
financiación para productos con potencial. La alianza recomendada combina 12
meses al 0 % de interés ordinario, cinco años de exclusividad, custodia de código,
calculadora de requerimientos y 60 horas renovables cada mes; la alternativa de
tres años conserva financiación, exclusividad y calculadora, pero no el paquete.
El backend bilingüe alimenta JSON y booklet PDF, sincroniza el paquete Pro activo
con fallback visible, y el frontend ofrece rutas públicas prerenderizadas,
acordeones, tema, idioma, compartir, WhatsApp y distribución desde Panel. No hay
cambio de esquema ni escritura de negocio. Verificación: 8 backend, 78
unitarias/config, 12 E2E, build y contratos de catálogo/flow verdes; se corrigió
el solapamiento detectado entre compartir y el WhatsApp global.

**2026-09-02 — rendimiento del Gestor Documental listo para integrar:** el
listado interactivo ya no descarga y serializa todo el inventario al entrar o
cambiar de carpeta. `documents/browse/` pagina en servidor (10 tabla, 12
galería), devuelve totales autoritativos, resuelve raíces globales/de proyecto y
usa estados compactos; el endpoint array existente permanece compatible.
Frontend conserva página/URL, reinicia página al cambiar filtros y cancela cada
request superado para impedir respuestas fuera de orden. En producción, lectura
solamente, el p95 quedó en 464 ms para 138 activos, 57 ms para la raíz del
proyecto mayor y 178 ms para la carpeta mayor, con cuatro queries en los casos
comunes y 14.5–16.9 KiB por página. Sin migración, índice ni caché nueva. El
build, las regresiones focales y el escenario E2E de paginación están verdes;
flow-map fresco y `admin-document-list` cubierto en sus tres outcomes.

**2026-09-02 — paridad administrativa de Comunicaciones por MCP lista para
integrar:** el conector pasa de 6 a 14 herramientas y ya puede editar hilos,
cerrarlos/reabrirlos, archivarlos/restaurarlos, eliminar borradores, anular
mensajes históricos y corregir sus fechas, además del flujo previo de consulta,
creación, edición de borrador y confirmación de envío. Todas las mutaciones
reutilizan serializers y `communication_service`; cliente, comunicaciones madre,
propiedad de proyecto/documentos, estados editables y auditoría conservan las
mismas guardas del panel. `list_threads` suma `scope` y `order`. Ninguna acción
envía correo o WhatsApp. La migración de datos sólo actualiza la descripción y
preserva token, prefijo, actividad y último uso. Verificación focal: 20 casos
administrativos, 19 de edición, 19 de regresión base, 23 de contratos y 17 de
paridad transversal; Django y migraciones sin drift, quality gate 93/100 con 0
errores/0 junk y un warning local porque `ruff` no está instalado.

**2026-09-02 — tracking de propuestas y alerta de primera vista listo para
integrar:** abrir el enlace ya no incrementa métricas. Una vista se confirma tras
cinco segundos visibles, se deduplica por sesión, actualiza heartbeats/final y
persiste contador, primera vista, estado comercial, actividad y alerta dentro de
una transacción. La entrega por email tiene estado/intentos/error durable,
reintentos Huey, reconciliación y reintento manual observable en Analítica; el
histórico queda marcado sin correos retroactivos. Payloads anónimos tienen límites
y un draft o sesión staff no escribe. Verificación: checks/migración, cortes
backend focales, 43 unitarias frontend focales, 10 E2E y flow audit completo para
heartbeat, display y retry success/failure.

**2026-09-02 — colores semánticos de correos contables listos para integrar:**
`accounting_change` usa verde para ingresos/entradas, naranja para
gastos/salidas/recurrentes/Ads/deuda y azul para entidades neutrales. Cabecera y
valores nuevos comparten el tono; valores anteriores siguen rojos. Los eventos
de Bolsillo guardan `movement_direction` para que Huey y los reintentos no lean
estado posterior; `content.0237` hace backfill sólo con evidencia del diff. Sin
cambio de REST, MCP, panel ni otros correos. Verificación focal: 17 casos de
clasificación/render, 3 de migración y 8 de regresión del envío, todos verdes;
`makemigrations --check --dry-run` no detecta drift y el quality gate focal
cerró en 93/100 sin errores ni advertencias.

**2026-09-02 — orden por fecha del Gestor Documental listo para integrar:** la
columna Creado alterna entre más nuevos y más antiguos con icono, `aria-sort` y
estado de carga; Galería y móvil conservan la misma capacidad mediante un
control compacto. El backend ordena el conjunto completo antes de paginar por
la fecha visible: creación en activos, archivo con fallback a creación en
archivados y la fecha correspondiente por fila en listas mixtas. `order=oldest`
se conserva al buscar, filtrar, cambiar de carpeta, scope o vista y se omite en
el default reciente; no existe preferencia entre visitas ni otras columnas
ordenables. Un error de refresh conserva filas, dirección y URL anteriores.
Verificación focal: 9 pytest, 13 unitarias, 4 E2E y flow-map fresco; el flujo
`admin-document-list` cubre `display`, `success` y `failure` sin brechas.

**2026-09-02 — contexto proyecto→carpeta de Documentos listo para integrar:**
el clic simple y el enlace real de una carpeta usan ya la misma decisión. Una
subcarpeta de Vástago conserva `project` junto con `folder`, mantiene el proyecto
seleccionado y entrega ese origen completo al editor; «Volver» restaura carpeta,
proyecto y foco. La paridad cubre clientes, mientras Carpetas propias o ajenas
siguen limpiando ambos ejes. Sin cambios de API, backend ni esquema.
Verificación: 20 unitarias focales, los 12 escenarios E2E del flujo, build Nuxt,
quality gate 100/100 y auditoría P1 (`display`, `success`, `failure`) en verde.

**2026-09-02 — compatibilidad cuenta de cobro / Gestor Documental lista para integrar:**
la investigación confirmó que una cuenta emitida no tiene contenido Markdown:
su fuente es el snapshot contable con el que se construye el PDF. Se implementó
la alternativa 2 sobre `Document.generated_file`: emitir archiva una sola vez
los bytes definitivos con SHA-256 y esos mismos bytes alimentan vista previa,
descarga, envío y reenvío. Título, cliente, proyecto, carpeta y datos contables
quedan de sólo lectura; archivado, hilos y observaciones privadas permanecen, y
una corrección exige anular/reemitir. El backfill dry-run-first prefiere el
adjunto histórico exacto del correo y sólo reconstruye cuando no existe esa
evidencia. El editor muestra la ruta completa bajo el título con cada carpeta
clickeable y limita las previsualizaciones Markdown/PDF a proporciones de
documento con scroll interno. Fake data respeta el mismo límite temporal; el
refresh real fue rehusado por la guardia de producción. Verificación focal:
backend, contratos MCP, unitarias, cuatro E2E, build Nuxt, diseño, responsive,
Django y ausencia de migraciones en verde.

**2026-09-01 — paridad pública de Módulos adicionales lista para integrar:** el
catálogo canónico y las selecciones ya no conservan el hueco del Navbar
retirado. Tema y guía quedan como acciones flotantes izquierdas; compartir y PDF
como acciones derechas, además del WhatsApp global. El PDF de cabecera permanece
y comparte loading/error con el flotante. El tema se recuerda, el modal de
detalle lo hereda, la guía ES/EN aparece una vez y puede reiniciarse, y compartir
copia exactamente la URL vigente para no perder el UUID de selección. Sin
cambios backend, tracking, contenido, precios ni esquema. Verificación: 28
unitarias, 16 E2E funcionales, matriz responsive 20/20, build Nuxt, flow-map
fresco y flows de guía/tema/share cubiertos; el único `junk-only` global es la
deuda previa ajena de suscripción de hosting.

**2026-09-01 — aceptación responsiva consolidada y ejecutable:** las 107 vistas
Nuxt quedan derivadas del catálogo real y repartidas entre 13 dueños, 92
escenarios visuales y 15 redirects. La matriz única recorre los cinco perfiles
canónicos (535 celdas) en batches de máximo 20 casos, sin retries, y reporta
`cumple`, `no cumple` o `cumple distinto` por vista/ancho. Los recorridos
especiales prueban tablas, filtros, navegación, acciones y modales reales; los
seis flujos contables largos pasan en sus 30 combinaciones: cuenta de cobro,
liquidación, abono, ingreso, Hosting y edición/transacción de Extractos. La
campaña detectó y corrigió cuatro fallos observables: el tooltip de un control
bloqueado que salía del viewport, un enlace expandido de tabla que cubría la
acción vecina, dos etiquetas de vigencia sin asociación accesible y los
`fieldset`/controles LinkedIn del editor de Blog que desbordaban 30 px en
compact. El auditor fusionó seis specials duplicados y aprobó los survivors;
el gate final quedó sin errores ni warnings nuevos. Los
redirects ya acreditan su comportamiento de compatibilidad, no el flow
funcional de la pantalla destino. CI selecciona módulos afectados en PR y
conserva la campaña completa mensual. La certificación en dispositivos físicos
sigue separada como RSP-F5-01 porque viewport/touch emulados no reproducen
teclado, barras de sistema ni safe areas.

**2026-09-01 — hilos lineales entre documentos listos para integrar:** cada
documento puede pertenecer como máximo a un hilo con nombre editable, aunque sus
miembros vivan en carpetas, clientes o proyectos distintos. La cronología usa
fecha de emisión o creación en Bogotá y desempata con posición estable. El modal
compartido Relacionar/Detalle/Cronología abre desde listado y editor, busca con
paginación y scope activo/todos, permite previsualizar markdown/PDF y muestra
archivados o conflictos sin ocultarlos. Las listas enseñan `Hilo · N`; archivar
preserva la relación, eliminar exige desvincular, dejar un único miembro disuelve
el hilo y duplicar no hereda membresía. Mergeado en #347 y desplegado el mismo
día (migración `0236` aplicada en producción). El conector de Documentos pasa de
17 a 22 herramientas con los cinco verbos de hilo; la edición de miembros es
incremental (`link`/`unlink_document_ids`) justamente porque el reemplazo total
del panel disuelve el hilo al quedar uno solo, y un caller que reconstruya la
lista de memoria borraría la historia sin querer. Fake data incorpora varios hilos
coherentes, pero el refresh real se omitió por guardia de producción. Verificación
focal: servicios/vistas/serializers/fake/MCP backend verdes; pruebas unitarias del
store, modal, visor y acciones; E2E en cuatro outcomes y cinco viewports;
Django/migración, build Nuxt, guards de diseño y flow-map en verde.

**2026-09-01 — modal de cambio de estado de Proyectos ordenado:** el aviso
amarillo sobre catálogo/contexto se conserva bajo el encabezado; estado destino,
decisión por ingreso y nota muestran su requisito rojo junto al control y lo
limpian al corregirse. Revisar consecuencias queda después del estado y antes
del impacto; los errores remotos permanecen con la acción correspondiente. La
fila sticky final contiene sólo Cancelar y Confirmar cambio. No cambia backend,
API, payload ni esquema. Verificación: 4 unitarias, 7 E2E del flujo y 5
viewports responsive en verde; design tokens/disabled controls pasan y el flow
audit declara display, success, error y failure cubiertos sin `junk-only`.

**2026-09-01 — calendario de cobros y pagos listo para integrar:** el comportamiento
vigente conserva un digest interno diario con hitos 15/7/día para ingresos y
recurrentes; hosting mantiene su cadencia previa de 15/7 y cada 5 días. Los
recordatorios de ingresos vencidos continúan semanales o quincenales hasta
liquidar o pausar. El flujo de ingresos permite silencio indefinido, con fecha y
reactivación, visible en la fila; cuentas de cobro mantiene separado cualquier
contacto al cliente. La aceptación cubre las cuatro clases E2E, contenido y
destinatarios del correo, targets por registro y la regla de no avanzar cadencia
ante fallo. El nombre del cliente ahora usa el helper canónico y una carga
relacional explícita. Sin migraciones ni historial nuevo de ciclos recurrentes.
Verificación focal: 24 pytest, 35 unitarias y 6 escenarios Playwright sin
retries; flow audit completo para las cuatro clases, quality gate sin errores
nuevos y auditoría final con 0 tests basura.

**2026-09-01 — pasada retroactiva cliente/proyecto ejecutada en producción:**
antes de escribir se generó el respaldo
`/var/backups/projectapp/2026-09-01-122433.sql` y su archivo de medios
`/var/backups/projectapp/2026-09-01-122437.tar`. El dry-run de
`link_records_single_project` encontró 102 de 117 ingresos asignables, 0 de 0
hostings y 0 de 11 documentos; los otros 15 ingresos y 11 documentos pertenecen
a clientes sin proyecto activo y permanecen como vacíos válidos y visibles. La
aplicación vinculó exactamente esos 102 ingresos y la segunda corrida encontró
0 filas asignables. Los ingresos 217/218 y las cuentas PA-DEIVISRI-001/002 ahora
leen el proyecto Vástago (`Project.id=10`); no quedan cruces cliente/proyecto
inconsistentes. Se registraron 102 auditorías de sistema, una por ingreso, y el
digest de los documentos emitidos muestreados permaneció idéntico. La pasada no
requirió cambios de API ni esquema. El cierre QA corrigió tres estados SPA que
todavía podían quedar viejos: `assign-unlinked` reconstruye también una cuenta
de cobro abierta, renombrar el proyecto actualiza las cuatro listas cargadas y
la cascada de cliente espera los refrescos de hostings, ingresos, cuentas draft
y documentos antes de resolver. Verificación focal: 29 pruebas backend, 31
unitarias frontend y 9 escenarios E2E verdes, además de lectura directa de los
serializers y salud de los tres servicios de producción.

**2026-09-01 — aceptación de enlaces entre Proyectos y Plataforma estabilizada:**
la auditoría confirmó que el mismo `Project.id` enlaza panel y plataforma, que
el puente abre el espacio en otra pestaña, que la vuelta comercial es exclusiva
de administradores y que hosting, ingreso y cuenta de cobro ya exponen la misma
acción. No fue necesario cambiar producto, API ni esquema. La aceptación E2E
ahora espera el montaje real de Nuxt, calienta con autenticación las rutas
localizadas críticas y prueba funcionalmente las tres referencias contables.
Verificación: los 3 casos antes inestables pasaron dos veces, los 3 casos nuevos
pasaron dos veces, la regresión completa de 10 casos quedó verde y el último
slice de 4 casos confirmó las aserciones explícitas. Quality gate focal:
93/100, cero errores y sin deuda nueva.

**2026-09-01 — reacción caricaturesca de iconos interactivos implementada:** el
primitive transversal conserva el contrato de activación/proceso/resultado y
reemplaza el halo por un salto contenido de 420 ms: el glifo presiona 1 px,
asciende como máximo 3 px al 108%, aterriza y vuelve a reposo. El movimiento
queda aislado de los transforms de cada consumidor y se reinicia ante clics
consecutivos; el foco visible se reserva al teclado. `prefers-reduced-motion`
usa un cambio estático de contraste. Copiar conserva sus estados reales: tras
éxito muestra temporalmente check + “Copiado”, mientras un fallo mantiene el
icono de copiar disponible para reintento. No añade toasts genéricos ni altera
loading. Verificación focal: 19 pruebas unitarias, 3 escenarios Playwright sin
reintentos, build Nuxt y tres guards estáticos en verde. El mapa E2E quedó
regenerado y fresco; su auditoría acredita success, failure y display para el
flujo transversal sin `junk-only`.

**2026-09-01 — acciones del catálogo de estados de Proyectos organizadas:**
cada estado activo separa la edición de la conservación del catálogo en dos
bandas legibles. Nombre, color, efecto operativo, orden y Guardar comparten una
grilla proporcionada; debajo, el destino de fusión, Fusionar y Retirar mantienen
anchos coherentes y al menos 8 px de separación. En celular las acciones ocupan
todo el ancho, en tableta vertical Guardar completa su fila y en anchos
expandidos los botones conservan la misma proporción. El catálogo de Documentos,
la API, el esquema y los mensajes inline de PA-120 no cambian. Verificación
focal: 12 unitarias, 5 escenarios responsive (412/835/1195/1440/2560 px), 3
regresiones E2E de Guardar/Fusionar/Retirar, design-token guard y build Nuxt en
verde.

**2026-09-01 — acción Archivar de Clientes alineada y verificada:** el control
de cada fila en `/panel/clients` usa las acciones canónicas `archive`/`restore`
y muestra **Archivar** o **Desarchivar** en su ayuda visible. La acción conserva
el flujo existente de vista previa, confirmación, cascada y filtro Archivados;
no cambia API, modelo ni migraciones. **Desactivar acceso** en `/platform/clients`
permanece intacto porque controla acceso a la plataforma, no el archivo del
cliente. Verificación focal: 2 unitarias, 4 escenarios E2E y el guard de acciones
del panel en verde.
**2026-09-01 — follow-up de Módulos adicionales listo para integrar:** todas las
rutas públicas del catálogo omiten el Navbar global. El panel prepara URL, PDF
completo, enlace seleccionado y PDF personalizado en español por defecto, sin
quitar el selector ES/EN. `is_staff_session` unifica la exclusión de aperturas
internas en módulos adicionales, propuestas —vista principal, enlaces
secundarios e interacciones— y diagnósticos —visita y secciones—; no crea marcas
alternas ni modifica aperturas históricas. Sin sesión iniciada, incluso para el
equipo, la visita cuenta como externa. La indexación permanece canónica
`index`/selecciones `noindex`. Verificación: 14 pytest focales, 12 unitarias, 4
E2E directamente afectados y checks de Django/diseño verdes; sin migraciones.

**2026-08-31 — edición MCP de borradores de Comunicaciones implementada:**
`update_message` corrige asunto, contenido, fecha, respuesta o documentos sobre
el mismo mensaje saliente activo, sin crear otro registro ni enviar por correo o
WhatsApp. El servicio compartido bloquea la fila, conserva identidad/hilo/canal/
dirección/creación, valida cliente y respuesta, y agrega una revisión append-only
con valores anterior/nuevo dentro de la misma transacción. `get_thread` devuelve
de inmediato la versión y revisiones actuales. La migración `content.0231`
incorpora el historial y refresca sólo la descripción del conector, sin tocar
tokens ni activación. Verificación focal: 14 casos de servicio, 19 de integración
MCP y 3 regresiones existentes verdes; Django no reporta problemas, no hay drift
de migraciones y el gate estricto del batch cerró con cero errores. Sólo falta la
confirmación del CI del PR.

**2026-08-31 — validación del catálogo de estados de proyectos lista para
integrar:** crear, editar y fusionar conservan sus acciones disponibles y, tras
el intento, muestran cada requisito junto al control correspondiente mediante
`BaseFormField`; nombre, descripción y efecto operativo identifican su
obligatoriedad. Los errores de serializer se mantienen en el mismo campo y se
limpian al corregirlo. La selección faltante de una fusión sigue este patrón,
mientras la prohibición permanente de fusionar estados semilla permanece como
ayuda accesible del control deshabilitado. El catálogo documental conserva su
comportamiento previo. Verificación: 6 unitarias, 14 escenarios E2E del archivo
afectado, guard de controles, build Nuxt, mapa fresco y auditoría con 0
`junk-only`/0 faltantes.

**2026-08-31 — reacción visible de iconos interactivos lista para integrar:** el
requerimiento transversal cubre controles icon-only ejecutables del panel, la
plataforma y las vistas públicas, incluidas acciones, navegación, apertura y
toggles. El contrato elegido conserva el glifo: una pulsación breve confirma la
activación; las operaciones asíncronas mantienen su loading; y los resultados
que no se explican por sí mismos, especialmente copiar, muestran halo más una
etiqueta temporal visible y accesible. Touch y teclado reciben la misma señal,
`prefers-reduced-motion` conserva color/anillo sin escala y los fallos mantienen
el mensaje accionable existente además del estado visual. La implementación
migra los controles crudos al primitive, añade un guard CI y registra el flow
transversal. Verificación: 27 unitarias focales, dos escenarios Playwright de
éxito/fallo, build Nuxt, 536 SFC válidos y checks estáticos en verde.

**2026-08-31 — Indicadores de Proyectos con paridad visual y responsive:**
`/panel/projects` presenta **Ciclo del proyecto** y **Pendientes operativos**
con la misma tarjeta horizontal de 80 px y la misma grilla de cuatro/cinco
columnas en anchos expandidos. La línea de apoyo operativa queda limitada a una
línea y ya no altera las dimensiones; cada ayuda permanece anclada dentro de su
tarjeta y no activa el filtro o workflow principal. En 412/835 px se conservan
exactamente los dos resúmenes iguales con drawers completos. Verificación: 19
pruebas unitarias, 17 escenarios funcionales y los cinco contratos responsive
de 412/835/1195/1440/2560 px pasan.

**2026-08-31 — acceso rápido de Módulos adicionales listo para integrar:** la
cabecera comercial de `/panel/additional-modules` deja visible y seleccionable
la URL pública canónica, permite copiarla, abrir la experiencia del cliente y
descargar el catálogo completo en PDF con el idioma activo. Desde el mismo lugar
se preparan selecciones con tracking, se personaliza su PDF y se consulta el
historial; administración, categorías y orden quedan como acciones separadas.
El dashboard global repite el acceso en modo compacto y muestra módulos activos,
enlaces seleccionados vigentes, pendientes de apertura y última apertura
histórica. El catálogo canónico se identifica como indexable/sin tracking y los
enlaces seleccionados como `noindex`/con tracking. No hay migración ni precios.
Verificación focal: 2 pytest, 19 unitarias frontend, 3 escenarios Playwright del
flow nuevo, 6 regresiones de compartir/PDF, build, guards y flow audit verdes.

**2026-08-30 — catálogo, archivo y conciliación documental corregidos, listos
para integrar:** Documentos y Comunicaciones enumeran todos los proyectos
canónicos, incluidos los que aún no tienen contenido. En Documentos sólo el
catálogo operativo aparece al entrar; «Ver proyectos no activos» revela Candle
de forma inclusiva y vuelve a Todos al ocultar una selección no operativa.
«Ver archivados» conserva el scope independiente de carpetas/documentos y vive
junto a Carpetas propias. PRUEBA permanece operativo para pruebas. Se
eliminó `Project.document_manager_enabled`; la relación única
`DocumentFolder.managed_project` identifica la raíz canónica y evita que una
carpeta de proyecto se duplique bajo **Carpetas propias**. El manifiesto v5 puede
promover las raíces conocidas de G&M, Vástago, Xpandia, Kore y Tenndalux, crear
las de Mimittos, PRUEBA y Candle y anidar Germán bajo Kore. También asocia de
forma explícita los documentos 1–5/135/157 a Vástago, 154 a Tenndalux y 159 a
G&M; 120 conserva Mimittos. Carlos, Gustavo, Aarón, Littigio, ProjectApp y
Requirement Estimates permanecen propias. Los tooltips de acciones usan una
sola burbuja horizontal y Actualizar recupera el contraste primario. Producción
no fue mutada: tras desplegar se debe respaldar, generar y revisar el plan, y
sólo entonces aplicar el artefacto aprobado.

**2026-08-30 — Configuraciones de Comunicaciones listas para integrar:** el acceso
quedó junto a Nuevo hilo y abre una superficie interna con preferencias personales
de agrupación, orden, tamaño de página, canal inicial, ayuda y ancho. El contrato
se persiste por administrador, migra una sola vez valores locales, mantiene la
precedencia URL/vista guardada y permite restablecer preferencias o pestañas por
separado. Un fallback evita que una falla de preferencias bloquee los hilos y el
guard protege borradores sin guardar. No incluye plantillas, automatizaciones,
proveedores ni cambia el significado del registro manual. Verificación: 15 pytest,
42 unitarias frontend, 13 Playwright, build, checks estáticos y flow audit verdes.

**2026-08-30 — Catálogo de módulos adicionales ampliado y listo para integrar:**
el inventario crece de 18 a 23 módulos con CRM, agendamiento, membresías,
autoservicio del cliente y fidelización/referidos, usando las cinco categorías y
el esquema bilingüe existentes. Panel, catálogo público y enlaces compartidos
permiten cambiar explícitamente entre español e inglés; estos últimos parten del
idioma elegido por el autor. Tarjetas, lista y acordeón comparten el mismo
detalle, y la preferencia se recuerda por separado para panel y público. Los PDF
usan el idioma activo, omiten precios y pueden llevar un destinatario/cliente
opcional desde el panel; el dato se escapa y no se persiste en esa descarga. Los
nueve flows afectados quedan cubiertos en success/display/failure según
corresponde, sin brechas ni `junk-only` del módulo.

**2026-08-30 — Pausado consolidado en Suspendido para Proyectos:** el ciclo
administrable queda con seis estados semilla y una sola detención reversible.
`paused` deja de ser una opción de modelo, efecto operativo, selector, filtro o
fixture. La migración convierte el proyecto existente y cualquier estado
personalizado con ese efecto a Suspendido, repunta sus episodios con un evento de
fusión, conserva la deuda causada y cancela únicamente proyecciones/cobros futuros
todavía abiertos. El despliegue aplicará la migración; no se ejecutó ninguna
escritura sobre producción desde el worktree.

**2026-08-30 — Asunto de Comunicaciones reducido al título:** la tabla y las
tarjetas compactas ya no repiten el cuerpo del último mensaje debajo del título
del hilo. El índice conserva cliente/proyecto, canal, estado, cantidad, fecha y
borradores; el contenido de cada mensaje queda exclusivamente en el detalle. El
DTO, la búsqueda por contenido y el modelo de datos no cambian. La verificación
queda verde con 7 pruebas unitarias, los 13 escenarios E2E de Comunicaciones y
el guard de tokens; el escenario modificado pasó en el primer intento. El mapa
está fresco y la auditoría conserva 0 `junk-only` y 0 faltantes.

**2026-08-29 — Gestor Documental navegable por proyecto o cliente (actualizado
2026-08-30):** Documentos reutiliza el interruptor segmentado de Comunicaciones
sobre la lista lateral y recuerda la elección por cuenta. Ambos modos enumeran
el catálogo completo aunque una entidad todavía tenga cero contenido; los
inventarios separados de carpetas/documentos cuentan todo el subárbol. Los
proyectos operativos se muestran por defecto y los no activos se revelan con un
toggle independiente. La selección filtra
el listado y queda reproducible con `by`, `project` o `client` en la URL.
**Carpetas propias** contiene únicamente raíces que no pertenecen a un proyecto
ni a un cliente y sigue disponible aun cuando fallen las facetas.

**2026-08-29 — Formularios de creación del panel listos para integrar:** Nuevo
proyecto ya se lee como un bloque: nombre, cliente, estado y descripción ocupan
el mismo ancho; En desarrollo aparece seleccionado sin texto contradictorio; la
ayuda del cliente es breve y Crear cliente permanece visible dentro del selector.
Los errores del intento o del API viven bajo su campo, marcan el control y se
limpian al corregirlo; el footer contiene únicamente Cancelar/Guardar. La
convención transversal usa asterisco sólo en obligatorios y elimina
“(opcional)”. `BaseFormField`, controles base y `ClientAutocomplete` llevan el
mismo comportamiento a creación de Clientes, Tareas, Documentos, Contabilidad
y contenido. No hay cambios backend ni de esquema. Las slices unitarias y cuatro
escenarios Playwright pasan; `admin-panel-projects` cubre display/success/error,
el mapa está fresco y la auditoría global informa 0 missing y 0 junk-only.

**2026-08-29 — Filtros prediseñados de Comunicaciones listos para integrar:**
la tira compartida incorpora seis recortes de fábrica, encabezados por
**Borradores pendientes**, con conteos de dataset completo incluso en cero. El
nuevo criterio `reply_status` permite que **Enviados sin respuesta** encuentre
sólo hilos abiertos con una salida enviada sin respuesta no anulada. Los
prediseñados y las vistas propias conviven con origen visible, reordenamiento y
el desborde responsivo de `BaseFilterTabs`; el activo nunca desaparece. La
configuración restablece únicamente orden/visibilidad de fábrica y conserva las
vistas propias, incluso en instalaciones que ya las tenían antes de sembrar los
builtins. REST, MCP y facetas usan un solo query service, y un endpoint acotado
calcula todos los conteos sin contaminarlos con el filtro activo. Pasan 20
pruebas backend, 32 unitarias frontend, los 8 escenarios E2E del flujo P1, el
build Nuxt y la auditoría de 355 flujos (0 missing, 0 junk-only).

**2026-08-29 — Conciliación de carpetas de proyecto (supersedida el
2026-08-30):** el filing automático reutiliza Cuentas de cobro/Propuestas bajo
la única raíz de cada proyecto y retira wrappers legados vacíos. La alerta
técnica de conciliación y el opt-out por proyecto fueron retirados de la UX; el
catálogo completo y el manifiesto v5 descritos al inicio de este archivo son el
contrato vigente. Producción sigue sin mutarse: tras el deploy corresponde
respaldar, generar, revisar y aplicar únicamente el artefacto aprobado.

**2026-08-29 — Píldoras de estado indivisibles en Documentos:** los filtros de
Consultas y Estados conservan icono y texto en una sola línea; cuando falta
espacio, el contenedor reubica la píldora completa en la fila siguiente sin
crear desbordamiento horizontal. Pasa el escenario Playwright responsive a
412 px.

**2026-08-29 — Segundo hotfix MySQL para la recuperación de snapshots:** el
primer hotfix ya llegó a `main`, pero el redeploy volvió a detenerse al entrar a
`content.0223_email_delivery_snapshots`. Django envolvía el `RunPython` de
recuperación en una transacción y MySQL rechaza el `DROP TABLE` de esa rutina
porque su DDL no admite rollback. La excepción ocurrió antes de ejecutar la
limpieza: las tres tablas siguen vacías, `EmailLog.snapshot_id` no tiene
referencias, `0223` continúa sin registrar y Gunicorn/Huey permanecen sanos. El
nuevo hotfix declara únicamente esa operación como `atomic=False` y añade una
regresión que prueba que Django no abre `transaction.atomic()` en un backend de
DDL no transaccional. Producción queda pendiente de merge y de una nueva corrida
de `$deploy-and-check`.

**2026-08-29 — Tracking de propuestas corregido:** el composable ya no cuenta
tiempo ni emite heartbeats mientras la pestaña está oculta. El cierre usa un
único beacon, la visibilidad abre un segmento nuevo y un guard evita POSTs
solapados o borrado de eventos añadidos durante un request lento. El contrato
backend permanece intacto y las 38 pruebas focales pasan.

**2026-08-28 — Catálogo comercial de módulos adicionales listo para integrar:**
los 17 módulos genéricos de PA-09 más Landing Page forman un inventario inicial
de 18, agrupado en cinco categorías administrables e independiente de las
propuestas. El panel cubre CRUD, retiro, reordenamiento, selección, PDF e
historial de aperturas; la experiencia pública reutiliza el mismo índice y
detalle responsivo. El catálogo completo es canónico/indexable, mientras los
enlaces con subconjuntos son revocables, sin vencimiento, `noindex`, con idioma
y selección inmutables, contenido vivo y aperturas únicas por sesión. No se
almacenan ni muestran precios; MCP queda fuera de esta primera versión. Pasan
38 pruebas backend, 10 unitarias y 21 E2E, además de migraciones/checks, gates de
flujos/calidad/responsividad y el build Nuxt de producción.

**2026-08-29 — Comunicaciones alineadas con el Gestor Documental:** el módulo
conserva una sola lista amplia y traslada el detalle del hilo a un modal de
trabajo direccionable por `thread=<id>`. A la izquierda incorpora navegación
ajustable por Proyectos/Clientes, conteos agregados, búsqueda y un corte explícito
**Sin proyecto**; por debajo del perfil landscape la misma navegación usa el
drawer compartido. Los selectores nativos se reemplazaron por filtros buscables
con conteos y selección múltiple; la URL conserva el corte y `SavedFilterTab`
guarda/restaura vistas propias con el nuevo catálogo `communication`. REST y MCP
convergen en `communication_query_service.py`, que aplica OR dentro de cada
dimensión, AND entre dimensiones y correlaciona filtros de mensaje sobre el
mismo registro. El aviso describe sólo el registro manual vigente, se puede
cerrar y reabrir desde ayuda. PA-89 queda cerrado: Comunicaciones ya es un módulo
propio, no una subsección de Documentos. El cierre de aceptación extiende la
búsqueda global al nombre legible del proyecto en el mismo servicio REST/MCP y
registra como outcomes E2E la persistencia del aviso y del ancho de navegación.
Pasan 7 pruebas REST, 15 MCP, las 25 unitarias existentes y los 8 outcomes E2E;
también permanecen verdes los 5 perfiles responsive, build y auditoría de flows.

**2026-08-28 — Historial probatorio de correos listo para integrar:** el gateway
central captura antes del SMTP un snapshot obligatorio con cuerpo, enlaces,
tamaño total y bytes/hash/tipo/tamaño de cada adjunto. Los logs primarios y BCC
comparten evidencia; fallar al archivarla bloquea el envío. `/panel/emails`
distingue captura exacta, adjuntos confirmados en cero y legado parcial/desconocido;
filtra por presencia/tipo, descarga, reutiliza el visor PDF y reenvía desde el
archivo cambiando sólo destinatario. Los Documentos muestran los correos donde
salieron y quedan protegidos de borrado. La migración `content.0225` habilita
`carlos18bp@gmail.com` en las ocho familias de `EmailCopyRecipient`; su BCC se
intenta sólo después del éxito principal y sigue siendo administrable. Backend,
unitarios, build, 7 E2E focales, freshness y flow audit están
verdes; fake-data refresh se omitió por el guardrail absoluto de producción.

**2026-08-28 — Carpetas automáticas de proyecto (actualizado 2026-08-30):** el
gestor asigna a cada proyecto una única raíz protegida que sigue su nombre. La
relación `managed_project` es el marcador canónico; no existe un segundo booleano
de visibilidad. El ciclo de vida sólo agrupa la navegación entre activos y
archivados. La plantilla inicial incluye Cuentas de cobro, Propuestas,
Entregables y QA; todo descendiente hereda proyecto/cliente salvo asociación
explícita. REST, MCP, admin y restricciones de base impiden alterar el primer
nivel automático, mientras borrar el proyecto conserva la jerarquía como carpeta
manual. La adopción histórica se realiza exclusivamente mediante el manifiesto
v5 revisado, con fingerprint, respaldo y snapshot inverso.

**2026-08-28 — Títulos de Documentos legibles con un solo aviso:**
`BaseOverflowText` mide el recorte real y publica el nombre completo mediante un
`BaseTooltip` flotante sólo cuando hace falta; el mismo primitive sirve las
acciones de fila y `BaseButton` ya no agrega un `title` nativo competidor. El
overlay se teletransporta fuera de la tabla, se voltea/limita al viewport y se
reubica con scroll o resize; la medición se repite al terminar de cargar las
fuentes web. **Ver completo/Contraer** conserva la alternativa táctil. El
separador visible y etiquetado usa la capacidad compartida de tabla: Título
usa 240–520 px, persiste por navegador, vuelve a 320 px con doble clic, recibe
espacio de Proyecto→Cliente→Fecha y no comprime Estados/Acciones. El límite de
520 px cubre el inventario productivo consultado (40 nombres, máximo 56
caracteres, 496 px estimados con padding y margen). Verificación focal:
unitarios de primitives/consumidores, 13 escenarios Playwright sin retries,
build Nuxt, guards de acciones y controles, flow-map fresco y auditoría global
sin `junk-only` ni faltantes.

**2026-08-28 — Un solo aviso breve para las acciones del panel:**
`BaseActionButton` separa las dos audiencias del texto: el tooltip visual usa la
etiqueta corta del catálogo (**Acciones**) y el `aria-label` conserva el contexto
de fila (**Acciones de Contrato de Servicios**). El primitive es el único dueño
del aviso, su texto breve usa `white-space: nowrap` y la capa flotante mantiene
el ancho dentro del viewport; los tooltips descriptivos largos conservan el
ajuste multilínea de `BaseTooltip`. `BaseButton` filtra el `title` nativo sin
perder el resto de `aria-*`, `data-*` ni la semántica de enlace.

**2026-08-28 — Catálogo permanente para asignar cliente en masa:** el modal de
Ingresos/Hostings ya no reserva altura para un autocomplete que sólo aparecía al
recibir foco. `ClientAutocomplete` conserva un único motor de consulta,
selección, retry, creación y paginación, pero suma una presentación `catalog` en
flujo; sólo `BulkAssignModal` la activa para cliente y los selectores de proyecto,
documentos e ingreso vinculado siguen usando la capa flotante compartida. La
lista se ve desde la apertura, muestra nombre/empresa/correo, señala correo
faltante y ofrece creación en vacío. Abre A-Z; el encabezado Nombre alterna
A-Z/Z-A y guarda la preferencia en el navegador. El endpoint suma
`order=name|-name` sin cambiar su cuerpo array ni `limit`/`offset`/
`X-Total-Count`. Cinco filas completas y el alcance de cuatro ingresos caben sin
scroll del panel; un catálogo largo desplaza sólo su lista y el perfil 412×915
usa pantalla completa. Pasan los cortes backend/store/componente/modal y tres
escenarios Playwright; el flow-map quedó regenerado con 0 junk-only y 0 missing.

**2026-08-28 — Cuarta tarjeta contextual de requerimientos lista para integrar:**
`functional_requirements` incorpora `cross_cutting_features` después de
`features` en los defaults ES/EN. La tarjeta conserva un contenedor obligatorio
y editable, con siete capacidades iniciales de calidad que el prompt comercial
debe mantener, reescribir, quitar o ampliar según negocio, etapa, audiencia y
alcance; el prompt técnico crea su épica exacta y enlaza cada item retenido.
Diseño Responsive salió de las funcionalidades específicas. La migración `0222`
actualiza configuraciones por defecto y borradores activos, preserva ids y no
toca propuestas históricas. El editor impide borrar el grupo completo, no su
contenido. Backend, unitarios frontend y ambos E2E focales están verdes; el mapa
está fresco y los flows público/admin siguen cubiertos sin junk-only.

**2026-08-28 — Documentos generados se archivan solos:** al emitir una cuenta
de cobro, el backend crea o reutiliza una jerarquía protegida basada en la fecha
de emisión de Bogotá: **Proyectos / {proyecto} / Cuentas de cobro / año / mes**.
La mayoría histórica que aún no tiene proyecto cae de forma permisiva en
**Clientes / {cliente} / Sin proyecto**; si tampoco se puede identificar al
cliente usa **Sin clasificar**. Anular una emitida la mueve bajo **Anuladas** sin
duplicarla, y anular un borrador usa **Sin emitir / Anuladas**. Reintentar el
correo conserva el mismo documento; una sustitución posterior a la anulación
nace como otra cuenta con otro consecutivo. El nombre queda
`fecha · consecutivo · concepto`, el estado visible se deriva del ciclo
comercial y del historial real de correo, y estas cuentas dejan de contaminar
el preset Por clasificar. Las carpetas automáticas tienen `system_key`: el panel,
REST y MCP permiten navegar, pero no renombrar, mover, reordenar, archivar ni
inyectar documentos manuales en ellas.

El alcance transversal incluye propuestas comerciales: cada envío o reenvío
genera primero el PDF, persiste exactamente esos bytes como versión inmutable
`vNN`, adjunta esa misma versión al correo y la archiva por cliente/proyecto,
año y mes. Un fallo de render no cambia el borrador ni envía; un fallo de correo
conserva la versión con señal de corrección. Cuando la aceptación crea el
proyecto, todas las versiones previas se mueven a su rama. En la UI el contenido,
carpeta y estados de estas versiones son de sólo lectura, mientras las
observaciones administrativas siguen editables. La migración `content.0223`
añade identidad de carpeta y origen/archivo de snapshot. Después de migrar,
producción debe previsualizar y luego aplicar
`python manage.py backfill_collection_account_filing --apply`; la orden sólo
toca cuentas sin carpeta y nunca inventa fechas. Verificación focal: 25 pruebas
de servicios/backfill, 16 de API, 3 de onboarding/MCP, 1 contrato de fake data,
13 unitarias y 3 E2E, más regresiones específicas de envío/reenvío y build de
producción.

**2026-08-28 — Indicadores de Proyectos e Ingresos listos para integrar:** un
`BaseIndicatorCard` compartido reserva siempre rótulo, cifra y apoyo, por lo que
la presencia de explicación ya no cambia la altura. Cada tarjeta visible tiene
ayuda y acción explícita. Proyectos ordena los estados no nulos según el ciclo y
separa pendientes operativos; Ingresos conserva cuatro preguntas priorizadas en
ancho expandido. En 412/835 ambos encabezados se convierten en exactamente dos
resúmenes con drawers que preservan estados en cero y el detalle completo. Sus
acciones aplican los filtros existentes y la primera fila permanece en la
pantalla inicial. La cobertura focal incluye unitarios, acciones y geometría en
los cinco anchos canónicos; el flow map queda versionado con el contrato.

**2026-08-28 — Hotfix del fallback SPA listo para integrar:** el panel de
producción seguía respondiendo 200, pero el `200.html` generado tras la
actualización Nuxt/i18n era sólo un meta refresh hacia `/en-us/200.html`; Django
volvía a servir el mismo fallback y el navegador quedaba en un bucle. Nuxt ya no
intenta detectar idioma porque Django decide el locale de `/` con cookie y país.
El chokepoint `build:django` valida ahora que el fallback tenga contenido, monte
`#__nuxt` y no redirija antes del swap atómico. Pasan 4 regresiones Jest, 3 casos
backend, la generación directa y el build completo de publicación. El artefacto
válido mide 8.235 bytes. Falta merge/deploy y sonda productiva para cerrar el
incidente; se registra como deuda una healthcheck de ruta SPA que inspeccione
contenido, no sólo HTTP 200.

**2026-08-28 — Bolsillo legible y operable en celular:** por debajo de 640 px
la vista abandona la tabla de ocho columnas y muestra una tarjeta completa por
movimiento. Una acción inicial de 44 px abre el mismo menú editar/eliminar que
usa la tabla; luego aparecen concepto, valor con signo, vínculo/reparto, fecha,
tipo y saldo corrido como hechos etiquetados. Los chips usan `BaseBadge` y no
parten palabras; el ordenamiento compacto sigue disponible. Con filtros, cada
tarjeta dice **Acumulado filtrado** y suma sólo filas visibles, mientras el saldo
superior permanece como total global. Desde 640 px vuelve la tabla priorizada.
Ingresos y Cuentas de cobro consolidaron también su menú inicial y badges
atómicos en Lista/Agrupada. Evidencia focal PA-103: 13 casos de Bolsillo en
412/835/1195/1440/2560, cuatro casos compactos de los tabs vecinos, una
validación de formulario y 13 unitarios en verde; el recorrido completo 12×5
permanece documentado como pendiente, no como ejecutado.

**2026-08-28 — Actualización secuencial completa de dependencias:** cada cambio
de librería se aisló en su propio commit y sólo avanzó después de cerrar el CI
completo del PR. Backend queda al día con Django 6.1, Faker 40.37, Gunicorn 26.2,
pytest-cov 7.1 y ReportLab 5; Python 3.12 y MySQL 8.4.11 cumplen los mínimos del
framework. La configuración de correo migró a `MAILERS`, el gateway dejó de usar
el argumento deprecado `fail_silently` de Django y conserva explícitamente su
semántica ante fallos SMTP. Frontend queda en Nuxt 4.5.2, Vue 3.5.42, Pinia 4.0.3,
VueUse 14.4, marked 18, Swiper 14, ApexCharts 7 y Vue Test Utils 2.5, con paquetes
sin uso y el setup huérfano de jest-dom eliminados. `pip-audit` y `npm audit`
reportan cero vulnerabilidades. El inventario backend no tiene updates de
aplicación pendientes; Jest/Babel permanecen en la línea compatible con
`@vue/vue3-jest` 29 y `vuedraggable` 4 no se baja al nominal latest 2.24.3 porque
esa es la línea Vue 2. La misma entrega incluye la corrección MySQL de
`DocumentState.system_key`, que elimina `models.W036`.

**2026-08-27 — Listo para merge: ciclo de vida y acciones de Recurrentes:**
`/panel/accounting/recurring` ya usa la columna inicial de PA-102 y un único menú
por fila para editar, duplicar con borrador, activar/desactivar, silenciar avisos
y archivar. Vigentes/Archivados son alcances separados; restaurar siempre deja
inactivo y eliminar definitivamente sólo existe después de archivar. La
selección múltiple aplica activar/desactivar/archivar en una transacción. El
predicado activo + no archivado gobierna total, porcentajes, gráficos, dashboard
y calendario; la interfaz lo explica. REST y seis tools MCP comparten el mismo
servicio auditado. Fake data cubre vigente, inactivo, silenciado y archivado.
Verificación: 34 casos backend enfocados, 62 unitarios frontend y 11 Playwright
en verde; migration/check sin drift, cuatro gates de panel, flow audit y build
Nuxt aprobados. Registrar cobros, crear gastos/movimientos de bolsillo y navegar
su historial quedan expresamente para la historia de origen contable posterior.

**2026-08-27 — Controles cortos atómicos, anchos semánticos y Gestor
Documental:** el barrido previo de 61 modales, 32 consumidores segmentados, 25
badges y 19 filas de formulario confirmó una causa compartida. `BaseButton`,
`BaseBadge`, `BaseSegmented` y `BaseSegmentedMulti` conservan texto, icono y
conteo como una unidad; el grupo puede reorganizarse, pero ninguna opción se
parte. `BaseModal` fija `confirm` 28 rem, `form` 42 rem, `form-wide` 64 rem,
`wizard` 80 rem, `detail` 64 rem y `workspace` hasta 100 rem, manteniendo ancho
disponible completo en pantallas angostas. `BaseFormRow` usa bandas compartidas
de etiqueta/control/error, coloca la ayuda bajo el grupo y
`BaseFormRowAction` centra el botón contra el control. Los casos de Clientes,
cuenta de cobro y Documentos quedaron migrados y probados con `9999`; Playwright
midió 0 px de diferencia entre campo y acción. El rótulo público ya es **Gestor
Documental** en navegación, vista, taxonomía, flujos y conector MCP; la ruta
`/panel/documents`, el slug y los identificadores internos permanecen estables.
La columna de título ya satisfacía consulta completa, tacto, ancho persistido y
restablecimiento, por lo que se conservó como regresión. Inventario:
`docs/audits/2026-08-27-ui-wrap-modal-widths.md`.

**2026-08-27 — Menú de acciones al inicio de todas las tablas kebab:**
Documentos, Propuestas, Diagnósticos e Ingresos (tabla clásica y agrupada) usan
un único orden: Casilla → Acciones → Identidad/Contenido. El encabezado queda
visualmente vacío con nombre accesible, y el track fijo de 56 px no dona ancho
ni participa del reparto de datos. Las celdas de control aíslan clic y clic
auxiliar de la navegación de fila sin bloquear el paneo táctil horizontal. El
contrato vive en `tableLayout.js`, `BaseResponsiveTable` e
`IncomeGroupedTable`; `inline-end` conserva explícitamente las filas con varios
iconos sueltos, incluidas Cuentas de cobro, hasta que exista una decisión previa
de consolidación. Cobertura focal: unitarias del primitive/layout/consumidores y
32 escenarios Playwright focales y de regresión verdes, incluido un gesto táctil
real iniciado sobre el kebab.

**2026-08-27 — Ayuda contextual y séptimo significado en el ciclo de Proyectos:**
el catálogo compartido conserva una sola selección por proyecto y suma **En
evolución** para distinguir el producto entregado que sigue operando mientras se
desarrolla su siguiente versión; comparte deliberadamente el efecto `operating`
con Activo. Cada estado de proyecto exige ahora una descripción administrable y
expone además una explicación del sistema derivada del efecto operativo, que no
puede alterarse al renombrar. Un badge accesible por hover, foco y toque muestra
ambas capas en conteos, filtro seleccionado, tabla, tarjetas compactas, catálogo y
modal de transición. La migración `content.0218_project_state_help` preserva
descripciones existentes, completa las faltantes e inserta En evolución después de
Activo; fake data y contratos MCP reconocen el nuevo campo y los siete significados.
El portal del cliente permanece fuera de alcance.

**2026-08-27 — Selector de clientes útil desde que abre:** la asignación masiva
en Contable enfoca el selector y muestra inmediatamente la primera página del
catálogo, ordenada alfabéticamente; escribir filtra esa lista en vez de ser el
único modo de obtener resultados. El endpoint conserva su array compatible,
añade `limit`/`offset` y publica el total en `X-Total-Count`; el listbox carga
páginas posteriores dentro de su propio scroll. Nombre, empresa, correo y la
falta de correo siguen visibles por fila. Vacío, fallo inicial y fallo de página
tienen salidas explícitas, incluida creación inline desde el modal. El alcance
de la edición masiva permanece visible y el modal no adquiere una segunda barra.
El mismo contrato corrige los consumidores compartidos y el cambio de cliente de
carpetas abre enfocado. Cobertura focal backend/unit, mapa E2E y escenario real
del modal actualizados.

**2026-08-27 — Integridad MySQL de `DocumentState`, refresh operativo y GC:**
`system_key` deja de depender de un `UniqueConstraint` condicional que MySQL
ignoraba. La unicidad simple `(catalog, system_key)` conserva múltiples `NULL`,
bloquea duplicados concretos y elimina `models.W036`; `content.0218` prevalida
duplicados antes del DDL. El contrato MCP no cambia y su suite 19/19 permanece
verde, junto con 4/4 pruebas focales, `sqlmigrate`, check de base y ausencia de
drift. En paralelo, los 13 updates compatibles que explicaban 18 paquetes
outdated se probaron en un venv aislado y se promovieron al productivo: audits y
compatibilidad en cero, Gunicorn/Huey activos. La ola secuencial del 2026-08-28
completó después los majors aplicables del manifiesto. El worktree mergeado
`vuln-audit` fue retirado conservando su rama y un GC con poda
de dos semanas llevó objetos loose 7.003→0 y packs 34→2; `gc.log` desapareció,
los objetos dangling recientes se preservaron y la conectividad/fetch quedaron
limpios. La corrección de esquema permanece en PR hasta integración/despliegue.

**2026-08-27 — Mapa de vistas convertido en un explorador operativo:**
`/panel/views` conserva el inventario completo y el mapa modular, y suma un modo
Explorador orientado al valor del producto. La portada se simplificó a tres
espacios: **Panel interno**, **Plataforma de clientes** y **Experiencias
públicas**. El Panel despliega ocho módulos principales con sus submódulos más
representativos; Plataforma conserva sus ocho capacidades profundas; y el
recorrido público incorpora captación, contenido/prueba social, propuesta y
diagnóstico. Cada interacción muestra propósito, valor operativo, actores,
etapa, relaciones y referencias técnicas de forma contextual: hover/foco sólo
previsualiza y el click fija un `node` compartible. Cada espacio permite recorrido
libre o guiado mediante `tour=<space-id>`; salir conserva el módulo actual. En
412/835 se usan tarjetas y desde 1195 se mantiene la órbita, con pausa automática
durante el tour y soporte de movimiento reducido. No se agregaron métricas vivas,
API ni backend. El validador ahora asigna exactamente una vez las 104 rutas y las
siete secciones técnicas. Cobertura focal: catálogo, composables, componente,
flujo E2E, guards de UI y build Nuxt.

**2026-08-26 — Copias BCC universales de correo listas para integración:** la auditoría
read-only de producción confirmó que `content.0209` está aplicada pero
`ClientEmailCopyRecipient` no tiene filas; por eso
`carlos18bp@gmail.com` registra cero intentos de copia aunque sí existen envíos
primarios posteriores al despliegue. La implementación de esta sesión amplía el
gateway vigente de 23 salidas al cliente a todo correo de plataforma, mantiene
segmentación por familias, deduplica contra destinatarios primarios y centraliza
la traza de principales/copias, incluidos los canales internos y de seguridad.
La migración `content.0213`, el inventario exacto de 56 canales, los 21 casos del
gateway, 9 casos de API global, 10 E2E y el build Nuxt están verdes; el flow-map
queda fresco con cero junk-only, unvalidated o missing. El seguimiento
`content.0225` provisiona a Carlos con las ocho familias durante el despliegue,
sin requerir una alta manual posterior.

**2026-08-26 — Eliminación recuperable de observaciones y cero diálogos nativos
en el panel:** **Descartar** conserva la observación y su motivo opcional;
**Eliminar** limpia cualquier observación pendiente, resuelta o descartada que
nunca debió existir. La eliminación es lógica (`deleted_at/deleted_by`), admite
selección masiva atómica dentro de un documento, sale de listas/conteos y queda
en Papelera. `DocumentNoteEvent` registra actor/fecha sin duplicar contenido. Al
quitar la última pendiente, sólo se cierra el episodio `origin=note`; restaurar
reabre/reutiliza un estado compatible y un conflicto revierte la operación. REST,
panel y las 17 herramientas del MCP Documentos comparten el servicio. El modal
muestra el contenido completo y advierte que correos/mensajes externos no se
borran; incluso en una cuenta emitida los mensajes siguen bloqueados, pero la
limpieza y recuperación de observaciones permanecen disponibles. El barrido de
`/panel` migró 14 `confirm/prompt` alcanzables a modales o
pasos inline, retiró un consumidor huérfano y añadió un guard estático de CI.
Migración `content.0216`; fake data representativa preparada pero no ejecutada
porque este checkout apunta a producción; cobertura focal y flow E2E registrados.

**2026-08-26 — Controles deshabilitados sin bloqueos silenciosos:** el panel
adopta un contrato híbrido: `BaseControlGate` enumera junto al control todos los
prerrequisitos que la persona puede resolver y replica la explicación en
hover/foco/táctil; `disabledReason` cubre límites de posición, estado o permisos,
y los estados transitorios conservan una etiqueta de operación en curso. El
barrido estático pasó de 85 hallazgos accionables a cero y quedó como guard de
CI. En cuentas de cobro, elegir un cliente marcado **Sin correo** avisa antes de
terminar, ofrece guardar explícitamente el correo en el perfil canónico sin
perder el borrador y sólo entonces habilita la previsualización; el gate lista a
la vez cliente, ingreso, valor, concepto, correo, conflicto y fecha fija que
falten. Verificación: 29 Jest focales, dos escenarios Playwright reales, build
Nuxt, flow-map fresco y el flow P1 `admin-accounting-collection-create` cubierto
en display/failure/error/success. Inventario: `docs/audits/disabled-controls-2026-08-26.md`.

**2026-08-26 — Prioridad de columnas del listado de Documentos:** la tabla usa
un contrato fijo y ejecutable Acciones → Título → Estados →
Creado/Fecha/Archivado → Cliente → Proyecto. Estados queda visible como segunda
columna de datos desde
tableta horizontal; Cliente/Proyecto se agrupan bajo Título hasta escritorio y
las tarjetas conservan Título/Estados como prioridad, con metadata Fecha →
Cliente → Proyecto. Acciones permanece al inicio. El orden no se personaliza y
la preferencia existente sólo recuerda el ancho de Título. La contención de
PA-90 y los estados de PA-88 se preservan; Proyecto se reevaluará tras el
backfill de PA-55. Sin cambios de API, backend o esquema.

**2026-08-26 — Cuentas de cobro agrupadas por cliente o proyecto:** el tab
contable alterna entre la tabla clásica y una agrupación de un solo nivel con el
mismo patrón de Ingresos. Los grupos se ordenan por saldo pendiente descendente,
desempatan alfabéticamente y dejan Sin cliente/Sin proyecto al final. Cada
encabezado muestra conteo, emitido, por cobrar, recaudado y anulado, además de
borradores, emitidas, vencidas, pagadas y anuladas; vencida es un subconjunto
temporal de emitida. Proyecto vivo, snapshot histórico y ausencia real se
presentan por separado. El pie resume todo el conjunto filtrado. La vista y el
criterio viven en `AccountingSettings`, se guardan inmediatamente con rollback de
UI si falla el PATCH y también pueden editarse en Configuración. La implementación
reutiliza `IncomeGroupedTable` mediante `AccountingGroupSummaryBand`, centraliza
las reglas en `collectionAccounts.js` y registra el flujo
`admin-accounting-collection-grouping`. Verificación focal: backend 8/8,
frontend unit 16/16 + regresión de Ingresos 5/5, E2E de agrupación/persistencia y
build Nuxt de producción verdes; sin ejecución de fake data por tratarse del host
de producción.

**2026-08-26 — Ingreso vinculado de cuentas de cobro abre en Esperados:**
`CollectionAccountFormModal` usa un punto de partida estable por tipo de ingreso:
al abrir o cambiar de cliente selecciona **Esperados**, conserva el alcance
**Del cliente** y sigue incluyendo esperados con pagos parciales porque no usa
`payment_status` para el recorte. El operador puede cambiar a Todos o Líquidos;
si el resultado esperado del cliente queda vacío, **Ver todos** amplía primero
el tipo sin perder el cliente y sólo amplía el alcance cuando ese cliente no
tiene ningún ingreso elegible. No se persiste la última elección y no cambió la
API ni el esquema.

**2026-08-26 — Resultados buscables de modales sin recorte:** `BaseModal`
expone un root flotante fuera de su panel desplazable y `BaseFloatingListbox`
teleporta allí los resultados, conserva el foco dentro del diálogo, cierra por
Escape/click exterior, se limita al viewport y gira arriba cuando corresponde.
Los selectores compartidos de cliente, proyecto, catálogo de proyectos e ingreso
vinculado ya usan ese contrato en Contable y Documentos. `BulkAssignModal` crece
con el contenido hasta un máximo del viewport: en escritorio muestra cinco
resultados completos y los cuatro registros afectados sin desplazar el modal;
si sobran resultados, sólo se desplaza la lista; en pantalla angosta conserva el
modo full-screen de PA-45. Verificación: unidades focales verdes, cinco flujos
Playwright afectados verdes y asignación masiva verde en los cinco viewports.

**2026-08-26 — Contención transversal de texto y títulos de Documentos:** el
panel dejó de depender de espacios para contener datos. `tableLayout.js` define
`wrap`/`truncate`/`atomic`; `BaseResponsiveTable` y `BaseExploratoryList` aplican
la política a tabla, detalles agrupados y tarjetas, y `BaseBadge` contiene sus
etiquetas. Los strings arbitrarios usan una cadena intrínsecamente segura de
`min-w-0`, ancho acotado y `overflow-wrap:anywhere`; fechas, dinero y números
acotados conservan nowrap. La adopción alcanzó listas representativas de Tasks,
Projects, Clients, Accounting, Emails, Content y MCP. En Documentos, Título usa
una línea con elipsis y el mismo **Ver completo/Contraer** medido para nombres con
o sin espacios; al expandir corta en cualquier punto. Carpeta queda primera en
un renglón inferior, seguida por Cliente/Proyecto/Estado en el perfil compacto;
sin carpeta no se reserva una línea vacía en escritorio. Los nombres reales
`guia_apuntar_dominio_ux_26082026`,
`Levantamiento_Fase_4_Multi-Tenant_24082026` y
`Respuesta_Etapa_3_Inventario` permanecen dentro de fila/tarjeta en los cinco
viewports canónicos. Verificación: slices Jest de primitives y consumidores,
Playwright 11/11, build Nuxt, contrato responsivo 103/13/5, flow-map fresco y
auditoría sin junk-only ni missing.

**2026-08-27 — Ciclo real y administrable para Proyectos (actualizado
2026-08-30):** el catálogo y los
episodios de PA-88 ahora están explícitamente acotados por dominio y sirven también
a `Project`, sin duplicar infraestructura. Se siembran En desarrollo, Activo, En
evolución, Suspendido, Completado y Dado de baja; el nombre, la
descripción y el color se pueden adaptar,
pero `operational_effect` conserva las consecuencias aun después de un renombre.
Suspendido concentra la única detención reversible. Cada cambio exige preview y token contra datos financieros actuales, se aplica en
transacción y deja fecha, actor y nota. Suspender preserva deuda causada y silencia
nuevos cobros/avisos; completar exige cierre limpio; dar de baja cancela futuro y
obliga a decidir saldo por saldo, con nota si se salta Suspendido. No existe avance
automático por tiempo: un hosting fallido sólo genera sugerencia. Los archivados
legados quedan Sin clasificar/Por revisar y bloqueados para automatización monetaria
hasta revisión manual. Panel, plataforma, filtros/conteos, fake data y contrato MCP
ya consumen la misma verdad; los flows P1 de transición/histórico y catálogo cubren
display/success/error/failure sin retries después de esperar hidratación observable.

**2026-08-26 — Dataset representativo, coherente y reproducible para desarrollo:**
`create_fake_data` reconstruye el grafo completo con volumen 60, semilla aislada
por módulo y fecha ancla explícita. El perfil produce 60 clientes/67 proyectos,
un proyecto pesado con 60 requerimientos/entregables/cambios/bugs, contabilidad
con estados y períodos extremos, documentos siempre vinculados a cliente/proyecto
y cuentas de cobro nacidas de su `IncomeRecord`, además de 60 hilos/264 mensajes
y datos de Email, QR, Linktree, LinkedIn y MCP. Cada entrada aplica el guard
positivo `FAKE_DATA_ALLOWED`; producción lo fija en falso, desarrollo usa SQLite,
los passwords son inutilizables por defecto y una falla revierte la transacción
completa. El inventario ejecutable clasifica los 102 modelos concretos para que
todo modelo nuevo entregue su seeder en la misma rama. La corrida integral y las
pruebas focales de volumen, relaciones, distribución, replay, guard y rollback
están verdes: 25/25 en lotes de 20+5, gate focal sin errores y auditoría QA con
los 25 tests en `KEEP`. La integración queda a cargo del PR y su CI, sin ejecutar
la generación contra producción.

**2026-08-26 — Comunicaciones por MCP y revalidación transversal:** PA-89 ya
había resuelto Comunicaciones como dominio propio dentro de `content`, por lo que
el catálogo nuevo se apoya en sus serializers, querysets y
`communication_service.py`: lista y abre hilos, crea hilos obligatoriamente ligados
a un cliente, agrega mensajes con canal/dirección/reply/documentos y registra como
enviado un borrador saliente sin fingir una integración de entrega. El seed `0212`
lo deja desactivado y sin token. La revisión de los ocho conectores previos cerró
drift real en detalle de Blog, cliente/proyecto/estados de Documentos, períodos de
hosting y pagos parciales de Contable, orfandad de Clientes y metadata/copia de
Propuestas y Diagnósticos. `content/mcp/contracts.py` clasifica todos los campos de
los nueve dominios y falla si aparece uno sin decisión; descripciones, schemas,
pruebas focales y `docs/MCP_VALIDATION_RUNBOOK.md` dejan una validación repetible.
La regla operativa queda explícita: todo cambio del modelo revisa su MCP en la misma
entrega. Verificación local: 49/49 casos MCP nuevos y 31/31 regresiones compartidas
verdes, Django sin issues, migraciones sin drift y quality gate focal 91/100 sin
errores ni warnings. El gate global local puntuó 97/100 y quedó pendiente de la
confirmación de CI únicamente porque este worktree backend-only no tiene
`frontend/node_modules` para cargar `@babel/parser`.

**2026-08-26 — Baseline patch/minor de dependencias:** esta primera ola actualizó
diez dependencias directas de frontend y once de backend sin cruzar majors. Sus
audits, build Nuxt, Django check, pytest y regresión focal quedaron verdes. El
virtualenv productivo ya recibió `pip` 26.2.1; la ola secuencial del 2026-08-28
retiró después jest-dom y completó los majors compatibles, tal como registra la
entrada vigente al inicio de este documento.

**2026-08-25 — Estados múltiples, administrables y con episodios para Documentos:**
el módulo dejó de presentar `draft/published` y etiquetas como dos verdades
solapadas. `DocumentStateGroup` separa un ciclo exclusivo de señales aditivas;
el catálogo editable conserva seis semillas con `system_key`, permite creación al
vuelo con sugerencias, renombre/color, incompatibilidades, fusión y retiro con
guardas sobre documentos activos. El estado vigente se deriva de episodios abiertos;
cerrar, quitar, transicionar, fusionar y corregir la fecha efectiva escriben eventos
append-only con actor, fecha/hora, resultado y nota. Lista, galería y edición muestran
ciclo antes de señales, duración viva, overflow y una alerta inequívoca para
Solucionar bug; el modal histórico combina fecha exacta y relativa. Los filtros OR,
por ausencia y cuatro presets responden pendientes/cerrados sin abrir cada documento.
Las observaciones privadas se normalizaron en `DocumentNote` y pueden abrir/cerrar el
episodio needs-fix; un correo manual confirmado ofrece abrir Enviado; el MCP tiene el
mismo contrato. `is_client_visible` desacopla portal y workflow.
`content.0210_document_state_episodes`
convierte Published sólo en visibilidad, expande tags como episodios aditivos de fecha
desconocida, normaliza notas y excluye cuentas de cobro, sin inventar Borrador para el
inventario existente. Verificación focal: 38 backend, 59 Jest y 19 Playwright verdes,
Django check/migration SQL sin drift, build Nuxt y tres flows nuevos cubiertos. El
refresh de fake data se negó correctamente porque este proyecto es producción; no se
aplicó la migración ni se alteraron datos productivos.

**2026-08-25 — iconos de acción del panel unificados:** las 51 páginas bajo `/panel` y sus componentes alcanzables resuelven 84 acciones desde un catálogo Heroicons 24 Outline. Copiar y duplicar, editar y renombrar, cerrar/quitar/eliminar y las flechas de descarga/expansión ya tienen símbolos distintos y estables; el módulo concurrente de Comunicaciones adoptó el catálogo al integrarse. `BaseActionButton` aporta tooltip en hover/foco, nombre accesible y el target táctil compartido de 44 px; el feedback de copiado se anuncia sin cambiar de glifo. El styleguide muestra el inventario completo y un guard de CI revisa 273 archivos contra SVG/emoji locales, Heroicons directos, claves desconocidas y controles icon-only sin etiqueta. El flow-map quedó fresco; auditoría: 261 covered, 39 partial, 0 junk-only, 0 missing y 34 exempt, sin cambio de rutas ni outcomes.

**2026-08-25 — Registro de comunicaciones con clientes:** la decisión
de producto es un módulo Comunicaciones propio que reutiliza el Django app
`content`, clientes, proyectos, Documentos y primitivas del panel sin deformar
`Document` en una conversación. La migración
`content.0210_communications_registry` añade hilos,
mensajes, referencias protegidas y correcciones de fecha; el servicio
transaccional conserva la evidencia entregada, valida canal/dirección/respuestas
y mantiene actividad derivada. `/panel/communications` ofrece filtros, timeline
responsive, borradores, registro manual de enviado/recibido, Respondido derivado,
cierre/reapertura, anulación y corrección de fecha. Clientes, Proyectos y
Documentos enlazan al registro; al cambiar el dueño de un proyecto sus hilos
históricos se desvinculan en vez de cambiar de cliente. Fake data y cobertura
focal backend/unit/E2E acompañan el flujo. El registro manual es la operación
elegida; plantillas, importaciones o integraciones necesitarían requerimientos
independientes. La decisión queda en
`docs/superpowers/specs/2026-08-25-client-communications-registry-design.md`.

**2026-08-25 — Notas de documentos con guardado directo desde el modal:** en
edición, `Guardar cambios` envía un PATCH limitado a asunto, correo, WhatsApp y
notas personalizadas, mantiene el modal abierto ante 4xx/5xx y sólo lo cierra
después de confirmar visualmente `Notas guardadas`. El guard de cambios admite
ahora una baseline parcial, por lo que guardar notas no marca como guardados el
título, Markdown u otros campos todavía pendientes. En creación, donde el
documento aún no existe, la acción se llama `Aplicar al borrador` y advierte
antes y después que todavía falta crear el documento. Renombrar documento,
editar carpeta/etiqueta y cambiar cliente también declaran con precisión su
acción. Verificación: build Nuxt aprobado; 53 unitarias focales verdes más la
regresión puntual del bloqueo durante guardado; escenarios E2E de creación y
edición cubren éxito, error, falla y cambios concurrentes; flow-map fresco
(260 covered, 39 partial, 0 junk-only, 0 missing) y quality gate focal sin
errores (96/100; ocho warnings preexistentes en los specs completos).

**2026-08-25 — Títulos de Documentos legibles y columna ajustable:** la lista
introdujo `BaseOverflowText` para una línea con elipsis final, medición de
recorte y **Ver completo/Contraer**; la misma expansión funciona en las tarjetas
de celular/tableta sin abrir el documento. El contrato vigente desde 2026-08-28
publica un único aviso flotante sólo cuando confirma recorte y vuelve a medir al
finalizar la carga de fuentes. Se evaluó el recorte central y se mantuvo el
final porque la revelación explícita resuelve la identidad sin una segunda regla
visual. Título parte en 320 px y se ajusta entre 240/520 mediante el mismo
`BaseResizeHandle` que ahora usa PA-61; teclado, pointer capture y doble clic
viven en el primitive. `useResizableTableColumns` persiste sólo preferencias no
default, encoge Proyecto→Cliente→Fecha, conserva Estados (224) y Acciones (56),
y deja scroll interno al agotar mínimos. La API genérica quedó
expuesta en `BaseResponsiveTable` y documentada en el styleguide. Sin backend ni
schema. Cobertura focal: primitives/engine/Documentos, flow P2
`admin-document-title-column-resize` con sus cinco resultados Playwright y
registro derivado sincronizado; quality gates focales 100/100 y build Nuxt de
producción aprobada.

**2026-08-25 — Retorno contextual desde la edición de Documentos:** se confirmó
que las cuatro salidas del editor estaban fijadas a la raíz y que el listado sólo
persistía una parte de su contexto. La URL del listado ahora canoniza carpeta,
scope normal/archivado, estados, cliente/proyecto, búsqueda global, orden, vista,
página y foco. Los enlaces de edición llevan un `from` interno validado; todos los
estados del editor vuelven al mismo destino con rótulo contextual, mientras una
entrada directa/externa cae a la raíz localizada. El enlace explícito agrega el id
como foco, recupera la página y enfoca la fila/tarjeta; Back del navegador consume
la ruta original. La búsqueda global ya no destruye el scope que debe restaurarse.
Verificación: 32 unitarias focalizadas, 3 E2E Playwright sin retries y build Nuxt
aprobado. La revisión transversal dejó Propuestas y Diagnósticos como P1, Blog y
Paquetes de horas como P2, y Portfolio/Linktrees como P3, sin ampliar este cambio;
detalle en `docs/audits/2026-08-25-list-detail-return-navigation.md`.

**2026-08-26 — Copias BCC configurables para toda salida de correo:**
`EmailDeliveryGateway` quedó como único dueño de Django mail I/O y ahora exige
que cada clave pertenezca al inventario universal exacto de 56 canales. Ocho
familias cubren propuestas, diagnósticos, documentos/comunicaciones, cuentas de
cobro, contabilidad, plataforma, tareas/operación y seguridad/acceso; por
decisión explícita se incluyen invitaciones, OTP, contraseñas temporales y
recuperación. La lista sigue separada de avisos internos y nace con todas las
familias seleccionadas. Cada primario exitoso dispara sobres BCC independientes;
se deduplican `to`/`cc`/`bcc`, y un lookup o SMTP de copia fallido nunca bloquea
ni reintenta el primario. El gateway crea la traza base de todo correo y el
Historial global filtra por familia/destinatario/estado/fecha, anida copias
enviadas/fallidas/omitidas y permite a cualquier admin ver el cuerpo completo,
incluido seguridad, con advertencia visible. Migración `content.0213`;
inventario y activación en `docs/client-email-copy-inventory.md`. El diagnóstico
read-only de producción confirmó la causa de que Carlos no recibiera: la tabla
de copias estaba vacía. El seguimiento `content.0225` crea o reactiva
`carlos18bp@gmail.com` con las ocho familias y conserva luego su administración
desde Configuración.

**2026-08-22 — Auditoría final responsiva Fase 5 sobre `main`:** las fases 0–4 quedaron integradas antes de iniciar el censo. La revisión triestado corrigió el E2E de Proyectos para sus representaciones fila/tarjeta y segmento/select, eliminó el breakpoint local de Blog edit y dio paridad táctil/teclado a completar tarjeta en Kanban y al avatar de Perfil. El contrato ahora fija también alturas, rechaza breakpoints JS locales del panel y detecta acciones interactivas ocultas sólo por hover; `.testquality.yml` expone al ledger los 12 módulos, breakpoints y viewports exactos. Verificación focal aprobada por QA independiente: contrato 101/12/5, 7/7 unitarias de configuración, Proyectos 5/5, Perfil/Kanban 15/15 y flujos de selector/guardado 2/2. El veredicto permanece amarillo: no hubo acceso a dispositivos físicos; PA-45 conserva overlays locales; el estándar fleet del toolkit está desfasado y el harness/ledger modela los módulos de forma distinta. El informe `docs/audits/2026-08-22-responsive-phase-5-final.md` y las fichas RSP-F5-01…04 registran esos pendientes.

**2026-08-22 — Recurrentes con equivalente mensual COP canónico:** se descartó el patrón de vista desactualizada: el PATCH ya refetcheaba y el valor seguía mal después de recargar porque `cop_equivalent` estaba persistido y el formulario reenviaba el cache anterior. La política queda explícita como **tasa vigente configurada manualmente**. `RecurringPayment.save()` deriva el equivalente desde precio/moneda, `monthly_cop_cost` lo prorratea con la frecuencia y `AccountingSettings.save()` resincroniza todos los USD cuando cambia la tasa; serializers, MCP, fake data e importación dejaron de aceptarlo como entrada. La migración `0208` barre COP y USD históricos. En producción, la auditoría read-only encontró un único desalineado: Chat-GPT a USD 200 conservaba COP 80.000 en vez de COP 800.000; el costo activo general estaba COP 720.000 por debajo y la categoría Suscripciones de IA también. El modal ahora enseña una previsualización de equivalente/costo mensual de solo lectura y la página reconstruye fila, subtotal y total general tras guardar. Verificación: 27 pytest, 31 unitarias frontend y 3 E2E sin retries; Django check/migraciones sin drift, tokens limpios, build Nuxt aprobado, flow-map fresh (`admin-accounting-recurring` cubierto; global 257 covered, 39 partial, 0 junk-only, 0 missing) y quality gate file-scoped aprobado sin errores. Despliegue y aplicación de la migración siguen pendientes del flujo de integración.

**2026-08-22 — Plan responsivo Fase 3 (Documentos, Clientes y Proyectos):** los tres módulos comparten ya un contrato explícito para 412×915, 835×1195, 1195×835, 1440×900 y 2560×1440. Documentos mueve el árbol de carpetas a un drawer táctil en teléfono/tableta vertical, fuerza galería en compacto, agrupa columnas secundarias antes de `panel-desktop` y conserva modo archivado/acciones. Clientes deja sólo búsqueda + resumen antes de la primera ficha compacta; el drawer único ordena estado→módulo→subfiltro→avanzados→configuración, las filas y detalles se vuelven tarjetas y mover propuestas/diagnósticos tiene alternativa táctil. Proyectos usa tarjetas 1/2 columnas y sort explícito en compacto, disclosure de KPI secundarios en teléfono, tabla desde 1195 px y modales full-screen con footer sticky; el cambio guiado de cliente apila impacto y decisión. `BaseDrawer` centraliza backdrop, Escape, focus trap y scroll lock; los tres topes de página usan 1400 px. Verificación final tras integrar las fundaciones: 16 unitarias focalizadas verdes, matriz E2E 15/15 por navegación real sin desborde, build Nuxt, flow registry sincronizado y auditor global con los tres flows `covered` (257 covered, 39 partial, 0 junk-only, 0 missing).

**2026-08-22 — Plan responsivo PA-75 → fase 4 cerrado:** las 101 páginas Nuxt tienen dueño dentro de 12 módulos y un guion repetible en los cinco viewports canónicos (412/835/1195/1440/2560 px). Comercial, Emails, Canvas de Documentos, Dashboard, Contenido, MCP y las superficies públicas adoptan los mismos breakpoints, shell, modales, navegación y acciones; las listas CRUD exploratorias usan `BaseExploratoryList`, mientras propuestas y diagnósticos conservan comparación tabular mediante `BaseResponsiveTable` con prioridad de negocio explícita. `responsiveAcceptance.js` es el registro ejecutable, el workflow corre módulos afectados por PR y la matriz completa cada mes, y febrero/agosto abren la revisión del estándar. Verificación final: matrices emuladas de los 12 módulos durante la implementación, 10/10 E2E post-merge de Fundamentos/Documentos en cinco anchos, 64 unitarias focales, build Nuxt, contrato 101/12/5, catálogo 101/101 sin hallazgos y flow-map fresco (257 covered, 39 partial, 0 junk-only, 0 missing). No hubo cambios backend ni de esquema.

**2026-08-22 — Fase 2 del plan responsivo implementada en Contabilidad:** los doce tabs usan el shell y la navegación compartidos; tabs y filtros guardados pasan a selectores por debajo de 1024 px. Cada tabla declara su prioridad de negocio y los indicadores enseñan hasta tres cifras principales con detalle secundario desplegable. Las vistas agrupadas apilan cliente y totales; las tablas especiales tienen representación compacta propia; los modales largos declaran tipo semántico y las acciones densas de cuentas de cobro/hostings convergen en un menú táctil. Bolsillo conserva el saldo corrido debajo del valor en angosto y recupera su columna independiente en horizontal. El guion `docs/ACCOUNTING_RESPONSIVE_TEST_SCRIPT.md` registra la matriz repetible de 12 tabs × 5 anchos y seis flujos largos. Verificación local con API simulada: 5/5 perfiles Playwright, sin desborde y tope de 1400 px; flow-map fresh y auditoría global 257 covered, 39 partial, 0 junk-only, 0 missing. Producción permaneció intacta.

**2026-08-22 — Fases 0–1 del plan responsive del panel:** quedó escrito el estándar y el inventario priorizado por módulo para los cinco viewports canónicos (412/835/1195/1440/2560 px), con tableta vertical como perfil propio y un máximo de contenido de 1400 px. `config/responsive.js` alimenta Tailwind y Playwright; los aliases `panel-*` evitan confundir ancho con orientación. La capa compartida incorpora tabla con política explícita `keep/group/hide` por columna, tabs y filtros que pasan a selector, cuatro tipos de modal full-screen en móvil, formularios con apilado previsible, shell/navegación unificados, menús de fila, barra bulk, escala tipográfica y targets táctiles. `AccountingTable`, `BaseTabs` y `ProposalFilterTabs` siguen funcionando como aliases de compatibilidad. El styleguide documenta ejemplos ejecutables y su flow `admin-styleguide` cubre los cinco perfiles; las fases por módulo quedan limitadas a adopción y retiro gradual de variantes locales. Verificación: slices unitarios de los primitives y consumidores compatibles, build Nuxt, 8/8 E2E del styleguide, CSS compilado con queries de ancho 640/1024/1280/1920, registry/flow-sync fresh y auditoría global con 257 covered, 39 partial, 0 junk-only y 0 missing.

**2026-08-22 — Fase 0 del plan responsivo cerrada:** `docs/RESPONSIVE_STANDARD.md` fija los cinco viewports canónicos (412, 835, 1195, 1440 y 2560 px), los modos compacto/intermedio/ancho, máximo general de 1400 px y máximo de 1600 px para workspaces. El censo cubrió las 50 páginas Vue de `/panel`: 47 superficies renderizables y 3 redirects; consolidó 16 hallazgos (1 P0, 11 P1, 4 P2) con trazabilidad por ruta y patrón canónico para shell, tablas, tabs/filtros, modales, formularios, acciones, bulk bars y layouts multipanel. PA-45 y PA-61 quedan dentro de las fases 1/3; PA-66 conserva su solución y comparte el ajuste de tableta vertical; PA-73 se adelanta dentro de un único PR transversal junto con shell y controles densos. No se modificó código de producto. La auditoría visual local usó APIs simuladas en los cinco viewports; producción respondió 200 y permaneció intacta.

**2026-08-22 — Fase 1 del plan responsivo implementada sobre el estándar:** `config/responsive.js` alimenta Tailwind y los aliases `panel-*` evitan confundir ancho con orientación. La capa compartida incorpora tabla con política explícita `keep/group/hide` por columna, tabs y filtros que pasan a selector, cuatro tipos semánticos de modal, formularios con apilado previsible, shell/navegación unificados, menús de fila, barra bulk, escala tipográfica y targets táctiles. `AccountingTable`, `BaseTabs` y `ProposalFilterTabs` siguen funcionando como aliases de compatibilidad. El styleguide documenta ejemplos ejecutables y su flow `admin-styleguide` cubre los cinco perfiles; las fases por módulo quedan limitadas a adopción y retiro gradual de variantes locales. Verificación: slices unitarios de los primitives y consumidores compatibles, build Nuxt, 8/8 E2E del styleguide, registry/flow-sync fresh y auditoría global con 257 covered, 39 partial, 0 junk-only y 0 missing.

**2026-08-21 — Encabezado simplificado de “Contrato y condiciones”:** el modo legal público ya no duplica la descarga del PDF en su introducción: se retiró el CTA superior “Descargar borrador” y permanecen las acciones flotantes de compartir y descargar. La descripción dejó de estar limitada a `max-w-3xl` y ahora usa el mismo ancho `max-w-5xl` del índice de cláusulas; el componente dejó de recibir el UUID que solo alimentaba el enlace eliminado. Endpoints y contenido contractual no cambiaron. Verificación: 10 unitarias, 7 E2E, build Nuxt y flow-map fresh; la prueba responsive fija una proporción mínima de 98% entre los anchos de descripción e índice a 1366 px, y la descarga flotante conserva el PDF `BORRADOR`.

**2026-08-21 — Notas personalizables privadas en documentos:** el modal administrativo pasó de “Nota para el cliente” a “Notas” y conserva asunto, correo y WhatsApp junto a una colección ordenada de notas adicionales, cada una con título y textarea. Todos los contenidos tienen una acción compacta 📋 que cambia a ✅ al copiar; las cuentas de cobro emitidas siguen siendo solo lectura pero permiten copiar. La API interna y el MCP comparten validación para exigir título/contenido no vacíos y limitar el título a 255 caracteres. Duplicar limpia toda la colección; PDF, listados y portal cliente no la exponen. El generador de fake data incluye ejemplos deterministas sin ejecutarse en producción. Verificación focalizada: Django check y migraciones sin drift, 15 pytest, 10 unit del modal, 9 E2E de creación/edición, build Nuxt y flow-map fresh; auditoría global: 257 covered, 39 partial, 0 junk-only y 0 missing.

**2026-08-21 — Acciones compactas para la nota privada de documentos:** los formularios de crear y editar documentos sustituyen “Agregar nota” por 📝 y “Editar nota” por ✏️ sin cambiar el modal ni la persistencia. Los botones conservan nombres accesibles y ayudas `title`; las cuentas de cobro emitidas mantienen la acción textual “Ver nota”. Verificación: 23 E2E verdes entre ambos formularios, build Nuxt aprobado y flow-map fresh; los tests fijan los dos estados visuales, sus nombres accesibles y el estado de solo lectura.

**2026-08-21 — Refinamiento responsive y editorial de propuestas:** `FinalNote` conserva sus dos columnas solo desde `xl`, amplía el ancho útil y reduce padding interno; a 1366 px cada columna supera 520 px. La lista de pagos usa 672 px disponibles y reserva una línea indivisible para importes como `$112.000.000 COP + IVA`. Los prompts comercial y `_seller_prompt` enumeran los 14 campos introductorios que deben llevar uno o dos fragmentos `<b>` seguros. La migración reversible `content/0206` normaliza únicamente el borrador `ramon-emiliani` mediante reemplazos exactos, sin reescribir otras propuestas ni ediciones posteriores. El contrato público se presenta dentro de una hoja accesible con borde, sombra y segunda capa decorativa usando tokens semánticos. Verificación: 18 pytest, 21 unit, 14 E2E, Django check, migraciones sin drift, build Nuxt y flow-map fresh (257 covered, 39 partial, 0 junk-only, 0 missing).

**2026-08-21 — Grafo de migraciones `content` reunificado:** el deploy de `main` se detuvo antes del build y de los reinicios porque las features de condiciones contractuales y nota privada de documentos habían aterrizado con dos hojas `0204`, ambas dependientes de `0203_hosting_nine_month_terms`. La migración vacía `0205_merge_contract_terms_and_client_communication` depende de ambas ramas y restaura una única hoja sin renombrar ni re-parentar migraciones ya mergeadas. El fix no toca datos ni esquema; el runtime anterior permaneció activo durante el deploy abortado.

**2026-08-21 — Nota privada para comunicaciones de documentos:** `Document` ya guarda asunto, cuerpo de correo y mensaje de WhatsApp opcionales como metadata administrativa. Creación y edición los presentan juntos en un modal compacto con copia individual; serializers internos y el conector MCP permiten crearlos, leerlos, actualizarlos y limpiarlos, mientras markdown, PDF, listados y portal del cliente los excluyen. Duplicar un documento limpia la nota para impedir mensajes obsoletos. El flujo compartido `client-report` genera y persiste los tres textos en todo reporte nuevo o actualizado después de la confirmación del operador; `client-message` reutiliza exactamente ese mismo par cuando encadena el reporte. Verificación focalizada: 39 pytest de serializers/vistas/MCP y privacidad, 5 unit del modal, 7 E2E de la nota (creación/edición en display/success/error/failure), Django check, migración sin drift y flows `admin-document-create`/`admin-document-edit` cubiertos.

**2026-08-21 — Refinamiento de propuesta Aerocivil/Ramon y reglas reusables:** el borrador comercial 115 quedó recalibrado después de la reunión a **$280.000.000 COP + IVA**, hosting en cero, pagos 40/30/30, ocho semanas aceleradas y garantía contractual de un año. El total persistido, el KPI de resumen y las cuotas de $112M/$84M/$84M declaran expresamente `+ IVA`; una regla reusable conserva ese sufijo en inversión, resumen y cierre incluso cuando el frontend recalcula montos, sin duplicarlo si ya existe. El producto es un visor web público y responsive: no incluye cuentas, autenticación, roles, administración, PWA, analítica, reportes ni módulos adicionales; Airavata/Aerocivil suministra staging y producción. Las integraciones dejaron de expresarse como “ocho productos” abiertos: ahora son **máximo ocho cupos fuente-producto**, cada uno cerrado por fuente, producto, nivel o variante, cobertura Colombia, una presentación, autenticación y uno de los formatos preparados admitidos. El levantamiento concreta esa matriz sin ampliar el perímetro, y toda ampliación exige control de cambio escrito. El alcance mantiene 37 items comerciales —7 vistas, 14 componentes y 16 capacidades— enlazados al 100% con **85 requerimientos verificables** —17/30/38— y al menos dos requerimientos por item; los comportamientos ambiguos de huecos temporales, fallback, responsive, caché y rendimiento se sustituyeron por reglas únicas de aceptación. El modelo técnico conserva 11 entidades para fuentes, ingestión, versionado, último dato válido, caché, salud y retención. El borrador permanece sin enviar y con automatizaciones pausadas; la API pública devuelve el precio y alcance nuevos, y los PDF comercial/técnico se generaron en 21 páginas cada uno sin precio anterior, hosting ni catálogo adicional. En la presentación reusable, `FinalNote` reparte nota/compromisos y kickoff en dos columnas, guarda los insumos de arranque en un `<details>` cerrado y mueve CTA/contactos al `ProposalClosing`; las introducciones aceptan negrillas seguras y usan el ancho del contenido. `ProposalSummary` no inventa analítica, `TechnicalDocumentEditor` exige trazabilidad y los prompts favorecen historias de 1–3 puntos. Build Nuxt, 35 pruebas unitarias focales y 2 E2E nuevos aprobados en la implementación reusable; la validación final del contenido incluyó dry-run transaccional, verificación ORM/API, render PDF y recorrido Playwright sin errores de consola.

**2026-08-21 — Cuarto modo “Contrato y condiciones” en propuestas:** las propuestas activas en español muestran, por defecto, un cuarto acceso en el gateway público. No es una sección ni cambia el prompt/JSON: `BusinessProposal.show_contract_terms` es metadato top-level, configurable desde creación (manual o JSON) y edición, con rollback visual si el PATCH falla; en inglés queda indisponible. El frontend carga bajo demanda dos paneles sintéticos: apertura con explicación/aviso/índice y un único documento vertical con anchors `clause-NN`. `ContractTermsService` toma exclusivamente el `ContractTemplate` global vigente, reutiliza el enmascarado de draft y separa cada H2; los endpoints públicos `contract-terms/` y `contract/draft-pdf/` aplican los mismos gates, `Cache-Control: no-store`, y el PDF fuerza template global, datos `XXX-XXX-XXX`, ausencia de firma e incluye marca `BORRADOR`, aunque la propuesta tenga contrato personalizado. Tracking/analytics aceptan `legal` y guardan la cláusula en `subsection_key`. Migración `content/0204`; build Nuxt, system check, slices backend/unit y 9 recorridos E2E focalizados verificados. Flujos nuevos: `proposal-contract-terms`, `proposal-contract-draft-download`, `admin-proposal-contract-terms-visibility`.

**2026-08-20 — Skill local para crear propuestas comerciales:** `proposal-create` quedó disponible en los ecosistemas Codex y Claude con una única metodología: extrae el brief, pregunta hasta cerrar decisiones de hosting/ROI/módulos/pagos/visibilidad, exporta las 18 secciones desde `ProposalService.get_default_sections()`, genera JSON + manifiesto, audita shape, precio efectivo y trazabilidad comercial↔técnica, y solo crea un borrador después de una segunda aprobación. El creador reutiliza `ProposalFromJSONSerializer` + `build_proposal_from_json`, exige `--apply --confirm CREATE_DRAFT`, bloquea duplicados no autorizados, deja `status=draft`, `automations_paused=true` y registra `calc_confirmed` aun con selección vacía para impedir que reaparezcan defaults. Nueve pruebas unitarias, exportación Django de plantilla y validación con el serializer real aprobadas; no se creó ninguna propuesta durante la implementación.

**2026-08-20 — Hosting comercial cada 9/6/3 meses:** la oferta nueva ya no incluye anual ni mensual: usa `nine_month` (Cada 9 meses / Every 9 months, 40%), semestral (20%) y trimestral (10%). El cambio atraviesa creación/edición/defaults de propuestas, vista pública, PDF, snapshots y suscripciones de plataforma, módulo contable, MCP, fake data y flows E2E. La frontera histórica queda explícita: propuestas cerradas o inactivas, suscripciones canceladas/archivadas, hostings inactivos y ciclos/pagos ya realizados conservan anual/mensual con etiqueta “histórico”; los registros operativos actuales se convierten y los cobros pendientes seguros se recalculan. La migración de plataforma aborta si encuentra un pago en procesamiento o enlazado a Wompi. Build Nuxt, migraciones, slices backend/frontend, E2E y flow-registry verificados.

**2026-08-19 — Hardening de dependencias, MySQL y bundles:** las auditorías pasaron de 24 vulnerabilidades npm y 88 asociaciones de avisos Python a **0/0** mediante updates directos y transitivos, incluidos los majors necesarios de Pillow, cryptography, pytest y pypdf. Los cinco constraints condicionales que MySQL ignoraba ahora son índices únicos funcionales con `NULLIF(campo, '')`, precedidos por una migración que detecta duplicados antes de crear los índices. Los helpers de estado con autoimports ambiguos recibieron nombres por dominio. ApexCharts pasó de plugin global a `LazyApexChart` client-only con imports modulares y chunks exclusivos del cliente; el máximo final bajó de ~1.18 MB a 448,634 bytes y el build quedó sin los warnings objetivo. El smoke del primer deploy descubrió payloads Nuxt servidos como HTML bajo el CDN estático; el hotfix desactiva `payloadExtraction` para mantenerlos inline y ejecuta `collectstatic --clear` tanto en deploy como en rebuilds del blog. El build Django real termina con cero `_payload.json`, y la navegación read-only home → portfolio no realiza requests de payload. Verificación focalizada: 32 pruebas backend, 37 unitarias frontend y 3 E2E de canvas reales, todas aprobadas.

**2026-08-19 — Arranque concurrente de conectores MCP:** `McpEndpointThrottle` ya no comparte una sola cuota por IP entre todos los conectores. La cache key es `IP + slug registrado`, de modo que blog, documentos, propuestas, contabilidad y LinkedIn pueden inicializarse en paralelo sin hacerse 429 entre sí. Los slugs desconocidos comparten deliberadamente el bucket `unknown`, evitando que inventar rutas permita evadir el límite. La regresión cubre tanto el aislamiento entre conectores válidos como la protección de rutas inventadas. El despliegue de runtime sigue siendo manual mediante `$deploy-and-check`.

**2026-08-17 — Abono multi-ingreso (bulk settle) en rama `feat/17082026-bulk-settle-abono`:** un pago del cliente que cubre varios esperados se registra con UN `PocketMovement` + N hijos liquid compartiéndolo (`IncomeRecord.pocket_movement` OneToOne→FK, migración `content/0202` — **validar en staging MySQL antes de prod**: el drop del unique que respalda el FK no lo detecta el SQLite de dev). Endpoint `POST accounting/incomes/bulk-settle/`; acción "Registrar abono" en la barra bulk de Ingresos con modal de reparto editable (más antiguo primero); excedente = saldo a favor (hijo liquid sin padre, se aplica re-apuntando `expected_income`); reversa = borrar el movimiento (cascadea todos los hijos); hijos compartidos con monto/destino/kind bloqueados. Flow E2E nuevo `admin-accounting-income-bulk-settle` (7 specs, 4 outcomes, covered). **Gastos: evaluado y descartado para v1 (2026-08-18).** El caso equivalente existe —una sola transferencia que paga varias obligaciones— pero el espejo no: `ExpenseRecord` **no tiene `kind`**, así que no hay noción de gasto esperado contra la cual imputar, ni pagos parciales, ni `payment_status` (`payment_status_for` es income-only y `_paid()` devuelve `None` para lo que no es esperado). Un gasto se registra ya pagado: `register_in_pocket=True` y `_sync_pocket` espeja UN movimiento 1:1; sus endpoints son CRUD puro, sin settle ni bulk. Lo más parecido a un esperado es `RecurringPayment`, un catálogo sin registros de pago. Construirlo costaría: inventar el gasto esperado + self-FK, migrar `ExpenseRecord.pocket_movement` de OneToOne a FK (espejo de la `0202`, con la misma advertencia de MySQL), re-derivar `linked_record`/`is_auto_managed`/`attribution` y sus dos espejos SQL —`attribution` es el duro: con N hijos de gasto el split de socios queda ambiguo justo donde el lado ingresos es unánime por construcción—, más endpoint, guards, reversa, UI y flow E2E nuevos. Es #212 otra vez MÁS el sustrato que #212 heredó gratis. **Defecto real que sí queda anotado:** hoy una transferencia que paga tres suscripciones produce tres movimientos OUT donde el extracto muestra uno — el saldo es correcto, la forma del ledger no. **Primer paso barato si llega a doler:** permitir que un gasto se cuelgue de un movimiento existente (sólo OneToOne→FK, sin `kind` ni bulk) — N gastos, un movimiento, reconciliación read-only. **Disparador para reabrir:** que se empiecen a registrar gastos esperados (que `RecurringPayment` genere registros de pago); ahí el sustrato ya existe y el espejo completo se vuelve barato.

ProjectApp is in **production** at projectapp.co. No long-lived active branch: work lands on short-lived `fix|feat/DDMMYYYY-*` branches off `main` (as of 2026-08-16 the open one is `feat/16082026-documents-clients-module`). **Round 9 COMPLETE — every junk-only E2E flow now genuinely interacts + asserts** (the rewrite work Round 8's audit deferred): **covered 189→261, junk-only 72→0**; closed ALL modules (P1, layout, public, platform, proposal, and the full admin module: portfolio/accounting/blog/proposal-admin/diagnostic-misc). Each spec left gate-0/0 (strict) and dev-server-verified across ~15 coverage commits; the final admin batch was parallelized across 3 `qa-engineer-e2e` subagents. Fix pattern: a real interaction + a gate-recognized state-change assertion (`.not.`/`toContainText`/`toHaveURL`/`toHaveValue`/`toHaveCount`/`toEqual`), or a documented `allow-no-interaction`/`allow-render-only`/`allow-fragile-selector` + concrete data assertion for genuine display/redirect/SEO/contract cases. Out of scope: **38 `missing` flows** (never had any test — a separate backlog). This follows **Round 8, the first-ever `test-audit`**: a whole-corpus junk inventory (301 no-interaction E2E, 168 flow-tag-mismatch, 164 weak-assertion, 147 `duplicate_coverage`, 72 junk-only flows) whose two approved safe-cleanup batches (delete no-subject, merge exact duplicates) both came back **empty on inspection** — no tests deleted or merged (report: `docs/audits/test-audit-2026-07-24.md`). **Rounds 6 & 7 + the canonical test-quality core merged 2026-07-23/24** (#122 closed all 9 🟡 partial + 10 ❌ P3/P4 flows; #123 giant-component units + last P3 flows; #124 adopted the canonical `scripts/quality/*` + gate refresh). **Round 5 merged + deployed to production 2026-07-23** (#121, squash `96796ae7`; deploy: 612 prerendered routes, post-deploy PASS=16). **Round 4 merged 2026-07-22 as PR #120** (squash `391d3168`, all checks green): CI coverage floors live (backend --cov-fail-under=92.5; frontend 85%/81% via dedicated step), all MCP modules 92-98%, gate warnings 8→0, blog-publish-mode E2E covered. **Round 3 merged 2026-07-22 as PR #119** (squash `928dce4b`, all checks green): task/linkedin tools + technical filter to 92–98%, 4 components →100%, gate warnings 18→8 via assertion splits, tags-manage + standalone-email-attachments E2E covered. **Round 2 merged 2026-07-22 as PR #118** (squash `2654e336`, all checks green): MCP proposal/accounting tools 57%/60%→97%/94%, 8 components →100%, gate warnings 32→18, three P2 document flows covered, plus a pre-existing strict-mode flake fix. **Round 1 merged 2026-07-22 as PR #117** (squash `8d173a41`, both workflows green): memory bank refresh, #114 pocket-draw rule modeled in fake accounting data, MCP diagnostic/statement tools 29%/50%→92%, six 0% shared frontend files →100%, gate warnings 50→32 (freeze_time in 18 tests), P1 E2E gap `admin-document-send-email` closed. Previous wave: **#113** (2026-07-17, QA cycles #2–#3 — PDF-challenges coverage, accounting store/statements/collections tests + E2E, BaseDropdown NuxtLink fix; also fixed the red gate: the CI job runs DEFAULT semantic-rules mode, whose `forbidden_token` rule rejected "batch" in a test name), **#114** (2026-07-17, pocket draws attributed to a partner now count against company utility as a 100%-partner company expense, migration `0164`; liquidate defaults to Bolsillo ProjectApp + exact-date toggle; `period_date` accepts full dates), **#115** (2026-07-22, COP email formatting via `format_cop_email` + the "Jue, 16 jul 2026" weekday date standard in backend helpers + central `frontend/utils/formatDate.js` + clickable expected-income stat card with month-detail modal), and **#116** (2026-07-22, COP formatting + weekday dates in phase-onboarding/payment-status notifications). Merged on 2026-07-16: **PR #110** (income liquidation + panel dashboard redesign), **PR #111** (QA cycle #1 + the AccountingTable sortable-hint icon), and **PR #112** (proposal PDF identified-challenges badge panel — its tests landed in #113). The current wave (Jul 7–16, 2026) is **accounting maturation + PDF redesign + panel dashboard command center**: accounting gained pocket↔records bidirectional sync (#103), a credit-card catalog with computed debt plus monthly statements with PDF and an 8-day reminder (#105), summary debt/expected cards (#106), and the income liquidation lifecycle expected→liquid/lost (#110); the proposal PDF was rebuilt on a layout engine (#99) with documents getting a dual friendly/professional template (#100); and `/panel/` was redesigned as a multi-module command center over a consolidated endpoint (#110). Earlier waves remain in place: Documents UX redesign + emoji pipeline (#97), proposals hardening (Jul 6), the Accounting module (#79), MCP connectors (#77/#78), the `/platform/documents` client signing portal with email-OTP verification, hosting stored-card + multi-phase billing, and the blog-SEO prerender pipeline. Codex-first methodology is documented via `AGENTS.md` scopes, native repo skills in `.agents/skills/`, and `.codex/config.toml`, with `CLAUDE.md`, `.claude/`, and `.windsurf/` retained only as compatibility surfaces.

---

## Recent Focus Areas

- **Las casillas de portada/subportada/contraportada y el archivo que se descarga** (2026-08-18, rama `fix/18082026-document-cover-options`, worktree propio): la ficha reportaba que desmarcar las tres no cambiaba el PDF descargado, y pedía descartar primero guardado → generación → caché. **Los tres descartes salieron negativos, con evidencia**: el round trip guarda (las tres claves viajan en el PATCH, `DocumentCreateUpdateSerializer` las declara, y en la BD de producción hay 37 documentos con `include_subportada=False` persistido, con `content_json['meta']` coincidiendo con el modelo en los 112); el generador lee los campos **del modelo vivo** (`document_pdf_service.py` — la segunda pasada del TOC también, así la paginación no se desincroniza); y no hay caché posible (ni FileField, ni ruta guardada, ni tarea Huey, ni señales: cada descarga renderiza en el momento). **La causa real es de tiempo, no de mapeo**: la descarga se arma con el documento GUARDADO mientras el botón no estaba gateado por cambios sin guardar (Guardar exigía `hasChanges`, Descargar no), y **ninguna previsualización mostraba las portadas** — la vista previa renderiza sólo el markdown. Quien desmarcaba y descargaba recibía en silencio el PDF de la configuración anterior. Lo confirma el dato duro: **ningún documento de producción tiene `include_portada=False` ni `include_contraportada=False`**, pese al reporte de haberlas desmarcado. Piezas: `guardedExport('download'|'preview')` en `useUnsavedGuard` (reusa `confirmExit`, verbos «Guardar y descargar» / «Descargar lo guardado» / «Seguir editando»; la rama sin guardado posible —cuenta emitida— cae sola en dos salidas), `utils/documentCoverPages.js` + línea viva `doc-included-pages` («El PDF incluirá: portada · contenido · contraportada») en edit y create, `DocumentPdfPreviewModal.vue` (visor `<embed>` + sonda `fetch`, patrón de `CollectionAccountDetailModal`) sobre `documents/<id>/pdf/?inline=1` — parámetro nuevo con `@xframe_options_sameorigin` + `content_disposition_header`, el default sigue siendo `attachment`. El `src` lleva el `updated_at` como sello: sin él, previsualizar tras guardar devolvía el PDF cacheado. El encabezado del visor describe la configuración **guardada**, no la de pantalla. **Tres defectos vecinos aprobados y arreglados**: el correo filtraba adjuntos por `content_json['blocks']` crudo y saltaba en silencio un documento sin parsear que la descarga sí genera (ahora `resolve_blocks`, mismo criterio que la vista de descarga); duplicar copiaba las tres casillas pero no `template_style` (toda copia volvía a «profesional»); y las tools MCP no podían fijar las casillas (todo documento del Gestor nacía con las tres en true) — ahora las aceptan, sólo booleanos (un `'false'` de texto habría entrado como True), y `_doc_detail` las expone. **Fuera de alcance, anotado**: `cover_type` es configuración muerta (se guarda, se serializa y se filtra en admin, pero ningún renderer la lee — sólo mandan los tres booleanos) y la portada es un único asset fijo, sin portada por documento ni por tipo (`COVER_TECHNICAL_PDF` apunta a un archivo inexistente y degrada en silencio al genérico). Verificación: 5 tests de páginas reales contando el PDF con pypdf (las cinco combinaciones que pedía la ficha), 2 de vista (round trip PATCH→descarga e `inline=1`), 1 de duplicado, 1 de correo, 3 de MCP, 13 unit (util + guard + modal) y **6 E2E** en `admin-document-pdf-download.spec.js` (dev server :3011, 6/6 + 17/17 de regresión en edit y unsaved-guard), quality gate **PASSED 0 errores**, tokens sin hallazgos nuevos. Flows: `admin-document-pdf-download` suma `display` y `admin-document-pdf-preview` nace como P2 en definitions **2.80.0**.

- **Eliminar cuentas de cobro, separado de anular** (2026-08-17, rama `feat/17082026-delete-collection-accounts`, worktree propio): el tab de Cuentas de cobro sabía emitir, reenviar, marcar pagada y anular, pero no había forma de quitar la creada por error — cliente equivocado, duplicada, monto mal —, y esa convivía para siempre con las reales ensuciando listado y contadores. **Tres hallazgos del código reencuadraron la ficha antes de escribir nada.** (1) **"Enviada" no es un estado**: `commercial_status` sólo tiene `draft/issued/paid/cancelled`, y crear una cuenta desde un ingreso **emite y manda el correo en el mismo acto** (`create_collection_account_view`), así que "emitida sin enviar" ocurre únicamente cuando el correo falló; el envío se consulta en `EmailLogTarget`, tabla sin FK a propósito para sobrevivir al borrado. (2) **La marca de "facturado" del ingreso no está persistida**: es derivada de *"existe un documento no anulado"* en 6 sitios, así que con borrado físico el ingreso se libera solo — el punto 4 de la ficha se resolvió sin código. (3) **El consecutivo nunca se reutiliza por construcción** (`last_value = F+1`, jamás decrece): el hueco queda, sólo hubo que fijarlo con un test. **Decisiones del operador**: borrado **físico** (el rastro no se pierde — `AccountingChangeLog` y `EmailLogTarget` guardan `object_id` + `object_repr` sin FK; un borrado lógico habría obligado a añadir la exclusión en los 6 sitios y una query que la olvidara dejaría el ingreso bloqueado por un documento invisible); regla **eliminable ⇔ anulada Ó nunca salió al cliente** (pagada nunca, y como tampoco se puede anular es callejón cerrado); permisos **`IsSuperUser`**, el mismo gate del módulo, sin inventar roles; confirmación con consecutivo/cliente/monto **más `requireTypeText: 'ELIMINAR'`** — la única acción de la tabla que lo pide, porque es la única irreversible. Un **rebote cuenta como entregado** a propósito: no prueba que el cliente no lo tenga, y en un documento con consecutivo el sesgo va hacia no borrar. Piezas: `delete_collection_account` + `collection_account_was_delivered` en `collection_account_service.py`, `_log_record_removal` promovido a **`log_entity_removal`** público (par de `log_entity_diff`, para entidades fuera del pipeline CRUD genérico), endpoint `DELETE .../collection-accounts/<id>/delete/`, campo `can_delete` en el serializer resuelto con un `Exists` anotado en el listado (con fallback por objeto en el detalle, patrón de `_collection_account`), y `deleteCollectionAccount` en el store. **Dos deudas del código encontradas de paso y pagadas**: el borrado genérico de Documentos eliminaba una cuenta en borrador **sin dejar fila en el historial** (ahora delega en el servicio, un solo camino con una sola regla), y el reset de `billing_requested_at` que hacía anular hacía falta también al eliminar — sin él un hosting quedaba mudo para siempre detrás de una cuenta que ya no existe. Verificación: 10 tests de servicio, 5 de endpoint, 1 de numeración, 2 unit del store, 2 E2E nuevos (21/21 verdes en el spec), gate **PASSED 0 errores**. El test de sólo-lectura lleva `allow-no-interaction` + `allow-deep-link` justificados: su sujeto ES la ausencia del botón. Nota de contexto: **`PA-23`, `PA-37` y `PA-56` no existen en este repo** (como pasó con PA-58), y **`PA-29` significa otra cosa acá** — *"projects archive, they never delete"*, no borrado lógico de Documentos; lo que la ficha llamaba PA-56 sí existe y es `AccountingChangeLog`, que ya tenía `EntityType.COLLECTION_ACCOUNT` y `Action.DELETED` sin que nada los escribiera.
- **Coherencia cliente/proyecto F7: la propagación hacia atrás** (2026-08-17, rama `feat/17082026-client-project-coherence-f7`, worktree propio): cierre del seguimiento del 15-ago (PA-DEIVISRI-001 con Proyecto vacío teniendo Vástago vinculado; dos cuentas de Daniel Felipe Corredor en desacuerdo — una con Mimittos, la otra no). Cuatro brechas cerradas. (1) **La columna Proyecto de cuentas leía SOLO el snapshot congelado** (`customer_project_name`, escrito al emitir) mientras el filtro usaba el FK vivo — drafts siempre en blanco, emitidas congeladas, celda y filtro contradiciéndose; ahora la columna responde con la **relación viva** (el precedente es la columna Cliente del MISMO serializer) y el snapshot queda como verdad del PDF y fallback para filas FK-null ("(histórico)" intacto); los DOS comentarios que documentaban la regla vieja se reescribieron para que un lector futuro no la "restaure". (2) **Asignar proyecto a un ingreso/hosting no alcanzaba sus cuentas draft** — y al emitir, el snapshot se escribe DESDE `document.project` y la numeración resuelve por él (`resolve_client_user`), así que una draft desactualizada emitía con proyecto en blanco: `_sync_project_to_draft_cuentas` engancha en `update_record`, ambos bulk (en el de cliente: cuando limpia el proyecto ajeno) y la cascada de hijos líquidos; emitidas/pagadas/anuladas jamás se tocan. De paso dos fixes reales: el PATCH individual de un esperado NO cascadeaba el proyecto a los hijos líquidos (el bulk sí — paridad cerrada) y `object_repr` no tenía rama DOCUMENT/DOCUMENT_FOLDER (esas filas de auditoría decían "Configuración contable"). (3) **Pasada retroactiva** `link_records_single_project` (requisito 14): ingresos/hostings/documentos (cuentas de CUALQUIER estado comercial — llenar el FK de una emitida es metadata organizativa; snapshot/PDF/estado intactos) con cliente y sin proyecto reciben el **único proyecto activo** de su cliente — la misma regla del auto-select del form (`ProjectSelect`); 2+ activos o 0 → skip con razón (PA-25, jamás adivinar); fill-only re-verificado fila a fila en una transacción, una fila de auditoría c/u (actor-less = sistema), dry-run con plan por fila y conteos ANTES, `--apply`, segunda corrida = 0. **Post-deploy ejecutado el 2026-09-01:** dry-run 102/117 ingresos asignables, apply 102 y segunda corrida 0; PA-DEIVISRI-001/002 y sus ingresos de origen quedaron coherentes. Quedan 15 ingresos y 11 documentos sin proyecto porque sus clientes no tienen uno activo; la corrida independiente de `link_documents_from_folders` conserva su pendiente operativo (ver la entrada de Current State). (4) **Decisión del operador: la oferta assign-unlinked incluye documentos** — cuentas por su número público; una emitida sin proyecto NO tiene camino de escritura HTTP (el PATCH genérico rechaza no-drafts), así que el writer compartido `assign_project_to_documents` (service, auditado, entity-typed cuenta-vs-documento como la cascada de folders) es su único vehículo junto al comando; `unlinked_documents_count` espeja el queryset de `documents_no_project_count` para que ambas superficies concilien; mismo contrato 409 de staleness; las filas de respuesta hacen map-replace del store de documentos (la lista de cuentas refetchea al montar, a propósito). Decisiones confirmadas por el operador (17-ago): **sin proyecto = válido pero visible** (se mantiene), **cascada pregunta cada vez** (se mantiene), **documentos en la oferta = sí en esta fase**. Verificación: backend 9+9+5+5 nuevos + 99 de regresión (project_service, panel cuentas, bulk-assign, collection services, assign-unlinked), jest 7+15, E2E **22/22** (collections + inline-offer: caso mixto con filtro y misma verdad tras reload, creación desde ingreso con proyecto aterriza mostrándolo, oferta con documentos) + **9/9** regresión (project-coherence + panel-projects) en dev server :3272, quality gate file-scoped 0 errores (1 negation-only corregido en el spec del modal), tokens limpios, flows **2.78.0** (collections 5→6 specs, collection-create 8→9, inline-assign-offer con documentos). Barrido del requisito 15 (dónde vive cada relación): Ingresos/Hostings FK+FK completos con bulk y contadores; Cuentas **dual a propósito** (FK vivo para el panel + snapshot congelado del PDF); Documentos/Carpetas FK con trío de asociación y herencia; Egresos sin eje **por diseño** (cliente sólo vía `source_income`); Propuestas cliente-FK y proyecto sólo vía Deliverable; Diagnósticos sólo cliente; Bolsillo/Recurrentes/Ads/Tarjetas sin eje (dinero a nivel empresa). Candidato a seguimiento declarado: lock análogo al de cuentas para documentos **firmados** por el portal (hoy sólo las cuentas tienen candado de emisión) — responde el "qué otros registros comparten la condición" del requisito 7.

- **Aviso de cambios sin guardar en los editores del panel** (2026-08-16, rama `feat/16082026-unsaved-changes-warning`, worktree propio): el caso reportado era asignar cliente y proyecto a un documento, salir creyendo que quedó guardado, y encontrar al cliente sin documentos. La única señal de trabajo pendiente era que el botón Guardar se habilitaba — y un botón habilitado se lee como "puedes guardar", no como "te falta guardar". **Decisión del operador: aviso, NO autoguardado**, y la razón es estructural, no estética: no hay endpoint de asignación (cliente y proyecto viajan dentro del PATCH completo del documento) y `apply_client_project_association` acopla los dos campos, así que mandar cliente sin proyecto nulifica el proyecto. Piezas nuevas: `utils/spanishList.js` (regla `y→e`, obligatoria acá porque `language` se etiqueta *idioma*), `composables/useUnsavedGuard.js` y `components/panel/UnsavedChangesNotice.vue`. El guard empaqueta las tres fugas de trabajo (navegación con router, cierre de pestaña, y el botón global de refrescar — que hasta ahora recargaba encima del formulario en silencio) detrás de un solo modal, y **nombra los campos**: hasta 3 los lista ("Cliente y proyecto sin guardar"), a partir de 4 los cuenta. **Las tres salidas sobre un `Promise<boolean>`**: `handleSecondaryAction` de useConfirmModal resuelve FALSE igual que Cancelar y ~25 call sites dependen de eso, así que NO se tocó — como es `async` y hace `await fn()` ANTES de resolver, el resultado se lee de banderas que escriben los callbacks. **Guardar va en el botón primario**: la acción destacada debe ser la que preserva el trabajo, y si el guardado falla la navegación se bloquea en vez de irse de un guardado fallido. Dos fuentes de suciedad porque no hay una sola forma en el panel: `snapshot()` (reactive o refs sueltos) y `flags` (páginas cuyo estado sucio reportan los hijos). `requestConfirm` es inyectable porque **no hay `<ConfirmModal>` global**: un segundo confirmState sin enlazar abre un modal que nadie renderiza — falla en silencio. **Fase 0 (va primero y sola)**: `ClientAutocomplete`/`ProjectSelect` soltaban el id comprometido al primer caracter y no lo restauraban — rozar el campo cliente ensuciaba el formulario y guardar desvinculaba de verdad; ahora tipear busca y desvincular es la X. Cobertura: documentos edit+create (referencia), propuestas migrado (su copy decía "Hay secciones con cambios sin guardar" — el aviso genérico que el requisito rechaza; queda en **dos** salidas porque no existe guardado atómico: cada SectionEditor guarda el suyo), y blog/portfolio/hour-packages ×2, linktrees, diagnostics/create, accounting/settings y emails defaults. **Diagnostics edit**: el slug entra al snapshot como *null-cuando-limpio* en vez de como su valor, así guardarlo vuelve a limpio solo, sin re-fijar la baseline compartida (que se llevaría por delante ediciones pendientes de los datos generales). **Deliberadamente SIN guardar, con motivo**: `panel/views` y `NotificationRecipients` ya autoguardan, `ViewSettingsPanel` no tiene estado editable, `ProposalHourRateTab` ya implementa este patrón y las Secciones de diagnostics autoguardan — avisar ahí sería una mentira de la UI; el borrador de Redactar en `/panel/emails` queda fuera porque no se guarda, se envía ("sin enviar", no "sin guardar"). Bugs encontrados por los tests, no leyendo: la marca por campo empezó DENTRO del `<label>` y contaminaba el nombre accesible del input ("Título Sin guardar"), y el fixture de asociación de `admin-document-edit` declaraba lista de proyectos vacía con el documento reclamando el proyecto 11 — el picker lo soltaba con razón y el guard lo reportaba. Bug vivo corregido de paso: linktrees pintaba su error de botones con `<BaseAlert variant="error">`, que no es una variante válida y caía en `info` (azul). Flows nuevos `admin-document-unsaved-guard` y `admin-panel-unsaved-guard` (este último fija que cambiar de pestaña es un `router.replace({ query })` sobre la misma ruta y **no** debe disparar el guard — probado con aserción, no asumido) en flow-definitions **2.76.0** / USER_FLOW_MAP **2.41.0**. Verificación: 45 unit nuevos, E2E 9+3 nuevos y 42 de regresión sobre las páginas tocadas, build exit 0, tokens sin hallazgos nuevos, quality gate **PASSED 0 errores (96→97)**. Pendiente declarado: `PA-58` (la dependencia que citaba el requerimiento) **no existe en este repo** — los tickets llegan hasta PA-51; y queda abierto si guardar con el cliente en blanco debería pedir confirmación propia, que es lo único irreversible del formulario.

- **Coherencia y propagación cliente/proyecto entre módulos** (2026-08-16, F1+F2 en PR #187 `feat/15082026-client-project-coherence`; F3–F6 en `feat/16082026-client-project-coherence-f3`, worktree propio): la regla que faltaba detrás del caso Vástago, en 6 fases. **F1** cierra el bug: `assign-unlinked` devuelve las filas afectadas (hijos líquidos incluidos) y `panel_projects` reconstruye el accounting store; la creación inline conserva la fila anotada y las páginas contables ofrecen el modal PA-51 al cerrar el form; `without_project_count` en metas + tab/card "Sin proyecto" (decisión del operador: **sin proyecto = válido pero visible**); filtros de proyecto por catálogo completo (patrón history.vue); collections filtra por `project_id` vivo (nombre congelado sólo para filas legacy, "(histórico)"). **F2** agrega `bulk-assign-project` en hostings/ingresos (contrato 409 PA-51 + `client_mismatch`/`mismatched_ids`), `BulkAssignBar` con toggle Cliente|Proyecto + `ProjectCatalogSelect` + plan puro `projectAssignment.js` con bucket de bloqueados por pertenencia; **fix real detectado implementando**: `bulk_assign_client` NO limpiaba el proyecto ajeno al mover el cliente (la regla vivía sólo en el serializer individual) — ahora limpia y cascadea a hijos líquidos, y el preview de cliente lo anuncia (`projectCleared`). **F3** implementa la cascada (decisión: **preguntar cada vez**, modo sin preselección): `project_service.change_client_preview/apply` (una transacción; bloqueados = ingresos con cuenta activa → se desvinculan y conservan cliente; drafts sin ingreso siguen al proyecto con snapshot fresco; emitidas byte-intactas; hijos líquidos SÓLO vía cascada del padre — procesarlos como filas propias partía un negocio en dos clientes), endpoints `change-client/preview|apply` con ids como token de staleness, guard 409 `project_has_records` en el force-delete de plataforma (PA-29), migración **`content/0199`** (entity types `project`/`collection_account`; main ocupó 0196-0198 — EmailLogTarget deduplica el choice heredado). **F4**: PATCH/DELETE genéricos de documentos bloquean cuentas no-draft (400 `collection_account_locked`; edit page se auto-bloquea con el code), serializers exponen `document_type_code`/`commercial_status`; **política**: cuenta activa congela el cliente EXISTENTE de su ingreso (single 400 + bulk 409 `records_with_collection_account`/`conflicting_ids`; completar cliente faltante sigue permitido — 92/115 legacy — y hostings exentos a propósito; la adopción al emitir llama al service directo y no se toca); columna Proyecto en subtablas de /panel/clients (el detalle ya servía `project_name`). **F5**: auditoría — escritores en panel projects CRUD/archive, plataforma project create/PATCH (campos de identidad; progress es ruido operativo), PATCH de cuenta draft y transiciones issue/paid/cancel (`log_entity_diff` compartido); `change_log_queryset` acepta `?client=`/`?project=` (espejo del email log; **límite documentado**: filas de registros borrados sólo por `object_repr`) y el tab Cambios gana esos filtros. **F6 — procedimiento retroactivo (requisito 13, operativo, SIN migración adivina-identidades per PA-25)**: (1) en hostings/ingresos, tab "Sin cliente" → bulk-assign-client hasta `without_client_count`=0; (2) tab "Sin proyecto" → bulk-assign-project por cliente, o `assign-unlinked` desde cada fila de /panel/projects; (3) la dimensión se ve ANTES de empezar en `without_project_count`, `records_without_project` y el backlog por cliente. Flows nuevos `admin-accounting-project-bulk-assign`/`-project-coherence` (P1, el segundo ES el requisito 14: mock stateful, sin recarga y tras recarga) + `admin-project-inline-assign-offer`/`-change-client` (P2) en flow-definitions **2.74.0** / USER_FLOW_MAP **2.39.0** (§28). Fake data sin cambios: "sin proyecto" sigue siendo bucket real.
- **Documentos vinculados a cliente/proyecto + módulo Documentos en /panel/clients** (2026-08-15/16, en dos PRs por el barrido de integración del operador: **#185** con F1-F5 mergeado con CI verde, y la rama `feat/16082026-documents-clients-module` con F6-F8): la pertenencia de un documento vivía en el nombre de su carpeta; ahora es relación. `Document.project`/`client_user` YA existían (los escribían las cuentas de cobro y los leía el portal) — el panel los expone con el contrato contable: `client` = pk de **UserProfile** en read/write mapeado a `client_user` (auth.User) por `apply_client_project_association` (serializers/document.py), que **deriva el cliente desde el proyecto** (la cascada inversa también server-side), rechaza el par ajeno vía `validate_project_client_match` (error field-scoped en `project`), desvincula el proyecto al cambiar de cliente (patrón income) y autocompleta `client_name` SÓLO cuando el cliente cambia y no vino un valor propio (el PDF lo lee del meta; un texto personalizado sobrevive a saves que no tocan la asociación). Listado con params `client`/`project` (`none`|ids CSV, 400-si-inválido) + ejes espejados en `useDocumentFilterQuery` (URL persistente — a diferencia del `ephemeralParams` contable) + columnas Cliente/Proyecto (nombre libre heredado en itálica) + `DocumentsAssociationFilters` (chips «Sin cliente»/«Sin proyecto» excluyentes). `ProjectSelect` ganó `allowNoClient` (lista TODOS los proyectos con su dueño en la fila, emit `select` con la fila completa, y el watch de cliente pasó de «limpiar siempre» a **«recargar y conservar si sigue en la lista»** — lo que evita que el autofill borre el proyecto recién elegido); el picker `list_client_projects` pasó de IsSuperUser a **IsAdminUser** (lo consume el form de documentos) con `client_profile_id`/`client_display_name` por fila. Forms create/edit: par `ClientAutocomplete`+`ProjectSelect` con creación inline, **sin el input libre** de cliente (decisión: la relación es la verdad; el texto legado se muestra como referencia), sugerencia por carpeta (`documents/folder-client-suggestion/`, mayoría estricta con ≥2 vinculados, prellenado nunca lock) y backlinks de lo GUARDADO → `/panel/projects?highlight=` y `/panel/clients?highlight=` (**deep-link nuevo**: expande la ficha + scroll, param de un solo uso, espejo del de projects). Clientes: módulo **Documentos** nivel-1 (subfiltros `docs-with`/`docs-none`/`docs-no-project` sobre `documentsStatus`), annotations `documents_count`/`documents_no_project_count`/`last_document_at` (Subquery + `OuterRef('user_id')` por la asimetría User/Profile, sólo docs activos), pill «N docs · fecha del último» **sin gate de superuser** (documentos comparte el gate admin de la página) → `/panel/documents?client=`, y sección Documentos en la ficha (últimos 5 + «Ver todos (N)») vía `ClientDocumentRowSerializer` ligero. Retroactivo: comando **`link_documents_from_folders`** (dry-run default + `--apply` atómico; normalización espejo de `clientMatch.js`; variantes por mitades `' - '` y sin sufijos finales {proj, project, proyecto, diseno, web}; **match inequívoco o nada**, proyecto con prioridad sobre cliente, herencia del ancestro más cercano para subcarpetas, pass 0 normalize proyecto→dueño; idempotente — segunda corrida aplica 0). **Post-deploy pendiente: correrlo en prod** (dry-run primero, `DJANGO_SETTINGS_MODULE=projectapp.settings_prod`); sin esa pasada la relación arranca vacía. Fake data: ~60% de los markdown docs asociados vía `_client_candidates()`. Verificación: backend 13+13+24 (F1) + 4+5 (F2) + 12 (F6) + 9 (F7) verdes; jest 17 ProjectSelect + 49 (store/composable/tabla/filtros) + 16+10 (clientFilters/panel); E2E 37 (36 + 1 flaky por cold-compile del chunk en dev, endurecido a 30s) y re-runs 24/24 + 7/7 tras rebasear sobre #189 — que conservó las columnas Cliente/Proyecto gracias a la coordinación por canal entre sesiones; quality gate file-scoped **96/100 PASSED**; flow map `flow-definitions` 2.74.0 / `USER_FLOW_MAP` 2.39.0 con el flow nuevo `admin-clients-documents-section`; audit **0 junk-only / 0 missing** (create/edit quedan `partial` por la clase `error` — gap preexistente al branch). Fuera de alcance explícito: MCP document tools, servicio PDF, `upload_document_markdown`, bulk-assign UI de documentos, FK `deliverable`, multi-cliente por documento (se resuelve duplicando el doc).

- **Correcciones al archivado de documentos: vista sincronizada, hardening y portal** (2026-08-13, rama `fix/13082026-document-archive-followups`): cierre de los residuales del ticket de archivado — el grueso ya había llegado en #162/#166 (los PRs #167/#168 resultaron ser **commits vacíos**; `requirements_mapping` ya estaba recuperado en prod por la migración 0186, verificación declarada en el commit de #166). Frontend (9 commits tamaño lote): `toggleTagFilter` conserva el scope archivado; **salir de la búsqueda navega de verdad** (`exitSearchAndNavigate`: anular `scopeBeforeSearch` ANTES de vaciar el término neutraliza la restauración del watcher — la insignia mid-search ahora aterriza en la carpeta en scope archivado); la búsqueda muestra el skeleton (`isSearchLoading` con token) y descarta resultados stale en cada término; archivar/eliminar la carpeta visible **o un ancestro** retira la vista al padre (`descendantIdsOf` + escritura directa de `activeFolderId` antes del `refreshView`); «Archivados» queda **encendida a cualquier profundidad** con regla de resaltado único + `aria-current` (decisión del operador: opción mínima, no árbol archivado en sidebar); contador de «Sin carpeta» (`unfiled_active`); `ConfirmModal` ganó `loading` y `useConfirmModal` el opt-in `waitForConfirm` (default byte-idéntico para los ~25 call sites); aviso «Restaurar esta carpeta» dentro de una carpeta archivada, con follow al scope activo; **persistencia en URL** `?folder=&scope=` (`useDocumentFilterQuery`: replace sin historial, defaults omitidos, el scope transitorio de búsqueda no se persiste, folder inexistente cae a Todos). Regresiones del mismo patrón stale (req 22 del ticket): **tareas** ya no vacían `archivedTasks` con el acordeón abierto (refetch); el **dashboard de propuestas** expone `refreshIfLoaded()` y `refreshData` lo invalida (abierto refetchea, cerrado marca la caché vieja). Backend: comando **`audit_archive_integrity`** (default dry-run; `--repair` = política exacta de 0186, jamás re-parenta ni toca ciclos/procedencia; help documenta `DJANGO_SETTINGS_MODULE=projectapp.settings_prod`); admin con campos de archivado **readonly** (el vector real era el registro pelado de `DocumentFolder`); locks `select_for_update` lock-only-fetch en archive/unarchive; **decisión del operador: el portal del cliente excluye archivados** (`_visible_docs_qs` filtra `is_archived=False` — único choke point de lista/detalle/PDF/firma). Incidente documentado como **ERR-016**. Verificación: unit 50+29+29+7 verdes, backend 7+8+20+28 verdes, 5 E2E nuevos en `admin-document-archive.spec.js` (corridos contra dev server propio en worktree aislado — había sesión paralela de contabilidad en el árbol principal). **Post-deploy pendiente: correr `audit_archive_integrity` (dry-run) en prod como cierre del req 8 («verificar que no haya más perdidos»).**

- **Módulo Plataforma: Proyectos en el panel + creación al vuelo (PA-49 + dependiente)** (2026-08-13, rama `feat/13082026-panel-projects-module`, worktree propio, 8 commits): `accounts.Project` ya lo referenciaban hostings/ingresos/cuentas de cobro (#163) pero no tenía cara comercial — el hint de `ProjectSelect` apuntaba a un `/panel/projects` que 404eaba. **Tres decisiones del operador**: cliente OBLIGATORIO al crear (y resultó estructural: la FK ya es NOT NULL), consolidación por **migración determinística + resto manual**, y el espacio Plataforma del sidebar lleva **Proyectos + entrada duplicada a Hostings** (ítem con `superuserOnly` nuevo A NIVEL DE ÍTEM en panelNav; la sección va DESPUÉS de Contabilidad a propósito — el breadcrumb resuelve por primera coincidencia y hostings debe seguir bajo Contabilidad). Backend: `/api/projects/` session-side **IsAdminUser** (espejo /panel/clients; el picker IsSuperUser de accounting quedó intacto) — list con `?scope=active|archived|all` (inválido → 400, patrón documentos), counts por Subquery, meta con `clients_without_projects` (espejo del default oculta-desactivados); create con mínimo PA-38 (`client_profile_id` → `profile.user`); update con cliente inmutable (400 `client_immutable`) y archivados fuera de circulación (400 `project_archived`); archive/unarchive dedicados sobre `status='archived'` (SIN migración de esquema — mecanismo ya establecido por el DELETE de platform; unarchive siempre → active, trade-off documentado); `?without_projects=` en list_proposal_clients (predicado más débil que `orphans`). **Gotcha de convención**: los 400 de guardas van por `error_response()` — `normalizeApiError` renderiza `data.error` COMO mensaje humano, un slug ahí sale en el toast. Frontend: página híbrida shell-qr-cards + `AccountingTable` (`showActions=false` — proyectos archivan, no borran; acciones propias como BaseButton ghost icon-only) + `useAccountingCrudPage` (verificado agnóstico del store) y SIN `useAccountingFilters` (habría exigido migrar `SavedFilterTab.VIEW_CHOICES`); búsqueda local con `normalizeName` + `BaseSegmented` de scope; store `panel_projects.js` refetch-tras-mutación; warn de duplicado **no bloqueante** (sin unique en DB — no existía ningún detector de casi-duplicados en el repo, net-new sobre el patrón strip de sugerencia); panel de clientes sin proyecto con CTA que siembra el modal (`seedClient`). Saltos: counts → NuxtLink gated `isSuperuser` a `hostings?project=<id>` e `incomes?accounting_incomeTab=all&project=<id>` (el tab default ocultaría liquidados — precedente collections); seed de `currentFilters.projects` en el mount de ambas páginas (seguro: el mounted del composable retorna temprano con tab all/builtin). **R2**: `ProjectSelect` reescrito como combobox espejo de ClientAutocomplete pero con **filtrado local** (los proyectos del cliente ya están fetched) y el create inline EMBEBIDO en el componente (req: "un solo selector reutilizable, no solución por modal") — hosting/income modals no cambiaron, colecciones lo hereda vía el income modal apilado; 0 matches → "Crear proyecto «term»" (Enter incluido) → panel con nombre precargado + cliente heredado + warn no bloqueante + 400 mantiene el panel + éxito auto-selecciona; cancelar el form exterior deja el proyecto en pie. **Caché**: `projectsByClient` era memo eterno — `createProjectForClient` apendea in-place (y tira el bucket 'all') y el store del módulo invalida TODO el caché tras cualquier mutación. Consolidación: migración `content/0192` (espejos 0173/0186, lógica inline SIN importar services, normalización NFKD+casefold) — split `' - '` SOLO con cliente vinculado y project NULL (~6-7 filas prod), sin separador → skip y afloran vía el indicador; se corrigió el bloque ASPIRACIONAL del USER_FLOW_MAP que afirmaba una "migración 0188" + celda inline-editable + «revisar» inexistentes; su comportamiento quedó pinneado ejecutando la función forward contra el registry vivo (5 tests — el archivo vive en la RAÍZ de content/tests: el gate no admite área `migrations`). Fake data: catálogo pequeño en `create_fake_accounting` SOLO para clientes con cero proyectos (nunca ensanchar un catálogo preexistente — un test fija que toda fila linkeada usa el proyecto del caller) + 1 archivado; ciclo create→delete sin ProtectedError verificado en dev DB fresco. **Gotcha de stubs jest**: un stub de BaseButton sin `emits: ['click']` hace fallthrough nativo del listener y TODO click dispara doble (la 2ª llamada se comió el 400 mockeado y enmascaró el error con el fallback). Verificación: 22+5+11+15 backend, 24+13+12 jest, E2E 8/8 módulo (entrada real por sidebar — el gate exige no-deep-link en display) + 4/4 fly-create + regresión 12 hostings + 55 incomes/collections en dev server :3245, gate **PASSED** modo CI, tokens limpios (deuda neta cero; los 2 raw buttons flaggeados de hostings.vue son preexistentes), flow map fresh y audit 0 junk-only / 0 missing. Flows `admin-panel-projects` (P1) y `admin-project-fly-create` (P2) en flow-tags/flow-definitions **2.69.0**/USER_FLOW_MAP **2.35.0** (§7 + §27), viewCatalog con la entrada nueva. Fuera de alcance explícito: MCP tools de proyectos, bulk-assign de proyecto en ingresos, celda inline-editable + «revisar», mover hostings de Contable, saved tabs del módulo, salto a colecciones (filtra por nombre congelado), cambiar cliente de un proyecto, hard delete panel.

- **Cuentas de cobro desde el tab propio: desplegable de ingresos por cliente** (2026-08-12, rama `fix/12082026-document-archive-hierarchy-restore`): el origen "desde un ingreso" ya estaba validado; el del **tab propio** fallaba por tres causas acumuladas en `CollectionAccountFormModal`, todas del lado del cliente: `loadIncomes()` **nunca enviaba el cliente** (solo `kind=expected,liquid` y `q`), **no había watcher sobre `clientId`** (el único `watch` era sobre `props.open`, así que la lista se quedaba con la primera carga) y un **`.slice(0, 8)` invisible** recortaba el listado. El dato de producción que definió el diseño (consulta de solo lectura): de **115 ingresos elegibles** (73 esperados + 42 líquidos) **solo 23 tienen cliente** (TORRIOS 22, MIMITTOS 1) y **92 no tienen ninguno** — con el tope de 8 se veía el 7% del libro, y un filtro estricto por cliente habría dejado el 80% inalcanzable. **Cinco decisiones del operador** quedan registradas aquí: (1) con cliente elegido se piden `?client=<id>,none` y las filas se parten en dos grupos, **"De {cliente}"** y **"Sin cliente asignado"** — los huérfanos siguen siendo seleccionables **a propósito**, porque `create_income_collection_account` **adopta** el cliente al emitir (`bulk_assign_client`), así que esconderlos cortaría justo el camino que completa el vínculo; (2) sin cliente, se listan todos; (3) el alcance es **esperados Y líquidos** (nunca perdidos), que es lo que ya hacía el código y lo que ofrece el tab de Ingresos — se corrigió el copy que prometía solo esperados; (4) el **consecutivo es por cliente** y siempre lo fue: `PA-MIMITTOS-001` salió del perfil 35 (`company_name` "MIMITTOS"), **no del proyecto** — la asimetría real estaba en el `issue` de `/platform/`, que caía en la serie legacy `PA-{year}-{NNNN}` y ahora usa el helper nuevo `client_number_allocator(document, issuer)` (mismo patrón que hostings; `_resolve_client_user` pasó a público `resolve_client_user` para no duplicar la resolución cliente-directo/vía-proyecto); (5) **cuenta pagada ↔ ingreso liquidado ya estaba resuelto en ambas direcciones** — liquidar al 100% marca la cuenta pagada (sync en la transacción de settle) y marcar pagada enruta al modal Liquidar mientras el esperado tenga saldo (409 en el endpoint directo) — así que solo se registró y se cerró el borde que faltaba: cuenta ligada a un ingreso **líquido** marca pagada directo, porque un líquido no tiene estado de cobro que liquidar. Dos hallazgos de diseño en el camino: el `.slice(0,8)` se reemplazó por tope **declarado** de 25 por grupo con pie "Mostrando 25 de 92 · escribe para filtrar" (truncar en silencio era el defecto de origen), y elegir un ingreso **bloqueaba el cliente** (PA-24) dejando el escenario de incoherencia del requerimiento literalmente inalcanzable desde este tab — el candado ganó un **"Cambiar"** (solo cuando el ingreso no llega por prop), y con eso el aviso `incomeClientConflict` es una guarda viva: bloquea `canPreview` y ofrece adoptar el cliente del ingreso o quitarlo, en vez de gastar un round-trip para recibir el 400 del backend como un genérico "No se pudo generar la previsualización". Detalle de implementación: `loadIncomes` lleva **token monótono** porque cambiar de cliente mientras corre la búsqueda debounced (250 ms) dejaba ganar a la respuesta vieja. Verificación: +6 unit (27/27 en el spec del modal), +3 backend (31/31 entre `accounts/tests/test_collection_account_views.py` y `content/tests/views/test_collection_accounts_panel_views.py`), +1 E2E de punta a punta desde el tab (11/11 en dev server). El store `searchIncomesForCollection` no necesitó cambios: `buildQuery` ya reenvía cualquier param, y el backend ya aceptaba `client` como `null_filter` con el centinela `none`.

- **Renegociación Vasta aplicada + vista de ingresos agrupada por cliente** (2026-08-11, rama `feat/11082026-document-archive-state`): DATOS en prod vía MCP — el **Otrosí Nº1 v3** (Gestor Documental doc 103, firmado) sustituyó el 40-30-30 de las Fases 2/3: se crearon **14 esperados** (abono $6.000.000 ago-2026 + cuotas 1-11 de $1.646.746 y cuota 12 de $1.646.748, sep-2026→ago-2027 = $25.760.954, + **hosting semestral $6.022.972** oct-2026 = 18% de $33.460.954 con reajuste SMMLV cada 1-ene, causación desde la puesta en producción pendiente de acta), se **eliminaron los 8 esperados obsoletos** (158-165, incl. los 3 de hosting por fase), se vinculó TODO Vastago (22 registros) al cliente **22 — Deivis Rios** (el perfil 32 "David" es de prueba) y se creó la **ficha Hosting #13** (semestral, `valid_from` tentativo 2026-10-01). CÓDIGO: `AccountingSettings.income_default_view_mode` (migración `content/0184`, default `grouped`, auditado; schema MCP de `update_settings` completado y **fijado al serializer por test**) decide cómo aterriza `/panel/accounting/incomes` en CADA visita; el toggle Agrupado/Clásico es **de sesión** (sin localStorage — a propósito distinto de recurrentes; `useIncomeViewMode`); `IncomeGroupedTable` (clon subgrid del de recurrentes sin drag) agrupa el set filtrado completo vía `groupByClient` — headers colapsables con count/Facturado/Pendiente/peso, bucket "Sin cliente" con pill "por completar", totales al pie, row-actions intactas; sort/selección/paginación quedan clásico-only; `onMounted` secuencial `initFromSettings()`→`loadRecords()` (comparten `isLoading`; en paralelo flashea el empty state). Fixes: **cascade de cliente esperado→líquidos** (update + bulk, un audit por hijo, sin `_notify`), la **cuenta de cobro adopta el cliente** de un ingreso huérfano y rechaza 400 el mismatch, búsqueda por nombre de cliente (q backend + espejo front), KPI `without_client_count` (set filtrado completo, no year-scoped — las filas legacy viven en años pasados), pill "sin vincular" en la tabla clásica, el **snapshot de facturación de hosting se refresca al reasignar el cliente** (serializer + bulk; el override del mismo request gana; unlink lo conserva — antes la cuenta se iba al buzón del cliente anterior), **N+1 eliminado** del retrieve de cliente (select_related + anotaciones de lista; test fija que las queries no escalan con las filas) y choice `accounting_cards` en SavedFilterTab (`accounts/0045` — guardar pestañas en Tarjetas daba 400). Won't fix deliberado: opciones del filtro de cliente derivadas de las filas cargadas. Gotcha E2E: la página ahora consulta `GET accounting/settings/` al montar — `buildHandler` de incomes y filters lo mockean con default `classic` (prod es `grouped`) porque el fallback `{}` de mockApi dejaría todo agrupado y rompería las suites clásicas. Verificación: +18 backend, +18 jest, +4 e2e (aterrizaje agrupado `display` con allow-no-interaction, toggle de sesión sin PATCH, settings persiste el modo, pill), gate 0 errores, flow map 2.65.0 (`admin-accounting-income-client` **covered** 7/7; settings sigue partial pre-existente). Wave compartido con 4 sesiones paralelas (bulk-assign-confirm, calendario/mute, recurring-charts, collection-metadata) — commits por capa, no por feature.

- **Hostings vinculados a su cliente** (2026-08-06, misma rama `feat/05082026-collection-accounts-create-flows`, 4 commits): hermano de PA-24 pero con el vínculo **no opcional** — todo hosting se presta a un cliente. `HostingRecord.client` (FK a `UserProfile`, `PROTECT`, migración `content/0177` con índice), **nullable solo en la base** para que los registros previos se puedan abrir y guardar mientras se completan: la obligatoriedad vive en el serializer **al crear**, lo que evita que un `NOT NULL` rompa las ~7 fábricas de test por ORM y el seeding standalone. Los cuatro `client_*` quedan documentados como **snapshot de facturación** (el contacto de cobro puede diferir del titular): se llenan del perfil cuando el formulario los deja vacíos y nunca pisan lo que el operador tipeó. Nombres sin colisión: la FK se expone como `client` + `client_display_name` (no se puede reusar `client_name`, que ya es columna real, columna 1 del export, `Meta.ordering` y etiqueta 'Cliente' del change log). **Hallazgo de producción que definió dos decisiones** (consulta de solo lectura): hay **6 hostings, ninguno con `client_email`**, y como el flujo lo exigía **ninguno podía emitir cuenta de cobro**; y de sus nombres `Persona - Marca` solo 1 coincide claro con un cliente (Mimittos por empresa), 2 parcial (Germán/Néstor por nombre de pila con tildes distintas) y 3 no existen aún como perfil. De ahí: (1) **sin migración que adivine** — el formulario **sugiere** el emparejamiento al abrir (`utils/clientMatch.js` normaliza sin tildes, parte por `' - '` y prueba ambas mitades contra nombre y empresa) y el operador confirma con un clic, más asignación masiva y creación inline; (2) el destinatario pasa a resolverse con `HostingRecord.billing_email` (**override del hosting → correo del cliente**, ignorando placeholders), que **desbloquea los 6** y reemplaza los 4 sitios donde el frontend leía `client_email`; (3) un hosting con cliente emite en la **serie por cliente** `PA-{CODE}-{NNN}` (los sin cliente conservan la legacy) y el documento enlaza `client_user`. La guarda de borrado suma `client_has_hostings` (5º bloque) con sus tres espejos — el conteo va como **Subquery**, no un quinto `Count(distinct=True)`. `bulk_assign_income_client` se generalizó a `bulk_assign_client(entity, ...)` y se expuso para hostings. **Vista por cliente (ambas)**: `retrieve_proposal_client` anida `hostings` (con `hostings_monthly_total`, solo activos) e `incomes`, y la ficha expandible de `/panel/clients` los renderiza junto a propuestas/proyectos/diagnósticos; el modal "Totales por cliente" ganó una segunda sección de hostings (`groupByClient` parametrizado con su reductor). Verificación: 17 tests backend nuevos + regresión (billing, cycles, expiry, export, MCP con sus 54 tools intactas), 15 unit nuevos (`HostingFormModal` — que **no tenía spec** — y `clientMatch`), **9/9 + 16/16 E2E** en dev server, quality gate **97/100 PASSED**, ciclo `create_fake_data`→`delete_fake_data` sin `ProtectedError`. De paso se cerraron dos flows **partial preexistentes**: `admin-accounting-hostings` no tenía test de la clase `error` y el `display` de `admin-accounting-hosting-billing` era junk (no interactuaba); ambos quedaron **covered**, igual que el flow nuevo `admin-accounting-hosting-client` (P1, flow-definitions 2.64.0). Nota de despliegue: producción **no tiene aplicadas** `accounts/0044`, `content/0175`, `0176` ni `0177` — el próximo deploy las corre juntas.

- **Ingresos vinculados a su cliente + línea de negocio** (2026-08-05, misma rama `feat/05082026-collection-accounts-create-flows`, 4 commits): `IncomeRecord` gana `client` (FK **opcional** a `UserProfile`, `PROTECT` + `limit_choices_to={'role':'client'}` — el mismo molde de `BusinessProposal.client` y `WebAppDiagnostic.client`) y `origin` (desarrollo/hosting/diagnóstico/otro; **blanco = sin clasificar** para lo histórico), migración `content/0176` con índice `(client, period_date)` y **sin backfill** (decisión del operador: se completa desde la UI). Tres decisiones lo gobiernan: (1) históricos por **asignación masiva en la UI**, (2) el campo de **origen entra ahora** (es lo único que clasifica los ingresos de hosting, cuyos clientes son texto plano sin perfil de plataforma), (3) los totales viven en un **modal "Totales por cliente"**. Hallazgo que definió el diseño: **el filtrado del tab Ingresos es 100% client-side** (la página pide la lista sin params y filtra en memoria, paginando de a 15), así que los totales se calculan en el navegador sobre `filteredRecords` — **sin endpoint ni agregación nueva**, y el "período" sale de los filtros activos. El filtro de cliente es un *matcher*; el filtro backend existe igual para **export CSV y MCP**, vía una clave declarativa nueva `null_filters` que habla el vocabulario de centinelas de documentos (`none` aísla los sin asignar, `all`/vacío no filtra, ids por coma como OR) y ahora acepta `none` **mezclado** con ids; los `choice_filters` aprendieron el mismo `none` para elegir los valores en blanco (así el CSV nunca diverge de lo que muestra el tab con "Sin clasificar"). Endpoint nuevo `POST accounting/incomes/bulk-assign-client/` con `bulk_assign_income_client`: transacción, **una entrada de auditoría por fila** (el historial es por registro) y no-op cuando el cliente ya coincide. `AccountingTable` gana columna de casillas **opt-in** (`selectable` + `v-model:selected`; la casilla del encabezado marca la página, y la barra ofrece "seleccionar los N filtrados"), y `IncomeFormModal` gana selector de cliente con creación inline + segmented de origen, más un prop `lockedClient` para cuando se monta **apilado dentro del modal de cuenta de cobro** (evita un segundo selector que contradiga al de arriba). Liquidar **hereda** `client`/`origin` al hijo líquido y a los follow-ups (sin eso el dinero cobrado se caía de los totales de su cliente). La guarda de borrado de cliente suma `client_has_incomes` al service (el `PROTECT` es la segunda línea de defensa) y a sus **tres espejos** — `get_is_orphan`, las anotaciones de `_base_queryset` (como **Subquery**, no un cuarto `Count(distinct=True)`: ya hay tres joins inversos) y el filtro `orphans` — más el texto de la MCP y el copy del panel. Auditoría: `display_value` ahora renderiza un perfil cliente con `build_client_display_name` en vez de `"email (Client)"`. Verificación: 18 tests backend nuevos + regresión (settlement, export, MCP con su conteo de 54 tools intacto, filtros genéricos), 8 unit del helper `groupByClient`, specs de modales actualizados (el `toEqual` exhaustivo del payload de `IncomeFormModal` rompía por diseño), **29/29 E2E de ingresos + 20/20 de filtros/cuentas** en dev server, quality gate 96/100 PASSED y **ciclo `create_fake_data` → `delete_fake_data` sin `ProtectedError`** (el riesgo concreto del `PROTECT`: el comando no borra perfiles cliente, y quedó documentado en el código). Flow `admin-accounting-income-client` (P1) registrado en flow-tags/flow-definitions 2.63.0/USER_FLOW_MAP y **covered**.

- **Cuentas de cobro: creación desde el tab + desde ingresos, con preview** (2026-08-05, branch `feat/05082026-collection-accounts-create-flows`, 4 commits): the Cobros tab became the **Cuentas de cobro** center (label renamed; key `collections`, testids and saved-tabs untouched — the tab never had them). Three operator decisions shape the design: **per-client numbering `PA-{CODE}-{NNN}`** (continuous, never year-reset; `ClientDocumentNumberSequence` OneToOne to UserProfile + `collection_account_numbering` service with race-safe allocate, manual override globally collision-checked + own-series fast-forward; `billing_code` auto-derived — never purely numeric so it can't collide with legacy `PA-{year}-{NNNN}`, which hostings keep using), **mandatory income link** (new `Document.income_record` FK SET_NULL; max ONE non-cancelled cuenta per income enforced row-locked in the create service — MySQL can't express the conditional unique; income API exposes `has_collection_account`/`collection_account_id`/`number` via subquery annotations with `__dict__`-based fallback detection since NULL is a legit annotated value), and **paid↔settlement sync** (settle fully-paid → linked ISSUED cuenta auto-marks paid inside the settle transaction via `income_payment_status()`, the single boundary-rule owner reused by the panel mark-paid 409 guard; the UI routes expected-linked mark-paid through the Liquidar modal — never a silent settlement). **Create+preview+send pipeline**: `collection_account_email_service` split build (zero side effects) vs send — the panel `preview/` endpoint runs the REAL create+issue+build+PDF pipeline inside `transaction.set_rollback(True)` (no rows, no EmailLog, no consecutivo consumed; preview==send by construction); `create/` issues + emails synchronously with hosting semantics on email failure; `next-number/` peeks without consuming. Payload keys on `client_profile_id` (UserProfile pk — what ClientAutocomplete carries; user pk ≠ profile pk in prod). **PDF upgrade shared by all origins**: valor en letras via `num2words` (new dep, `amount_in_words_es` in pdf_utils), `_format_cop` amounts, `format_date_es` dates, NIT/C.C. identification types drawn, signature block, internal Estado line removed; email body gained its missing `$`. **Clients module unification**: `UserProfile.nit` + unique-nullable `billing_code` (migrations accounts/0044 + content/0175; blank ALWAYS normalizes to None), editable in `/panel/clients` (proposal_clients view validates format/uniqueness), carried by the autocomplete search serializer for the modal's editable snapshot (NIT wins over cédula). **Frontend**: `CollectionAccountFormModal` (2 steps: form with client autocomplete + inline create, income combobox blocking flagged rows + stacked IncomeFormModal for inline expected income, dirty-tracked consecutivo sent only when edited; step-2 preview renders subject + `srcdoc` iframe + PDF blob embed before Confirmar y enviar); entry points: tab button/empty-state CTA + income row generate/view icons with `?focus=` row-flash both ways; viewCatalog + breadcrumbs gained the missing collections entry. Tests: +33 backend (numbering 10, create service 10, endpoints incl. preview-persists-nothing 10, settle-sync 5, income flags 4, panel guard/origin 3, PDF content 1 — some overlap in counts by file), +12 frontend unit (modal spec 8, store 4), +4 E2E (create-through-preview, Liquidar routing, generate-locked-modal, linked-navigation) — 9/9 E2E green on dev server, quality gate 95/100 PASSED (one justified allow-deep-link), design-token debt net-zero (3 new row actions use BaseButton ghost). Flow map: `admin-accounting-collection-create` (P1) registered in flow-tags/flow-definitions 2.62.0/USER_FLOW_MAP; `admin-accounting-collections` description refreshed. Seeds: demo client gained a NIT. Ops note pre-release: **verify prod IssuerProfile row** (city, identification, `default_payment_methods`) — create/preview error in Spanish if absent.

- **Deducciones first-class + convención de ingreso bruto** (2026-08-03, branch `chore/03082026-quality-core`, 3 commits): the deductions backlog item was mostly shipped already (persisted `deduction_type` + typed settle deductions + Naturaleza filter, Aug 1); what changed is the **accounting convention**, decided by the operator: the expected income now stays **gross** at settlement (only follow-ups shrink it) and the deduction counts as **payment credit** through the new `ExpenseRecord.source_income` FK (`paid = liquid children + linked deductions`, wired into `paid_amount_subquery`, the serializer fallback and the settle service's `_paid_total`). Utility turned asymmetric on purpose — expected utility subtracts deductions, liquid utility keeps subtracting only operational spending (lesson #24). Migration `content/0173` backfills the FK from the `income:<pk>:settlement` stamp and re-grosses the netted parents using each deduction's stored split (exact: Jimmy junio $81.546→$86.400). Deductions are born in Liquidar only: the write serializer rejects manual set/clear of `deduction_type` and forces `register_in_pocket` off. Surfaces: `deduction_type` joined the expense `choice_filters` (panel + export + MCP list for free), `_expense_meta` gained `deductions_total`/`deductions_by_type`, the export carries 'Tipo de deducción' + 'Ingreso origen' columns, the frontend catalog lives once in `utils/accountingDeductions.js`, and the Gastos tab gained the type multi-filter, Operativo/Deducciones chips, the 'Deducciones (año)' KPI with per-type breakdown, an origin tooltip on the pill and a pocket-toggle-free edit modal for deduction rows. Tests: settle suite rewritten to gross (28/28), serializer guard/read (+5), views/MCP/export slices green, +1 E2E (spec 7/7), quality gate 0 errors, flows `admin-accounting-income-crud` and `admin-accounting-expenses-crud` both covered with all declared outcomes. Deploy note: dashboard expected totals rise $9.708 (the two Jimmy incomes re-gross) and expected utility now also subtracts `deductions_total`.

- **Det. técnico tab perf round** (2026-08-03, branch `chore/03082026-quality-core`, 7 commits `9f73fcb4..`): the one business-edit tab still slow after PR #146 was diagnosed as **pure render** — zero requests on open; the cost was a per-requirement module/item checkbox matrix (~38k DOM nodes at 12 epics / 144 reqs / 60 commercial items), 20 flat `v-for` sections, ~320 `v-auto-resize` textareas thrashing layout, a per-entry full-document `JSON.stringify` and the eagerly mounted JSON sub-tab. Fixes: JSON pane behind `v-if` + a boolean-source refresh watcher; reference watch + stringify-equality guard replacing the `{deep:true}` watcher (all write paths replace the section object); idle warm-up of the editor chunk via a hoisted shared loader (hidden pre-mount rejected: `v-auto-resize` would measure `display:none`); link grids extracted to `TechnicalRequirementLinks.vue` behind a per-requirement "Vincular alcance/ítems (n)" disclosure with computed-Set lookups; 14 sections collapsed by default (Set + `v-if` à la ProposalSectionsTab, only Propósito open, live counts in headers, `expand-all` prop keeps the 58-test unit suite intact via a 1-line helper change). Backend: change-log **queryset** slice (SQL LIMIT 50 vs materialize-all — benefits every `ProposalDetailSerializer` consumer), composite indexes `(proposal,-created_at)` + `(proposal,change_type)` (migration `0172`), `effective_total_for_proposal` reuses prefetched sections. **Measured** (scratchpad Playwright harness, dev, inflated proposal): warm switch **2909→155 ms** (0.46× the Secciones reference tab; target was ≤1.5×), DOM delta **38,259→105**, long tasks **2579→0 ms**, cold **4525→134 ms**. Verification: 58/58 unit, 8/8 + 2/2 E2E, 14/14 backend, repo-wide quality gate exit 0, flow map fresh. Known pre-existing gap: `admin-proposal-edit` declares an `error` outcome no spec covers (no `@outcome` tags in the spec — predates this round).

- **Income-filter incident closed + restorable saved-tab bases + MCP/export gaps** (2026-08-03, branch `chore/03082026-quality-core`, 3 commits): the backlog item "Solo esperados no discrimina" turned out **already shipped** (#145/#148) — prod verified current via read-only checks (migration `accounts/0041` applied, build + backend live, MCP `list_income` shows ~42 paid / ~25 pending expected incomes, all 42 liquid records linked to their parent). Root cause of the operator's symptom: a pre-deploy browser SPA session running the old bundle, whose filter engine silently ignored the tab's `paymentStatus` key (lesson #23 in `lessons-learned.md`); a reload fixed it. Hardening shipped: (1) **`SavedFilterTab.base_filters` restore point** — migration `accounts/0042` backfills seeded names from the registry even when the live filters drifted; seed/reset/create populate it; `ProposalFilterTabs` shows a drift dot and offers "Restaurar filtros" / "Fijar como base" across the 5 tab-bearing panel views (semantic comparison via exported `sameFilters` — inactive keys ignored because stored tabs carry the expanded default shape while seeded bases stay sparse); `restoreTab` cancels pending debounced auto-saves so they can't overwrite the restore. (2) **MCP `list_income`** now builds from `base_queryset` (kills a latent `FieldError` and a per-row N+1) and exposes the `payment_status` filter (`pending`/`partial`/`paid`). (3) **Income exports** gained an "Estado de cobro" column (CSV/XLSX + year workbook, which now also uses `base_queryset`); the boundary rule lives once in `payment_status_for()` (`content/serializers/accounting.py`), reused by the row serializer and the export. Tests: +12 backend, +14 frontend unit, +1 E2E reproducing the whole incident (drifted "Solo esperados" → dot → restore → "Cobro: Sin pagos" chip back, 12/12 green); quality gate 0 errors under the widened 3-app scan; flow map updated (`admin-accounting-filters` declares display+success, covered). Pending data nit: prod income #114 "Tendalux - Entrega 30%" ($960.000, feb-2026) says "Pagado" in notes but has no linked settlement — operator to confirm and liquidate via the UI.

- **QA Campaign Rounds 6–8 + canonical test-quality core** (2026-07-23 → 2026-07-24, PRs #122–#124 merged; Round 8 audit in the open `test/24072026-qa-campaign-round-8` branch): Round 6 (#122) closed all 9 🟡 partial + 10 ❌ P3/P4 flows; Round 7 (#123) added the last giant-component units + P3 flows; #124 adopted the fleet canonical test-quality core (`scripts/quality/*` + `scripts/test_quality_gate.py` + `.testquality.yml`, pre-existing junk pinned in `.junk-baseline.json`). **Round 8 = the first-ever `test-audit`**: a whole-corpus junk inventory via the quality gate (`--semantic-rules strict`) + `scripts/flow_coverage_audit.py` — 301 no-interaction E2E tests, 168 flow-tag-mismatch, 164 weak-assertion, 147 `duplicate_coverage`, 72 junk-only + 38 missing flows (of 299). **Key finding**: the 147 `duplicate_coverage` are *not* mergeable — 115 are the same generic test name (`"handles error"`, `"sets error on failure"`) across *different* describe blocks (a naming problem → rename, not merge) and 32 are cross-component structural twins (parallel coverage → keep); and 0 no-subject tests exist. So both approved safe-cleanup batches (delete-no-subject, merge-duplicates) were empty and **no tests were changed** this round. Also surfaced: 67 `misplaced_file` gate errors in `accounts` that CI never sees (its backend gate scans only the `content` app, per `.testquality.yml backend_app_name`). Report at `docs/audits/test-audit-2026-07-24.md`; rewrite/rename work deferred to Round 9. Counts re-verified against the codebase: 77 model files, 299 components, 96 pages, 35 stores, 59 composables, **256 backend / 373 frontend-unit / 219 E2E** test files (5,133 backend test funcs), content/accounts URL patterns 284/94.

- **Accounting correctness + display standards + QA cycles #2–#3** (2026-07-17 → 2026-07-22, PRs #113–#116, all merged to `main`):
  - **Pocket draws → company utility (#114)**: a pocket egreso attributed to a partner is now mirrored as a **company-ledger expense fully assigned to that partner** (category personal) so it reduces liquid utility and the partner's participation — before, it landed on the personal ledger and silently drained the pocket. Migration `0164_pocket_draws_to_company_ledger` normalizes existing pocket-linked personal expenses; the expense form converts personal+pocket submissions the same way with a warning hint; the pocket modal's OUT selector is relabeled "Atribuir a" (Empresa/Gustavo/Carlos) with attribution prefilled from the split. The liquidate modal defaults destination to **Bolsillo ProjectApp** with a "Registrar el día exacto de pago" toggle; `period_date` on income/expense accepts a full date (YYYY-MM still normalizes to day 1) and `period_label` shows the day; statements remain strictly month-only.
  - **Display standards (#115/#116)**: emails now format COP through the `cop` template filter → `format_cop_email` (millions apostrophe, autoescape off in TXT bodies) and dates through `bogota_date`; `format_bogota_date`/`format_bogota_datetime` emit the **"Jue, 16 jul 2026" weekday standard** propagated to proposal/diagnostic/accounting notification emails; the frontend gained the central `utils/formatDate.js` (formatDate/formatDateTime/formatDayMonth — Bogotá TZ via `Intl.formatToParts`, literal parsing of date-only strings to avoid the UTC day-shift). #116 extended the fix to phase-onboarding + team payment-status notifications in `accounts/views.py`. Also in #115: `AccountingStatCard` gained a `clickable` prop and the expected-income card opens the read-only `ExpectedIncomeDetailModal` (company expected incomes of the card month).
  - **QA cycles #2–#3 (#113)**: PDF challenges badge-panel backend coverage + remaining accounting filter branches; accounting store statement/collection/cycle operations, error paths and pocket tiebreak; statement/transaction/alias audit labels; statement-ledger, card-catalog, collections and quick-create E2E flows; `BaseDropdown` now resolves NuxtLink for `to`-items. Gate compliance: plain asserts for the no-assertion rule and a test rename for `forbidden_token` — the CI gate runs in DEFAULT semantic-rules mode (strict SUPPRESSES rules; validate pre-push without `--strict`).
  - **Methodology refresh (2026-07-22, QA campaign fase 1)**: counts re-verified — 76 model files (content models 56), 299 components, 96 pages, 35 store files, 59 composables, **254 backend / 346 frontend-unit / 209 E2E** test files, content migrations at `0164`, content/accounts URL patterns 284/94 — across `technical.md`, `architecture.md`, `tasks_plan.md`, the PRD and this file.

- **Accounting maturation + panel dashboard command center + PDF redesign** (2026-07-07 → 2026-07-16, PRs #91–#110, all merged to `main`):
  - **Income liquidation + dashboard redesign (#110, merged 2026-07-16)**: `IncomeRecord.Kind` = expected/liquid/lost — a liquid record links the projection it settles via the `expected_income` FK (`limit_choices_to={'kind':'expected'}`), `lost` is a write-off excluded from projection/utility aggregates; `/panel/accounting/incomes` gained the `IncomeLiquidateModal.vue` flow (`income-liquidate-<id>` actions), a `Pérdidas` tab, and `lost_total`/`received_pct` KPIs; expenses expose paid/pending via a `paid_amount` subquery. The `/panel/` dashboard page was rebuilt as a **multi-module command center** on one consolidated endpoint (`build_dashboard_core` + accounting `year_totals` extracted into `content/services/panel_dashboard_service.py`), with a dedicated dashboard store + component set and redesigned flows registered in flow-tags/flow-definitions/USER_FLOW_MAP. Also: view-map default filter tabs + `ViewMapSettings` (migration `0163`), proposal panel UX fixes (hosting seeding, toggle polarity, currency inputs, bold terms), currency-aware money + branded badge panels in the proposal PDF.
  - **Accounting wave**: pocket↔records bidirectional sync + sortable columns + hero utility chart (#103); credit-card catalog with server-side computed debt (quota − available) + statement UI editing/PDF + 8-day statement reminder (#105 — models `credit_card.py`/`credit_card_statement.py`, services `accounting_statement_service.py`/`accounting_statement_reminder_service.py`; alias normalization + reversal flag follow-up); summary cards for card debt + current-month expected income (#106); chart month-label distribution fix (#109); cuentas de cobro + hosting expiry notices + cycle history + KPIs (#94).
  - **PDF/emails wave**: proposal PDF redesign — layout engine + tables/badges/KPIs on comercial + técnico (#99); documents dual friendly/professional PDF template (#100); emails page tabs + configurable greeting/footer/signer defaults (#101); "+ IVA"/"+ Tax" investment suffix (#92); hour packages + scope clause + free AI module with conditions (#91, July 2026 rates with "Extranjero" replacing "México").
  - **Panel UX / infra**: centered pagination, admin status select, inactive clients tab, seedable `SavedFilterTab` rows, drag-and-drop reassign (#93); unattended frontend rebuild hardening — heap OOM + alerting for silent failures + MCP hygiene (#98); markdown parser 502 hang fix + `append_document` MCP tool (#108); LinkedIn summary English-default UTF-8 fix (#104); main greened via document serializer field-set tests + quality-gate no-assertion fixes (#102).
  - **QA cycle #1 (2026-07-16, #111)**: accounting record-endpoint/hosting-cycle/change-log backend tests (`views/accounting.py` 85.7→95.2%, serializers 95.6→99.4%); 4 panel-dashboard section component specs (folder ~36→99% statements); stable `income-form-concept` locator in the incomes E2E; new `admin-accounting-hosting-billing-cycles.spec.js` covering the P1 hosting-billing and P2 hosting-cycles flows (flow-definitions 2.45.0). Carry-over documented: ~20 backend lines in `views/accounting.py`, `stores/accounting.js`+`panel_dashboard.js` at ~63% unit, and E2E gaps statements/card-catalog/collections (P2) + quick-create (P3) — the first four are QA cycle #2's scope.
  - **Methodology refresh (2026-07-16, cycle #2 pass)**: counts re-verified — 76 model files, 286 components, 96 pages, 35 stores, 59 composables, **251 backend / 338 frontend-unit / 207 E2E** test files, content migrations at `0163`, content/accounts URL patterns 283/94 — across `technical.md`, `tasks_plan.md` and this file.

- **Documents module UX redesign + emoji rendering (screen & PDF)** (2026-07-10, branch `feat/10072026-documents-ui-redesign`, 6 commits): `/panel/documents` aligned to the panel's canonical patterns and extended with a gallery view. Frontend — store normalizes errors via `normalizeApiError` with Spanish fallbacks; page feedback moved to `usePanelNotify` (duplicate/copy/move/delete/PDF/save) with a persistent `BaseAlert` + retry for load failures; delete uses the shared `ConfirmModal`; CTA/search/empty states/skeletons moved to Base components (`DocumentListSkeleton` silhouettes, contextual `BaseEmptyState` per search/tags/folder/global); the 3 document `v-html` sinks now go through new `DocumentMarkdownBody.vue` (DOMPurify-sanitized — MCP-written markdown is untrusted; single owner of the previously duplicated `md-*` styles; variants default/full/mini). New gallery: `DocumentCard` (sanitized markdown mini-preview from the list serializer's new `content_excerpt`, status overlay, 2 tag chips + `+N` tooltip, 44px kebab, real edit link), `DocumentsGrid` (TransitionGroup; dashed subfolder drop-target cards), `DocumentsToolbar` (search + `BaseSegmented` Lista/Galería), `DocumentsTable` extracted verbatim; toggle persists via `useDocumentViewMode` (`projectapp-documents-view-mode`, default `list` to protect E2E); page size 10↔12; motion = accounting `data-enter` stagger + grid enter/move/leave + 150ms out-in view swap + hover elevation + drop scale, all gated by `prefers-reduced-motion`. Emojis — `:shortcode:` → Unicode with a single source of truth `frontend/assets/emoji/shortcodes.json` (~190 GitHub-style entries) consumed by `utils/emojiShortcodes.js` (renderer, skips code spans) and `backend/content/services/emoji_shortcodes.py` (applied in `markdown_to_blocks`, covers panel + MCP + seeds); PDFs now render emojis in monochrome via `NotoEmoji-Regular.ttf` (OFL, in `frontend/assets/fonts/`) — `pdf_utils` gained `_sanitize_pdf_text` + mixed-font run primitives (`_draw_mixed_string`/`_mixed_string_width`/`_draw_mixed_centred`) wired through `_draw_line_with_links` and every direct-draw site incl. both TOCs; cluster policy: ZWJ → member emojis, skin tones → base, unglyphed codepoint → strip (never tofu); missing font degrades to legacy stripping with one warning; `_strip_emoji` untouched so proposal/contract/diagnostic PDFs are byte-identical in behavior. New E2E flow `admin-document-gallery` (4 tests) registered in flow-tags/flow-definitions/USER_FLOW_MAP; full documents E2E slice green (25 tests); backend slices green (pdf_utils_emoji 16, document_pdf emoji 7, serializer 23, regression 125+257). Known gap: `admin-document-pdf-download` E2E spec still missing (pre-existing).

- **Proposals hardening + editor UX + panel consistency** (2026-07-06, branch `feat/06072026-proposals-panel-improvements`, 21 commits): backend — effective-total/analytics/alerts logic extracted from `views/proposal.py` (5,834 → ~3,700 lines) into `proposal_totals_service` / `proposal_analytics_service`; `proposal_audit.log_proposal_change` helper + `transaction.atomic` on respond/comment/create/update and both from-JSON paths; strict per-section-type `content_json` validation (`section_content_schemas.py`, unknown keys pass, numeric strings pass) wired into section update, from-JSON and defaults serializers (covers the MCP connector); new add/delete section endpoints (`proposals/<id>/sections/create/`, `proposals/sections/<id>/delete/`, FR guarded by `fr_has_confirmed_selection`); prefetch + cache-friendly serializers kill the public-detail N+1 (query-guard test pins ≤20); throttles on respond/comment/share/followup (10/min), PDF (6/min), magic-link (5/min). Frontend — SectionEditor split into 16 `section-forms/` components (1,298 → ~340 lines) with a `sectionFormRegistry`; edit.vue tabs (activity/prompt/json) extracted (3,196 → ~2,450); notifications unified on `usePanelNotify` and the legacy `usePanelToast`/`PanelToast` deleted repo-wide; the fake '✓ Guardado' bug fixed (feedback now collapse-on-success / notify-on-error); dirty tracking with 'Sin guardar' badges + collapse/route/unload/refresh guards (`useDirtyTracker`, autosave seam via `defineExpose({save,isDirty})`); drag & drop section reorder (wired the dormant `reorderSections` + endpoint); add/delete sections UI; editor status colors tokenized. Panel — `admin-auth` enforced on `/panel/emails` + stubs with a guard test walking `pages/panel/**`; `accounting/cards` registered in nav/catalog; redirect stubs typed `viewType: 'redirect'`; broken `/panel/email-templates` link fixed; breadcrumbs derived from panelNav (LinkedIn/MCPs/Cards gained breadcrumbs; sections resolve from nav ancestors so the parallel nav-localization branch merges clean); `proposal_clients.js` snake_case rename. New E2E flows registered: `admin-proposal-section-dirty-guard`, `admin-proposal-section-add-delete`. B4 completed in follow-up commits: `ProposalSectionsTab.vue` + `ProposalGeneralTab.vue` extracted; `edit.vue` ends at 1,374 lines (was 3,205). Work done in a git worktree (`projectapp-wt-proposals`) with `E2E_PORT=3210` due to a parallel session sharing the main tree.

- **Panel Modules + MCP Connectors + Client Document Portal** (late Jun – Jul 2026, PRs #77–#80 + uncommitted working tree):
  - **Accounting module** (#79, 2026-07-03): superuser-only double-ledger bookkeeping (`Ledger` = COMPANY/GUSTAVO/CARLOS) with a partner-split invariant (a personal-ledger record must be 100% the owner's), enforced in `PartnerSplitMixin.clean()`. 9 models (`content/models/accounting_base.py` + income/expense/hosting/recurring/ads/pocket/card-snapshot/change-log/settings), views `content/views/accounting.py` (dashboard + charts + per-ledger CRUD, `IsSuperUser`) + `accounting_export.py` (CSV/XLSX section export + full-year workbook), services `accounting_*`. Weekly card-debt reminder Huey task (`send_card_debt_reminder`, Fridays, re-alerts every 2 days until a snapshot clears the cycle). Frontend `/panel/accounting/*` + `accounting.js`; 12 `admin-accounting-*` E2E flows covered.
  - **MCP connectors for claude.ai** (#77/#78, 2026-07-02/03): remote Model-Context-Protocol connectors exposing panel modules as claude.ai custom connectors. `McpConnector` + `McpRequestLog` models; token-auth JSON-RPC endpoint `content/views/mcp_blog.py` (Origin/DNS-rebinding defense + activity log); tool package `content/mcp/*` (blog, documents, proposals, diagnostics, clients, tasks, accounting; seeded inactive by migrations `0129`/`0131`/`0136`). Management UI `/panel/mcps` (superuser-gated: generate/rotate one-time token URL, toggle active, connection-activity feed). The `client-report` skill now publishes session reports to the Documents MCP after writing the local `.md` (#80).
  - **Client document-signing portal (uncommitted)**: `/platform/documents` — the client landing page after first login. Lists the main contract (`requires_signature`) first + annexes, downloads branded PDFs, and click-to-accept signs the main document, gated on a **verified email** (6-digit OTP: `POST /api/accounts/email/verify/request/` + `/confirm/`, `UserProfile.email_verified`, migration `0037`). Signing records `signed_at/signed_by/signature_name/signature_ip/signature_user_agent` and fires best-effort team milestone notifications (`accounts/services/client_flow_notifications.py`: first login, email validated, document signed). Backend `accounts/document_views.py` + `serializers_documents.py`; store `platform-documents.js`; E2E `platform-client-documents.spec.js` (portal/email-validation/sign, P1, all passing).
  - **Project scope items (uncommitted)**: `ProjectScopeItem` layer between `ProjectPhase` and `Requirement` (chain Project → ProjectPhase → ProjectScopeItem → Requirement), mirrored from accepted-proposal functional-requirement groups by `accounts/services/technical_requirements_sync.py`; re-sync overwrites proposal-authored content unless a card was taken over (`Requirement.content_overridden`). Migration `accounts/0038_project_scope_item.py`; rendered on the board via `GET /api/accounts/projects/<id>/scope-items/`.
  - **Proposal discount-offer (uncommitted)**: manual "Enviar oferta de descuento" action on `/panel/proposals/:id/edit` (shown only when `discount_percent > 0` + client email) → preview `proposal_urgency` email → `POST /api/proposals/:id/discount-offer/send/` (`ProposalEmailService.send_urgency_email(force=True)`). Never auto-sent. Flow `admin-proposal-discount-offer-send` (P2) + spec.
  - **Methodology refresh (2026-07-04)**: re-verified all Memory Bank counts (75 models, 226 components, 90 pages, 31 stores, 53 composables, 199 backend / 290 frontend-unit / 191 E2E tests, content migrations at 0137) and documented the above features across `technical.md`, `architecture.md`, `tasks_plan.md`, the PRD, and this file.

- **Blog SEO — prerendered posts + publish-triggered rebuild** (Jun 13, 2026):
  - **Motivation**: Production is a static `nuxi generate` build served by Django (`serve_nuxt` reads files from disk per request). Blog posts were never in the prerender route list **and** both blog pages fetched in `onMounted`, so all ~62 published posts served the SPA shell: generic `<title>Project App.</title>`, no meta description, no canonical, no JSON-LD, zero article text. WhatsApp/LinkedIn previews (no JS execution) showed nothing; Google relied on second-wave JS rendering. Additionally the sitemap emitted `/blog/<slug>` URLs that are not routes at all under i18n `strategy: 'prefix'` (client-side 404s).
  - **Frontend**: `pages/blog/[slug].vue` and `pages/blog/index.vue` now fetch via `await useAsyncData` + `$fetch` (SSR-compatible), hydrating the Pinia blog store; server-side fetches use new `runtimeConfig.apiInternalOrigin` (env `PRERENDER_API_ORIGIN`, falls back to `DJANGO_DEV_TARGET`). Unknown slugs return a real 404 via `setResponseStatus`. Both pages now set document `title` (only og:title existed). Post headlines in the index/related cards became real `NuxtLink` anchors (`@click.stop`) — cards previously navigated via `@click` only, leaving zero crawlable internal links. `nuxt.config.ts` gained `blogPrerenderRoutes()`: fetches `/api/blog/sitemap-data/` at build time and prerenders `/es-co/blog/<slug>` + `/en-us/blog/<slug>` per post; gated by `PRERENDER_BLOG=1` (set in `update-django-template.js`) so dev/CI builds skip it, with `PRERENDER_REQUIRE_BLOG=1` turning an unreachable API into a hard build failure (a deploy silently dropping 62 prerendered posts is a regression). `update-django-template.js` now swaps the build into `backend/static/frontend/` atomically (staging dir + two renames) — gunicorn serves those files per request, so the live dir must never be empty mid-rebuild.
  - **Backend**: new `content/services/frontend_build.py` — `run_frontend_rebuild()` (subprocess `FRONTEND_BUILD_COMMAND`, 30-min timeout, marker file `backend/logs/frontend-build-marker.json` storing last build start vs latest published `updated_at`, collectstatic when `not DEBUG`) and `schedule_rebuild_after_publish()` (never raises; 120s coalescing delay). `content/tasks.py`: `rebuild_frontend_prerender` (`@task(retries=2, retry_delay=600)` + `@lock_task('frontend-rebuild')`) and `nightly_frontend_rebuild` (02:30, same lock, marker-skip). Hooks: blog create/update/delete views (any save touching a published post) and both scheduled-publish tasks. Sitemap now emits blog index + posts per locale with `hreflang` alternates and lastmod; `serve_nuxt` 301s legacy `/blog/*` → `/es-co/blog/*`; `BLOG_PUBLIC_BASE` (LinkedIn shares) points at the `/es-co` canonical. Settings: `FRONTEND_REBUILD_ENABLED` (default `not DEBUG`; explicit `True` + `PRERENDER_API_ORIGIN=https://projectapp.co` in `settings_prod` because it hardcodes `DEBUG=False` *after* `import *`).
  - **Deploy note (VPS)**: Huey runs the build, so the server needs `node_modules` kept in `frontend/` (the deploy flow currently `rm -rf`s them after building — the rebuild task will `npm` rebuild slower without them) and npm reachable from the `projectapp-huey.service` environment (`FRONTEND_BUILD_COMMAND` env can wrap with `bash -lc 'source ~/.nvm/nvm.sh && npm run build:django'`). No gunicorn restart involved anywhere — `serve_nuxt` reads from disk per request.
  - **Verification**: `pytest content/tests/services/test_frontend_build.py` (14 new), `TestServeNuxtLegacyBlogRedirect` (4 new) + `TestServeSitemapXml` (10, updated to locale URLs) all green. Real `nuxi generate` with `PRERENDER_BLOG=1` against local API: post HTML emitted in both locales with real title/description/og:image/canonical/BlogPosting JSON-LD and full article text. Design-token check clean.

- **Platform — Hosting Subscriptions reworked to stored-card automatic billing** (May 20, 2026):
  - **Motivation**: The hosting module billed each cycle through one-shot Wompi card/PSE/Nequi transactions, so the client had to re-pay manually every period. The seller wants the client to enter a card **once** and have every renewal charged automatically at the service expiration date, with card as the only payment method.
  - **Wompi integration**: Switched from one-shot transactions to **payment sources** (stored card). Flow: tokenize card → `POST /v1/payment_sources` → 3D Secure authentication (3RI protocol, chosen over simple COF to maximize renewal approval rate and avoid declines that prompt cancellations) → `POST /v1/transactions` with `payment_source_id` + `recurrent:true`. `accounts/services/wompi.py` gained `get_acceptance_tokens`, `create_payment_source`, `get_payment_source`, `charge_with_payment_source`; `tokenize_card` now returns the full token dict.
  - **Schema** (migration `0031`): `HostingSubscription` += `wompi_payment_source_id`, `card_brand`, `card_last_four`, `card_exp_month`, `card_exp_year`. `Payment` += `charge_attempts`, `last_charge_error`, `next_retry_at`.
  - **Backend endpoints**: `card_setup_start_view` / `card_setup_status_view` (3DS polling proxy — the frontend cannot hit the private-key payment-source endpoint directly) / `card_setup_confirm_view` (persists card + charges the first open payment) / `payment_charge_stored_view` (manual retry with stored card). Shared helper `_charge_payment_with_source`.
  - **Automatic renewal**: new Huey periodic task `accounts/tasks.py::auto_charge_due_subscriptions` (daily 06:00). Charges every open `Payment` past its `due_date` with the stored card; on failure retries up to 3 times spaced 2 days apart (`next_retry_at`), then suspends the subscription and notifies client + admins.
  - **Frontend** (`payments.vue`): PSE/Nequi/Bancolombia removed — card only. New 3DS card-setup modal (renders the 3DS `three_ds_method_data` in iframes — hidden for browser-info/fingerprint, visible for the bank challenge — polled every 2s). Stored-card panel with brand · •••• last4 · expiry, "Cambiar tarjeta", manual "Reintentar cobro" for failed payments.
  - **Cancellation**: deliberately **not** self-service. The card panel tells the client to contact support by email; an admin sets the subscription to `cancelled` (the cron filters on `status=active`). No `auto_renew` field.
  - **Decision rationale**: 3DS/3RI over COF was the operator's explicit call — fewer unattended-charge declines means fewer clients using a rejected renewal as an excuse to cancel.
  - **Tests**: `test_subscription_card_setup.py` (16 tests — wompi service, card-setup views, charge-stored, Huey task incl. suspension). Flow `platform-hosting-card-setup` registered in `USER_FLOW_MAP.md` + `flow-definitions.json` (P1, **❌ Missing E2E spec** — the 3DS iframe flow needs a Wompi-sandbox-driven `e2e/platform/platform-hosting-card-setup.spec.js`).
  - **Multi-phase billing follow-up (same date)**: the subscription now bills the **sum of all started phases** at one frequency, not a single proposal. Migration `0032` adds `ProjectPhase.hosting_activated_at`. New service `accounts/services/hosting_billing.py` centralizes per-phase pricing, the project sum, and proration. `_create_subscription_multi_phase` charges only phases whose `hosting_start_date` is null or reached; future-dated phases join later. The billing cron gained `_onboard_due_phases`: when a phase's start date arrives it creates a **prorated** catch-up payment charged at the **full undiscounted rate** (`monthly_base × months ÷ cycle_days × remaining_days` — the frequency discount only rewards a whole prepaid cycle, not a partial catch-up), recomputes `billing_amount`, and updates the next-cycle pending payment. `payments.vue` replaced the 3 plan cards with a per-phase cost table + frequency pills (live recompute). The pills stay editable while the subscription is `pending` (the PATCH realigns the unpaid first payment); the frequency locks once the first payment settles. Decisions taken with the operator: proration via daily cron; frequency editable until the first payment settles, then locked; activation bills only already-started phases. Wompi sandbox test keys live in `backend/.env` — the 3DS flow is testable end-to-end against `sandbox.wompi.co`. `_create_subscription_from_proposal` was removed; `discount_percent` on a subscription is no longer meaningful (each phase carries its own discount) and is left at 0.

- **Proposal — 3 New Additional Modules: Biometric Verification, QR Generator, AI Content Generator with Editorial Calendar** (May 7, 2026):
  - **Motivation**: The seller wanted to expose 3 more selectable add-ons to clients via the calculator. Biometric verification is provider-billed (we don't collect — the integration provider invoices the end client directly), so it follows the `is_invite=True, price_percent=0` pattern of `ai_module` / `integration_conversion_tracking`. The QR generator (25%) and AI content generator (30%) are regular calculator modules. The content generator must explicitly include an **editorial calendar with scheduling/auto-publishing** so the client sees the planning workflow, not just AI text generation.
  - **Catalog (`backend/content/services/proposal_service.py`)**: 3 entries added to both `DEFAULT_SECTIONS` (ES) `additionalModules` and `DEFAULT_SECTIONS_EN` `additionalModules`.
    - `biometric_verification_module` (🪪) inserted after `integration_conversion_tracking`, before `reports_alerts_module`. 6 items: ID document reading + OCR, facial recognition, liveness detection, antifraud + KYC, frictionless digital onboarding, verifications panel. `invite_note` explicitly says a "specialized provider runs the integration and bills the service directly to the end client". No specific provider named (per user requirement).
    - `qr_generator_module` (🔳) and `content_generator_module` (✍️) inserted after `email_marketing_module`, before `i18n_module` — adjacent to the marketing/content cluster. QR has 6 items (instant generation, branded customization, dynamic editable codes, scan tracking, code library, ready-to-use cases like digital menu/WhatsApp link/event check-in/login/surveys/tipping). Content gen has 7 items: AI-assisted writing, brand voice + templates, multichannel (blog/email/social), **visual editorial calendar (monthly/weekly views)**, **scheduling + auto-publishing**, tracking panel, channel integrations.
  - **AI auto-select prompt (`backend/content/views/proposal.py`)**: `CRITICAL_additionalModules_autoselect` extended with 3 detection-hint blocks:
    - Biometric: "biometric verification, KYC, e-KYC, identity verification, facial recognition, liveness, ID document validation, antifraud onboarding, verificación biométrica, validación de identidad, reconocimiento facial, prueba de vida, validación de cédula, onboarding digital, antifraude → biometric_verification_module"
    - QR: "QR, código QR, qr code, dynamic qr, menú digital, código de mesa, link tree, physical-to-digital, scan to action → qr_generator_module"
    - Content gen: "AI content, content generation, generación de contenido, blog AI, copy AI, calendario editorial, content calendar, social media scheduling, programación de publicaciones, scheduled posts, auto-publishing, editorial planning → content_generator_module"
  - **Calculator labels (`frontend/components/BusinessProposal/InvestmentCalculatorModal.vue`)**: 3 bilingual entries added to `groupLabels` so the calculator modal shows the full title instead of falling back to `_other`. Component is otherwise data-driven — no logic change.
  - **Tests (`backend/content/tests/services/test_proposal_service.py`)**: `EXPECTED_ADDITIONAL_MODULE_ORDER` and `CALCULATOR_MODULE_IDS` constants updated with the 3 new ids in their inserted positions. `additionalModules` count assertions changed 13 → 16 in `test_functional_requirements_has_default_groups` and `test_en_functional_requirements_has_7_groups_and_16_modules` (renamed from `_and_13_modules`). 3 new module-specific tests asserting id, icon, item count, flags, percent, and (for content gen) that `'Calendario'` appears in title + `'calendario'`/`'programaci'` appear in items haystack.
  - **E2E**: new spec `frontend/e2e/proposal/proposal-calculator-biometric-module.spec.js` (2 tests) covers the `is_invite` flow — module renders with "Agendar llamada" badge instead of price, and clicking reveals the invite note. Models the AI module pattern from `proposal-calculator-modules.spec.js`. New flow tag `PROPOSAL_CALCULATOR_BIOMETRIC_MODULE` (P2) registered in `frontend/e2e/helpers/flow-tags.js`. The QR + content modules don't need new E2E specs — they're regular `is_calculator_module: true, is_invite: false, price_percent>0` modules already covered structurally by the existing `proposal-calculator-modules.spec.js` (PWA 40%) and `proposal-calculator-new-modules.spec.js` (email/i18n/giftcards) patterns.
  - **Important non-changes**: no DB migration (catalog is JSON defaults). No model change. No backfill: existing proposals keep their `content_json` snapshot — they only see the new modules if re-edited (the merge logic in `proposal_service.py:2300, 2351` injects defaults into JSON payloads that omit them). The seller's request was explicitly "de aquí para adelante, los nuevos proyectos" — this is the natural behavior of the current architecture.
  - **Verification**: `pytest content/tests/services/test_proposal_service.py --no-cov` → 80 passed (was 78); `jest test/components/InvestmentCalculatorModal.test.js` → 51 passed; `playwright e2e/proposal/proposal-calculator-biometric-module.spec.js` → 2/2 passed.

- **Proposal — New `roi_projection` Section (Web-only Sponsor Outcomes Block)** (May 5, 2026):
  - **Motivation**: The Albunmanía proposal (id=91) read like a tech purchase — six features in `executive_summary.highlights`, technical reasons in `investment.valueReasons`, dense `functional_requirements`. The sponsor needs quantified business outcomes (daily visualizations, ad reach, MRR, payback, year-1 revenue) **before** the price ask. First explored as data-only patches but discovery showed `proposal_summary.kpis` is dead schema and `conversion_strategy.result` is rendered inside `<p>` (breaks `<table>`). Decision: ship a dedicated section type instead of hacking existing copy.
  - **Backend — model + migration**: `ProposalSection.SectionType.ROI_PROJECTION = 'roi_projection'`. Migration `0118_roi_projection_section.py` clones the canonical pattern from `0102_value_added_modules_section.py` — `AlterField` choices + `RunPython` backfill that creates one disabled empty row per proposal and bumps `order >= 4` by `F('order')+1`. Reverse function deletes the rows but does **not** decrement orders (rollback+reapply unsupported by design).
  - **Backend — defaults**: `DEFAULT_SECTIONS` (es) and `DEFAULT_SECTIONS_EN` gain a `roi_projection` entry at `order=4`; all existing entries from `order >= 4` shifted +1 via regex script. Pre-existing collision `final_note=14, next_steps=14, technical_document=15` simultaneously fixed to 14/15/16 in both ES + EN lists. `EXPECTED_DEFAULT_SECTION_COUNT` 16 → 17 in `tests/constants.py`.
  - **Backend — serializer key map**: `SECTION_KEY_MAP['roiProjection'] = 'roi_projection'` so the JSON template/import endpoints (`get_proposal_json_template`, `create_proposal_from_json`, `update_proposal_from_json`, `export_proposal_json`) handle the section automatically. Reverse `SECTION_TYPE_TO_KEY` derives.
  - **Backend — PDF (web-only)**: per user decision, the section is **intentionally absent** from `SECTION_RENDERERS` in `proposal_pdf_service.py`. The generator's section loop was tightened to also skip the TOC entry when both `is_paste=False` and `renderer is None` — making web-only sections fully invisible in the PDF (no orphan TOC links). Behavior is now consistent with `proposal_summary` and `process_methodology` which also lack renderers.
  - **Frontend — public component**: `frontend/components/BusinessProposal/RoiProjection.vue` renders KPI cards (icon, value, label, sublabel, source), scenarios block (icon, label/name, metric rows with optional `emphasis` flag for totals), and an optional CTA note banner. Receives `content` prop (single object). Uses semantic design tokens (`bg-surface`, `text-text-brand`, `bg-primary-soft`, `border-border-default`); legacy `esmerald` tokens explicitly avoided per `frontend/CLAUDE.md`.
  - **Frontend — dispatcher gotcha**: `getSectionProps` in `pages/proposal/[uuid]/index.vue` flat-spreads `content_json` for unrecognized section types. The component expects `{ content }` (single prop), so a named branch was added: `if (section.section_type === 'roi_projection') return { content: { ...content, index: paddedIndex } };`. Without this, the section mounted but the inner data was never bound (h2/cards rendered empty in production until the dispatcher was fixed).
  - **Frontend — admin editor**: bloque `<template v-else-if="sectionType === 'roi_projection'">` in `SectionEditor.vue` with vuedraggable for both KPIs and scenarios; per-metric `emphasis` checkbox; emoji picker via `EmojiIconField`. 3 new cases in `sectionEditorUtils.js` (`buildFormFromJson` / `formToJson` / `formToReadableText`); `formToJson` filters empty rows and omits `emphasis: false` to keep payload tidy.
  - **Frontend — XSS hardening of `linkify`**: HTML is now escaped before URL replacement, with a small whitelist re-allowing `<b>`, `<strong>`, `<i>`, `<em>`, `<br>` (the inline tags admin copy historically uses). Closes the silent XSS surface introduced by `v-html="linkify(content.subtitle)"` in `RoiProjection.vue`. Existing 20 linkify tests still green; 6 new escape tests added.
  - **Migration silent no-op caveat**: `ProposalDefaultConfig (es)` row in prod had the old 16-section list, so the migration's `_defaults_index(language).get('roi_projection')` returned `None` and skipped row creation in all 32 proposals (the order bump still ran). Recovered via Django shell using `from content.services.proposal_service import DEFAULT_SECTIONS, DEFAULT_SECTIONS_EN` (canonical source, not DB-backed config) — created the 32 missing rows, populated Albunmanía (id=91) with approved copy, and updated `ProposalDefaultConfig.sections_json` to the new 17-section list so future proposals via panel/UI will include the section.
  - **Albunmanía populate**: 6 KPIs (≈90K visualizations/day, 8–20M sponsor reach, $34M MRR mes 6, $280M year-1 revenue, 5–9 mo payback, $80–200M ad value equivalent) + 3 scenarios (Conservative/Realistic/Optimistic with MAU, daily impressions, merchants, sponsor anchor, MRR, accumulated year 1) + closing CTA. Investment used $122M COP (sum of 3 payment milestones; the existing `total_investment=$48M` stored value is the 40% upfront — flagged as a separate historical bug).
  - **Tests**: 11 backend pytest cases (`test_roi_projection.py`: enum membership, ES/EN defaults at order=4, count==17, unique orders, key map, PDF renderer absent, ORM persistence, disabled-from-public-filter), 6 frontend unit (`useLinkify-html-escape.test.js`), 8 frontend unit (`admin-sectionEditorUtils-roi.test.js` round-trip + filters), 2 E2E (`proposal-roi-projection.spec.js` enabled-render + disabled-skip). Backend tests pass; E2E spec needs the dev-server's hot-reloaded build to stabilize.
  - **Flow registry**: `proposal-roi-projection` (P1) registered in both `frontend/e2e/flow-definitions.json` and `docs/USER_FLOW_MAP.md`. Description of `admin-proposal-section-edit-form` updated from "12 section types" to the actual 17.
  - **Pending**: stabilize the new E2E spec (currently flaky — gateway `addInitScript` ordering); kill ratty leftover Nuxt dev servers between `npm run e2e` runs (`reuseExistingServer: !CI` lets them linger and block subsequent `nuxi generate` runs with PID-lock errors).

- **Proposal Multi-Send — Single Email Referencing N Proposals** (May 5, 2026):
  - **Motivation**: Sellers frequently work multiple proposals for the same client (Fase 1, Fase 2, …) and were sending each as a separate email. The client had to chase multiple threads. Goal: one email with N proposals listed as numbered phases, plus one PDF attachment per proposal, triggered from the lightning-bolt menu.
  - **Backend — `services/proposal_email_service.py`**: new `send_multi_proposal_to_client(proposals)` reuses `_build_initial_email_context(proposal)` per proposal to build the per-phase dict (`title`, `proposal_url`, `total_investment`, `currency`, `email_intro`, `payment_options`, `total_duration`, `payment_summary`), generates one `EmailMultiAlternatives` with N attachments via the shared `_attach_commercial_pdf` helper, and writes one `EmailLog` per proposal sharing a `group_uuid` (+ `group_size`, `pdfs_attached`) in metadata. Returns `{ok, reason, detail}` matching the single-send contract; `detail` carries `group=<uuid>`. `import uuid` is module-level.
  - **Backend — `services/proposal_service.py`**: new `ProposalService.send_multi_proposals(proposals)` orchestrates per-proposal side effects using `BusinessProposal.Status.*` enum (no raw strings), then dispatches the single email. Three branches: `draft → sent` + `sent_at` + `expires_at` if missing; `expired` or `expires_at <= now` → reopens (`viewed` if `view_count>0` else `sent`) + extends `expires_at` to `now + default_expiration_days(language)`; `sent/viewed/negotiating` → resets `sent_at`/`reminder_sent_at`/`urgency_email_sent_at` only. Validates same-client across all proposals (raises `ValueError` otherwise). Calls `_schedule_email_tasks(proposal)` per proposal after delivery to (re)agendar Huey reminders + urgency. Returns delivery dict merged with `transitions` map (`{id: 'sent'|'resent'|'reopened'}`).
  - **Backend — `views/proposal.py`**: new `send_multi_proposal(request, proposal_id)` FBV gated by `IsAdminUser`. Body `{ proposal_ids: [...] }`. Validates: list non-empty, integer coercion, **dedups via `dict.fromkeys`**, max 10 (`MAX_PROPOSALS_PER_EMAIL`), primary has `client_id`, all selected belong to same client. ORM query uses `prefetch_related('sections')` so `_build_initial_email_context` doesn't trigger N+1. Builds `ordered` list with a single-pass `seen` set, prepending `primary` only when missing. Requires `len(ordered) >= 2`. Writes one `ProposalChangeLog` per proposal with action label (`sent`/`resent`/`reopened`). Reuses `_proposal_admin_response` helper.
  - **Backend — `urls.py`**: `path('proposals/<int:proposal_id>/send-multi/', send_multi_proposal, name='send-multi-proposal')`.
  - **Backend — `services/email_template_registry.py`**: new entry `proposal_multi_sent_client` with editable `subject`, `greeting`, `body`, `closing` and `available_variables: [client_name, phases_count]`. Sample context renders 2 sample phases.
  - **Backend — templates**: new `emails/proposal_multi_sent_client.html` + `.txt` iterate `phases` with badge "Propuesta N de M", title, intro, link, exec summary line, and payment breakdown table. Same brand palette and signature block as `proposal_sent_client`.
  - **Backend — `views/proposal.py` (list_proposals)**: new `?client_id=` query param so the modal can fetch only the current client's proposals. Status filter remains.
  - **Frontend — `stores/proposals.js`**: `fetchProposalsByClient(clientId)` and `sendMultiProposal(primaryId, ids)` actions.
  - **Frontend — `components/BusinessProposal/admin/ProposalActionsModal.vue`**: new action `send-multi` (visible whenever `client_email` is set), emits `@send-multi` event.
  - **Frontend — `components/BusinessProposal/admin/ProposalMultiSendModal.vue`** (new): `BaseModal` size `xl`. Lists candidate proposals categorized into 3 status groups (`Borradores`, `Enviadas/Vistas/Negociación`, `Expiradas`) via `STATUS_GROUPS` matchers. Pre-filter excludes `TERMINAL_STATUSES = {finished, accepted, rejected}` so the expired matcher reduces to `status==='expired' || is_expired`. Current proposal is always in `selectedIds` and its checkbox is disabled. `MAX_PROPOSALS_PER_EMAIL = 10` enforced in both `toggle()` and `canSend` computed. `loadError` ref surfaces fetch failures. Reusable `formatMoney` extracted to `frontend/utils/formatMoney.js`. Test ids: `proposal-multi-send-modal`, `proposal-multi-send-option-<id>`, `proposal-multi-send-cancel`, `proposal-multi-send-confirm`.
  - **Frontend — `pages/panel/proposals/[id]/edit.vue`**: imports the new modal, wires `@send-multi="showMultiSendModal = true"`, `handleMultiSendSent({count, error})` shows toast + refreshes data.
  - **Tests**: 6 new pytest cases — `TestSendMultiProposalToClient` (4: N attachments + group_uuid metadata, rendered HTML mentions each phase + numbering, empty proposals rejected, missing primary email rejected) and `TestSendMultiProposalsService` (2: status transitions for draft/expired/sent + mixed-clients ValueError).
  - **E2E flow map updates**: `flow-definitions.json` adds `admin-proposal-multi-send` (P1, expectedSpecs: 1). `docs/USER_FLOW_MAP.md` adds the full flow with steps and the suggested spec path. `admin-proposal-send` description and steps extended to mention `email_intro` and PDF attachment, with `knownGaps` reflecting them. Coverage Index updated.
  - **Pending**: write `e2e/admin/admin-proposal-multi-send.spec.js`. Long-term: if multi-send is used heavily, consider moving the synchronous PDF generation loop to a Huey task (cap of 10 keeps the worst case bounded for now).

- **Proposal Initial Email — Refreshed Layout, `email_intro` Field & PDF Attachment** (May 5, 2026):
  - **Motivation**: The initial proposal email shown to clients was a generic card with title and total only. The team wanted a richer layout matching an approved template (saludo, alcance, link, executive summary, payment breakdown, signature) and the commercial PDF attached automatically so the client receives the full proposal in one place.
  - **Backend — model + migration**: `BusinessProposal.email_intro = TextField(blank=True, default='')` (migration `0117_add_business_proposal_email_intro.py`). Empty falls back to a default derived from `title`. Exposed in `ProposalDetailSerializer` (read) and `ProposalCreateUpdateSerializer` (write).
  - **Backend — `services/proposal_email_service.py`**: new `_build_initial_email_context(proposal)` reads `paymentOptions` from the `INVESTMENT` section and `totalDuration` from the `TIMELINE` section (using `ProposalSection.SectionType` enum, no raw strings). Computes `payment_summary` (`'40/30/30'`) by parsing percentages. New shared `_attach_commercial_pdf(email, proposal) -> bool` helper attaches the PDF and is reused by both `send_proposal_to_client` and `send_acceptance_confirmation` (eliminating the previous duplicated try/except block and unifying the filename casing to `Propuesta_Comercial_<Cliente>.pdf`). `safe_slug` and `uuid` moved to module-level imports.
  - **Backend — templates**: rewritten `emails/proposal_sent_client.html` + `.txt` with phase card, link block, executive summary line (Inversión · Duración · Pagos), payment breakdown rows iterating `payment_options`, validity badge, editable closing block, and signature with `team@projectapp.co | +57 323 812 2373 | www.projectapp.co`.
  - **Backend — `services/email_template_registry.py`**: `proposal_sent_client` gains editable `closing` field and new `available_variables` (`email_intro`, `total_duration`, `payment_summary`). Sample context expanded for the preview.
  - **Frontend — `pages/panel/proposals/[id]/edit.vue`**: new `BaseTextarea` with `data-testid="edit-email-intro"` between client snapshot fields and project type/market type grid. `email_intro` added to the form reactive object and to `hydrateFormFromProposal`.
  - **Tests**: 5 new pytest cases — `TestSendProposalToClientEnrichedContext` (helper context reads sections, fallback when `email_intro=''`, PDF attached with correct filename, PDF failure does not block send, end-to-end render places `email_intro`/`payment_options`/`total_duration` in the HTML).
  - **Verification**: 13 related tests green; `python manage.py check` clean; design tokens audit clean on the touched Vue file.

- **Proposal Expired — Recover Editing & Auto-Reopen On `expires_at` Extension** (May 4, 2026):
  - **Motivation**: An admin tried to edit a proposal in `expired` status and the JSON re-import endpoint refused the payload because the original JSON carried the past `expires_at` (`ProposalFromJSONSerializer.validate_expires_at` rejected anything `< now()`); same blocker affected `ProposalCreateUpdateSerializer` for the form path. Even when the admin successfully bumped the date to the future, `status` remained `expired` because no code recomputed it on update — `is_expired` returns `True` whenever `status == 'expired'`, so the proposal looked expired forever.
  - **Backend — `serializers/proposal.py`**: both `validate_expires_at` methods now treat the value as valid when it equals the bound instance's existing `expires_at`. `ProposalCreateUpdateSerializer` reads `self.instance.expires_at`; `ProposalFromJSONSerializer` reads `self.context['proposal'].expires_at` (the JSON view now passes `context={'proposal': proposal}`). The future-only check still fires when the value is genuinely changing.
  - **Backend — `services/proposal_service.py`**: new `ProposalService.reopen_if_unexpired(proposal, *, old_status)` mutates `proposal.status` in memory only when `old_status == EXPIRED` and the new `expires_at > now()`. Reverts to `viewed` when `proposal.view_count > 0`, else to `sent` — mirrors the `expire_stale_proposals` cron that only marks `sent`/`viewed` proposals as expired. Uses the model field `view_count` directly (no `ProposalViewEvent` query).
  - **Backend — `views/proposal.py`**: `update_proposal_from_json` calls the helper *before* `proposal.save()` so the status mutation rides the single save (no double save). `update_proposal` calls it after `serializer.save()` (status is not part of the serializer's normal payload) and persists with `update_fields=['status']` only when the helper fires. Both views log the auto-reopen via `ProposalChangeLog` with the description `'Auto-reopened from expired after expires_at moved to the future (<old> → <new>).'` — the form path reuses the existing tracked-fields loop with a description override; the JSON path inlines the create.
  - **Tests**: 5 new pytest cases in `test_proposal_views.py`:
    - `TestAdminUpdateProposal.test_update_succeeds_for_expired_proposal_when_expires_at_unchanged`
    - `TestAdminUpdateProposal.test_update_reopens_status_when_expires_at_moved_to_future_no_views`
    - `TestAdminUpdateProposal.test_update_reopens_to_viewed_when_proposal_was_visited`
    - `TestUpdateProposalFromJSON.test_update_from_json_succeeds_for_expired_proposal_when_expires_at_unchanged`
    - `TestUpdateProposalFromJSON.test_update_from_json_reopens_status_when_expires_at_moved_to_future`
  - All 20 tests in `TestAdminUpdateProposal` + `TestUpdateProposalFromJSON` green; `python manage.py check` clean.
  - **E2E flow map updates**: `flow-definitions.json` adds two new admin flows (217 → 219): `admin-proposal-reopen-from-expired` (P1) and `admin-proposal-update-from-json` (P2). `docs/USER_FLOW_MAP.md` documents both with steps + branches; both flagged ❌ Missing (backend covered, no Playwright spec yet).
  - **Pending**: write `e2e/admin/admin-proposal-reopen-from-expired.spec.js` and `e2e/admin/admin-proposal-update-from-json.spec.js`.

- **Proposal Send — `email_delivery` Surface & Inline Dropdown Defense-in-Depth** (May 4, 2026):
  - **Motivation**: An admin moved a proposal `draft → sent` from the panel and the client never received the email, while the UI showed a generic success toast. Two compounding bugs: (1) `ProposalEmailService.send_proposal_to_client` swallowed every failure path (placeholder email, disabled template, render/SMTP exception) into `logger.exception` and returned `bool` that the view ignored, so `POST /proposals/<id>/send/` always returned 200 even when the email had not been dispatched; (2) the inline status dropdown's endpoint `update_proposal_status` only changed the `status` field on `draft → sent` and **never invoked the email service at all**.
  - **Backend — `proposal_email_service.py`**: `send_proposal_to_client` now returns `{ ok, reason, detail }` constructed via the module-local `_delivery()` helper. Reasons: `sent`, `placeholder_email`, `template_disabled`, `send_failed`, `unexpected_error`.
  - **Backend — `proposal_service.py`**: `_send_initial_email`, `send_proposal`, and `resend_proposal` propagate the delivery dict to callers. The outer `try/except` in `_send_initial_email` returns `unexpected_error` instead of bubbling, so the status change is never rolled back.
  - **Backend — `views/proposal.py`**: new private helper `_proposal_admin_response(request, proposal, delivery=None)` consolidates the three sites that build `ProposalDetailSerializer + email_delivery`. `send_proposal` and `resend_proposal` always include `email_delivery`; `update_proposal_status` includes it only on `draft → sent`. The `draft → sent` branch of `update_proposal_status` now **delegates to `ProposalService.send_proposal`** (defense-in-depth so the dropdown can never silently mark a proposal as `sent` without dispatching the email).
  - **Frontend — `stores/proposals.js`**: `sendProposal`, `updateProposalStatus`, and `resendProposal` propagate `email_delivery: response.data?.email_delivery ?? null`.
  - **Frontend — `pages/panel/proposals/index.vue`**: `confirmSend`, `handleInlineStatusChange`, and `handleResend` show a red toast with `email_delivery.detail || email_delivery.reason` when `ok === false`, instead of a generic success.
  - **Tests**: 6 new/updated cases in `test_proposal_email_service.py` (validate the `{ok,reason,detail}` contract for sent/placeholder_email/template_disabled/send_failed); 5 new cases in `test_proposal_views.py::TestInlineStatusChange` (draft→sent invokes `send_proposal`, propagates email_delivery on ok and on failure, returns 400 on ValueError, no email on other transitions); 2 new cases in `TestAdminSendProposal` (200 with email_delivery.ok=True/False); 3 cases in `TestResendProposal` updated; 4 new cases in `frontend/test/stores/proposals.test.js` (sendProposal & updateProposalStatus propagate email_delivery; null when omitted).
  - **E2E flow map updates**: `flow-definitions.json` v2.35.0 adds `admin-proposal-resend` and updates the descriptions of `admin-proposal-send` + `admin-proposal-inline-status-change` to mention `email_delivery`. `docs/USER_FLOW_MAP.md` marks both existing flows 🟡 Partial (failure-feedback toast and draft→sent dispatch not yet asserted in E2E) and adds a new ❌ Missing flow `admin-proposal-resend` with suggested spec `e2e/admin/admin-proposal-resend.spec.js`.
  - **Pending**: extend `admin-proposal-send.spec.js` and `admin-proposal-inline-status.spec.js` to mock `email_delivery.ok=false` paths, and write the new `admin-proposal-resend.spec.js`. Also pending: actual diagnosis of the production proposal `id=85` (queries provided to the user; needs `DJANGO_SETTINGS_MODULE=projectapp.settings_prod`).

- **Documents Tab Reorganization & doc_refs Email Attachment** (Apr 22, 2026):
  - **Motivation**: "Documentos" and "Documentos & Plantillas" tabs were mixing concerns — listing documents, sending emails, and showing unrelated template sections. Separation of concerns: the Documents tab is purely for listing/downloading/uploading documents; sending belongs exclusively in the Emails tab. The proposal's aside with diagnostic templates (Diagnóstico de Aplicación, Diagnóstico Técnico, Anexo) was moved to the Diagnostic Documents tab where it belongs.
  - **Proposal — `ProposalDocumentsTab.vue` rewrite**: Section 1 = unified list (Contract with generate/download/draft actions + Propuesta Comercial PDF + Detalle Técnico PDF). Section 2 = "Documentos adjuntos" list + upload form. Removed: "Enviar documentos al cliente" section, `SendDocumentsModal` usage, `selectedMainDocs`/`selectedAdditionalDocIds` state. Tab label changed from `'Documentos & Plantillas'` → `'Documentos'`. `TabSplitLayout` wrapper + `ProposalDiagnosticTemplatesSection` aside removed from `panel/proposals/[id]/edit.vue`.
  - **Diagnostic — `DiagnosticDocumentsTab.vue` rewrite**: Section 1 = unified list (NDA with PDF download/draft/edit params + 3 MD templates loaded from `GET /api/diagnostic-templates/`). MD actions: copy content, download .md, vista previa. Section 2 = "Documentos adjuntos" list + upload form (unchanged). Removed: "Enviar documentos al cliente", `SendDiagnosticDocumentsModal`, `attachConfidentiality` checkbox (user picks NDA via modal instead).
  - **New `AttachFromDocumentsModal.vue`**: shared modal (props: `open`, `source: 'proposal'|'diagnostic'`, `entity`, `templates`, `preselected`; emits `@close`, `@attach(picked: [{key, label, ref}])`). `proposalDocs()` builds contract/draft/PDFs/uploaded docs. `diagnosticDocs()` builds NDA variants/template slugs/uploaded attachments. Checklist UI with confirm button.
  - **New `useDocRefsAttachment.js` composable**: `docRefs`, `removeDocRef`, `handleDocRefsAttach` (merge-by-key), `appendDocRefsToFormData`, `resetDocRefs`. Shared by both email tabs.
  - **ProposalEmailsTab + DiagnosticEmailsTab updated**: "Adjuntar desde Documentos" button opens `AttachFromDocumentsModal`. Doc refs rendered with emerald badge. `handleSend()` calls `appendDocRefsToFormData(formData)`; `resetForm` calls `resetDocRefs`.
  - **Backend — new `backend/content/views/_doc_refs.py`**: shared `DocRefError` exception + `parse_doc_refs_field(request)` that handles JSON parsing and list validation (eliminates ~22 duplicated lines from both proposal.py and diagnostic.py).
  - **Backend — `_resolve_proposal_doc_refs(proposal, doc_refs)`**: pre-batches `ProposalDocument` queries; supports `contract_pdf`, `contract_draft`, `commercial_pdf`, `technical_pdf`, `proposal_document:<id>`. Integrated into `_parse_composed_email`.
  - **Backend — `_resolve_diagnostic_doc_refs(diagnostic, doc_refs)`**: pre-batches `DiagnosticAttachment` queries; supports `nda_final`, `nda_draft`, `template:<slug>`, `attachment:<id>`. Integrated into `_parse_diagnostic_email`.
  - **`diagnostic_template.py`**: `_TEMPLATES_DIR` renamed to `TEMPLATES_DIR` (public) to avoid private-symbol cross-module import.
  - **Deleted**: `SendDocumentsModal.vue`, `ProposalDiagnosticTemplatesSection.vue`, `SendDiagnosticDocumentsModal.vue`, `frontend/test/components/admin-SendDocumentsModal.test.js`, `frontend/test/components/ProposalDiagnosticTemplatesSection.test.js`, `frontend/e2e/admin/admin-proposal-documents-send.spec.js`.
  - **Tests updated**: `admin-ProposalDocumentsTab.test.js` updated (store mock: `uploadProposalDocument`/`deleteProposalDocument`; no `SendDocumentsModal`; asserts unified list + "Documentos adjuntos"; confirms "Enviar documentos al cliente" absent). `admin-diagnostic-email-documents.spec.js` pruned (removed NDA checkbox, attach_confidentiality POST, send-to-client section tests; added "documents tab renders Documentos list and uploader" test).
  - **Verification**: 59 backend tests green (composed email views + diagnostic email markdown attachment + diagnostic template views + diagnostic attachments/emails). 23 frontend tests green (ProposalDocumentsTab + ProposalEmailsTab).
  - **Pending**: Orphaned store actions `sendProposalDocuments` (proposals.js) and `sendDiagnosticAttachments` (diagnostics.js) still exist but are unused by UI — cleanup deferred. Backend endpoints `POST /api/proposals/{id}/documents/send/` and `POST /api/diagnostics/{id}/attachments/send/` still registered but no longer called from frontend.

- **UX — Dynamic Browser Tab Titles & Task Board Order** (Apr 20, 2026):
  - **`layouts/admin.vue`**: added `useHead(() => ({ title: ... }))` with a reactive inline route map (`_panelRouteMap`, `_panelDynamic`) covering all 24 static panel routes and 5 dynamic `[id]/edit` routes. Title format: `Project App (ViewName)` when on a named view, `Project App.` otherwise. Updates reactively on navigation.
  - **`layouts/platform.vue`**: same pattern — `_platformRouteMap` (12 routes) + `_platformDynamic` (11 regex patterns for project sub-routes and collection account/client detail pages).
  - **`pages/panel/tasks/index.vue`**: moved `macro` board to first position in the `boards` array — `Macro-Tareas` now renders before `Sin periodicidad`, `Semanal`, `Mensual`.

- **View Catalog — Diagnósticos Públicos Section** (Apr 20, 2026):
  - `frontend/config/viewCatalog.js`: added a new `'public-diagnostics'` section between `'public-proposals'` and `'admin-panel'` with one entry: `Diagnóstico público` (`/diagnostic/:uuid`, `audience: 'public'`, `viewType: 'detail'`). Catalog total: 71 → 72 views. The diagnostic public page (`pages/diagnostic/[uuid]/index.vue`) was the only functional non-redirect page missing from the catalog.

- **MarkdownAttachmentModal — Diagnostic Template Copy Buttons** (Apr 20, 2026):
  - New prop `showDiagnosticTemplates: Boolean` (default `false`) on `MarkdownAttachmentModal.vue`.
  - When true, renders a "Plantillas base" row with 3 copy-to-clipboard buttons above the markdown textarea — order: Diagnóstico de Aplicación → Diagnóstico Técnico → Anexo. Fetches via existing `GET /api/diagnostic-templates/<slug>/` (lazy, per-slug cache in `reactive({})`).
  - `copyFeedbackTimer` ref tracks the 2 s "¡Copiado!" `setTimeout`; cleared on `resetState` (modal close) and `onBeforeUnmount` — no leak.
  - `DiagnosticEmailsTab.vue` passes `show-diagnostic-templates` to the modal. No backend changes.
  - Tests: 3 new cases in `MarkdownAttachmentModal.test.js` (hidden by default, correct order, fetch+clipboard on click). Fixed `resetModules: true` incompatibility by wrapping the `get_request` mock through a stable `mockGetRequest` function-level variable.

- **Diagnostic Public View — Brand Redesign, PDF Download & Share** (Apr 20, 2026):
  - **`diagnostic/[uuid]/index.vue`**: outer `<div>` gains `data-diagnostic-wrapper` + `diagnostic-public` class; all `gray-*` tokens replaced with brand tokens (`esmerald/xx`, `lemon`); cards use `rounded-3xl` + custom shadow; footer buttons use `esmerald`/`esmerald-dark`; three new fixed FAB buttons added bottom-right: `<ShareDiagnosticButton>`, `<DownloadDiagnosticPdfButton>`, and a dark-mode theme toggle.
  - **`DownloadDiagnosticPdfButton.vue`** (new): fixed FAB at `bottom-[4.75rem] right-4`; calls `GET /api/diagnostics/public/{uuid}/pdf/`; Blob download with slugified title + date suffix; spinner while generating.
  - **`ShareDiagnosticButton.vue`** (new): fixed FAB at `bottom-[8.5rem] right-4`; opens a Teleport modal with copy-link (2.5 s feedback) + native Web Share API fallback; bilingual (es/en via inline `i18nStrings`); `<Transition name="share-modal">` slide-up animation.
  - **`useDiagnosticDarkMode.js`** (new): module-level singleton `isDark` ref (not per-component); `watch` registered at module load to apply `data-theme="dark|light"` to `[data-diagnostic-wrapper]` and persist to `localStorage('diagnostic-dark-mode')`; `onMounted` rehydrates from storage.
  - **Public section components** (`CategoriesSection`, `CostSection`, `DeliveryStructureSection`, `ExecutiveSummarySection`, `PurposeSection`, `RadiographySection`, `ScopeSection`, `SectionHeader`, `TimelineSection`): updated to use brand/esmerald tokens and dark-mode-aware classes.
  - **Backend** (`diagnostic.py`): new `download_public_diagnostic_pdf` view — `GET /api/diagnostics/public/<uuid>/pdf/` — gated by `PUBLIC_VISIBLE_STATUSES`, uses new `DiagnosticPdfService.generate(diagnostic)`, returns `attachment` PDF with `safe_pdf_filename`. Route added in `content/urls.py`.
  - **`DiagnosticPdfService`** (`backend/content/services/diagnostic_pdf_service.py`, new): mirrors `ProposalPdfService` — per-section-type renderers walk `content_json`, shared helpers from `pdf_utils.py`.
  - New E2E spec registered in `flow-definitions.json` + `flow-tags.js`.
  - New frontend tests: `TimelineSectionDiagnostic.test.js`, `DefaultsShell.test.js`.

- **Value Added Modules — Order Fix & Hide-when-empty** (Apr 20, 2026):
  - **Backend** (`proposal_service.py`): swapped `value_added_modules` to `order=10` (was 9) and `functional_requirements` to `order=9`. Migration `0103_swap_value_added_modules_order.py` created (pending commit/apply).
  - **Frontend** (`proposal/[uuid]/index.vue`): `displayPanels` computed now hides `value_added_modules` when none of its `module_ids` resolve against the current `functional_requirements` groups — prevents the section from rendering an empty card.
  - **`useSellerPrompt.js`**: narrative flow updated to include "Incluido sin costo (módulos base)" between functional_requirements and investment; `index` field for `value_added_modules` corrected to `"10"`.

- **Business Proposal — Calculator Module Reorder + Seller Prompt Auto-Select** (Apr 21, 2026):
  - `additionalModules` array in `proposal_service.py` reordered (ES + EN): payment integrations first (DIAN, regional, international), then PWA, AI, conversion tracking, reports, email marketing, i18n, live chat, dark mode.
  - `reports_alerts_module` renamed to "Reportes y Alertas vía Correo, WhatsApp o Telegram"; 6th item (WhatsApp 💚) added to `items`.
  - `_seller_prompt` in `proposal.py` gained `CRITICAL_additionalModules_autoselect` with keyword→module detection map. When requirements mention DIAN/PSE/Stripe/AI/chatbot/etc., Claude sets `default_selected: true` on the matched module and adapts its copy to the brief.
  - `CRITICAL_functionalRequirements` count phrase made count-agnostic.
  - Tests updated: new module order asserted; `reports_alerts_module` test now asserts 6 items + WhatsApp title.

- **Business Proposal — Personal Slug URL** (Apr 21, 2026):
  - New `slug` field (`SlugField, unique=True, blank=True, max_length=120`) on `BusinessProposal`. Auto-generated on `save()` from `ProposalDefaultConfig.default_slug_pattern` (interpolated via `render_slug_pattern`) or `client_name` fallback; collision-free via `resolve_unique_slug` (single `__startswith` DB query + Python set).
  - `ProposalDefaultConfig` gained `default_slug_pattern = CharField(default='{client_name}')`.
  - New shared utilities in `content/utils.py`: `render_slug_pattern`, `resolve_unique_slug`, `safe_slug`.
  - `validate_slug()` in `ProposalCreateUpdateSerializer` enforces format + uniqueness.
  - New URL `proposals/by-slug/<slug>/` delegates to `_serve_public_proposal` helper; UUID route fully preserved for backward compatibility. `'slug'` added to `tracked_fields` for audit log.
  - Migrations `0104` (populate + dedupe + `unique=True`) + `0105` (`default_slug_pattern` field).
  - Frontend: `frontend/utils/slugify.js` (`toSlug()` NFD normalize); `fetchPublicProposal` UUID/slug branch detection; editable slug input on proposal edit General tab (Save + Regenerate); live pattern preview in `ProposalDefaultsPanel.vue`. All copy-URL and public href references use `slug || uuid`.
  - `public_url` property uses `slug or uuid` as identifier.
  - Tests: `TestBusinessProposalSlug` (3 cases: auto-gen, collision suffix, preserved); `TestBusinessProposalPublicUrl` updated; 4 new by-slug API tests.

- **FIX — Admin-auth Middleware Hardening & Dark Mode** (Apr 20, 2026):
  - **`admin-auth.js`**: middleware rewritten — simplified conditional logic, removed unused branches.
  - **Blog calendar** (`panel/blog/calendar.vue`): dark mode token fix.
  - **Tasks page** (`panel/tasks/index.vue`): dark mode token fix.
  - **`proposals.js` store**: minor fix; 16 new assertions added to `proposals.test.js` for the affected code path.

- **Diagnostic Detail — UI Parity & NDA Email Attachment** (Apr 20, 2026):
  - **Sticky title format**: replaced `formatMoney(amount) + currency` with `formatInvestment(amount, currency)` → format `$1.234.567 COP` identical to business proposal sticky header. Guard condition changed from `v-if="investment_amount"` to `v-if="investment_amount > 0"`.
  - **Removed size_category from General tab**: the `<select>` (Tamaño), its reactive `form.size_category` init, `syncFormGeneral` sync, and `handleUpdate` payload key all removed. The DB field and `DiagnosticRadiographyForm.vue` usage are untouched — only the general-tab editor dropped it.
  - **Tab width standardization**: removed `max-w-4xl` wrapper from Sections, Activity, and Analytics tabs in `panel/diagnostics/[id]/edit.vue` so they expand to full page width, matching business proposal parity (General stays `max-w-2xl`, Emails/Documents/Prompt/JSON stay `max-w-4xl`).
  - **NDA checkbox in Correos tab** (`DiagnosticEmailsTab.vue`): `attachConfidentiality = ref(false)` checkbox appends `attach_confidentiality: '1'` to the `FormData`; reset in `resetForm`. Backend `_parse_diagnostic_email` reads the flag, calls `generate_confidentiality_pdf(diagnostic)` (returns bytes or None), appends `(nda_filename, pdf_bytes, 'application/pdf')` to attachments, or returns 400 when generation fails (params missing). `nda_filename` via existing `_confidentiality_filename` helper.
  - **Tests**: 2 new backend tests in `test_diagnostic_attachments_and_emails.py` (happy path with monkeypatched PDF bytes + 400 when generator returns None). Redundant double-patch simplified to single service-module patch.

- **Admin Panel — Unified Defaults Page** (Apr 20, 2026):
  - **Motivation**: The sidebar "Sales" section had a "Proposal defaults" link buried mid-list. The diagnostic defaults page (`/panel/diagnostics/defaults`) existed (backed by `DiagnosticDefaultConfig` from Apr 18) but had no sidebar entry — only a header button from the diagnostics list. The UX goal: one top-level "Defaults" entry that switches between proposal and diagnostic config modes.
  - **Sidebar** (`frontend/config/panelNav.js`): item renamed `'Proposal defaults'` → `'Defaults'`, moved to position 0 of the `commercial` section, href changed from `/panel/proposals/defaults` → `/panel/defaults`.
  - **New unified shell** (`frontend/pages/panel/defaults.vue`): header with dynamic "Volver a…" back link, segmented-control mode switch ("Propuesta" / "Diagnóstico") synced to `?mode=` query param (computed, no separate ref), lazy-loads each panel via `defineAsyncComponent`. Layout: `admin`, middleware: `admin-auth`.
  - **Extracted panel components** (`frontend/components/panel/defaults/`): `ProposalDefaultsPanel.vue` (full 6-tab proposal defaults UX extracted from the old page — General, Secciones, Det. técnico, Emails, Prompt, JSON) and `DiagnosticDefaultsPanel.vue` (full 5-tab diagnostic defaults UX — General with 60/40 default payments, Secciones, Emails, Prompt, JSON). Both had `definePageMeta` and their top navigation header stripped; all tabs, state, and API logic are unchanged.
  - **Backward-compatible redirects**: `frontend/pages/panel/proposals/defaults.vue` → `/panel/defaults?mode=proposal` (preserves `?tab=`); `frontend/pages/panel/diagnostics/defaults.vue` → `/panel/defaults?mode=diagnostic` (preserves `?tab=`). Existing E2E tests that navigate to old URLs continue to pass via redirect.
  - **Internal links updated**: `panel/diagnostics/index.vue:21` (header button), `panel/proposals/index.vue`, `panel/index.vue` (dashboard shortcut), `panel/proposals/email-templates.vue` (redirect chain), `config/viewCatalog.js`.
  - **No backend changes**: `DiagnosticDefaultConfig` (60/40 payment default), `proposals/defaults/`, and `diagnostics/defaults/` endpoints are unchanged.
  - **Simplify pass**: `mode` ref + watcher replaced with a single `computed(() => route.query.mode === 'diagnostic' ? 'diagnostic' : 'proposal')` — router is the sole source of truth. Both panels wrapped in `defineAsyncComponent` for code-splitting (ProposalDefaultsPanel is ~1518 lines with large sub-component tree).

- **Diagnostic Analytics — Full Parity with Proposal Analytics** (Apr 20, 2026):
  - **Motivation**: `DiagnosticAnalytics.vue` was a ~136 LOC stub showing only 4 KPIs, a basic section heatbar, and 3 lifecycle timestamps. The proposal analytics tab (`ProposalAnalytics.vue`, ~1000 LOC) delivers engagement score, funnel, comparison with global averages, device breakdown, sessions history, activity timeline, suggested actions, and CSV export. The goal was full parity minus features that don't apply to the diagnostic data model (`view_mode`, `ProposalShareLink`, `subsection_key`).
  - **Backend — `diagnostic_analytics` rewrite** (`backend/content/views/diagnostic.py`):
    - Added `_ACTIVE_ENGAGEMENT_STATUSES` frozenset using `WebAppDiagnostic.Status` enum (replaces stringly-typed status checks).
    - Added `_compute_diagnostic_engagement_score(recent_sessions, sections_data, has_cost_engagement, unique_ips, days_since_last_view, revisit_count)` — same 0–100 heuristic formula as proposals but without view_mode/share_link components.
    - Response now includes: `total_views`, `unique_sessions`, `first_viewed_at`, `last_viewed_at`, `time_to_first_view_hours`, `time_to_response_hours`, `responded_at`, `sections`, `skipped_sections`, `device_breakdown`, `sessions`, `timeline`, `funnel`, `comparison`, `engagement_score`.
    - **N+1 eliminations (3)**: funnel `reached_sessions` folded into main `section_stats` annotate (eliminates 8 per-section count queries); comparison uses a single `DiagnosticViewEvent.annotate(Min('viewed_at'))` map instead of per-diagnostic helper calls (2N → 2 queries); sessions loop uses `.prefetch_related('section_views')[:50]` (eliminates 50 N+1 queries).
    - Device classification: tablet (iPad-first) / mobile / desktop from user-agent — identical to proposal logic.
    - `first_viewed_at` computed on-demand from `DiagnosticViewEvent` (no model field needed).
    - `skipped_sections`: enabled section types not present in any `DiagnosticSectionView`.
    - Funnel: ordered by `DiagnosticSection.order`, `drop_off_percent` = `(1 - reached/max_reached) * 100`.
    - Comparison: excludes the current diagnostic; averages over all other diagnostics with at least one view event.
  - **Backend — `export_diagnostic_analytics_csv`** (new view): `GET /api/diagnostics/<id>/analytics/csv/` → `text/csv` attachment with 3 sections (SECTION ENGAGEMENT, SESSION HISTORY, CHANGE LOG). Same column structure as proposal CSV export minus view_mode and share_links columns. Gated by `IsAdminUser`.
  - **Backend — `backend/content/urls.py`**: added `path('diagnostics/<int:diagnostic_id>/analytics/csv/', ...)` under the diagnostics block.
  - **Frontend — `DiagnosticAnalytics.vue` rewrite** (~963 LOC): 12 collapsible `<details>` blocks in proposal order — CSV export button, engagement score (color-coded ≥70/≥40/<40), 6 summary KPI cards, global comparison (3 metrics with ↑↓ arrows), funnel (single tab — no executive/technical toggle), device breakdown, suggested actions (adapted for diagnostic sections, no investment/technical references), skipped sections warning, section interest heatmap + top-2 insights, section engagement table, activity timeline (`DiagnosticChangeLog` types with icons/colors), sessions history (no Mode column). Reuses `useTooltipTexts().analytics` composable for all tooltips. CSV download via `window.open(...)`.
  - **Tests — new `backend/content/tests/views/test_diagnostic_analytics.py`** (10 tests): empty state, `first_viewed_at`/`time_to_first_view_hours`, `skipped_sections` excludes visited, device breakdown (iPad → tablet), funnel drop-off, engagement score 0–100 range, timeline includes change logs, comparison excludes self, CSV attachment headers/content, CSV requires admin (401/403). All 10 pass.
  - **Tests — updated `test_web_app_diagnostic.py`**: `test_analytics_endpoint_summary` updated to use `unique_sessions` (was `total_sessions`) and `purpose_row['total_time_seconds']` (was `total_time_spent_seconds`) — keys removed in the simplify pass.
  - **`/simplify` pass**: eliminated 3 N+1 patterns, removed backwards-compat legacy response keys, replaced stringly-typed status checks with enum constants, removed narration comments.

- **Diagnostic Template Documents Audit & Restructure** (Apr 20, 2026):
  - **Motivation**: The three diagnostic template Markdown files (`diagnostico_aplicacion_es.md`, `diagnostico_tecnico_es.md`, `anexo_es.md`) had structural inconsistencies, redundant sections, and tone mismatches that could confuse clients or create maintenance risk.
  - **Audit findings**: 5 cross-doc duplications (identical Roadmap text, near-identical Escala de Severidad, same classification tables, repeated hallazgo plantilla, repetitive alcance phrase); 4 internal redundancies in técnico doc (plantilla repeated twice, Resumen Ejecutivo misplaced before Estructura de la Entrega, empty Recomendaciones subsection, orphaned table in Hallazgos); 2 high-severity structural issues (category 8 in comercial broke tone with a dense tech-only bullet list; Cronograma's fixed 5-day distribution conflicted with the `{{duration_label}}` placeholder).
  - **Comercial fixes**: Rewrote cat. 8 in accessible narrative tone; replaced fixed "Día 1/2-4/5" cronograma with relative Fase inicial/evaluación/consolidación; collapsed empty Recomendaciones section; promoted Resumen Ejecutivo and Roadmap as subsections of Estructura de la Entrega; grouped Costo + Cronograma under new "Términos Comerciales" parent; updated TOC; aligned alcance canonical phrase; fixed "vive en…vive en" repetition.
  - **Técnico fixes**: Eliminated duplicate plantilla table inside Hallazgos (kept only the one in Estructura de los Hallazgos); moved Resumen Ejecutivo inside Estructura de la Entrega (as first subsection after Radiografía); removed empty Recomendaciones subsection; refactored run-on pruebas de integración sentence; updated TOC.
  - **Anexo fixes**: Corrected ambiguous ranges note in 5.3; added clarifying `blockquote` for `{{test_coverage_label}}`; rewrote circular "alcance/alcance" phrase in sección 4; split run-on conclusion sentence.
  - **Transversal**: Unified the canonical alcance phrase across all three docs ("El diagnóstico se ejecuta exclusivamente sobre los repositorios de código fuente (backend y frontend). No se evalúa infraestructura del servidor, procesos de despliegue ni sistemas de monitoreo externos."); added HTML sync comments (`<!-- Mantener sincronizado con... -->`) on both classification tables and both roadmap sections to flag cross-doc dependency.

- **Diagnostic Public View — Sidebar Index & No Default Header** (Apr 20, 2026):
  - **Motivation**: align the client-facing diagnostic URL (`/diagnostic/{uuid}`) with the proposal public view pattern. The page had `layout: 'default'` (showing the Nuxt site header) and a centered pill-style nav as section index. Proposals use `layout: false` and a floating sidebar index (`ProposalIndex.vue`).
  - **New component** (`frontend/components/WebAppDiagnostic/public/DiagnosticIndex.vue`): adapted from `ProposalIndex.vue` — hamburger toggle fixed top-left, backdrop blur, panel fullscreen on mobile / floating left on desktop, numbered badges with visited checkmarks, emit `navigate`. Removed proposal-specific `viewMode`/`language` props and `switchToDetailed`/`backToGateway` action buttons.
  - **Page changes** (`frontend/pages/diagnostic/[uuid]/index.vue`): `definePageMeta({ layout: false })` (was `'default'`); removed the "Project App / title / Preparado para" header block; replaced pill nav with `<DiagnosticIndex :sections :current-index :visited-ids @navigate>`; added `visitedIds = ref(new Set())` + `markSectionVisited(id)` helper (used in `selectSection` and `onMounted`). Prev/next controls and accept/reject footer unchanged.
  - **Simplify pass**: extracted duplicate visited-tracking into `markSectionVisited`; simplified `v-if` guard; removed dead `update:open` emit from `DiagnosticIndex.vue`.

- **Diagnostic Markdown Attachment & Diagnostic Template Tab in Proposal** (Apr 19, 2026):
  - **Motivation (Feature 1 — Templates tab)**: The 3 static markdown files used to build diagnostics (`diagnostico_aplicacion_es.md`, `diagnostico_tecnico_es.md`, `anexo_es.md`) were buried in `_legacy/` with no consumer. Sellers had to ask for a copy or dig through the repo. Added a "Documentos & Plantillas" tab to the proposal admin detail page to expose them with copy-to-clipboard, download, and inline preview buttons.
  - **Motivation (Feature 2 — Markdown attachment)**: When a diagnostic is in `negotiating` status, the seller needs to compose and attach custom branded PDF documents (e.g., expanded scopes, annexes) directly from the email composer, without uploading pre-built PDFs.
  - **Backend — diagnostic_template.py** (new view): `GET /api/diagnostic-templates/` → list 3 templates (slug, title, filename, size_bytes, updated_at); `GET /api/diagnostic-templates/<slug>/` → full content_markdown. Slugs hardcoded in a module-level `TEMPLATES` dict, path resolved via `pathlib.Path(__file__).parent.parent / "templates" / "diagnostics"`. No path traversal possible (slug validated against the dict). Both views gated by `IsAdminUser`.
  - **Backend — _email_attachment.py** (new shared helper): Extracted the 40-line markdown→PDF view body into two reusable functions: `inline_pdf_response(pdf_bytes, filename)` builds the `HttpResponse` with `Content-Disposition: inline`; `render_markdown_pdf_response(request, *, client_name)` validates `title` + `markdown`, calls `DocumentPdfService.generate_from_markdown()`, and returns the response (or 400/500 on error). Both proposal and diagnostic markdown attachment views are now 3 lines each.
  - **Backend — diagnostic.py additions**: `generate_diagnostic_email_markdown_attachment` (POST `/api/diagnostics/<id>/email/markdown-attachment/`) + `download_draft_confidentiality_pdf` refactored to use `inline_pdf_response`. `generate_email_markdown_attachment` added to proposal views.
  - **Backend — URLs**: 4 new patterns: `diagnostic-templates/`, `diagnostic-templates/<slug>/`, `diagnostics/<id>/email/markdown-attachment/`, `proposals/<id>/proposal-email/markdown-attachment/`.
  - **Backend — utils.py**: `coerce_bool(value, default=True)` uses DRF's `BooleanField.TRUE_VALUES` (handles bool/str/None without the stringified-default bug); `safe_slug(value, fallback='document')` guards `slugify(value or '') or fallback` (protects against `slugify(None)` → `'none'`). Both hoisted from inline helpers across views.
  - **Frontend — ProposalDiagnosticTemplatesSection.vue**: New component. Fetches template list on mount via `request_http.js`. Renders 3 template cards each with "Copiar contenido" (fetches detail, `navigator.clipboard.writeText`, 2 s feedback) + "Descargar .md" (Blob + `<a download>` click) + expandable inline `<pre>` preview. Caches detail response per slug in a local `ref` to avoid repeat fetches.
  - **Frontend — edit.vue (proposals)**: Tab `'Documentos'` renamed to `'Documentos & Plantillas'`; `hasDocumentsTab` condition expanded to include `sent|viewed` (in addition to `negotiating|accepted|rejected`); `ProposalDocumentsTab` (contract/PDFs sub-section) still only renders for `negotiating|accepted|rejected`.
  - **Frontend — MarkdownAttachmentModal.vue**: Moved from `BusinessProposal/admin/` to `components/` root. Key refactor: prop changed from `proposalId: [Number, String]` to `endpoint: String` (caller constructs the full API path). Enables reuse from both the proposal and diagnostic email tabs.
  - **Frontend — DiagnosticEmailsTab.vue**: Import `MarkdownAttachmentModal` + `useMarkdownAttachmentHandler` + `DIAGNOSTIC_STATUS`. When `diagnostic.status === 'negotiating'`, shows "Crear documento desde markdown" button. On `@attach`, pushes the File to `attachments` + shows success toast.
  - **Frontend — New utilities**: `utils/emailAttachments.js` (`validateEmailAttachments`, `ALLOWED_EXTENSIONS`, `MAX_FILE_SIZE`); `composables/useMarkdownAttachmentHandler.js` (encapsulates attach-to-list + toast); `stores/proposals_constants.js` (frozen `PROPOSAL_STATUS` object).
  - **Conftest**: Added `diag_client_profile` and `diagnostic` shared fixtures to `content/tests/conftest.py`, replacing local-only copies in multiple test files.
  - **Tests**: Backend — 50 tests passed; `test_value_added_modules.py` and `test_diagnostic_email_markdown_attachment.py` also added in the same commit. Frontend unit — `ProposalDiagnosticTemplatesSection.test.js`, `MarkdownAttachmentModal.test.js`, `ValueAddedModules.test.js` created (node_modules not installed locally). E2E — `admin-proposal-diagnostic-templates.spec.js` + `admin-diagnostic-markdown-attachment.spec.js` created and registered in `flow-definitions.json` + `USER_FLOW_MAP.md`.
  - **Cleanup rounds**: 3x `/simplify` + 2x "implement discarded findings". Key fixes: `coerce_bool`/`safe_slug` lazy imports hoisted to module top; `props.proposal?.status` → `props.proposal.status` in `ProposalEmailsTab.vue` (required prop, no optional chaining needed); `safe_slug` import moved to first-party group in `document.py`; `business_proposal.py:save()` migrated to `safe_slug(slug_source, 'propuesta')`; conftest fixture double-write replaced with single `save(update_fields=['client_name'])`.

- **Value Added Modules — New Proposal Section Type** (Apr 19, 2026):
  - **Motivation**: Proposals lacked a structured place to present bonus or included-free modules (maintenance period, training, performance monitoring). The section surfaces these as a card grid on the client-facing proposal view, separate from `functional_requirements`.
  - **Backend**: New `section_type = 'value_added_modules'` added to `ProposalSection` choices (migration `0102_value_added_modules_section.py`). Migration seeds the section from the `functional_requirements` default `manual_module` group for pre-existing proposals. `test_value_added_modules.py` verifies `manual_module` group schema in `es` defaults.
  - **Frontend**: `components/BusinessProposal/ValueAddedModules.vue` — public-facing card grid. Props: `content` (title, intro, footer_note, cards[] with id/icon/title/justification/description), `language`. Shows `🎁` header, "Sin costo" badge, 2-column card grid, optional footer note. GSAP `data-animate` attributes consistent with existing section components. `frontend/test/components/ValueAddedModules.test.js` created (not yet run locally).

- **Client Panel + Diagnostic Filters Enhancements** (Apr 18, 2026):
  - **Edit client modal** (`panel/clients/index.vue`): inline "Editar" button per row opens a prefilled modal (name, email, phone, company). On save calls `proposalClients.updateClient()` — reuses existing `PUT /api/proposals/client-profiles/<id>/update/` endpoint.
  - **Invalid date crash fix** (`panel/proposals/[id]/edit.vue`): `expires_at = "Invalid Date"` crashed the bidirectional days/date sync watcher; guarded with `isNaN(Date.parse(...))` before calling `getExpiryDaysFromStr()`.
  - **Block client deletion with diagnostics** (`accounts/services/proposal_client_service.py`): `delete_orphan_client` now also checks for linked `WebAppDiagnostic` rows. Raises `ValueError('client_has_diagnostics:<count>')`, surfaced as `client_has_diagnostics` code in the API (same pattern as `client_has_proposals` / `client_has_projects`).
  - **Auto-sync investment on module changes**: when a seller toggles a functional_requirements module, investment amount recomputes automatically without a full reload.
  - **Diagnostic saved filter tabs** (`panel/diagnostics/index.vue`): new `useDiagnosticFilters.js` composable — 5 filter dimensions (statuses, investmentMin/Max, createdAfter/Before), saved tabs with localStorage (`diagnostic_filter_tabs`, max 12), URL sync. Same architecture as `useProposalFilters.js`. JSON metrics panel added above the diagnostics table.

- **Diagnostic Defaults — Per-Language Singleton Config** (Apr 18, 2026):
  - **Motivation**: parity with `/panel/proposals/defaults/`. Diagnostics now created from `panel/diagnostics/create.vue` had hardcoded payment terms (`{"initial_pct": 40, "final_pct": 60}` only as `help_text`, actually empty `{}` in practice), no admin-controllable default currency/investment/duration, and no editor over the section seed shipped from `content/seeds/diagnostic_template.py`. The product pricing default also flipped to **60% inicial / 40% final** — encoded in the new model defaults.
  - **Backend model**: new `DiagnosticDefaultConfig` (`backend/content/models/diagnostic_default_config.py`) — singleton per `language` (es/en) holding `sections_json`, `payment_initial_pct=60`, `payment_final_pct=40`, `default_currency` (COP/USD), `default_investment_amount` (decimal, nullable), `default_duration_label`, `expiration_days=21`, `reminder_days=7`, `urgency_reminder_days=14`. `clean()` enforces `payment_initial_pct + payment_final_pct == 100`. Registered in `content/models/__init__.py`. Migration `0101_diagnostic_default_config.py`.
  - **Serializer** (`backend/content/serializers/diagnostic.py:DiagnosticDefaultConfigSerializer`): mirrors the proposal pattern but trimmed — language and currency are validated by the model's `choices` (no redundant `validate_language`/`validate_default_currency`). Custom `validate_sections_json` ensures list of `{section_type, title, order, content_json}` dicts and normalizes missing/non-dict `content_json` to `{}`. Cross-field `validate()` re-checks the payment sum (catches PUT-time mismatches).
  - **Service helpers** (`backend/content/services/diagnostic_service.py`): added module-level constants `DEFAULT_PAYMENT_INITIAL_PCT=60`, `DEFAULT_PAYMENT_FINAL_PCT=40`, `DEFAULT_EXPIRATION_DAYS=21`, `DEFAULT_REMINDER_DAYS=7`, `DEFAULT_URGENCY_REMINDER_DAYS=14`; new `get_default_config(lang)`, `get_default_section_specs(lang)`, `get_hardcoded_section_specs()`. `seed_sections(diagnostic, config=None)` now accepts a pre-fetched config to avoid a duplicate query, and filters out specs whose `section_type` isn't a valid choice. `create_diagnostic` calls `get_default_config(language)` once, applies `payment_terms`/`currency`/`investment_amount`/`duration_label` from it (or the constants when no row exists), then passes the same config to `seed_sections` — single DB read per create.
  - **Views & URLs**: 2 new admin endpoints (`backend/content/views/diagnostic.py`): `GET/PUT /api/diagnostics/defaults/?lang=` (returns DB config or hardcoded fallback wrapped in the same shape; PUT upserts and preserves existing `sections_json` when the payload omits it) and `POST /api/diagnostics/defaults/reset/` (deletes the row for that language). Routes added under the diagnostics block in `content/urls.py`.
  - **Frontend page** (`frontend/pages/panel/diagnostics/defaults.vue`): 5 tabs — **General** (idioma, moneda, inversión, duración, % pagos con auto-sync a 100, días de recordatorio/urgencia/expiración, botón Restablecer con `useConfirmModal`), **Secciones** (lista read-only de las 8 secciones del seed activo), **Plantillas de Email** (informativo, link a `/panel/email-templates`), **Prompt** (placeholder — todavía no hay defaults compartidos), **JSON** (vista cruda para debugging). Reusa `ResponsiveTabs`, `ConfirmModal`, `usePanelToast` (no inline `setTimeout` que se filtraría al desmontar) y `<PanelToast />`. `applyConfig(data)` actualiza `rawConfig` + `sectionsList` + `generalForm` desde la respuesta del backend; `handleSaveGeneral` no recarga del backend tras guardar — usa `result.data` directo, ahorrando una query.
  - **Store** (`frontend/stores/diagnostics.js`): añadidos imports `put_request` + actions `fetchDiagnosticDefaults(lang)`, `saveDiagnosticDefaults(lang, sectionsJson, generalConfig)` (whitelist explícito de campos; ignora claves extra), `resetDiagnosticDefaults(lang)`. Mismo patrón Options API de `proposals.js:saveProposalDefaults`/`resetProposalDefaults`.
  - **Nav**: `frontend/pages/panel/diagnostics/index.vue` ahora muestra un botón "Valores por Defecto" en el header (estilo idéntico al de `/panel/proposals/`).
  - **Bug colateral arreglado**: una edición externa había dejado `penal_clause_value = serializers.CharField(...)` dentro de `DiagnosticDefaultConfigSerializer`. Movido a `ConfidentialityParamsSerializer` donde corresponde (placeholder del NDA; ya consumido por `confidentiality_pdf_service.py`).
  - **Tests**: backend nuevos `test_diagnostic_default_config.py` (8) + `test_diagnostic_defaults_views.py` (16) — 24 verdes; las 29 tests del módulo `test_web_app_diagnostic.py` y 11 de `test_diagnostic_attachments_and_emails.py` siguen verdes (pasaron por el cambio de `seed_sections`/`create_diagnostic`). Frontend: 6 tests añadidos al final de `frontend/test/stores/diagnostics.test.js` para las 3 actions; `put_request` añadido al mock del módulo. Jest no se ejecutó localmente (binario ausente en `node_modules`), correr con `npm --prefix frontend install && npm --prefix frontend test -- test/stores/diagnostics.test.js` cuando se necesite.
  - **No tocado** (a propósito): la página `panel/diagnostics/[id]/edit.vue` (los pagos por diagnóstico se editan ahí independiente del default), `panel/diagnostics/create.vue` (el backend ya aplica los defaults en `create_diagnostic`), las plantillas de email (`/panel/email-templates` ya las gestiona).
  - **Ops**: `python manage.py migrate content 0101` aplica la nueva tabla en producción. Sin cambios de config ni nuevas dependencias.

- **Diagnostic Edit — "Det. técnico" Tab Removed** (Apr 18, 2026):
  - **Motivation**: the consolidated `technical` tab (Pricing + Radiografía sub-tabs) no longer matches the real workflow. Pricing fields already live in the **General** tab; the Radiografía is one of the 8 section rows and is edited from **Secciones**. The actual diagnostic deliverable is produced offline — the team downloads the three markdown documents (diagnóstico aplicación, diagnóstico técnico, anexo), completes them, and sends them to the client from the **Correos** tab. The tab had nothing left to drive.
  - **Frontend change** (`frontend/pages/panel/diagnostics/[id]/edit.vue`): removed the `technical` entry from the `tabs` computed, the entire `<section v-if="activeTab === 'technical'">` template (outer visibility checkbox + Pricing/Radiografía sub-tab pills + `DiagnosticPricingForm`/`DiagnosticRadiographyForm`), their imports, and the matching script state (`technicalSubTab`, `formPricing`, `formRadiography`, `technicalSection` computed, `toggleTechnicalSectionEnabled`, `savePricing`, `saveRadiography`). The `syncForms` wrapper became a no-op and was inlined — the `watch(() => store.current?.id, …)` now calls `syncFormGeneral` directly.
  - **Legacy deep-link redirects**: `LEGACY_TAB_REDIRECTS` updated from `{ pricing: 'technical', radiography: 'technical', … }` to `{ pricing: 'general', radiography: 'sections', technical: 'sections', … }`. Bookmarked URLs land on the new owner of that data.
  - **Checkbox alignment** (`frontend/components/WebAppDiagnostic/admin/DiagnosticSectionEditor.vue`): the "Activa en la vista pública" checkbox used to hang off the bottom of the 3-col meta grid (`flex items-end`). Switched to `flex items-center gap-3 sm:self-center` so the grid item aligns itself to the row's vertical center — no more hand-rolled `sm:pt-5` compensation for the sibling labels.
  - **Not touched** (preserved on purpose): the `radiography` JSONField on `WebAppDiagnostic`, `DiagnosticDetailSerializer.radiography`, the `radiography` seed in `diagnostic_template.py`, `build_render_context()` use, and the public `RadiographySection.vue`. All radiography data still round-trips through the sections array, just without the extra editor.
  - **No backend/API/test changes.** Stale memory entries (tab list in the "Web App Diagnostics — JSON-Section Rewrite" / "Diagnostic Edit — UI/UX Parity" sections below) describe the superseded 10-tab layout; keep them as historical context.

- **Diagnostic Edit — UI/UX Parity With Proposal Edit** (Apr 16, 2026):
  - **Motivation**: the diagnostic admin page had acquired all the functional tabs of the proposal editor but its shell had drifted (sticky header shape, tab order, card chrome, dark-mode palette). Admins switching between the two flows noticed the mismatch. This pass aligns only the shell — no functional or backend changes.
  - **Template rewrite** in `frontend/pages/panel/diagnostics/[id]/edit.vue`: back-link lifted above sticky header; sticky header now carries only title + investment + status (client name + public URL moved into the Resumen info grid); margin collapse unified to `-mx-4 sm:-mx-6 lg:-mx-8`; dark tokens migrated from `dark:bg-gray-*` / `dark:border-gray-*` to `dark:bg-esmerald[-dark]` / `dark:border-white/[0.06]` / `dark:text-green-light/60`.
  - **Tab order re-sequenced** for proposal-editor parity: `summary` → `emails` → `documents` → `pricing` → `radiography` → `sections` → `prompt` → `plantillas` → `activity` → `analytics`. Labels unchanged.
  - **Resumen restructured**: three separate `rounded-2xl` cards collapsed into a single `bg-gray-50 dark:bg-white/[0.03] rounded-xl` info grid (ID, URL pública with copy button using `DocumentDuplicateIcon`/`CheckIcon` heroicons, Cliente block with inline Cambiar form, Idioma, Inversión, Vistas, fechas). Actions promoted to a sticky bottom bar mirroring the proposal's pattern.
  - **Per-tab width wrappers**: `max-w-2xl` on summary/pricing/radiography; `max-w-4xl` on the rest. Pricing/Radiografía/Plantillas cards unified to `bg-white dark:bg-esmerald rounded-xl shadow-sm border border-gray-100 dark:border-white/[0.06] p-4 sm:p-8`.
  - **Timer-leak fix**: both `urlCopied` and `jsonCopied` `setTimeout`s are now captured in module-scoped bindings and cleared in `onUnmounted` alongside `toastTimer`. Preexisting `jsonCopied` leak was the same pattern — fixed while in the area. See updated lessons-learned entry.
  - **No schema/API/test changes**; out of scope by design. No new dependencies — `@heroicons/vue/24/outline` was already in use on the proposal page.

- **Web App Diagnostics — JSON-Section Rewrite** (Apr 16, 2026):
  - **Motivation**: standardize the diagnostic client-facing presentation against the proven `BusinessProposal` pattern — JSON-typed sections edited via per-type form components instead of the 3 legacy markdown documents. Added the missing companion tabs (*Prompt*, *Actividad*, *Analítica*) so the diagnostic panel matches the proposal panel surface for surface.
  - **Backend models added**: `DiagnosticSection` (FK to diagnostic, 8-entry `SectionType` enum: `purpose`/`radiography`/`categories`/`delivery_structure`/`executive_summary`/`cost`/`timeline`/`scope`; `content_json` JSONField; `order`; `is_enabled`; `visibility` enum `initial|final|both`; `unique_together=[diagnostic,section_type]`), `DiagnosticChangeLog` (audit trail mirroring `ProposalChangeLog` — `ChangeType` / `ActorType` enums, `created_at`), `DiagnosticViewEvent` (per-session page-load tracking, indexed by `session_id`), `DiagnosticSectionView` (per-section time spent during a view event, `entered_at` + `time_spent_seconds`). `DiagnosticDocument` **removed** — replaced by `DiagnosticSection`.
  - **Migrations**: `0094_diagnostic_sections.py` (schema for 4 new models), `0095_seed_diagnostic_sections.py` (data — seeds the 8 default sections for any pre-existing diagnostic using `content/seeds/diagnostic_template.py` with an inline fallback), `0096_drop_diagnostic_document.py` (deletes the legacy model; kept as a separate migration so rollback is clean). Legacy `.md` templates moved to `backend/content/templates/diagnostics/_legacy/`.
  - **Seed** (`backend/content/seeds/diagnostic_template.py`): `default_sections()` returns the 8-section payload with the 14 diagnostic categories (architecture, code_quality, ui_ux, database, security, performance, scalability, testing, maintainability, reliability, integrations, tech_currency, documentation, functional_capabilities), severity scale, radiography table, delivery structure blocks, cost/timeline/scope boilerplate — all derived from the retired markdown proposal.
  - **Service** (`backend/content/services/diagnostic_service.py`): `create_diagnostic()` uses `seed_sections()` with `bulk_create` (1 INSERT batched) instead of loading `.md`. `build_render_context()` retained as the shared variable map for section components (stack, entities, routes, etc.). New helpers: `reset_section()` restores a single section from seed, `log_change()` centralizes `DiagnosticChangeLog.objects.create` (called from status transitions, section edits, email sends, client responses), `visible_sections()` filters by `is_enabled` + `visibility ∈ {phase, 'both'}` where `phase = 'final' if final_sent_at else 'initial'`, `transition_status()` now also writes a `STATUS_CHANGE` log entry.
  - **Serializers** (`backend/content/serializers/diagnostic.py`): `DiagnosticSectionSerializer` (read + update), `DiagnosticChangeLogSerializer`, `DiagnosticDetailSerializer` exposes `sections` + `attachments` + `change_logs` + `render_context`, `PublicDiagnosticSerializer` ships `sections` + a **whitelisted** `render_context` (`PUBLIC_RENDER_CONTEXT_KEYS` frozenset — admin-only fields like `controllers_disconnected` / `routes_protected` stay off the wire). Both detail + public memoize `build_render_context` on the serializer instance via `_render_context_for()`. `get_change_logs` slices the prefetched list in Python (`list(qs)[:60]`) to preserve the `_admin_qs().prefetch_related('change_logs')` cache. `get_sections` also consumes via `list()` to reuse the prefetch.
  - **Views** (`backend/content/views/diagnostic.py`): Admin — added `list_diagnostic_sections`, `update_diagnostic_section`, `bulk_update_diagnostic_sections`, `reset_diagnostic_section`, `list_diagnostic_activity`, `create_diagnostic_activity`, `diagnostic_analytics` on top of the existing CRUD + send endpoints. `_send_and_transition` now returns `(ok, email_ok)` and the response body carries `email_ok` so the UI can surface silent email failures. Private `_client_ip` deduped — new `get_client_ip()` helper hoisted to `content/utils.py`. `_ensure_view_event()` extracted so `track_public_diagnostic` + `track_diagnostic_section_view` share the lookup-or-create path (avoids the duplicate-session-row race). Public — added `track_diagnostic_section_view` endpoint.
  - **URLs** (`content/urls.py`): 8 new patterns under `/api/diagnostics/<id>/` for sections/activity/analytics + 1 public `track-section/`. Legacy `/documents/<id>/update|restore/` routes removed.
  - **Admin UI** (`frontend/pages/panel/diagnostics/[id]/edit.vue`): tab list expanded from 6 to **10** — see parity re-order in the Apr 16 follow-up entry below. Legacy `DiagnosticDocumentEditor` deleted; the debounced save timer map now keys by `sectionId`. `resyncJsonBuffer()` guards against clobbering unsaved JSON edits when the user is actively typing in Plantillas.
  - **Admin components** (`frontend/components/WebAppDiagnostic/admin/`): `DiagnosticSectionEditor.vue` + 8 per-type forms under `admin/sections/` (`PurposeForm`, `RadiographyForm`, `CategoriesForm`, `DeliveryStructureForm`, `ExecutiveSummaryForm`, `CostForm`, `TimelineForm`, `ScopeForm`). Watchers key on `[section.id, section.section_type]` instead of deep watch to avoid clobbering in-flight keystrokes when the parent merges the debounced-save response. `DiagnosticPromptPanel.vue` uses the shared `~/components/panel/PromptSubTabsPanel.vue` with `useDiagnosticCommercialPrompt`/`useDiagnosticTechnicalPrompt` (both built on the new `usePromptState({storageKey, defaultPrompt})` factory in `frontend/composables/usePromptState.js` — same factory replaces the duplicated localStorage ceremony of `useSellerPrompt`/`useTechnicalPrompt`). `DiagnosticActivityTab.vue` renders a timeline + nota form. `DiagnosticAnalytics.vue` shows view KPIs, per-section heatbar, and lifecycle timestamps. `PromptEditor.vue` is the shared edit/copy/download/reset UI.
  - **Public components** (`frontend/components/WebAppDiagnostic/public/`): 8 section components (one per `section_type`) + a shared `SectionHeader.vue` so the `<div flex items-baseline><span>{{index}}</span><h2>{{title}}</h2></div>` header stays in one place. Components receive `content`, `diagnostic`, `render_context` props.
  - **Public page** (`frontend/pages/diagnostic/[uuid]/index.vue`): section-based render with dynamic `<component :is>` dispatch via a `COMPONENTS` map, tab nav, prev/next controls, accept/reject footer. Session analytics: `generateSessionId()` on mount → `store.trackView(uuid, sessionId)` → per-section dwell timer flushed on section change; `onBeforeUnmount` uses `navigator.sendBeacon` so the final row survives tab unload (fetch fallback when beacon unavailable).
  - **Store** (`frontend/stores/diagnostics.js`): added `updateSection`, `bulkUpdateSections`, `resetSection`, `fetchActivity`, `logActivity`, `fetchAnalytics`, `trackSectionView` actions. Getters: `enabledSections`, `sectionsByPhase(phase)`. Legacy `updateDocument`/`restoreDocument`/`visibleDocuments` removed. `trackView` now sends `session_id`.
  - **Shared constants** (`frontend/stores/diagnostics_constants.js`): `SECTION_VISIBILITY`, `VISIBILITY_OPTIONS`, `SEVERITY_LEVELS`, `SEVERITY_LEVEL_CLASSES`, `severityLevelClass()`, `ACTIVITY_CHANGE_TYPES` — single source of truth used by the admin forms, the public `CategoriesSection`, and `DiagnosticActivityTab`. `arrToText`/`textToArr` re-imported from `frontend/components/BusinessProposal/admin/sectionEditorUtils.js` (no duplication).
  - **Prompt defaults** (`frontend/composables/useDiagnosticPrompt.js`): two diagnostic-specific prompts — commercial (fills the 8-section JSON narrative) + technical (fills the `categories` section with per-category findings/recommendations at the 4 severity levels).
  - **Dropped legacy**: `DiagnosticDocument` model + `DiagnosticDocumentEditor.vue` + `DiagnosticDocumentViewer.vue` + `_load_template`/`render_document`/`restore_document_from_template`/`visible_documents` service helpers. The 3 `.md` templates live under `templates/diagnostics/_legacy/` for reference only; nothing imports them.
  - **Tests (all green)**:
    - Backend 29: 18 in `test_web_app_diagnostic.py` (seed creates 8 sections, 14 categories seeded, reset_section restores default, status transition + change log entry, `visible_sections` phase filtering, section update + bulk update, activity log API, track-section view records time, analytics aggregate) + 11 in `test_diagnostic_attachments_and_emails.py` (unchanged — attachments + composer).
    - Frontend 41: 31 in `test/stores/diagnostics.test.js` (state/getters/fetchAll/detail/CRUD/update+bulk+reset sections/activity/analytics/transitions/public+track+trackSection) + 10 in `test/components/diagnosticSectionEditorUtils.test.js` (JSON↔form roundtrip per section_type).
  - **Ops**: `python manage.py migrate content 0096` in production applies the 3 new migrations. No config changes. Legacy `.md` files stay in-tree for history but are not loaded at runtime.

- **Proposal Admin & Public — 4 UX Improvements** (Apr 15, 2026):
  - **Expiry days input** (create + edit proposal pages): Number input placed inline beside the `datetime-local` field. Bidirectionally synced via two `watch()` calls — datetime change → days update; days change → date update while **preserving the existing time component** (`form.expires_at.slice(11, 16)`) so a custom hour is not overwritten when only the day count changes. Helpers: `getExpiryDaysFromStr()` in both pages; `create.vue` reuses existing `pad` + `buildDefaultExpiryStr`; `edit.vue` adds `padDate` + `DEFAULT_EXPIRY_DAYS`. Days watcher in `create.vue` also syncs `jsonForm.expires_at` (consistent with the existing cross-mode sync comment at line 1021). Timer stacking in `edit.vue` prevented via `updateMsgTimer` ref + `clearTimeout`.
  - **Smooth back-to-gateway transition** (`proposal/[uuid]/index.vue`): `handleBackToGateway()` now triggers the existing `switch-mode-overlay` `<Transition>` with `switchOverlayMode = 'gateway'` before resetting state. Overlay template gained a 4th case: grid icon, "Seleccionar vista" / "Select view" heading, bilingual subtitle. Timing mirrors `handleViewModeSelect`: 1 s hold → state reset + 1.2 s overlay hide.
  - **`@temp.example.com` email bypass** (`backend/content/utils.py`): `validate_email_domain_mx()` now short-circuits with `True` when `domain == 'temp.example.com'`, before any DNS lookup. `_PLACEHOLDER_EMAIL_DOMAIN = 'temp.example.com'` constant is local to `utils.py` (avoids cross-app import). `jsonForm.client_email` default in `create.vue` changed from `''` to `'usuario@temp.example.com'` so the JSON-import form is pre-filled with a valid placeholder address.
  - **Save toast notification** (`edit.vue`): Inline `updateMsg` div (inside the form, often scrolled away) replaced with a `<Teleport to="body">` toast fixed bottom-right. Uses Tailwind `<Transition>` enter/leave classes. Green = success, red = error; auto-dismisses in 5 s; `clearTimeout` + `updateMsgTimer` ref prevents timer stacking on rapid saves; manual ✕ button for immediate dismiss.

- **Admin Panel — Internal Kanban Task Board** (Apr 15, 2026):
  - **Backend model**: `backend/content/models/task.py` — `Task` with `Status` / `Priority` TextChoices (todo/in_progress/blocked/done; low/medium/high), `assignee` FK (SET_NULL to `AUTH_USER_MODEL`), `due_date`, `position` (ordering within column), `created_at`, `updated_at`. Migration `0087_task.py` (manual, no venv available). Registered in `content/models/__init__.py`.
  - **Serializers**: `TaskListSerializer` — read-side with `assignee_name` (`get_full_name() or username`) and `is_overdue` (reads `today` from serializer context — computed once per request via `_serializer_context()`). `TaskCreateUpdateSerializer` — write-side, `assignee_id` PrimaryKeyRelatedField.
  - **Views** (`backend/content/views/task.py`): `_next_position(status_value, exclude_pk=None)` helper (used by both create + update); `_serializer_context()` (hoists `timezone.localdate()` once per request); `_grouped_tasks()` (always returns all 4 status keys via `select_related('assignee')`). FBVs: `list_tasks` (GET), `create_task` (POST), `update_task` (PATCH — injects computed position into `serializer.validated_data` before single `serializer.save()` to eliminate double-save), `reorder_task` (PATCH `tasks/<id>/reorder/` — `transaction.atomic`, renumbers full column), `delete_task` (DELETE). 5 URL patterns in `content/urls.py`.
  - **Frontend store** (`frontend/stores/tasks.js`): Pinia Options API. State: `{ columns: {todo,in_progress,blocked,done}, isLoading, isUpdating, error }`. Actions: `fetchTasks`, `createTask` (appends optimistically), `updateTask` (replaces in-place, refetches only if status changed), `moveTask` (replaces board from API response; on error: fetches then sets `this.error` so fetchTasks reset doesn't overwrite it), `deleteTask`, `replaceTaskInPlace`.
  - **Components** (`frontend/components/Tasks/`): `TaskCard.vue` (priority badge gray/blue/red, due_date formatted `es-CO`, red if `is_overdue`); `TaskColumn.vue` (wraps vuedraggable with `group: { name:'tasks' }`, `handleChange(evt)` dispatches move for both `evt.added` and `evt.moved`); `TaskFormModal.vue` (create/edit, unified `buildForm()`, single dep watch on `modelValue`, emits `submit` + `delete`).
  - **Page** (`frontend/pages/panel/tareas/index.vue`): `definePageMeta({ layout:'admin', middleware:['admin-auth'] })`; 4 `TaskColumn` components in a responsive grid; `TaskFormModal`; delete gated through `useConfirmModal` + `ConfirmModal`.
  - **Navigation**: Added `{ id:'tasks', label:'Tareas', items:[{label:'Kanban', href:lp('/panel/tareas'), icon:'board'}] }` as first section in `frontend/config/panelNav.js`.
  - **Tests**: 11 backend (`test_task_views.py` — CRUD, non-admin 403, reorder within/across columns, position logic); 9 frontend unit (`tasks.test.js` — all actions + replaceTaskInPlace); 2 E2E (`admin-tasks-kanban.spec.js` — 4-column render + create, edit title). Flow tag `ADMIN_KANBAN_TASKS` registered in `flow-tags.js` + `flow-definitions.json`.
  - **Pending ops**: `python manage.py migrate` to apply `0087_task.py` in production.

- **Document System — Folders & Tags** (Apr 15, 2026):
  - **Backend models**: `DocumentFolder` (flat, slug auto-generated with collision avoidance, `order` sort field) and `DocumentTag` (M2M, 6 `Color` enum choices: gray/emerald/blue/yellow/red/purple). Both in `backend/content/models/`. `Document` model gained `folder` (FK `SET_NULL`) and `tags` (M2M). Migration `0086_document_folders_and_tags.py`.
  - **Serializers** (`backend/content/serializers/`): `DocumentFolderSerializer` reads `document_count` from `Count` annotation when available (N+1 free). `DocumentTagSerializer` (simple). `DocumentListSerializer` exposes `folder`, `folder_name`, `tag_details`. `DocumentCreateUpdateSerializer` accepts writable `folder_id` (PrimaryKeyRelatedField) and `tag_ids` (sets M2M via `.set()`). `DocumentFromMarkdownSerializer` extended with same fields.
  - **Views** (`backend/content/views/`): `document_folder.py` and `document_tag.py` — full CRUD FBV with `@api_view` + `IsAdminUser`. `list_document_folders` annotates `Count('documents')`. `list_documents` in `document.py` now accepts `?folder=<id|none>` and `?tags=<id,id,...>` (OR with `.distinct()`), prefetches tags and folder via `prefetch_related`/`select_related`.
  - **URLs**: 8 new patterns for `/api/document-folders/` and `/api/document-tags/` registered in `backend/content/urls.py`.
  - **Frontend stores**: `frontend/stores/document_folders.js` and `frontend/stores/document_tags.js` — Pinia Options API, snake_case filenames, CRUD with local mutation (no re-fetch after mutate). `frontend/stores/documents.js` extended: `activeFolderId`, `activeTagIds` state; `fetchDocuments(overrides={})` builds query params; `setFilters({folder,tags})`; `toggleTagFilter(tagId)`.
  - **Shared utility**: `frontend/utils/documentTagColors.js` — single source of truth for all tag Tailwind classes (`TAG_BADGE_CLASS`, `TAG_ACTIVE_CLASS`, `TAG_DOT_CLASS`, `TAG_IDLE_CHIP_CLASS`) + helper functions `tagBadgeClass()`, `tagActiveClass()`, `tagDotClass()`. Eliminates duplicate color maps that had existed across components.
  - **Components** (all new in `frontend/components/panel/documents/`): `FolderSidebar.vue` (pure `<script setup>`), `TagFilterChips.vue` (pure `<script setup>`), `TagSelector.vue` (v-model, pure `<script setup>`), `FolderManagerModal.vue`, `TagManagerModal.vue`.
  - **Pages updated**: `frontend/pages/panel/documents/index.vue` — 2-column layout (`lg:grid-cols-[240px_1fr]`), FolderSidebar left, tag chips + table right; table has folder badge on title and "Etiquetas" column. `create.vue` and `[id]/edit.vue` — folder dropdown + `<TagSelector>`, pre-populated from `?folder=` query param on create.
  - **Tests**: 25 backend tests across `test_document_folder_views.py` and `test_document_tag_views.py` (CRUD + SET_NULL + filter coverage). Frontend unit: `document_folders.test.js` (8), `document_tags.test.js` (8), `documents.test.js` extended (filter params, setFilters, toggleTagFilter). E2E: `e2e/admin/admin-document-folders.spec.js` (3 specs: sidebar filter, tag chip filter, "Sin carpeta" filter).
  - **Key patterns**: `?folder=none` → `filter(folder__isnull=True)`; M2M OR filter via `tags__id__in=[...].distinct()`; modal mutations emit `@changed` → parent only refreshes document list (folder/tag stores self-maintain local state after mutations).

- **Real Client Entity for Proposals** (Apr 9, 2026):
  - **Model**: New `BusinessProposal.client = ForeignKey('accounts.UserProfile', on_delete=PROTECT, limit_choices_to={'role':'client'}, null=True)`. Migration `0079_add_business_proposal_client_fk.py` (schema), `0080_backfill_proposal_clients.py` (data — dedups existing proposals by normalized email and creates UserProfile rows; empty emails get a placeholder via two-step save so the id can be embedded in `cliente_<id>@temp.example.com`). Legacy `client_name`/`client_email`/`client_phone` columns kept as **write-through snapshots**, never dropped.
  - **Service**: New `backend/accounts/services/proposal_client_service.py` — silent variant of `accounts/services/onboarding.py:create_client` that does NOT send invitation emails. Public API: `get_or_create_client_for_proposal(name, email, phone, company)`, `update_client_profile(profile, ...)` (cascades snapshots to all linked proposals via single bulk `BusinessProposal.objects.filter(client=profile).update(...)` and bumps `updated_at` manually because `.update()` bypasses `auto_now`), `delete_orphan_client(profile)` (3 guards: zero proposals + zero projects + zero deliverables), `sync_snapshot(proposal)`, `generate_placeholder_email(profile_id)`, `build_client_display_name(profile)` (shared with serializer). Refuses to hijack existing admin accounts when an email collision is detected.
  - **API**: 6 FBV endpoints under `proposals/client-profiles/*` — `list_proposal_clients` (with `?search=`, `?orphans=`, `?limit=`), `search_proposal_clients` (max 20 results, lightweight payload, AbortController-friendly), `retrieve_proposal_client` (with nested `proposals` history), `create_proposal_client` (standalone, no invite email), `update_proposal_client` (cascades snapshots), `delete_proposal_client` (returns 400 with `client_has_proposals` / `client_has_projects` codes when guard trips). All gated by `IsAdminUser`. Routes registered in `backend/content/urls.py`.
  - **Serializers**: `backend/content/serializers/proposal_clients.py` — `ProposalClientSerializer` (full, with annotated `total_proposals` + `is_orphan` + `is_email_placeholder`) and `ProposalClientSearchSerializer` (lightweight). `ProposalListSerializer` and `ProposalDetailSerializer` now expose nested `client = ProposalClientSerializer(read_only=True)`. `ProposalCreateUpdateSerializer` accepts write-only `client_id` (FK), `client_company`, `propagate_client_updates` and routes `create()`/`update()` through the service + `sync_snapshot`.
  - **Frontend**: `frontend/stores/proposalClients.js` — Pinia Options API with `fetchClients`, `searchClients` (uses `AbortController` + identity guard so rapid keystrokes don't race), `fetchClient`, `createClient`, `updateClient`, `deleteClient`. Getters: `orphanClients`, `activeClients`, `getClientById`. `frontend/components/ui/ClientAutocomplete.vue` — searchable dropdown with debounce 200ms (`useDebounceFn`), keyboard navigation, click-outside via `onClickOutside` from `@vueuse/core` (auto-cleanup on unmount), placeholder badge, "Crear nuevo" inline footer. `frontend/pages/panel/clients/index.vue` rewritten — tabs (Todos / Activos / Huérfanos), "+ Nuevo cliente" modal, trash icon visible only on orphans wired through `requestConfirm`, lazy-loaded proposals on row expand. `frontend/pages/panel/proposals/[id]/edit.vue` and `frontend/pages/panel/proposals/create.vue` use `<ClientAutocomplete>` + snapshot fields + propagate checkbox; the edit page extracted `hydrateFormFromProposal()` helper to dedup `onMounted` and `refreshData`. `frontend/stores/services/request_http.js` got an optional `config` arg on `get_request` (backward compatible) for AbortController support.
  - **Email automation skip**: `_is_unsendable_client_email(email)` helper in `proposal_email_service.py` returns `True` for empty strings and any address ending in `UserProfile.PLACEHOLDER_EMAIL_DOMAIN` (`@temp.example.com`, RFC 2606 reserved TLD). All **13 client-facing email methods** in `ProposalEmailService` (acceptance, finished, rejection, reminder, urgency, abandonment, investment-interest, scheduled-followup, negotiation-confirmation, documents, etc.) now exit early when the helper returns `True`. The 4 huey tasks in `content/tasks.py` (`send_proposal_reminder`, `send_urgency_reminder`, `send_rejection_reengagement`, `send_scheduled_followup`) use the same gate. Two candidate-selection querysets in `process_engagement_alerts` exclude placeholders via `.exclude(client_email__iendswith=UserProfile.PLACEHOLDER_EMAIL_DOMAIN)`.
  - **N+1 fixes**: `select_related('client__user')` added to `list_proposals` (admin dashboard hot path), `retrieve_proposal` (admin detail), `retrieve_public_proposal` (client view), and `retrieve_proposal_client` (the new client detail with nested proposals).
  - **Bug fix**: `respond_to_proposal` in `backend/content/views/proposal.py` was missing the `elif action == 'accepted':` branch — clients accepting a proposal never received the confirmation email even though the docstring promised it. See `error-documentation.md` ERR-007 for the full incident.
  - **Tests**: 15 (`accounts/tests/test_proposal_client_service.py`) + 19 (`content/tests/views/test_proposal_clients_views.py`) + 10 (`content/tests/services/test_proposal_email_service_placeholder_skip.py`) backend + 25 (`frontend/test/stores/proposalClients.test.js`) frontend = **69 new tests**, all green. Ran the full proposal regression slice afterwards (368 backend + 847 frontend tests) — zero regression.

- **Project Schedule Notifications (Cronograma)** (Apr 9, 2026):
  - New `ProposalProjectStage` child model on `BusinessProposal` (`backend/content/models/proposal_project_stage.py`) with `start_date`, `end_date`, `completed_at`, `warning_sent_at`, `last_overdue_reminder_at`. Migration `0081`, backfill `0082`, change-type enum `0083`.
  - New `ProposalStageTracker` service (`backend/content/services/proposal_stage_tracker.py`) with `STAGE_DEFINITIONS` constant, `ensure_stages` / `get_or_create_stage` classmethods, `format_remaining_time(days)` ("hoy", "1 día", "1 semana 5 días", "2 semanas"), and `process(proposal)` decision logic
  - Daily Huey periodic task `notify_proposal_stage_deadlines` at `crontab(hour='13', minute='30')` = 08:30 Bogotá. Filters by stage existence + dates + not-completed (NOT by proposal status), with `prefetch_related('project_stages')`.
  - Two new internal-team email templates registered in `EmailTemplateRegistry`: `proposal_stage_warning_notification` (70% elapsed, sent once) + `proposal_stage_overdue_notification` (overdue, every 3 days while not completed). Both with HTML+TXT twins under `backend/content/templates/emails/`.
  - Send methods `send_stage_warning` / `send_stage_overdue` in `ProposalEmailService` share a private `_send_stage_notification` helper. They use `_get_notification_recipients()` (CSV via `NOTIFICATION_EMAIL`) and do NOT call `_log_email` — internal team notifications use `logger.info` only, matching the convention of `send_first_view_notification`, `send_comment_notification`, etc.
  - Admin UI: new "Cronograma" tab in proposal edit page (`frontend/pages/panel/proposals/[id]/edit.vue`), only visible when status is `accepted`/`finished`. Component: `frontend/components/BusinessProposal/admin/ProjectScheduleEditor.vue`. Composable: `frontend/composables/useStageStatus.js` (mirrors backend `format_remaining_time` + computes status badges in JS).
  - Onboarding hook: `_ensure_project_stages` in `proposal_platform_onboarding.py` calls `ProposalStageTracker.ensure_stages` so accepted proposals get two empty stage rows automatically.
  - 2 new endpoints: `PUT /api/proposals/<id>/stages/<stage_key>/` and `POST /api/proposals/<id>/stages/<stage_key>/complete/`.
  - `ProposalDetailSerializer.get_project_stages` is gated by `is_admin` context — internal-only data is never exposed to public proposal views.
  - Tests: 26 tracker + 9 email service + 13 view + 5 task + 2 onboarding (backend); 11 store + 22 composable + 16 component (frontend); 6 E2E (`admin-proposal-project-schedule.spec.js` registered in `flow-definitions.json` + `USER_FLOW_MAP.md`).
  - Bogotá time helpers added to `backend/content/utils.py`: `now_bogota()`, `today_bogota()`, `to_bogota_date(dt)`. `format_bogota_date()` now accepts both `date` and `datetime`.
  - **Ops action pending**: set `NOTIFICATION_EMAIL=team@projectapp.co,carlos18bp@gmail.com` in production environment. This is a single env var change; affects all internal team notifications, not just stage alerts.

- **Codex Native Runtime Cleanup** (Apr 9, 2026):
  - Replaced the plugin-based Codex runtime with native repo skills in `.agents/skills/`
  - Added project-scoped Codex config in `.codex/config.toml`
  - Rewrote `AGENTS.md` / `CLAUDE.md` scopes to match the actual repo conventions (FBV backend, JS-first Nuxt frontend, Pinia Options API, split HTTP clients)
  - Kept `debug` canonical and `debugme` as the only legacy alias in the native skill inventory
  - Rewrote Codex setup docs around the native runtime and marked Claude-only guidance as compatibility documentation

1. **Proposal Advanced Filters & Saved Tabs** (Apr 5, 2026):
   - New composable `useProposalFilters.js` — 11 filter dimensions (status, project type, market type, currency, language, investment range, heat score range, view count range, created date range, last activity date range, active status), saveable named tabs with localStorage persistence, URL sync (`?tab=xxx`), max 12 tabs
   - New components: `ProposalFilterTabs.vue` (tab bar with +, rename, delete), `ProposalFilterPanel.vue` (collapsible filter panel with responsive grid)
   - Shared utility: `selectArrowStyle.js` extracted from duplicated SVG constant
   - Backend: added `language`, `sent_at` to `ProposalListSerializer`; batch engagement summary computation in `list_proposals` view (3 aggregated queries instead of N+1)
   - Performance: single filter pass, pre-computed date boundaries, `structuredClone`, shallow watcher
   - Replaced old status pills with filter tabs + "Filtros" toggle button; `statusOptions` array simplified to `statusLabelMap` object
2. **LinkedIn Integration for Blog Publishing** (Apr 5, 2026):
   - `LinkedInToken` singleton model with Fernet-encrypted access/refresh token storage (`linkedin_token.py`)
   - `linkedin_service.py` — OAuth 2.0 authorization code flow, automatic token refresh, publish/unpublish blog post summaries with cover images via LinkedIn Posts API (`/rest/posts`)
   - Admin panel UI: connect/disconnect LinkedIn account, publish toggle per blog post
   - Scopes: `openid profile email w_member_social`; encryption key via `LINKEDIN_ENCRYPTION_KEY` env var
2. **Branded + Proposal Composed Email System** (Apr 4, 2026):
   - Two new email tabs on proposal edit page: "Correos" (branded, for negotiating/accepted/rejected) and "Enviar correo" (proposal, for sent+ statuses)
   - Shared composer UI with draggable sections (vuedraggable), file attachments, branded preview, paginated history
   - Backend: `_send_composed_email()` shared service method, `send_branded_email()` + `send_proposal_email()` wrappers; proposal email creates `ProposalChangeLog` with `EMAIL_SENT` change type
   - 6 new URL patterns: send/defaults/history for each variant (branded-email + proposal-email)
   - `EmailLog.metadata` JSONField for storing full email content in history
   - New component: `ProposalEmailsTab.vue` with `mode` prop ('branded'/'proposal')
   - Store actions: `sendComposedEmail()`, `fetchEmailDefaults()`, `fetchEmailHistory()` with `basePath` parameter
   - Tests: 14 service + 19 view + 2 registry (backend), 30 component + 3 store (frontend), 4 E2E
   - 2 new flows in `flow-definitions.json` + `USER_FLOW_MAP.md` (v2.11.0)
   - Seed data: `create_fake_proposals.py` generates EmailLog entries for negotiating/accepted proposals
2. **Contract System** — Full contract parameters and proposal document handling (merged to main Apr 2–3, 2026):
   - New models: `CompanySettings` (contractor_signature ImageField), `ContractTemplate`, `ProposalDocument` — migrations 0061–0068
   - Service: `contract_pdf_service.py` — full contract PDF generation with template support, contractor signature rendering, draft mode (no signature), Helvetica/Times fonts
   - PDF enhancements in `pdf_utils.py`: `_apply_toc_links()` (clickable GoTo annotations), `_draw_line_with_links()` (inline justification with bold/italic/link tokens), `_draw_toc_page()`, `lru_cache` on `_font()`
   - Admin UI: `ContractParamsModal.vue`, `SendDocumentsModal.vue`, `ProposalDocumentsTab.vue`
   - Email: `proposal_documents_sent` template; enhanced `ProposalEmailService`
   - E2E: 5 new admin proposal specs (contract download/edit/generate, documents manage/send)
2. **Data Model Entities** — Platform feature for deliverables and project data models (Apr 3, 2026):
   - New models: `DataModelEntity`, `ProjectDataModelEntity` in accounts app — migrations 0021–0022
   - Service: `technical_requirements_sync.py` — sync entities with technical requirements
   - New page: `/platform/projects/[id]/data-model.vue` — JSON upload, entity list, template download
   - New store: `platform-data-model.js` — fetchEntities, uploadEntities, fetchTemplate
   - Tests: `test_data_model_entity.py` (60 cases), `test_data_model_views.py`, `platform-data-model.test.js` (26 cases), `platform-data-model.spec.js` (E2E)
3. **Platform UI Improvements** (Apr 1, 2026):
   - Terminology: 'Épica' → 'Módulo' across all platform pages
   - `useConfirmModal.js` refactored to promise-based API (+34 lines); `useConfirmModal.test.js` added
   - Dark mode removed from platform login, verify, complete-profile pages; `usePlatformTheme.js` simplified
4. **Document System (branch `generate-pdf-with-template` — not yet merged)** — Generic branded PDF documents:
   - `Document` model in `content/models/document.py` — uuid, title, slug, status (draft/published/archived), language, cover_type
   - Services: `document_pdf_service.py`, `markdown_parser.py`, `pdf_utils.py` (shared PDF utilities)
   - Panel pages: `/panel/documents/` (index, create, edit)
   - Store: `documents.js`
   - New composable: `useMarkdownPreview.js`
   - Backend tests: `test_document_pdf_service.py`, `test_markdown_parser.py` (in `backend/tests/`)
5. **Platform — Expanded Modules** — Five new Platform feature areas added to accounts app:
   - Bug Reports: `platform-bug-reports.js`, `/platform/bugs`, `/platform/projects/[id]/bugs`, `test_bug_reports.py`
   - Change Requests: `platform-change-requests.js`, `/platform/changes`, `/platform/projects/[id]/changes`, `test_change_requests.py`
   - Deliverables: `platform-deliverables.js`, `/platform/deliverables`, `/platform/projects/[id]/deliverables`, `test_deliverables.py`
   - Notifications: `platform-notifications.js`, `/platform/notifications`, `test_notifications.py`
   - Payments: `platform-payments.js`, `/platform/payments`, `/platform/projects/[id]/payments`, `test_payments.py`
   - Global Board: `/platform/board`; Profile page: `/platform/profile`
   - New composable: `usePlatformCustomTheme.js`
   - New accounts tests: `test_permissions.py`, `test_views_edge_cases.py`
3. **Panel Admins** — Admin management: `panel/admins/index.vue` + `panel_admins.js` store
4. **Panel Login** — Dedicated `panel/login.vue` page
5. **Proposal → Project integration** — Link proposals to projects: auto-create Kanban requirements from `functional_requirements` section, extract payment milestones and hosting tiers, auto-renewal on payment approval
6. **Platform E2E test fixes** — Fixed all platform Playwright spec files; removed `defineI18nRoute(false)`, fixed security bug in `platform-auth.js` middleware, replaced `networkidle` with `domcontentloaded`
7. **E2E coverage audit & remediation** — current workspace carries 129 E2E spec files; Quality gate: **100/100** with **0 warnings**
8. **CI/CD pipeline** — GitHub Actions with pytest, Jest, Playwright (5 shards), quality gate
9. **SEO On-Page Optimization** — Comprehensive SEO improvements across main views and blog:
   - Enhanced `useSeoHead.js` composable: added canonical URL, `og:locale`, `twitter:site`
   - Created `useSeoJsonLd.js` composable: `useJsonLd`, `useServiceJsonLd`, `useBlogPostJsonLd`, `useBlogListJsonLd`, `useWebPageJsonLd`
   - Enhanced global JSON-LD in `layouts/default.vue`: Organization + WebSite `@graph` with `@id` references
   - Added Service + BreadcrumbList JSON-LD to: `index.vue`, `landing-software.vue`, `landing-apps.vue`, `landing-web-design.vue`
   - Added WebPage JSON-LD to: `about-us.vue` (AboutPage), `contact.vue` (ContactPage), `portfolio-works/index.vue` (CollectionPage)
   - Fixed `contact.vue`: added missing `useSeoHead('contact')` + router locale meta (en/es)
   - Fixed `blog/index.vue`: locale-aware canonical, `og:url`, `og:site_name`, `og:locale`, `twitter:card/site`, hreflang, Blog JSON-LD
   - Fixed `blog/[slug].vue`: locale-aware canonical, `og:url`, `og:site_name`, `og:locale`, `article:author`, `twitter:card/site`, hreflang, BlogPosting JSON-LD
   - Fixed hardcoded CTA links in blog pages to use `localePath('/contact')`
10. **Terms & Privacy Pages** — Created localized Terms and Conditions + Privacy Policy views with SEO, routing, and footer links

---

## Active Decisions

- **FBV over CBV** — all views remain function-based; no plans to migrate
- **Pinia Options API** — all stores use Options API pattern; no Composition API stores
- **Pinia in-place mutation** — store helpers that update nested arrays must mutate in place (`this.currentProposal.sections[idx] = response.data`), never spread + reassign the parent. Components reading via `computed(() => store.currentProposal)` don't reliably pick up the spread+reassign combination but DO pick up in-place index assignments. See `_mergeProjectStage` / `updateSection` / `applySync` / `reorderSections` in `frontend/stores/proposals.js`.
- **Two Django apps** — `content` (proposals, blog, portfolio, contact) + `accounts` (platform auth, projects, kanban)
- **Hybrid rendering** — SSR for SEO pages, SPA for admin, proposal, and platform views
- **Dual auth strategy** — Session/CSRF for `/panel/` admin; JWT (SimpleJWT) for `/platform/`
- **Stage tracking is admin-managed** — `ProposalProjectStage.start_date` / `end_date` are set manually from the Cronograma tab. We do NOT auto-derive them by parsing the free-text `timeline` proposal section ("1 semana", "2 weeks") because that text is sales/marketing copy, not project execution data.
- **Internal team notifications use `_get_notification_recipients()` only** — recipient list lives in the `NOTIFICATION_EMAIL` env var (comma-separated). Do NOT add per-feature recipient settings. The gateway records baseline `EmailLog` rows for client, internal and security sends; manual visible To/CC groups share one `delivery_id`, while configured BCC copies keep `delivery_role=copy`.
- **Internal-only model fields must be gated by `is_admin` in shared serializers** — when a model docstring says "internal-only" (e.g., `ProposalProjectStage`), the field on `ProposalDetailSerializer` must be a `SerializerMethodField` returning `[]` for non-admin context, never a nested `read_only=True` model serializer.
- **Hosting has separate current and historical catalogs** — new selections are 9/6/3 months; monthly/annual values may be rendered for preserved history but must never re-enter offered choices. Proposal public/PDF consumers preserve closed snapshots; new platform/accounting operations use current terms.

---

## Development Environment

- **Backend**: Django 6.1 + DRF, SQLite (dev) / MySQL 8.4 (prod), Huey immediate mode
- **Frontend**: Nuxt 4 + Pinia 4 + TailwindCSS, dev server on port 3001 (port 3000 occupied by kore_project Next.js)
- **Both servers** must run simultaneously for full functionality in development
- **Redis**: Required in production for Huey task queue

---

## Verified Codebase Metrics (April 22, 2026 — refreshed post-Documents-Reorganization)

| Metric | Count |
|--------|-------|
| Backend test files | 157 |
| Frontend unit test files | ~200 (-admin-SendDocumentsModal.test.js -ProposalDiagnosticTemplatesSection.test.js) |
| E2E spec files | ~153 (-admin-proposal-documents-send.spec.js) |
| Vue components | ~168 (-SendDocumentsModal -ProposalDiagnosticTemplatesSection -SendDiagnosticDocumentsModal +AttachFromDocumentsModal) |
| Pages | 72 |
| Pinia stores | 27 |
| Composables | 42 (+useDocRefsAttachment.js) |
| Content model files | 30 |
| Accounts model classes | 21 |
| Accounts URL patterns | 65 |
| Content URL patterns | ~150 (+proposals/by-slug/<slug>/ + public diagnostic pdf + doc_refs backend helpers) |
| Email templates | 61 (32 HTML + 29 TXT across `accounts` + `content`) |
| Content services | 20 |
| Accounts services | 11 |
| Content migrations | 107 (0106 + 0107 pending apply for slug/diagnostic-slug features) |
| Quality gate score | 100/100 |

---

## Next Steps

- **Manual browser verification** — Start dev servers (`npm --prefix frontend run dev` + `source backend/venv/bin/activate && cd backend && python manage.py runserver`). Verify: (1) Proposal "Documentos" tab shows unified list + adjuntos + uploader; no templates aside; no "Enviar" section. (2) Diagnostic "Documentos" tab shows NDA + 3 MD templates + adjuntos; (3) Both Emails tabs: "Adjuntar desde Documentos" button opens modal, selected refs appear in composer, send includes them in the email.
- **Cleanup orphaned store actions** — `sendProposalDocuments` in `frontend/stores/proposals.js` and `sendDiagnosticAttachments` in `frontend/stores/diagnostics.js` are no longer called by any UI. Remove both actions and their corresponding backend endpoints (`POST /api/proposals/{id}/documents/send/` and `POST /api/diagnostics/{id}/attachments/send/`) + URL patterns in `content/urls.py`. Run `grep -rn "documents/send\|attachments/send"` before deleting to confirm no other callers.
- **Run pending frontend unit tests** — `npm --prefix frontend test -- test/components/ValueAddedModules.test.js` — `MarkdownAttachmentModal.test.js` is now verified (12/14 pass; 2 pre-existing failures at HEAD). `ValueAddedModules.test.js` still untested locally.
- **Deploy 3 pending commits to production** — commits `e2f3785a` (module reorder + auto-select), `22512aac` (slug URL), and `5c7ba3fe` (simplify refactor) are on local `main` but not yet pushed. Run `git push`, then `/deploy-and-check`.
- **Apply pending migrations in production** — `python manage.py migrate` — required to activate the Kanban board (`0087_task.py`), the Web App Diagnostics module (`0090_web_app_diagnostic.py`), the new Diagnostic Defaults table (`0101_diagnostic_default_config.py`), the Value Added Modules section type (`0102_value_added_modules_section.py`), the order swap (`0103_swap_value_added_modules_order.py`), and the new slug migrations (`0104` + `0105`).
- **Set `NOTIFICATION_EMAIL` in production env** to `team@projectapp.co,carlos18bp@gmail.com` so the new stage warning + overdue alerts reach the right inbox.
- Consider extending `ProposalStageTracker.STAGE_DEFINITIONS` beyond design + development (e.g., QA, Lanzamiento, Entrega Final) — the model + service already support N stages, only the catalog constant needs an update.
- Complete Document System PDF generation (branch `generate-pdf-with-template`): template rendering, preview, download flow — **folders & tags layer is now in place**
- Keep Codex docs, native repo skills, and compatibility mirrors synchronized when adding or renaming recurring workflows
- Add unit tests for `useProposalFilters.js` composable and `ProposalFilterPanel.vue` / `ProposalFilterTabs.vue` components
- Add E2E coverage for Contract System (ContractParamsModal, SendDocumentsModal admin workflows)
- Add E2E coverage for Platform Data Model page (`/platform/projects/[id]/data-model`)
- Add backend test coverage for contract/document services (`contract_pdf_service.py`, `technical_document_pdf.py`)
- ~~Fix 4 failing `usePlatformApi.test.js` tests~~ — all 56 tests pass (already resolved)
- **Deferred E2E:** `platform-verify-onboarding` — requires OTP test infrastructure (mock OTP delivery or test bypass)
- Add E2E coverage for new Platform modules (bug reports, change requests, deliverables, notifications, payments)
- Increase backend test coverage (target areas: services edge cases, accounts app edge cases)
- Increase frontend unit test coverage (target areas: remaining composables, components)
- Consider splitting the largest proposal/backend modules (`views/proposal.py`, `proposal_service.py`, `proposal_email_service.py`) now that the shared PDF helpers already live in `pdf_utils.py`
- Credential rotation for production secrets exposed in git history
- Explore API rate limiting for public endpoints

## Linktrees: personalización de marca (2026-09-21)

Implementado: colores por tarjeta, logo independiente del avatar y familia Google Fonts, conservando los valores iniciales del diseño. QR Cards mantiene su redirección estable. Misma tarjeta para vista previa y página pública. El editor espera la carga antes de permitir cambios. Validación local: 14 pruebas de marca backend, 3 MCP de create/read/update/error, 11 contratos MCP/redirecciones QR, 18 pruebas unitarias de componentes/store. Editor revisado sin overflow a 412/835/1195/1440/2560 px. Flow admin-linktree-branding registra success/error/failure/display; catálogo de vistas y contrato responsivo válidos. PR #396; estado final de CI verificable en GitHub.

## Marca por proyecto (2026-09-21)

Implementado: relación opcional Linktree → Project y biblioteca privada por proyecto con categorías de branding, manual, sistema de diseño y logos. Entrada desde Acciones en Proyectos; reutiliza el almacenamiento privado y las sesiones del panel.

## Programa de Alianza — exclusividad conceptual (2026-09-25)

La modalidad de cinco años añade un compromiso de Project App. de no reproducir
para otros clientes conceptos, ideas o enfoques específicos del producto en
proyectos competidores del mismo sector y nicho durante la vigencia original.
El programa público, su vista previa y booklet comparten la octava condición
bilingüe. El formulario guía la delimitación escrita del alcance y el otrosí
incluye el compromiso sólo con `five_year`; tres años lo excluye. Los snapshots
legales existentes se conservan y el segundo ciclo no amplía el plazo. Sin
migraciones ni cambios de política financiera. Backend focal y regresión:
27 casos aprobados; mapa de vistas: 20 tests aprobados; quality gate focal:
100/100, sin errores ni warnings. Flow-map vigente, con las clases declaradas
del módulo cubiertas. El estado de navegador y CI se registra en el PR.
