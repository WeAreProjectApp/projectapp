"""Default technical requirements for the optional additionalModules catalog.

Every visible, non-invite module of the functional-requirements
``additionalModules`` catalog ships a per-item set of technical requirements
(ES + EN). ``seed_module_technical_requirements`` injects them into a
proposal's ``technical_document`` when the generation/import left the module
without its own epic, so the "Ver requerimientos (N)" breakdown per module
item never depends on how thorough a given generation was.

Contract:

* One or more catalog requirements per default module item, matched to the
  item's real scope (breakdown dimensions: configuration/setup, provider
  integration, states and errors, permissions, limits/lifecycle). Every
  default item of a cataloged module is referenced by at least one
  requirement. Each requirement's ``item`` holds exactly ONE default item
  name and resolves to ``linked_item_ids`` at seed time via ``build_item_id``
  (never stored in the catalog — item ids are localized).
* ``flowKey`` values are kebab-case, namespaced per module, and IDENTICAL
  across languages (texts are translated, keys are not).
* Seeded epics/requirements always carry ``linked_module_ids`` with the raw
  module id; ``normalize_technical_document_module_links`` canonicalizes it
  to ``module-<id>`` right after seeding, which is what keeps them gated by
  the client's module selection everywhere (web, PDFs, platform sync).
* Seeding is seed-if-absent PER MODULE: any epic or requirement already
  covering the module (by link or verbatim ``epicKey``) disables seeding for
  it, so seller/LLM-authored content and manual deletions in the panel editor
  always win. The editor save path never seeds.
"""

from __future__ import annotations

import copy
from typing import Any

from django.utils.text import slugify

from content.services.proposal_module_links import build_item_id

MODULE_REQUIREMENTS_CATALOG: dict[str, dict[str, Any]] = {
    'es': {
        'integration_electronic_invoicing': {
            'epic_title': 'Alcance ampliado: Facturación Electrónica e Integración DIAN',
            'epic_description': (
                'Desglose técnico del módulo de facturación electrónica. Cada requerimiento '
                'detalla un elemento del alcance del módulo y su criterio de aceptación.'
            ),
            'requirements': [
                {
                    'flowKey': 'invoicing-generacion-comprobantes',
                    'item': 'Generación de comprobantes electrónicos',
                    'title': 'Emisión de facturas, notas y documentos soporte desde los flujos del negocio',
                    'description': 'Cada venta o pedido completado puede generar su comprobante electrónico (factura, nota crédito/débito o documento soporte) sin salir de la plataforma ni digitar dos veces la información.',
                    'configuration': 'Mapeo de campos fiscales (cliente, ítems, impuestos), numeración autorizada y emisión vía la API del proveedor de facturación; cola con reintentos ante errores del proveedor.',
                    'usageFlow': 'Se completa un pedido → el sistema arma el comprobante → lo envía al proveedor → guarda número, CUFE y PDF → notifica el resultado.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'invoicing-generacion-errores-reintentos',
                    'item': 'Generación de comprobantes electrónicos',
                    'title': 'Los errores del proveedor fiscal no bloquean la venta',
                    'description': 'Si el proveedor de facturación falla, la venta se completa igual: el comprobante queda en cola, se reintenta solo y el responsable recibe una alerta únicamente si los reintentos se agotan.',
                    'configuration': 'Cola de emisión con reintentos escalonados (Huey), alerta al responsable al agotarse los reintentos y reemisión manual disponible desde el panel.',
                    'usageFlow': 'El proveedor falla → la venta se completa igual → el comprobante se reintenta en segundo plano → si se agotan los reintentos, llega la alerta y se puede reemitir a mano.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'invoicing-generacion-consecutivos-pdf',
                    'item': 'Generación de comprobantes electrónicos',
                    'title': 'Numeración autorizada, CUFE y PDF guardados por comprobante',
                    'description': 'Cada comprobante emitido conserva su número autorizado, su CUFE y su PDF oficial, descargables desde el detalle del pedido cuando se necesiten.',
                    'configuration': 'Almacenamiento del consecutivo, el CUFE y el PDF devueltos por el proveedor, asociados al pedido de origen, con descarga desde el panel.',
                    'usageFlow': 'Se emite el comprobante → número, CUFE y PDF quedan guardados con el pedido → el usuario los descarga desde el detalle cuando los necesita.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-sincronizacion-fiscal',
                    'item': 'Sincronización de datos fiscales',
                    'title': 'Sincronización bidireccional de clientes, productos e impuestos',
                    'description': 'Los catálogos fiscales se mantienen alineados entre la plataforma y el sistema de facturación: lo que se crea o edita en un lado queda reflejado en el otro, sin doble digitación.',
                    'configuration': 'Tareas periódicas (Huey) más webhooks del proveedor cuando existan; llave externa por registro y resolución de conflictos por fecha de última actualización.',
                    'usageFlow': 'Se crea o edita un cliente/producto → se encola la sincronización → el registro queda vinculado por id externo → los cambios remotos se reflejan en la plataforma.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'invoicing-sincronizacion-conflictos',
                    'item': 'Sincronización de datos fiscales',
                    'title': 'Conflictos de sincronización resueltos sin duplicar registros',
                    'description': 'Si el mismo cliente o producto cambió en ambos sistemas, gana la edición más reciente y nunca se crean duplicados; el vínculo por id externo queda auditable.',
                    'configuration': 'Resolución por fecha de última actualización, llave externa única por registro y bitácora de la última sincronización aplicada.',
                    'usageFlow': 'El registro cambia en ambos sistemas → la sincronización detecta el conflicto → aplica la versión más reciente → el vínculo y la bitácora quedan consultables.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-trazabilidad-estado',
                    'item': 'Trazabilidad del estado fiscal',
                    'title': 'Seguimiento del estado DIAN de cada comprobante',
                    'description': 'Desde la plataforma se consulta si cada comprobante fue emitido, aceptado, rechazado o sigue en proceso, con su historial completo y el motivo cuando hay rechazo.',
                    'configuration': 'Consulta de estado vía API con sondeo programado; almacenamiento de la línea de tiempo de estados por comprobante.',
                    'usageFlow': 'El usuario abre el detalle de una factura → ve la línea de tiempo de estados → si hubo rechazo, ve el motivo reportado y puede reemitir.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-trazabilidad-reemision',
                    'item': 'Trazabilidad del estado fiscal',
                    'title': 'Reemisión controlada tras un rechazo de la DIAN',
                    'description': 'Un comprobante rechazado se corrige y se reemite desde el mismo detalle, conservando el historial del intento anterior para la auditoría.',
                    'configuration': 'Acción de reemisión con corrección de datos, nuevo consecutivo cuando aplique y rechazos anteriores conservados en la línea de tiempo.',
                    'usageFlow': 'La DIAN rechaza → el usuario corrige el dato señalado → reemite desde el detalle → el historial muestra ambos intentos.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-proveedores-colombia',
                    'item': 'Integración con proveedores colombianos',
                    'title': 'Conexión con el proveedor de facturación del cliente (Siigo, Alegra u otro)',
                    'description': 'La integración se construye contra el proveedor que el negocio ya usa o elija, validada de punta a punta antes de salir a producción.',
                    'configuration': 'Credenciales API del cliente en variables de entorno; adaptador por proveedor con contrato común (emitir, consultar, anular) para poder cambiar de proveedor sin rehacer los flujos.',
                    'usageFlow': 'Se configuran las credenciales → se valida la conexión con una emisión de prueba en sandbox → se activa el modo producción.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-automatizaciones-api',
                    'item': 'Automatizaciones vía API',
                    'title': 'Reconciliación de pagos y emisión automática',
                    'description': 'Los eventos del negocio disparan acciones fiscales sin intervención manual: emitir al completar un pedido, conciliar pagos recibidos y avisar cambios de estado.',
                    'configuration': 'Reglas de disparo por evento (pedido completado, pago confirmado) y notificaciones de estado fiscal por correo al responsable.',
                    'usageFlow': 'Ocurre el evento configurado → la automatización ejecuta la acción fiscal → el resultado queda registrado y notificado.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-automatizaciones-anulacion',
                    'item': 'Automatizaciones vía API',
                    'title': 'Notas crédito automáticas al cancelar o devolver un pedido',
                    'description': 'Las cancelaciones y devoluciones generan su nota crédito vinculada a la factura original, sin pasos manuales ni descuadres fiscales.',
                    'configuration': 'Disparador de anulación/devolución que emite la nota crédito referenciando el comprobante original y registra el vínculo entre ambos.',
                    'usageFlow': 'Se cancela o devuelve un pedido facturado → el sistema emite la nota crédito vinculada → el estado fiscal del pedido queda consistente.',
                    'priority': 'medium',
                },
            ],
        },
        'integration_regional_payments': {
            'epic_title': 'Alcance ampliado: Pasarela de Pago Regional (Colombia)',
            'epic_description': (
                'Desglose técnico de la integración de pagos locales. Cada requerimiento '
                'cubre un criterio verificable de las pasarelas del alcance del módulo.'
            ),
            'requirements': [
                {
                    'flowKey': 'regional-payu',
                    'item': 'PayU',
                    'title': 'Checkout con PayU: tarjeta, PSE y medios en efectivo',
                    'description': 'El cliente final paga con los medios locales más usados en Colombia (tarjeta, PSE, Efecty, Nequi, Daviplata) y el pedido se confirma solo cuando la pasarela confirma el pago.',
                    'configuration': 'Cuenta PayU del cliente (sandbox y producción), firma de integridad por transacción, webhook de confirmación y validación de monto/moneda antes de aprobar el pedido.',
                    'usageFlow': 'Carrito → checkout → pago en PayU → retorno con estado → confirmación del pedido y correo al cliente.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'regional-payu-pagos-pendientes',
                    'item': 'PayU',
                    'title': 'Pagos PSE pendientes resueltos sin intervención',
                    'description': 'Un pago PSE puede quedar «pendiente» durante horas: el pedido espera en un estado intermedio y solo se aprueba o se libera cuando la pasarela reporta el estado final, con opción de reintentar si falla.',
                    'configuration': 'Estado intermedio de pedido con sondeo y webhook del estado final, y liberación del inventario si el pago no se concreta en el plazo.',
                    'usageFlow': 'El cliente paga por PSE → el banco deja el pago en proceso → el pedido espera pendiente → al confirmarse se aprueba, o al vencer se libera y el cliente puede reintentar.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'regional-payu-conciliacion',
                    'item': 'PayU',
                    'title': 'Conciliación de transacciones PayU contra pedidos',
                    'description': 'El panel cruza las transacciones aprobadas por la pasarela con los pedidos registrados y señala las diferencias (pagos sin pedido, pedidos sin pago) para el cuadre contable.',
                    'configuration': 'Cruce periódico de transacciones reportadas por PayU contra pedidos, con listado de discrepancias por período.',
                    'usageFlow': 'El administrador abre la conciliación → ve el cruce del período → resuelve las diferencias señaladas.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'regional-wompi',
                    'item': 'Wompi (Bancolombia)',
                    'title': 'Checkout con Wompi: PSE, tarjetas y botón Bancolombia',
                    'description': 'Alternativa local con excelente cobertura Bancolombia: el cliente paga con PSE, tarjeta, Nequi o botón Bancolombia y el estado del pago queda trazado en la plataforma.',
                    'configuration': 'Llaves pública/privada de Wompi del cliente, verificación de firma de eventos y conciliación del estado final de cada transacción.',
                    'usageFlow': 'Checkout → widget o redirección Wompi → pago → evento de confirmación → pedido aprobado o rechazado según el estado.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'regional-wompi-eventos-idempotentes',
                    'item': 'Wompi (Bancolombia)',
                    'title': 'Eventos de Wompi procesados exactamente una vez',
                    'description': 'Los reintentos o eventos duplicados de la pasarela no generan dobles confirmaciones ni dobles descuentos de inventario: cada transacción se procesa una sola vez.',
                    'configuration': 'Idempotencia por id de transacción en el manejador de eventos y verificación de firma antes de procesar cada evento.',
                    'usageFlow': 'Wompi reenvía un evento ya procesado → el sistema lo reconoce → no repite la confirmación → el pedido conserva un único estado.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'regional-epayco',
                    'item': 'ePayco',
                    'title': 'Checkout con ePayco: PSE, tarjetas y recaudo físico',
                    'description': 'Opción colombiana de integración ágil: pagos con PSE, tarjeta y recaudos físicos, con confirmación asíncrona verificada del lado del servidor.',
                    'configuration': 'Credenciales ePayco del cliente, página de respuesta y URL de confirmación server-to-server con validación de firma.',
                    'usageFlow': 'Checkout → pago en ePayco → respuesta al cliente → confirmación server-to-server → actualización del estado del pedido.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'regional-epayco-recaudo-pendiente',
                    'item': 'ePayco',
                    'title': 'Recaudo físico con reserva y vencimiento del pedido',
                    'description': 'Al elegir pago en efectivo, el pedido queda reservado con su referencia de pago y solo vence si el dinero no llega en el plazo definido.',
                    'configuration': 'Estado reservado con referencia de recaudo, vencimiento configurable y liberación automática del inventario al expirar.',
                    'usageFlow': 'El cliente elige efectivo → recibe la referencia → paga en el punto físico → la confirmación llega y el pedido se aprueba, o vence y se libera.',
                    'priority': 'medium',
                },
            ],
        },
        'integration_international_payments': {
            'epic_title': 'Alcance ampliado: Pasarela de Pago Internacional',
            'epic_description': (
                'Desglose técnico de la integración de pagos internacionales. Cada '
                'requerimiento cubre un criterio verificable de las pasarelas del alcance del módulo.'
            ),
            'requirements': [
                {
                    'flowKey': 'intl-stripe',
                    'item': 'Stripe',
                    'title': 'Cobros internacionales con Stripe: tarjetas y múltiples divisas',
                    'description': 'El negocio recibe pagos con tarjeta de crédito/débito desde cualquier país, en pagos únicos o recurrentes, con confirmación verificada antes de entregar el producto o servicio.',
                    'configuration': 'Claves API restringidas, webhooks firmados (pago exitoso/fallido), manejo de divisas habilitadas y modo suscripción cuando aplique.',
                    'usageFlow': 'Checkout → formulario seguro de Stripe → pago → webhook de confirmación → pedido aprobado y correo de comprobante.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'intl-stripe-3ds-sca',
                    'item': 'Stripe',
                    'title': 'Autenticación 3D Secure cuando el banco la exige',
                    'description': 'Los pagos que el banco marca para verificación adicional pasan por 3D Secure sin romper el flujo: el cliente completa el reto y el pedido continúa normal.',
                    'configuration': 'Flujo de confirmación con manejo del estado de autenticación requerida y retorno al checkout tras completar el reto.',
                    'usageFlow': 'El banco exige autenticación → el cliente completa el reto 3D Secure → el pago se confirma → el pedido sigue su curso.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'intl-stripe-reembolsos-disputas',
                    'item': 'Stripe',
                    'title': 'Reembolsos y disputas gestionados desde el panel',
                    'description': 'Los reembolsos totales o parciales se emiten desde el propio pedido, y las disputas (contracargos) quedan visibles con su estado y su plazo de respuesta.',
                    'configuration': 'Emisión de reembolsos vía API ligada al pedido y registro de disputas notificadas por webhook con su estado.',
                    'usageFlow': 'El negocio decide reembolsar → lo emite desde el pedido → el estado del reembolso y cualquier disputa quedan trazados en el panel.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'intl-paypal',
                    'item': 'PayPal',
                    'title': 'Cobros con PayPal: saldo, tarjeta y cuentas internacionales',
                    'description': 'Los clientes que prefieren PayPal pagan con su saldo o tarjeta asociada; la plataforma verifica la captura del pago antes de confirmar el pedido.',
                    'configuration': 'Credenciales de la app PayPal del cliente (sandbox y live), captura de órdenes vía API y verificación del estado antes de aprobar.',
                    'usageFlow': 'Checkout → botón PayPal → aprobación en PayPal → captura del pago → confirmación del pedido.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'intl-paypal-capturas-expiradas',
                    'item': 'PayPal',
                    'title': 'Órdenes PayPal no capturadas se liberan solas',
                    'description': 'Si el cliente aprueba en PayPal pero la captura falla o la orden expira, el pedido no queda colgado: el inventario se libera y el cliente puede pagar de nuevo.',
                    'configuration': 'Verificación del estado de la orden con reintento de captura y liberación automática al expirar la ventana de PayPal.',
                    'usageFlow': 'El cliente aprueba pero la captura falla → el sistema reintenta → si la orden expira, el pedido se libera y se avisa al cliente para reintentar.',
                    'priority': 'medium',
                },
            ],
        },
        'pwa_module': {
            'epic_title': 'Alcance ampliado: Aplicación Móvil Instalable (PWA)',
            'epic_description': (
                'Desglose técnico del módulo PWA. Cada requerimiento detalla un elemento '
                'del alcance instalable/offline del módulo.'
            ),
            'requirements': [
                {
                    'flowKey': 'pwa-instalacion-dispositivo',
                    'item': 'Instalación en dispositivo',
                    'title': 'Instalación como aplicación en celular y computador',
                    'description': 'El sitio se instala desde el navegador como una app con ícono y nombre de la marca en la pantalla de inicio, y abre en ventana propia sin barra del navegador.',
                    'configuration': 'Web App Manifest (nombre, colores, íconos maskable), service worker registrado y cumplimiento de los criterios de instalabilidad de Chrome/Safari.',
                    'usageFlow': 'El visitante navega el sitio → el navegador ofrece "Instalar aplicación" → confirma → el ícono queda en la pantalla de inicio y abre en modo standalone.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'pwa-instalacion-criterios-navegadores',
                    'item': 'Instalación en dispositivo',
                    'title': 'Criterios de instalabilidad cubiertos en Chrome, Safari y Edge',
                    'description': 'La app cumple los requisitos de instalación de cada navegador soportado; donde no existe aviso nativo (Safari en iOS) el usuario ve una guía breve de «Agregar a pantalla de inicio».',
                    'configuration': 'Manifest válido (íconos maskable 192/512, display standalone, start_url), service worker con manejador fetch y detección de plataforma para la guía de iOS.',
                    'usageFlow': 'El usuario entra desde iOS → no hay aviso nativo → ve la guía paso a paso → agrega la app a su pantalla de inicio.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'pwa-offline',
                    'item': 'Funcionamiento offline',
                    'title': 'Acceso al contenido sin conexión a internet',
                    'description': 'Sin conexión, la app sigue mostrando el contenido ya visitado y una pantalla offline clara para lo no disponible; al reconectar, el contenido se actualiza solo.',
                    'configuration': 'Estrategias de caché por tipo de recurso (precache del shell, stale-while-revalidate para contenido) y página offline de respaldo.',
                    'usageFlow': 'El usuario pierde conexión → abre la app → ve contenido cacheado y aviso de modo offline → al reconectar, todo se actualiza en segundo plano.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'pwa-offline-limites-cache',
                    'item': 'Funcionamiento offline',
                    'title': 'La caché offline no crece sin control',
                    'description': 'Lo guardado para uso offline respeta límites de tamaño y antigüedad: se conserva lo útil y se depura lo viejo, sin llenar el almacenamiento del dispositivo.',
                    'configuration': 'Política de expiración y tope por tipo de recurso con limpieza automática de las entradas antiguas.',
                    'usageFlow': 'El usuario navega durante semanas → la caché se depura sola → la app sigue rápida y sin consumir almacenamiento de más.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'pwa-notificaciones-push',
                    'item': 'Notificaciones push',
                    'title': 'Notificaciones push con permiso del usuario',
                    'description': 'El negocio envía avisos directos al dispositivo (novedades, promociones, actualizaciones) solo a usuarios que aceptaron recibirlos, con opción de desuscribirse.',
                    'configuration': 'Suscripción Web Push con llaves VAPID, solicitud de permiso explícita y envío segmentado desde el backend.',
                    'usageFlow': 'El usuario acepta el permiso → el negocio publica un aviso → la notificación llega al dispositivo aun con el sitio cerrado → al tocarla abre la vista correspondiente.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'pwa-push-gestion-suscripciones',
                    'item': 'Notificaciones push',
                    'title': 'Suscripciones push vigentes y bajas respetadas',
                    'description': 'La baja de notificaciones aplica de inmediato y los dispositivos que ya no existen se depuran solos: nadie recibe avisos que no pidió.',
                    'configuration': 'Alta y baja de suscripción sincronizadas con el backend y depuración de tokens inválidos reportados en cada envío.',
                    'usageFlow': 'El usuario se desuscribe → no recibe más avisos → los envíos siguientes omiten y depuran los dispositivos inválidos.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'pwa-splash-personalizada',
                    'item': 'Pantalla de carga personalizada',
                    'title': 'Splash screen con la identidad de la marca',
                    'description': 'Al abrir la app instalada aparece una pantalla de carga con logo y colores corporativos, en lugar de un fondo genérico del navegador.',
                    'configuration': 'Íconos y colores de fondo/tema definidos en el manifest para generar el splash nativo en Android/iOS.',
                    'usageFlow': 'El usuario abre la app instalada → ve el splash con la marca → entra a la pantalla inicial ya cargada.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'pwa-sincronizacion-segundo-plano',
                    'item': 'Sincronización en segundo plano',
                    'title': 'Reintento automático de operaciones al recuperar conexión',
                    'description': 'Las acciones hechas sin conexión (formularios, cambios) quedan en cola y se envían solas cuando vuelve la señal, sin que el usuario repita nada.',
                    'configuration': 'Cola de operaciones pendientes con Background Sync y reintentos con confirmación al completar.',
                    'usageFlow': 'El usuario envía una acción sin conexión → queda en cola con aviso → al recuperar señal se sincroniza → recibe confirmación.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'pwa-sync-conflictos',
                    'item': 'Sincronización en segundo plano',
                    'title': 'Conflictos al sincronizar resueltos sin perder datos',
                    'description': 'Si el dato cambió en el servidor mientras el usuario estaba sin conexión, la operación en cola no lo pisa a ciegas: se aplica la versión más reciente y el resultado queda notificado.',
                    'configuration': 'Marca de tiempo por operación encolada y regla del más reciente con notificación del resultado al usuario.',
                    'usageFlow': 'El usuario edita sin conexión → otro cambio llega antes al servidor → al reconectar se respeta el más reciente → el usuario ve el resultado notificado.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'pwa-actualizacion-automatica',
                    'item': 'Actualización automática',
                    'title': 'Actualización transparente a la última versión',
                    'description': 'La app se actualiza sola: el usuario siempre usa la versión más reciente sin pasos manuales ni tiendas de aplicaciones.',
                    'configuration': 'Versionado del service worker con activación controlada y aviso discreto de "nueva versión disponible" cuando aplique.',
                    'usageFlow': 'Se publica una nueva versión → el service worker la descarga en segundo plano → en la siguiente apertura la app ya está actualizada.',
                    'priority': 'medium',
                },
            ],
        },
        'corporate_branding_module': {
            'epic_title': 'Alcance ampliado: Identidad Visual e Imagen Corporativa',
            'epic_description': (
                'Desglose técnico del módulo de branding. Cada requerimiento cubre un '
                'punto de contacto donde la identidad de marca se aplica.'
            ),
            'requirements': [
                {
                    'flowKey': 'branding-correos-transaccionales',
                    'item': 'Correos transaccionales con identidad corporativa',
                    'title': 'Todos los correos del sistema salen con plantilla de marca',
                    'description': 'Bienvenida, confirmaciones, alertas y recuperación de contraseña llegan con logo, colores, tipografía y firma de la marca — nunca en texto plano genérico.',
                    'configuration': 'Plantillas HTML responsivas probadas en Gmail/Outlook, con variables por evento y versión de texto plano de respaldo.',
                    'usageFlow': 'Ocurre un evento del sistema → se renderiza la plantilla de marca con los datos del evento → el correo llega con la identidad del negocio.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'branding-correos-dominio-propio',
                    'item': 'Correos transaccionales con identidad corporativa',
                    'title': 'Correos que llegan a la bandeja con el dominio del negocio',
                    'description': 'Los correos salen desde una dirección del dominio propio y autenticados (SPF/DKIM), con el nombre correcto del remitente y menos riesgo de caer en spam.',
                    'configuration': 'Remitente con dominio del cliente y registros SPF, DKIM y DMARC configurados y verificados.',
                    'usageFlow': 'El sistema envía un correo → sale firmado desde el dominio del negocio → llega a la bandeja principal con el remitente correcto.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'branding-pdfs-exportables',
                    'item': 'PDFs y exportables con branding',
                    'title': 'Documentos generados con encabezado y pie de marca',
                    'description': 'Facturas, reportes, certificados y descargas Excel/CSV salen con logo, paleta corporativa y pie de marca: cada documento refuerza la imagen profesional.',
                    'configuration': 'Encabezado/pie estandarizados en el generador de PDFs y estilos de marca en los exportes tabulares.',
                    'usageFlow': 'El usuario descarga o recibe un documento del sistema → el archivo llega con la identidad visual completa de la marca.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'branding-pdfs-plantilla-central',
                    'item': 'PDFs y exportables con branding',
                    'title': 'Un solo lugar para actualizar la identidad de todos los documentos',
                    'description': 'Logo, paleta y pie se definen una vez: si la marca evoluciona, todos los PDFs y exportes futuros salen actualizados sin tocar documento por documento.',
                    'configuration': 'Plantilla central de branding consumida por todos los generadores de documentos y exportes.',
                    'usageFlow': 'La marca evoluciona → se actualiza la plantilla central → todos los documentos siguientes salen con la nueva identidad.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'branding-open-graph',
                    'item': 'Tarjetas de previsualización en redes (Open Graph)',
                    'title': 'Los links compartidos muestran tarjeta con logo e imagen de marca',
                    'description': 'Al compartir un link del sitio en WhatsApp, Facebook, LinkedIn o X aparece una tarjeta con logo, imagen y colores de la marca, no un link plano — impacto directo en percepción y clics.',
                    'configuration': 'Metadatos Open Graph y Twitter Card por vista pública (título, descripción, imagen), validados con los depuradores de Meta y LinkedIn.',
                    'usageFlow': 'El usuario comparte un link → la red social lee los metadatos → la conversación muestra la tarjeta de marca.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'branding-pantallas-sistema',
                    'item': 'Pantallas del sistema con identidad de marca',
                    'title': 'Errores, login y estados de carga con la voz de la marca',
                    'description': 'Las páginas 404/500, mantenimiento, login y estados de carga usan la identidad visual y mensajes propios del negocio, en vez de las pantallas genéricas del framework.',
                    'configuration': 'Plantillas de error y mantenimiento personalizadas, skeletons/spinners con la paleta corporativa y textos en la voz de la marca.',
                    'usageFlow': 'El usuario cae en un error o espera una carga → la pantalla mantiene la identidad y lo orienta para continuar.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'branding-pantallas-textos-editables',
                    'item': 'Pantallas del sistema con identidad de marca',
                    'title': 'Mensajes de error y mantenimiento editables sin desarrollador',
                    'description': 'Los textos de las pantallas 404/500 y de mantenimiento se editan desde el panel, para ajustar el tono de la marca sin despliegues técnicos.',
                    'configuration': 'Textos de pantallas de sistema administrables desde el panel, con valores por defecto de respaldo.',
                    'usageFlow': 'El negocio quiere ajustar el mensaje → lo edita en el panel → la pantalla lo muestra de inmediato.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'branding-metadatos-estructurados',
                    'item': 'Metadatos estructurados para buscadores e IA',
                    'title': 'La marca aparece correctamente en Google y asistentes de IA',
                    'description': 'Buscadores y asistentes (Google, Bing, ChatGPT, Perplexity) reciben datos estructurados de la organización para mostrar logo, contacto y redes en paneles y resultados enriquecidos.',
                    'configuration': 'JSON-LD Organization (logo, colores, redes sociales, datos de contacto) validado con la prueba de resultados enriquecidos de Google.',
                    'usageFlow': 'Un buscador o asistente indexa el sitio → lee el JSON-LD → muestra la marca con sus datos correctos en sus resultados.',
                    'priority': 'medium',
                },
            ],
        },
        'behavior_tracking_module': {
            'epic_title': 'Alcance ampliado: Rastreo de Comportamiento de Usuarios',
            'epic_description': (
                'Desglose técnico del módulo de comportamiento. Alcance incluido: hasta '
                '15 vistas rastreadas, panel con hasta 8 KPIs y 4 gráficos, retención de 12 meses.'
            ),
            'requirements': [
                {
                    'flowKey': 'behavior-sesiones',
                    'item': 'Registro de sesiones y aperturas',
                    'title': 'Registro first-party de cada sesión de uso',
                    'description': 'Cada ingreso queda registrado con fecha, dispositivo y si es primera visita o retorno — todo en datos propios del negocio, sin cookies de terceros ni herramientas externas.',
                    'configuration': 'Evento de sesión first-party con identificador anónimo persistente, marca de tiempo y clasificación nueva visita vs retorno.',
                    'usageFlow': 'El usuario entra a la plataforma → se registra la sesión con su contexto → el dato queda disponible para KPIs y gráficos.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'behavior-sesiones-privacidad',
                    'item': 'Registro de sesiones y aperturas',
                    'title': 'Medición sin datos personales ni cookies de terceros',
                    'description': 'Los eventos usan un identificador anónimo y nunca guardan nombre, correo ni datos sensibles: medición útil cumpliendo habeas data y sin depender de terceros.',
                    'configuration': 'Identificador aleatorio no reversible, eventos sin datos personales y documentación lista para la política de privacidad del sitio.',
                    'usageFlow': 'El usuario navega → los eventos se registran anónimos → el negocio mide sin exponer datos personales.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'behavior-tiempo-por-vista',
                    'item': 'Vistas abiertas y tiempo por vista',
                    'title': 'Medición de vistas abiertas y segundos de permanencia',
                    'description': 'Se registra qué vistas abre cada usuario y cuánto tiempo activo pasa en cada una, sobre las hasta 15 vistas acordadas con el cliente al inicio.',
                    'configuration': 'Instrumentación de las vistas acordadas con medición de tiempo activo (heartbeat) y corte por inactividad.',
                    'usageFlow': 'El usuario navega entre vistas → cada apertura y su duración quedan registradas → alimentan el mapa de interés y el embudo.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'behavior-tiempo-precision',
                    'item': 'Vistas abiertas y tiempo por vista',
                    'title': 'El tiempo medido es tiempo real de uso',
                    'description': 'Las pestañas en segundo plano, la inactividad o el dispositivo bloqueado no inflan la métrica: solo cuenta el tiempo realmente activo en la vista.',
                    'configuration': 'Pausa del conteo por visibilidad de pestaña e inactividad, con reanudación automática al volver.',
                    'usageFlow': 'El usuario cambia de pestaña → el conteo se pausa → vuelve → el conteo continúa → la métrica refleja uso real.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'behavior-mapa-interes',
                    'item': 'Mapa de interés por vista',
                    'title': 'Ranking de vistas por atención recibida',
                    'description': 'El negocio ve qué vistas concentran la atención (tiempo acumulado y visitas) y cuáles pasan desapercibidas, para decidir dónde invertir mejoras.',
                    'configuration': 'Agregación por vista de tiempo total y número de aperturas, ordenada de mayor a menor interés.',
                    'usageFlow': 'El administrador abre el panel de comportamiento → ve el ranking de vistas → identifica qué funciona y qué no.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'behavior-embudo-abandonos',
                    'item': 'Embudo de recorrido con abandonos',
                    'title': 'Embudo principal con puntos de abandono',
                    'description': 'Un (1) embudo definido junto al cliente muestra cómo avanzan los usuarios entre las vistas rastreadas y en qué paso exacto abandonan.',
                    'configuration': 'Definición del embudo sobre las vistas rastreadas con conversión y abandono por paso.',
                    'usageFlow': 'El administrador abre el embudo → ve el porcentaje que avanza en cada paso → detecta el punto de mayor fuga.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'behavior-embudo-comparativo',
                    'item': 'Embudo de recorrido con abandonos',
                    'title': 'El embudo se compara entre períodos',
                    'description': 'La conversión de cada paso se compara contra el período anterior, para saber con datos si los cambios del negocio mejoraron el recorrido.',
                    'configuration': 'Cálculo del embudo por rango de fechas con comparación contra el rango anterior equivalente.',
                    'usageFlow': 'El administrador elige el período → ve el embudo actual junto al anterior → confirma si la mejora funcionó.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'behavior-panel-integrado',
                    'item': 'Panel de comportamiento integrado',
                    'title': 'Dashboard propio con hasta 8 KPIs y 4 gráficos',
                    'description': 'Dentro del propio panel administrativo: sesiones, tiempo promedio, vistas más abiertas y desglose por dispositivo — sin licencias ni suscripciones externas.',
                    'configuration': 'Consultas agregadas optimizadas sobre los eventos propios; tarjetas KPI y gráficos limitados al alcance contratado (8 KPIs / 4 gráficos).',
                    'usageFlow': 'El administrador entra al panel → ve los KPIs y gráficos actualizados → filtra por rango de fechas.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'behavior-panel-exportacion',
                    'item': 'Panel de comportamiento integrado',
                    'title': 'KPIs y datos exportables para informes',
                    'description': 'Los indicadores del panel se exportan a Excel/CSV para armar informes o análisis fuera de la plataforma.',
                    'configuration': 'Exportación de los agregados visibles por rango de fechas en formatos tabulares.',
                    'usageFlow': 'El administrador filtra el período → exporta → usa el archivo en su informe.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'behavior-desglose-dispositivo',
                    'item': 'Desglose por dispositivo',
                    'title': 'Uso por móvil, tablet y escritorio',
                    'description': 'El negocio sabe desde qué tipo de dispositivo usan la plataforma para priorizar mejoras donde los usuarios realmente están.',
                    'configuration': 'Clasificación de dispositivo por user-agent en el evento de sesión, agregada en el panel.',
                    'usageFlow': 'El administrador abre el desglose → ve la proporción móvil/tablet/escritorio → prioriza el canal dominante.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'behavior-retencion-datos',
                    'item': 'Datos propios con retención de 12 meses',
                    'title': 'Eventos almacenados en la base del cliente por 12 meses',
                    'description': 'Los datos viven en la base de datos del negocio y se conservan 12 meses; no incluye grabación de pantalla, mapas de calor de clics ni rastreo entre sitios.',
                    'configuration': 'Purga programada de eventos mayores a 12 meses y límites de alcance documentados.',
                    'usageFlow': 'Los eventos se acumulan en la base propia → la purga mensual elimina lo que supera la retención → el panel siempre consulta datos vigentes.',
                    'priority': 'medium',
                },
            ],
        },
        'reports_alerts_module': {
            'epic_title': 'Alcance ampliado: Reportes y Alertas vía Correo o WhatsApp',
            'epic_description': (
                'Desglose técnico del módulo de reportes y alertas. Cada requerimiento '
                'cubre un canal o capacidad del alcance del módulo.'
            ),
            'requirements': [
                {
                    'flowKey': 'reports-correo-automatico',
                    'item': 'Reportes automáticos por correo',
                    'title': 'Resúmenes periódicos con métricas clave en la bandeja de entrada',
                    'description': 'El responsable recibe el resumen del negocio (ventas, registros, actividad) por correo sin entrar al sistema, en la frecuencia que elija.',
                    'configuration': 'Generación programada del reporte con plantilla de marca y métricas acordadas; registro de envíos.',
                    'usageFlow': 'Llega la hora programada → el sistema arma el reporte con los datos del período → lo envía al correo configurado.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'reports-correo-adjuntos',
                    'item': 'Reportes automáticos por correo',
                    'title': 'El detalle del reporte viaja adjunto',
                    'description': 'Además del resumen en el cuerpo del correo, el reporte adjunta el detalle (Excel/CSV o PDF) para revisarlo a fondo o archivarlo.',
                    'configuration': 'Generación del adjunto por reporte con el detalle del período y la plantilla de marca.',
                    'usageFlow': 'Llega el reporte → el responsable abre el adjunto → revisa el detalle completo sin entrar al sistema.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'reports-alertas-personalizadas',
                    'item': 'Alertas personalizadas',
                    'title': 'Alertas por eventos y umbrales definidos por el negocio',
                    'description': 'Nuevas ventas, registros de usuarios, stock bajo o cualquier métrica definida disparan un aviso inmediato al responsable.',
                    'configuration': 'Reglas por evento o umbral configurables; evaluación al ocurrir el evento y disparo inmediato del canal elegido.',
                    'usageFlow': 'Ocurre el evento (p. ej. stock bajo) → la regla se evalúa → el aviso llega por el canal configurado con el detalle.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'reports-alertas-antirruido',
                    'item': 'Alertas personalizadas',
                    'title': 'Alertas sin bombardeo: agrupación y silencio configurables',
                    'description': 'La misma condición no dispara avisos en cadena: las repeticiones se agrupan en un solo aviso y cada regla tiene su período de silencio.',
                    'configuration': 'Ventana de silencio configurable por regla y agrupación de ocurrencias repetidas en un único aviso.',
                    'usageFlow': 'El stock sigue bajo toda la mañana → llega UN aviso agrupado → el siguiente solo sale cuando termina el período de silencio.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'reports-whatsapp',
                    'item': 'Integración con WhatsApp',
                    'title': 'Alertas y reportes por WhatsApp con la API oficial',
                    'description': 'Los avisos llegan al número de WhatsApp del negocio por el mismo canal donde ya atiende a sus clientes, usando la API oficial.',
                    'configuration': 'API oficial de WhatsApp (Cloud API) con plantillas aprobadas, número verificado del negocio y manejo de fallos de entrega.',
                    'usageFlow': 'Se dispara un reporte o alerta → el sistema envía la plantilla aprobada por WhatsApp → el responsable la recibe en su chat.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'reports-whatsapp-respaldo-correo',
                    'item': 'Integración con WhatsApp',
                    'title': 'Si WhatsApp falla, el aviso llega por correo',
                    'description': 'Una falla de entrega o una plantilla no disponible no dejan al negocio sin su aviso: el sistema recurre al correo y registra el motivo del desvío.',
                    'configuration': 'Detección del fallo de entrega con reenvío automático por correo y registro del canal finalmente usado.',
                    'usageFlow': 'El envío por WhatsApp falla → el sistema reenvía por correo → el responsable recibe el aviso igual y el fallo queda registrado.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'reports-programacion',
                    'item': 'Programación de envíos',
                    'title': 'Frecuencia y horario de reportes configurables',
                    'description': 'Cada reporte se programa diario, semanal, mensual o en tiempo real, en el horario y zona horaria del negocio.',
                    'configuration': 'Tareas programadas (Huey) por reporte con frecuencia, hora y zona horaria configurables desde el panel.',
                    'usageFlow': 'El administrador define la frecuencia y hora → el sistema respeta la programación → puede pausar o ajustar cuando quiera.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'reports-historial-envios',
                    'item': 'Programación de envíos',
                    'title': 'Historial de envíos con estado de entrega',
                    'description': 'Cada reporte y alerta enviados quedan en un historial con fecha, canal y estado (entregado o fallido), consultable en cualquier momento.',
                    'configuration': 'Bitácora de envíos por regla y por reporte con su estado final de entrega.',
                    'usageFlow': 'El administrador duda si salió el reporte → abre el historial → confirma fecha, canal y estado.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'reports-resumen-ejecutivo',
                    'item': 'Resumen ejecutivo periódico',
                    'title': 'Informe consolidado para decisión rápida',
                    'description': 'Un informe con las métricas más relevantes del proyecto, diseñado para leerse en minutos y decidir con datos.',
                    'configuration': 'Selección de métricas clave acordadas con el cliente y formato ejecutivo (titulares + variaciones vs período anterior).',
                    'usageFlow': 'Llega el período configurado → se consolida el informe ejecutivo → el responsable lo lee y actúa sobre los cambios relevantes.',
                    'priority': 'medium',
                },
            ],
        },
        'email_marketing_module': {
            'epic_title': 'Alcance ampliado: Integración de Email Marketing',
            'epic_description': (
                'Desglose técnico del módulo de email marketing. Cada requerimiento '
                'cubre una capacidad del alcance del módulo.'
            ),
            'requirements': [
                {
                    'flowKey': 'email-mkt-captura-leads',
                    'item': 'Captura de leads',
                    'title': 'Formularios y pop-ups que capturan correos de interesados',
                    'description': 'Los visitantes interesados dejan su correo en formularios optimizados y pop-ups no invasivos, con validación y confirmación de suscripción.',
                    'configuration': 'Formularios con validación de correo, reglas de aparición del pop-up (tiempo/scroll/salida) y registro anti-duplicados.',
                    'usageFlow': 'El visitante ve el formulario o pop-up → deja su correo → recibe la confirmación → queda en la lista del negocio.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'email-mkt-captura-doble-optin',
                    'item': 'Captura de leads',
                    'title': 'Suscripciones confirmadas con doble opt-in',
                    'description': 'El suscriptor confirma su correo antes de entrar a la lista: listas limpias, menos rebotes y cumplimiento de las buenas prácticas de permiso.',
                    'configuration': 'Correo de confirmación con enlace de activación y estado pendiente hasta confirmar.',
                    'usageFlow': 'El visitante se suscribe → recibe el correo de confirmación → confirma → recién entonces entra a la lista activa.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'email-mkt-automatizaciones',
                    'item': 'Automatizaciones de email',
                    'title': 'Secuencias automáticas de bienvenida, carrito y re-engagement',
                    'description': 'Los suscriptores reciben secuencias sin intervención manual: bienvenida al registrarse, recordatorio de carrito abandonado, seguimiento post-compra y reactivación de inactivos.',
                    'configuration': 'Disparadores por evento (alta, carrito, compra, inactividad) conectados a las automatizaciones del proveedor elegido.',
                    'usageFlow': 'Ocurre el evento → se dispara la secuencia correspondiente → los correos salen en los intervalos definidos.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'email-mkt-automatizaciones-salida',
                    'item': 'Automatizaciones de email',
                    'title': 'Las secuencias saben cuándo detenerse',
                    'description': 'Comprar saca del flujo de carrito abandonado y darse de baja corta toda secuencia: nadie recibe correos fuera de contexto.',
                    'configuration': 'Condiciones de salida por secuencia (compra, baja, conversión) evaluadas antes de cada envío.',
                    'usageFlow': 'El cliente compra a mitad de la secuencia de carrito → la secuencia se detiene → solo siguen las comunicaciones que corresponden.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'email-mkt-segmentacion',
                    'item': 'Segmentación de audiencia',
                    'title': 'Suscriptores clasificados por comportamiento e intereses',
                    'description': 'Las listas se segmentan por comportamiento, intereses y datos demográficos para que cada mensaje llegue a quien le es relevante.',
                    'configuration': 'Sincronización de atributos y etiquetas desde la plataforma hacia el proveedor (compras, categorías vistas, origen del lead).',
                    'usageFlow': 'El suscriptor interactúa con el sitio → sus atributos se actualizan → las campañas se dirigen al segmento correcto.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'email-mkt-segmentacion-dinamica',
                    'item': 'Segmentación de audiencia',
                    'title': 'Los segmentos se actualizan solos con el comportamiento',
                    'description': 'El suscriptor entra y sale de los segmentos automáticamente cuando su comportamiento cambia, sin mantenimiento manual de listas.',
                    'configuration': 'Recálculo de pertenencia a segmentos al actualizarse los atributos sincronizados.',
                    'usageFlow': 'El suscriptor hace su primera compra → sale de «prospectos» y entra a «clientes» → las próximas campañas le hablan como cliente.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'email-mkt-analitica',
                    'item': 'Analítica de campañas',
                    'title': 'Métricas de apertura, clics y conversión por campaña',
                    'description': 'Cada campaña reporta aperturas, clics, conversiones y ROI para optimizar la estrategia de comunicación con datos reales.',
                    'configuration': 'Lectura de métricas vía API del proveedor y atribución de conversiones con parámetros UTM en los enlaces.',
                    'usageFlow': 'Se envía la campaña → las métricas se consultan desde el panel → el negocio ajusta contenido y segmentos según resultados.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'email-mkt-analitica-salud-lista',
                    'item': 'Analítica de campañas',
                    'title': 'Salud de la lista: rebotes, bajas y quejas visibles',
                    'description': 'La tasa de rebote, las bajas y las quejas de spam se monitorean para proteger la reputación del remitente y depurar la lista a tiempo.',
                    'configuration': 'Lectura de métricas de salud vía API del proveedor con umbrales de alerta configurados.',
                    'usageFlow': 'Una campaña dispara rebotes → el indicador lo muestra → el negocio depura la lista antes de dañar su remitente.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'email-mkt-integracion-plataformas',
                    'item': 'Integración con plataformas',
                    'title': 'Conexión nativa con el proveedor elegido (Mailchimp, SendGrid, Brevo…)',
                    'description': 'La plataforma queda conectada con el proveedor de email marketing que el negocio use o elija, con listas y eventos sincronizados.',
                    'configuration': 'Credenciales API del proveedor, mapeo de listas/audiencias y sincronización de altas, bajas y rebotes.',
                    'usageFlow': 'Se configuran las credenciales → se valida la conexión con una lista de prueba → las altas y eventos fluyen automáticamente.',
                    'priority': 'high',
                },
            ],
        },
        'qr_generator_module': {
            'epic_title': 'Alcance ampliado: Generador de Códigos QR',
            'epic_description': (
                'Desglose técnico del módulo QR. Cada requerimiento cubre una capacidad '
                'del generador y su ciclo de vida.'
            ),
            'requirements': [
                {
                    'flowKey': 'qr-generacion-instantanea',
                    'item': 'Generación instantánea',
                    'title': 'QR desde URLs, textos, vCard, WiFi o WhatsApp en segundos',
                    'description': 'Cualquier enlace, texto, contacto vCard, red WiFi o número de WhatsApp se convierte en un QR listo para usar, generado al instante desde el panel.',
                    'configuration': 'Generación server-side con corrección de errores configurable y tipos de contenido soportados (URL, texto, vCard, WiFi, wa.me).',
                    'usageFlow': 'El administrador elige el tipo de contenido → ingresa el dato → el QR se genera y queda listo para descargar o compartir.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'qr-generacion-validacion',
                    'item': 'Generación instantánea',
                    'title': 'El contenido se valida antes de generar el código',
                    'description': 'URLs mal formadas, vCards incompletas o textos que exceden el límite se detectan antes de generar: ningún QR impreso sale apuntando a un destino roto.',
                    'configuration': 'Validación por tipo de contenido (formato de URL, campos de vCard, longitud máxima) con mensajes de corrección claros.',
                    'usageFlow': 'El administrador pega el dato → el sistema valida → corrige si hay error → genera el QR ya verificado.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'qr-personalizacion-marca',
                    'item': 'Personalización con tu marca',
                    'title': 'QR con colores corporativos, logo y formatos de impresión',
                    'description': 'Cada código puede llevar los colores de la marca y el logo al centro, exportado en PNG, SVG o PDF en alta resolución sin perder lectura.',
                    'configuration': 'Paleta corporativa aplicada con verificación de contraste/escaneabilidad y exportes vectoriales para imprenta.',
                    'usageFlow': 'El administrador aplica el estilo de marca → previsualiza y prueba el escaneo → descarga el formato que necesita.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'qr-codigos-dinamicos',
                    'item': 'Códigos dinámicos editables',
                    'title': 'Cambiar el destino de un QR ya impreso sin reimprimirlo',
                    'description': 'Los QR dinámicos apuntan a un enlace propio editable: el negocio cambia el destino (menú de temporada, promoción, evento) y el código impreso sigue sirviendo.',
                    'configuration': 'Redirector propio con slug corto por código y edición del destino desde el panel; el QR impreso apunta siempre al redirector.',
                    'usageFlow': 'El administrador edita el destino del código → guarda → todos los escaneos siguientes llegan al nuevo destino.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'qr-dinamicos-historial',
                    'item': 'Códigos dinámicos editables',
                    'title': 'Historial de destinos de cada código dinámico',
                    'description': 'Cada cambio de destino queda registrado (cuándo y a dónde apuntaba), para saber qué vio quien escaneó el código en cada época.',
                    'configuration': 'Bitácora de destinos por código con su fecha de vigencia.',
                    'usageFlow': 'El administrador consulta un código → ve la línea de tiempo de destinos → entiende qué campaña estuvo activa en cada fecha.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'qr-tracking-escaneos',
                    'item': 'Tracking de escaneos',
                    'title': 'Conteo de escaneos por código, dispositivo y momento',
                    'description': 'Cada código reporta cuántas veces fue escaneado, desde qué tipo de dispositivo y cuándo — para medir campañas físicas con datos.',
                    'configuration': 'Registro de escaneo en el redirector (marca de tiempo, dispositivo) con agregados por código y campaña.',
                    'usageFlow': 'Alguien escanea el código → el redirector registra el evento y redirige → las métricas quedan visibles en el panel.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'qr-tracking-exportacion',
                    'item': 'Tracking de escaneos',
                    'title': 'Métricas de escaneo exportables por campaña',
                    'description': 'Los escaneos se exportan a Excel/CSV por código o por campaña, para reportar con datos el resultado de las piezas físicas.',
                    'configuration': 'Exportación de eventos agregados por código, campaña y rango de fechas.',
                    'usageFlow': 'Termina la campaña → el administrador exporta los escaneos → presenta el resultado con datos.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'qr-biblioteca',
                    'item': 'Biblioteca de códigos',
                    'title': 'Todos los QR organizados por campaña o propósito',
                    'description': 'Los códigos generados quedan en una biblioteca ordenada, listos para reutilizar, descargar de nuevo o desactivar cuando ya no apliquen.',
                    'configuration': 'Listado con agrupación por campaña/propósito, estados activo/inactivo y regeneración de descargas.',
                    'usageFlow': 'El administrador abre la biblioteca → filtra por campaña → reutiliza, descarga o desactiva el código que necesita.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'qr-casos-de-uso',
                    'item': 'Casos de uso listos para activar',
                    'title': 'Plantillas preconfiguradas: menú, WhatsApp, eventos, reseñas',
                    'description': 'Casos comunes listos para arrancar el mismo día: menú digital, link a WhatsApp, registro a eventos, descarga de catálogo, encuestas, propinas o reseñas.',
                    'configuration': 'Plantillas por caso de uso con el tipo de contenido y estilo predefinidos, editables antes de generar.',
                    'usageFlow': 'El administrador elige la plantilla del caso → ajusta el dato puntual → el QR queda operativo de inmediato.',
                    'priority': 'low',
                },
            ],
        },
        'content_generator_module': {
            'epic_title': 'Alcance ampliado: Generador de Contenido con IA y Calendario Editorial',
            'epic_description': (
                'Desglose técnico del módulo de contenido. Cada requerimiento cubre una '
                'capacidad del generador o del calendario editorial.'
            ),
            'requirements': [
                {
                    'flowKey': 'content-redaccion-ia',
                    'item': 'Redacción asistida con IA',
                    'title': 'Borradores de blogs, correos y posts desde un brief simple',
                    'description': 'A partir de una idea breve, la IA entrega borradores de blogs, newsletters y publicaciones, con control de tono, extensión y formato en un par de clics.',
                    'configuration': 'Generación vía proveedor de IA con plantillas de prompt por tipo de pieza y parámetros de tono/extensión.',
                    'usageFlow': 'El usuario escribe el brief → elige tipo de pieza y tono → recibe el borrador → lo edita y aprueba.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'content-redaccion-aprobacion',
                    'item': 'Redacción asistida con IA',
                    'title': 'Nada se publica sin aprobación humana',
                    'description': 'Todo borrador generado pasa por revisión: solo el contenido aprobado por una persona puede programarse o publicarse.',
                    'configuration': 'Estados borrador → en revisión → aprobado, con la publicación restringida a piezas aprobadas.',
                    'usageFlow': 'La IA entrega el borrador → el responsable lo revisa y ajusta → lo aprueba → recién entonces se puede programar.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'content-voz-de-marca',
                    'item': 'Voz de marca y plantillas',
                    'title': 'La identidad editorial se define una vez y se respeta siempre',
                    'description': 'Tono, estilo, palabras prohibidas y llamados a la acción se configuran una sola vez; cada pieza generada respeta esa voz.',
                    'configuration': 'Perfil editorial persistente (tono, estilo, vocabulario vetado, CTAs) inyectado en cada generación.',
                    'usageFlow': 'El negocio define su voz una vez → cada nueva pieza sale alineada → puede ajustar el perfil cuando la marca evolucione.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'content-multicanal',
                    'item': 'Multicanal: blog, email y redes',
                    'title': 'Una idea adaptada al formato de cada canal',
                    'description': 'La misma idea se convierte en post largo para blog, asunto y cuerpo para email, y copy corto para Instagram, LinkedIn o X — sin reescribir desde cero.',
                    'configuration': 'Transformaciones por canal con límites de longitud y formato específicos de cada plataforma.',
                    'usageFlow': 'El usuario elige la pieza base → pide las variantes de canal → recibe cada versión adaptada y lista para programar.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'content-multicanal-vista-previa',
                    'item': 'Multicanal: blog, email y redes',
                    'title': 'Vista previa fiel por canal antes de programar',
                    'description': 'Cada variante se previsualiza como se verá en su canal (longitudes, cortes, formato) antes de agendarla, sin sorpresas al publicar.',
                    'configuration': 'Previsualización por canal con los límites de longitud y formato de cada plataforma aplicados.',
                    'usageFlow': 'El usuario genera las variantes → previsualiza cada canal → ajusta la que se corta → agenda con confianza.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'content-calendario-editorial',
                    'item': 'Calendario editorial visual',
                    'title': 'Vista mensual y semanal con arrastrar y soltar',
                    'description': 'Todas las piezas (borrador, programada, publicada) se ven en un calendario mensual o semanal; reorganizar fechas es arrastrar y soltar.',
                    'configuration': 'Calendario con estados por pieza y reprogramación por drag & drop persistida al soltar.',
                    'usageFlow': 'El usuario abre el calendario → ve el plan del mes → arrastra una pieza a otra fecha → el cambio queda guardado.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'content-programacion-automatica',
                    'item': 'Programación y publicación automática',
                    'title': 'Publicación sola en la fecha y hora agendadas',
                    'description': 'Cada pieza agendada se publica sin intervención: el blog la publica, el correo se envía y las redes conectadas reciben el post en el momento definido.',
                    'configuration': 'Cola de publicación programada (Huey) por canal con manejo de fallos y reintento notificado.',
                    'usageFlow': 'El usuario agenda la pieza → llega la fecha/hora → el sistema publica en el canal → el estado pasa a "publicada".',
                    'priority': 'high',
                },
                {
                    'flowKey': 'content-programacion-fallos',
                    'item': 'Programación y publicación automática',
                    'title': 'Una publicación fallida avisa y se reintenta sin duplicar',
                    'description': 'Si un canal falla al publicar, el responsable recibe el aviso con el motivo, y el reintento nunca duplica una pieza ya publicada.',
                    'configuration': 'Reintento con verificación de publicación previa y notificación del fallo con su causa.',
                    'usageFlow': 'La red social rechaza la publicación → llega el aviso → el usuario reintenta → la pieza sale una sola vez.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'content-panel-seguimiento',
                    'item': 'Panel de seguimiento',
                    'title': 'Estado y desempeño de cada publicación en un solo lugar',
                    'description': 'Borrador, programada, publicada o fallida: cada pieza muestra su estado y métricas básicas, con reagendar o duplicar a un clic.',
                    'configuration': 'Estados por pieza con métricas básicas por canal y acciones rápidas (reagendar, duplicar).',
                    'usageFlow': 'El usuario abre el panel → revisa estados y desempeño → reintenta una fallida o duplica la que funcionó.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'content-integracion-canales',
                    'item': 'Integración con tus canales',
                    'title': 'Blog, proveedor de email y redes conectados al calendario',
                    'description': 'Lo planeado en el calendario sale publicado en los canales reales del negocio: su blog, su proveedor de correo y sus redes sociales conectadas.',
                    'configuration': 'Conexión API por canal (blog propio, proveedor de email, redes) con validación de credenciales y estado de conexión visible.',
                    'usageFlow': 'El negocio conecta sus canales una vez → el calendario publica en ellos → el estado de conexión avisa si algo requiere re-autorización.',
                    'priority': 'medium',
                },
            ],
        },
        'i18n_module': {
            'epic_title': 'Alcance ampliado: Multi-idioma y Localización Regional',
            'epic_description': (
                'Desglose técnico del módulo de internacionalización. Cada requerimiento '
                'cubre una capacidad del alcance multi-idioma.'
            ),
            'requirements': [
                {
                    'flowKey': 'i18n-multi-idioma',
                    'item': 'Soporte multi-idioma nativo',
                    'title': 'Todo el contenido servido en dos o más idiomas',
                    'description': 'El sitio sirve su contenido completo en los idiomas definidos, con selector visible y la preferencia del usuario recordada entre visitas.',
                    'configuration': 'Estructura i18n nativa (rutas o prefijos por idioma), selector persistente y contenido bilingüe por sección.',
                    'usageFlow': 'El visitante cambia el idioma en el selector → todo el contenido cambia → su preferencia queda recordada para la próxima visita.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'i18n-seo-hreflang',
                    'item': 'Soporte multi-idioma nativo',
                    'title': 'Cada idioma se posiciona por separado en Google',
                    'description': 'Cada versión de idioma tiene su URL propia con etiquetas hreflang: los buscadores muestran a cada usuario la versión de su idioma.',
                    'configuration': 'URLs por idioma con hreflang recíproco y sitemap multilingüe.',
                    'usageFlow': 'Google indexa el sitio → detecta las versiones por idioma → el usuario hispano ve el resultado en español y el anglo en inglés.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'i18n-formatos-regionales',
                    'item': 'Formatos regionales de moneda y fecha',
                    'title': 'Monedas, números y fechas en el formato de cada región',
                    'description': 'Los montos, números y fechas se muestran con el formato correcto de la región o idioma activo, sin ambigüedades para el visitante.',
                    'configuration': 'Formateo por locale (separadores, símbolo de moneda, orden de fecha) aplicado en todas las vistas con datos.',
                    'usageFlow': 'El visitante navega en su idioma → precios y fechas aparecen en su formato regional → no hay confusión de montos ni fechas.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'i18n-zona-horaria',
                    'item': 'Formatos regionales de moneda y fecha',
                    'title': 'Fechas y horas en la zona horaria del visitante',
                    'description': 'Horarios de eventos, publicaciones y vencimientos se muestran en la hora local de quien mira, sin confusiones de zona horaria.',
                    'configuration': 'Almacenamiento en UTC con conversión a la zona del navegador al mostrar.',
                    'usageFlow': 'El negocio publica un evento a las 7 pm de Bogotá → el visitante en Madrid lo ve en su hora local → nadie llega a deshora.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'i18n-catalogos-por-pais',
                    'item': 'Catálogos y precios por país',
                    'title': 'Productos, precios y disponibilidad diferenciados por mercado',
                    'description': 'El negocio puede mostrar catálogos, precios y disponibilidad distintos según el país o mercado objetivo del visitante.',
                    'configuration': 'Reglas de visibilidad y precio por región sobre el catálogo, con mercado por defecto de respaldo.',
                    'usageFlow': 'El visitante entra desde un mercado configurado → ve el catálogo y precios de su región → compra en las condiciones correctas.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'i18n-catalogos-fallback',
                    'item': 'Catálogos y precios por país',
                    'title': 'Mercados sin configuración caen al catálogo por defecto',
                    'description': 'Un visitante de un país no configurado ve el mercado por defecto completo, y un producto sin precio regional usa su precio base — nunca una página vacía.',
                    'configuration': 'Mercado por defecto obligatorio y reglas de respaldo por producto (precio base, disponibilidad global).',
                    'usageFlow': 'Entra un visitante de un país no configurado → ve el catálogo por defecto → compra en condiciones base sin errores.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'i18n-flujo-traduccion',
                    'item': 'Flujo de traducción integrado',
                    'title': 'Panel para gestionar traducciones sin intervención técnica',
                    'description': 'El equipo del negocio administra las traducciones de cada sección desde el panel, con indicador claro de contenido pendiente por traducir.',
                    'configuration': 'Editor de traducciones por sección con estado (traducido/pendiente) y vista previa por idioma.',
                    'usageFlow': 'El administrador abre el panel de traducciones → ve lo pendiente → completa la traducción → publica el idioma actualizado.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'i18n-deteccion-idioma',
                    'item': 'Detección automática de idioma',
                    'title': 'El visitante llega directo a la versión de su idioma',
                    'description': 'El sitio detecta el idioma preferido del navegador y redirige automáticamente a la versión correspondiente desde la primera visita.',
                    'configuration': 'Detección por encabezado del navegador con redirección a la variante correcta y respeto de la elección manual posterior.',
                    'usageFlow': 'El visitante abre el sitio → es llevado a su idioma automáticamente → si cambia manualmente, esa elección manda.',
                    'priority': 'medium',
                },
            ],
        },
        'live_chat_module': {
            'epic_title': 'Alcance ampliado: Chat en Vivo First-Party',
            'epic_description': (
                'Desglose técnico del módulo de chat. Cada requerimiento cubre una '
                'capacidad del chat alojado en la infraestructura del cliente.'
            ),
            'requirements': [
                {
                    'flowKey': 'chat-widget-embebido',
                    'item': 'Widget de chat embebido',
                    'title': 'Conversación en tiempo real sin salir de la página',
                    'description': 'Un componente flotante en el sitio permite al visitante iniciar y continuar una conversación mientras sigue navegando la página.',
                    'configuration': 'Widget propio (sin servicios externos) con estado abierto/minimizado persistente y branding del negocio.',
                    'usageFlow': 'El visitante abre el widget → escribe su mensaje → conversa en tiempo real sin abandonar la página.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'chat-widget-sin-agentes',
                    'item': 'Widget de chat embebido',
                    'title': 'Sin agentes conectados, el widget captura el contacto',
                    'description': 'Si nadie está disponible, el visitante deja nombre, correo y mensaje; la conversación queda creada en la bandeja y el negocio responde al volver.',
                    'configuration': 'Formulario de contacto en el widget cuando no hay agentes en línea, creando la conversación con los datos del visitante.',
                    'usageFlow': 'El visitante escribe sin agentes en línea → deja sus datos → el agente responde al conectarse → el visitante recibe la respuesta.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'chat-panel-agente',
                    'item': 'Panel de agente en el admin',
                    'title': 'Los agentes atienden desde el propio panel administrativo',
                    'description': 'Las conversaciones se atienden desde el mismo panel del sitio: sin aplicaciones externas, cuentas adicionales ni costos por asiento.',
                    'configuration': 'Bandeja de conversaciones con estados (nueva, en curso, cerrada), asignación de agente y vista de historial del visitante.',
                    'usageFlow': 'El agente abre la bandeja → toma una conversación → responde y la cierra al resolver.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'chat-agente-traspaso',
                    'item': 'Panel de agente en el admin',
                    'title': 'Traspaso de conversaciones entre agentes con contexto',
                    'description': 'Una conversación se reasigna a otro agente sin perder el hilo: quien la recibe ve el historial completo y el visitante no repite nada.',
                    'configuration': 'Reasignación desde la bandeja con historial completo visible y registro de qué agente atendió cada tramo.',
                    'usageFlow': 'El agente debe salir → reasigna la conversación → el nuevo agente lee el hilo completo → continúa la atención sin cortes.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'chat-websocket',
                    'item': 'Comunicación en tiempo real (WebSocket)',
                    'title': 'Mensajes instantáneos en ambos sentidos',
                    'description': 'Visitante y agente se leen al instante, sin recargar la página ni demoras perceptibles, incluso en conversaciones largas.',
                    'configuration': 'Conexión persistente WebSocket con reconexión automática y entrega confirmada de mensajes.',
                    'usageFlow': 'Cualquiera de las partes escribe → el mensaje aparece al instante del otro lado → si se corta la conexión, se restablece sola.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'chat-websocket-presencia',
                    'item': 'Comunicación en tiempo real (WebSocket)',
                    'title': 'Indicadores de presencia y escritura en tiempo real',
                    'description': 'El visitante ve cuándo el agente está en línea y escribiendo, y viceversa: la conversación se siente atendida y viva.',
                    'configuration': 'Eventos de presencia y de escritura sobre la conexión WebSocket existente.',
                    'usageFlow': 'El agente empieza a escribir → el visitante ve el indicador de escritura → la espera se siente atendida.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'chat-historial-propio',
                    'item': 'Historial de conversaciones propio',
                    'title': 'Todas las conversaciones guardadas en la base del cliente',
                    'description': 'El historial completo vive en la base de datos del negocio, con búsqueda, filtros por fecha y exportación — los datos son 100% propios.',
                    'configuration': 'Persistencia de conversaciones y mensajes con búsqueda por texto, filtros por fecha/estado y exportación.',
                    'usageFlow': 'El administrador busca una conversación → la encuentra por texto o fecha → la revisa o exporta cuando la necesita.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'chat-respuestas-automaticas',
                    'item': 'Respuestas automáticas configurables',
                    'title': 'Bienvenida, fuera de horario y FAQ sin agente disponible',
                    'description': 'El chat responde solo con mensajes de bienvenida, avisos fuera de horario y respuestas frecuentes, manteniendo la atención activa 24/7.',
                    'configuration': 'Mensajes automáticos configurables por horario de atención y catálogo de respuestas frecuentes.',
                    'usageFlow': 'El visitante escribe fuera de horario → recibe el aviso y las opciones de FAQ → su mensaje queda en la bandeja para el siguiente turno.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'chat-notificaciones',
                    'item': 'Notificaciones de nuevos chats',
                    'title': 'El agente se entera al instante de cada mensaje nuevo',
                    'description': 'Cada conversación nueva o mensaje entrante notifica al agente en tiempo real, garantizando tiempos de respuesta mínimos.',
                    'configuration': 'Alertas en el panel (sonido/contador) al crear conversación o recibir mensaje, con indicador de no leídos.',
                    'usageFlow': 'El visitante escribe → el agente ve la alerta y el contador → entra a la conversación y responde.',
                    'priority': 'medium',
                },
            ],
        },
        'dark_mode_module': {
            'epic_title': 'Alcance ampliado: Modo Oscuro y Claro',
            'epic_description': (
                'Desglose técnico del módulo de tema visual. Cada requerimiento cubre '
                'una capacidad del sistema de modo claro/oscuro.'
            ),
            'requirements': [
                {
                    'flowKey': 'dark-paleta-dual',
                    'item': 'Paleta de colores dual',
                    'title': 'Dos sistemas de color completos y coherentes',
                    'description': 'Claro y oscuro tienen cada uno su paleta completa: textos legibles, contrastes correctos y coherencia visual en todas las vistas.',
                    'configuration': 'Variables CSS semánticas por tema con verificación de contraste en componentes clave.',
                    'usageFlow': 'El usuario alterna el tema → toda la interfaz cambia al instante → nada queda ilegible ni fuera de estilo.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'dark-contraste-accesible',
                    'item': 'Paleta de colores dual',
                    'title': 'Contraste accesible verificado en ambos modos',
                    'description': 'Los textos y controles clave cumplen contraste AA tanto en claro como en oscuro: legibilidad garantizada también para usuarios con baja visión.',
                    'configuration': 'Verificación de contraste WCAG AA sobre los componentes principales en ambos temas.',
                    'usageFlow': 'El usuario usa cualquiera de los dos modos → todos los textos y botones se leen sin esfuerzo → la experiencia es accesible.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'dark-deteccion-sistema',
                    'item': 'Detección automática de preferencia del sistema',
                    'title': 'El tema inicial respeta la preferencia del dispositivo',
                    'description': 'Desde la primera visita, el sitio aplica el modo que el usuario ya usa en su sistema operativo, sin que tenga que configurarlo.',
                    'configuration': 'Lectura de prefers-color-scheme al cargar, antes del primer render para evitar parpadeo de tema.',
                    'usageFlow': 'El visitante con su sistema en oscuro abre el sitio → lo ve directamente en oscuro → sin destello claro intermedio.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'dark-persistencia',
                    'item': 'Persistencia de elección del usuario',
                    'title': 'La elección manual manda sobre el sistema y se recuerda',
                    'description': 'Si el usuario elige un modo manualmente, esa elección se guarda y prevalece en futuras visitas sobre la configuración del sistema.',
                    'configuration': 'Preferencia almacenada en el navegador con prioridad sobre prefers-color-scheme.',
                    'usageFlow': 'El usuario cambia el tema manualmente → cierra y vuelve otro día → el sitio abre en el tema que eligió.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'dark-persistencia-pestanas',
                    'item': 'Persistencia de elección del usuario',
                    'title': 'El cambio de tema aplica en todas las pestañas abiertas',
                    'description': 'Cambiar el tema en una pestaña lo aplica también en las demás pestañas abiertas del sitio: nunca conviven dos apariencias distintas.',
                    'configuration': 'Propagación del cambio de preferencia entre pestañas del mismo navegador.',
                    'usageFlow': 'El usuario tiene dos pestañas abiertas → cambia el tema en una → la otra se actualiza sola.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'dark-transicion',
                    'item': 'Transición fluida entre modos',
                    'title': 'Cambio de tema suave, sin parpadeos',
                    'description': 'Alternar entre claro y oscuro se siente elegante: transición suave, sin saltos visuales ni destellos que interrumpan la navegación.',
                    'configuration': 'Transiciones CSS acotadas a colores/fondos con duración corta y sin animar propiedades costosas.',
                    'usageFlow': 'El usuario pulsa el toggle → la interfaz funde de un tema al otro → sigue navegando sin interrupción.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'dark-adaptacion-medios',
                    'item': 'Adaptación de imágenes y multimedia',
                    'title': 'Imágenes e íconos legibles en ambos modos',
                    'description': 'Logos, íconos y gráficos se ajustan al modo activo para mantener contraste y legibilidad, sin elementos que "desaparezcan" en oscuro.',
                    'configuration': 'Variantes de assets por tema donde aplique e íconos con color heredado del tema.',
                    'usageFlow': 'El usuario alterna el tema → los elementos gráficos se adaptan → todo sigue visible y con buen contraste.',
                    'priority': 'medium',
                },
            ],
        },
        'gift_cards_module': {
            'epic_title': 'Alcance ampliado: Gift Cards y Vouchers Digitales',
            'epic_description': (
                'Desglose técnico del módulo de gift cards. Cada requerimiento cubre '
                'una etapa del ciclo de vida de la tarjeta de regalo.'
            ),
            'requirements': [
                {
                    'flowKey': 'gift-creacion-venta',
                    'item': 'Creación y venta de gift cards',
                    'title': 'Compra de tarjetas de regalo con saldo configurable',
                    'description': 'Los clientes compran gift cards digitales con el saldo que elijan directamente en el sitio, con pago integrado y entrega inmediata al destinatario.',
                    'configuration': 'Montos configurables (fijos o libres dentro de un rango), pago por la pasarela activa y entrega por correo al destinatario.',
                    'usageFlow': 'El comprador elige monto y destinatario → paga → el destinatario recibe la tarjeta con su código por correo.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'gift-creacion-envio-programado',
                    'item': 'Creación y venta de gift cards',
                    'title': 'Entrega programada para la fecha de la ocasión',
                    'description': 'El comprador elige la fecha de entrega (cumpleaños, aniversario) y la tarjeta llega al destinatario justo ese día, con confirmación al comprador.',
                    'configuration': 'Fecha de entrega opcional con envío programado y confirmación al comprador al completarse la entrega.',
                    'usageFlow': 'El comprador paga hoy → elige la fecha → el destinatario recibe la tarjeta ese día → el comprador recibe la confirmación.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'gift-canje-checkout',
                    'item': 'Canje en checkout con código único',
                    'title': 'El código se aplica como pago parcial o total en el checkout',
                    'description': 'El destinatario ingresa su código único en el checkout y el saldo se descuenta del total, como pago parcial o completo, con validación en el momento.',
                    'configuration': 'Códigos únicos verificables con validación de vigencia y saldo en el checkout; descuento aplicado de forma atómica.',
                    'usageFlow': 'El destinatario compra → ingresa el código en el checkout → el sistema valida saldo y vigencia → el total se descuenta y el saldo restante queda registrado.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'gift-canje-combinacion-pagos',
                    'item': 'Canje en checkout con código único',
                    'title': 'El saldo se combina con otros medios de pago',
                    'description': 'Si el total supera el saldo de la tarjeta, el resto se paga con la pasarela activa en la misma compra; el saldo sobrante queda disponible para la próxima.',
                    'configuration': 'Aplicación del saldo como descuento y cobro del excedente por la pasarela en una sola transacción de checkout.',
                    'usageFlow': 'El total supera el saldo → el cliente paga la diferencia con su tarjeta → la compra cierra completa y el saldo queda en cero.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'gift-canje-proteccion-codigos',
                    'item': 'Canje en checkout con código único',
                    'title': 'Códigos protegidos contra adivinación y reuso',
                    'description': 'Los códigos no son adivinables, cada canje descuenta el saldo de forma atómica y los intentos fallidos repetidos se bloquean temporalmente.',
                    'configuration': 'Códigos de alta entropía, descuento atómico del saldo y límite de intentos fallidos por sesión.',
                    'usageFlow': 'Alguien prueba códigos al azar → los intentos se bloquean → los códigos reales conservan su saldo intacto.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'gift-historial-saldo',
                    'item': 'Historial de saldo y movimientos',
                    'title': 'Saldo disponible y movimientos consultables por ambas partes',
                    'description': 'Comprador y destinatario consultan el saldo disponible, los canjes realizados y la fecha de vencimiento de cada tarjeta.',
                    'configuration': 'Registro de movimientos por tarjeta (compra, canjes, ajustes) con consulta por código.',
                    'usageFlow': 'El usuario consulta su tarjeta → ve saldo, movimientos y vencimiento → sabe exactamente cuánto puede canjear.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'gift-diseno-marca',
                    'item': 'Diseño de marca personalizado',
                    'title': 'Tarjetas con la identidad del negocio y mensaje personal',
                    'description': 'Cada gift card sale con el logo y colores de la marca, más un mensaje personalizable del comprador para el destinatario.',
                    'configuration': 'Plantilla de tarjeta con identidad visual del negocio y campo de mensaje personal del comprador.',
                    'usageFlow': 'El comprador escribe su mensaje → la tarjeta se genera con la marca y el mensaje → el destinatario recibe una pieza cuidada.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'gift-diseno-vista-previa',
                    'item': 'Diseño de marca personalizado',
                    'title': 'Vista previa de la tarjeta antes de pagar',
                    'description': 'El comprador ve la tarjeta final (diseño y mensaje) antes de pagar, evitando errores en un regalo que importa.',
                    'configuration': 'Previsualización renderizada con el diseño de marca y el mensaje ingresado por el comprador.',
                    'usageFlow': 'El comprador escribe el mensaje → previsualiza la tarjeta → corrige si hace falta → paga con seguridad.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'gift-vencimiento',
                    'item': 'Vencimiento configurable',
                    'title': 'Políticas de vencimiento por tipo de tarjeta con avisos',
                    'description': 'El negocio define el vencimiento por tipo de tarjeta (sin vencimiento, 6 meses, 1 año o personalizado) y el destinatario recibe avisos antes de expirar.',
                    'configuration': 'Política de vencimiento por tipo con notificaciones automáticas programadas antes de la expiración.',
                    'usageFlow': 'La tarjeta se acerca a su vencimiento → el destinatario recibe el aviso → canjea a tiempo o el negocio decide extender.',
                    'priority': 'medium',
                },
            ],
        },
    },
    'en': {
        'integration_electronic_invoicing': {
            'epic_title': 'Extended scope: Electronic Invoicing & DIAN Integration',
            'epic_description': (
                'Technical breakdown of the electronic invoicing module. Each requirement '
                'details one element of the module scope with its acceptance criteria.'
            ),
            'requirements': [
                {
                    'flowKey': 'invoicing-generacion-comprobantes',
                    'item': 'Electronic Receipt Generation',
                    'title': 'Invoices, notes and support documents issued from business flows',
                    'description': 'Every completed sale or order can generate its electronic receipt (invoice, credit/debit note or support document) without leaving the platform or re-typing data.',
                    'configuration': 'Fiscal field mapping (client, items, taxes), authorized numbering and issuance via the invoicing provider API; retry queue for provider errors.',
                    'usageFlow': 'An order is completed → the system builds the receipt → sends it to the provider → stores number, CUFE and PDF → notifies the result.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'invoicing-generacion-errores-reintentos',
                    'item': 'Electronic Receipt Generation',
                    'title': 'Fiscal provider errors never block the sale',
                    'description': 'If the invoicing provider fails, the sale still completes: the receipt is queued, retried on its own, and the responsible user is alerted only when retries run out.',
                    'configuration': 'Issuance queue with staggered retries (Huey), an alert to the responsible user when retries are exhausted, and manual re-issuance from the panel.',
                    'usageFlow': 'The provider fails → the sale completes anyway → the receipt retries in the background → if retries run out, the alert arrives and manual re-issuance is available.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'invoicing-generacion-consecutivos-pdf',
                    'item': 'Electronic Receipt Generation',
                    'title': 'Authorized numbering, CUFE and PDF stored per receipt',
                    'description': 'Every issued receipt keeps its authorized number, its CUFE and its official PDF, downloadable from the order detail whenever needed.',
                    'configuration': 'Storage of the consecutive number, CUFE and provider PDF linked to the source order, with panel download.',
                    'usageFlow': 'The receipt is issued → number, CUFE and PDF are stored with the order → the user downloads them from the detail when needed.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-sincronizacion-fiscal',
                    'item': 'Fiscal Data Synchronization',
                    'title': 'Bidirectional sync of clients, products and taxes',
                    'description': 'Fiscal catalogs stay aligned between the platform and the invoicing system: whatever is created or edited on one side is reflected on the other, with no double data entry.',
                    'configuration': 'Periodic jobs (Huey) plus provider webhooks when available; external key per record and conflict resolution by last-update date.',
                    'usageFlow': 'A client/product is created or edited → sync is enqueued → the record is linked by external id → remote changes flow back into the platform.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'invoicing-sincronizacion-conflictos',
                    'item': 'Fiscal Data Synchronization',
                    'title': 'Sync conflicts resolved without duplicate records',
                    'description': 'If the same client or product changed on both systems, the most recent edit wins and duplicates are never created; the external-id link stays auditable.',
                    'configuration': 'Last-update-wins resolution, a unique external key per record and a log of the last applied sync.',
                    'usageFlow': 'The record changes on both systems → the sync detects the conflict → applies the most recent version → the link and the log remain consultable.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-trazabilidad-estado',
                    'item': 'Fiscal Status Traceability',
                    'title': 'DIAN status tracking for every receipt',
                    'description': 'From the platform you can check whether each receipt was issued, accepted, rejected or is still in process, with its full history and the rejection reason when applicable.',
                    'configuration': 'Status queries via API with scheduled polling; per-receipt status timeline storage.',
                    'usageFlow': 'The user opens an invoice detail → sees the status timeline → on rejection, sees the reported reason and can re-issue.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-trazabilidad-reemision',
                    'item': 'Fiscal Status Traceability',
                    'title': 'Controlled re-issuance after a DIAN rejection',
                    'description': 'A rejected receipt is corrected and re-issued from the same detail view, keeping the previous attempt in the history for auditing.',
                    'configuration': 'Re-issuance action with data correction, a new consecutive number when applicable and previous rejections kept on the timeline.',
                    'usageFlow': 'DIAN rejects → the user fixes the flagged data → re-issues from the detail → the history shows both attempts.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-proveedores-colombia',
                    'item': 'Colombian Provider Integration',
                    'title': "Connection with the client's invoicing provider (Siigo, Alegra or other)",
                    'description': 'The integration is built against the provider the business already uses or chooses, validated end to end before going to production.',
                    'configuration': 'Client API credentials in environment variables; per-provider adapter with a common contract (issue, query, void) so switching providers never means rebuilding the flows.',
                    'usageFlow': 'Credentials are configured → the connection is validated with a sandbox test issuance → production mode is enabled.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-automatizaciones-api',
                    'item': 'API Automations',
                    'title': 'Payment reconciliation and automatic issuance',
                    'description': 'Business events trigger fiscal actions with no manual steps: issue on order completion, reconcile received payments and notify status changes.',
                    'configuration': 'Event-based trigger rules (order completed, payment confirmed) and fiscal status notifications by email to the responsible user.',
                    'usageFlow': 'The configured event happens → the automation runs the fiscal action → the result is logged and notified.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'invoicing-automatizaciones-anulacion',
                    'item': 'API Automations',
                    'title': 'Automatic credit notes on order cancellation or return',
                    'description': 'Cancellations and returns generate their credit note linked to the original invoice, with no manual steps and no fiscal mismatches.',
                    'configuration': 'Cancellation/return trigger that issues the credit note referencing the original receipt and records the link between both.',
                    'usageFlow': 'An invoiced order is cancelled or returned → the system issues the linked credit note → the fiscal state of the order stays consistent.',
                    'priority': 'medium',
                },
            ],
        },
        'integration_regional_payments': {
            'epic_title': 'Extended scope: Regional Payment Gateway (Colombia)',
            'epic_description': (
                'Technical breakdown of the local payments integration. Each requirement '
                'covers one verifiable criterion of the gateways in the module scope.'
            ),
            'requirements': [
                {
                    'flowKey': 'regional-payu',
                    'item': 'PayU',
                    'title': 'PayU checkout: cards, PSE and cash methods',
                    'description': 'End customers pay with the most used local methods in Colombia (card, PSE, Efecty, Nequi, Daviplata) and the order is confirmed only when the gateway confirms the payment.',
                    'configuration': "Client's PayU account (sandbox and production), per-transaction integrity signature, confirmation webhook and amount/currency validation before approving the order.",
                    'usageFlow': 'Cart → checkout → payment at PayU → return with status → order confirmation and customer email.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'regional-payu-pagos-pendientes',
                    'item': 'PayU',
                    'title': 'Pending PSE payments resolved without intervention',
                    'description': 'A PSE payment can sit pending for hours: the order waits in an intermediate state and is only approved or released when the gateway reports the final status, with a retry available on failure.',
                    'configuration': 'Intermediate order state with polling and final-status webhook, and inventory release if the payment never completes in time.',
                    'usageFlow': 'The customer pays via PSE → the bank leaves the payment in process → the order waits as pending → on confirmation it approves, or on expiry it releases and the customer can retry.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'regional-payu-conciliacion',
                    'item': 'PayU',
                    'title': 'Reconciliation of PayU transactions against orders',
                    'description': 'The panel crosses gateway-approved transactions with recorded orders and flags differences (payments without an order, orders without a payment) for accounting.',
                    'configuration': 'Periodic cross-check of PayU-reported transactions against orders, with a per-period discrepancy list.',
                    'usageFlow': 'The admin opens the reconciliation → sees the period cross-check → resolves the flagged differences.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'regional-wompi',
                    'item': 'Wompi (Bancolombia)',
                    'title': 'Wompi checkout: PSE, cards and Bancolombia button',
                    'description': 'Local alternative with excellent Bancolombia coverage: customers pay with PSE, card, Nequi or the Bancolombia button, with the payment status traced in the platform.',
                    'configuration': "Client's Wompi public/private keys, event signature verification and reconciliation of each transaction's final status.",
                    'usageFlow': 'Checkout → Wompi widget or redirect → payment → confirmation event → order approved or rejected by status.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'regional-wompi-eventos-idempotentes',
                    'item': 'Wompi (Bancolombia)',
                    'title': 'Wompi events processed exactly once',
                    'description': 'Gateway retries or duplicated events never cause double confirmations or double inventory deductions: each transaction is processed a single time.',
                    'configuration': 'Idempotency by transaction id in the event handler and signature verification before processing each event.',
                    'usageFlow': 'Wompi resends an already-processed event → the system recognizes it → no repeated confirmation → the order keeps a single state.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'regional-epayco',
                    'item': 'ePayco',
                    'title': 'ePayco checkout: PSE, cards and physical collection',
                    'description': 'Agile Colombian option: PSE, card and physical collection payments, with asynchronous confirmation verified server-side.',
                    'configuration': "Client's ePayco credentials, response page and server-to-server confirmation URL with signature validation.",
                    'usageFlow': 'Checkout → payment at ePayco → customer response page → server-to-server confirmation → order status updated.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'regional-epayco-recaudo-pendiente',
                    'item': 'ePayco',
                    'title': 'Physical collection with order hold and expiry',
                    'description': 'When cash payment is chosen, the order is held with its payment reference and only expires if the money never arrives within the defined window.',
                    'configuration': 'Held state with a collection reference, configurable expiry and automatic inventory release on expiration.',
                    'usageFlow': 'The customer picks cash → receives the reference → pays at the physical point → confirmation arrives and the order approves, or it expires and releases.',
                    'priority': 'medium',
                },
            ],
        },
        'integration_international_payments': {
            'epic_title': 'Extended scope: International Payment Gateway',
            'epic_description': (
                'Technical breakdown of the international payments integration. Each '
                'requirement covers one verifiable criterion of the gateways in the module scope.'
            ),
            'requirements': [
                {
                    'flowKey': 'intl-stripe',
                    'item': 'Stripe',
                    'title': 'International charges with Stripe: cards and multiple currencies',
                    'description': 'The business takes credit/debit card payments from any country, one-time or recurring, with verified confirmation before delivering the product or service.',
                    'configuration': 'Restricted API keys, signed webhooks (payment succeeded/failed), enabled currency handling and subscription mode when applicable.',
                    'usageFlow': 'Checkout → Stripe secure form → payment → confirmation webhook → order approved and receipt email.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'intl-stripe-3ds-sca',
                    'item': 'Stripe',
                    'title': '3D Secure authentication whenever the bank demands it',
                    'description': 'Payments flagged by the bank for extra verification go through 3D Secure without breaking the flow: the customer completes the challenge and the order continues.',
                    'configuration': 'Confirmation flow handling the authentication-required state and returning to checkout after the challenge.',
                    'usageFlow': 'The bank demands authentication → the customer completes the 3D Secure challenge → the payment confirms → the order continues.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'intl-stripe-reembolsos-disputas',
                    'item': 'Stripe',
                    'title': 'Refunds and disputes managed from the panel',
                    'description': 'Full or partial refunds are issued from the order itself, and disputes (chargebacks) stay visible with their status and response deadline.',
                    'configuration': 'Refund issuance via API tied to the order and webhook-notified dispute records with their status.',
                    'usageFlow': 'The business decides to refund → issues it from the order → the refund status and any dispute stay traced in the panel.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'intl-paypal',
                    'item': 'PayPal',
                    'title': 'PayPal charges: balance, cards and international accounts',
                    'description': 'Customers who prefer PayPal pay with their balance or linked card; the platform verifies the payment capture before confirming the order.',
                    'configuration': "Client's PayPal app credentials (sandbox and live), order capture via API and status verification before approval.",
                    'usageFlow': 'Checkout → PayPal button → approval at PayPal → payment capture → order confirmation.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'intl-paypal-capturas-expiradas',
                    'item': 'PayPal',
                    'title': 'Uncaptured PayPal orders release themselves',
                    'description': 'If the customer approves at PayPal but the capture fails or the order expires, the order never hangs: inventory is released and the customer can pay again.',
                    'configuration': 'Order-status verification with capture retry and automatic release when the PayPal window expires.',
                    'usageFlow': 'The customer approves but the capture fails → the system retries → if the order expires, the order releases and the customer is invited to retry.',
                    'priority': 'medium',
                },
            ],
        },
        'pwa_module': {
            'epic_title': 'Extended scope: Installable Mobile App (PWA)',
            'epic_description': (
                'Technical breakdown of the PWA module. Each requirement details one '
                'element of the installable/offline scope.'
            ),
            'requirements': [
                {
                    'flowKey': 'pwa-instalacion-dispositivo',
                    'item': 'Device Installation',
                    'title': 'Installation as an app on phone and computer',
                    'description': "The site installs from the browser as an app with the brand's icon and name on the home screen, opening in its own window without the browser bar.",
                    'configuration': 'Web App Manifest (name, colors, maskable icons), registered service worker and compliance with Chrome/Safari installability criteria.',
                    'usageFlow': 'The visitor browses the site → the browser offers "Install app" → confirms → the icon lands on the home screen and opens standalone.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'pwa-instalacion-criterios-navegadores',
                    'item': 'Device Installation',
                    'title': 'Installability criteria covered on Chrome, Safari and Edge',
                    'description': 'The app meets the install requirements of every supported browser; where no native prompt exists (Safari on iOS) the user sees a short «Add to Home Screen» guide.',
                    'configuration': 'Valid manifest (maskable 192/512 icons, standalone display, start_url), service worker with a fetch handler and platform detection for the iOS guide.',
                    'usageFlow': 'The user arrives on iOS → no native prompt exists → sees the step-by-step guide → adds the app to their home screen.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'pwa-offline',
                    'item': 'Offline Functionality',
                    'title': 'Content access without an internet connection',
                    'description': 'Offline, the app keeps showing previously visited content and a clear offline screen for what is unavailable; on reconnection, content refreshes by itself.',
                    'configuration': 'Per-resource caching strategies (shell precache, stale-while-revalidate for content) and a fallback offline page.',
                    'usageFlow': 'The user loses connection → opens the app → sees cached content and an offline notice → on reconnection everything refreshes in the background.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'pwa-offline-limites-cache',
                    'item': 'Offline Functionality',
                    'title': 'The offline cache never grows unchecked',
                    'description': 'Offline content respects size and age limits: what is useful stays, what is old is purged, and the device storage never fills up.',
                    'configuration': 'Per-resource expiration policy and cap with automatic cleanup of stale entries.',
                    'usageFlow': 'The user browses for weeks → the cache purges itself → the app stays fast without hoarding storage.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'pwa-notificaciones-push',
                    'item': 'Push Notifications',
                    'title': 'Push notifications with user consent',
                    'description': 'The business sends direct device notices (news, promotions, updates) only to users who opted in, with an unsubscribe option.',
                    'configuration': 'Web Push subscription with VAPID keys, explicit permission prompt and segmented sending from the backend.',
                    'usageFlow': 'The user grants permission → the business publishes a notice → the notification reaches the device even with the site closed → tapping it opens the right view.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'pwa-push-gestion-suscripciones',
                    'item': 'Push Notifications',
                    'title': 'Valid push subscriptions and honored opt-outs',
                    'description': 'Unsubscribing applies immediately and devices that no longer exist purge themselves: nobody receives notices they did not ask for.',
                    'configuration': 'Subscription create/remove synced with the backend and pruning of invalid tokens reported on every send.',
                    'usageFlow': 'The user unsubscribes → no more notices arrive → following sends skip and prune the invalid devices.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'pwa-splash-personalizada',
                    'item': 'Custom Splash Screen',
                    'title': "Splash screen with the brand's identity",
                    'description': 'Opening the installed app shows a loading screen with the corporate logo and colors instead of a generic browser background.',
                    'configuration': 'Icons and background/theme colors defined in the manifest to generate the native splash on Android/iOS.',
                    'usageFlow': 'The user opens the installed app → sees the branded splash → lands on the loaded home screen.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'pwa-sincronizacion-segundo-plano',
                    'item': 'Background Sync',
                    'title': 'Automatic retry of operations on reconnection',
                    'description': 'Actions performed offline (forms, changes) are queued and sent on their own when the signal returns, without the user repeating anything.',
                    'configuration': 'Pending-operation queue with Background Sync and retries with completion confirmation.',
                    'usageFlow': 'The user submits an action offline → it queues with a notice → on reconnection it syncs → the user gets the confirmation.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'pwa-sync-conflictos',
                    'item': 'Background Sync',
                    'title': 'Sync conflicts resolved without losing data',
                    'description': 'If the data changed on the server while the user was offline, the queued operation never blindly overwrites it: the most recent version applies and the outcome is notified.',
                    'configuration': 'Timestamp per queued operation and a most-recent-wins rule with a result notification to the user.',
                    'usageFlow': 'The user edits offline → another change reaches the server first → on reconnection the most recent wins → the user sees the notified outcome.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'pwa-actualizacion-automatica',
                    'item': 'Automatic Updates',
                    'title': 'Transparent updates to the latest version',
                    'description': 'The app updates itself: users always run the latest version with no manual steps and no app stores.',
                    'configuration': 'Service worker versioning with controlled activation and a discreet "new version available" hint when applicable.',
                    'usageFlow': 'A new version ships → the service worker downloads it in the background → next launch the app is already updated.',
                    'priority': 'medium',
                },
            ],
        },
        'corporate_branding_module': {
            'epic_title': 'Extended scope: Visual Identity & Corporate Branding',
            'epic_description': (
                'Technical breakdown of the branding module. Each requirement covers one '
                'touchpoint where the brand identity is applied.'
            ),
            'requirements': [
                {
                    'flowKey': 'branding-correos-transaccionales',
                    'item': 'Branded Transactional Emails',
                    'title': 'Every system email ships with the brand template',
                    'description': 'Welcome, confirmations, alerts and password recovery arrive with the brand logo, colors, typography and signature — never as generic plain text.',
                    'configuration': 'Responsive HTML templates tested on Gmail/Outlook, with per-event variables and a plain-text fallback version.',
                    'usageFlow': 'A system event happens → the brand template renders with the event data → the email arrives with the business identity.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'branding-correos-dominio-propio',
                    'item': 'Branded Transactional Emails',
                    'title': "Emails that reach the inbox from the business's own domain",
                    'description': 'Emails go out from an address on the own domain, authenticated with SPF/DKIM, with the right sender name and a lower risk of landing in spam.',
                    'configuration': "Sender on the client's domain with SPF, DKIM and DMARC records configured and verified.",
                    'usageFlow': 'The system sends an email → it leaves signed from the business domain → it reaches the main inbox with the correct sender.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'branding-pdfs-exportables',
                    'item': 'PDFs & Exports with Branding',
                    'title': 'Generated documents with branded header and footer',
                    'description': 'Invoices, reports, certificates and Excel/CSV downloads ship with logo, corporate palette and brand footer: every document reinforces the professional image.',
                    'configuration': 'Standardized header/footer in the PDF generator and brand styles in tabular exports.',
                    'usageFlow': 'The user downloads or receives a system document → the file arrives with the complete brand identity.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'branding-pdfs-plantilla-central',
                    'item': 'PDFs & Exports with Branding',
                    'title': 'One place to update the identity of every document',
                    'description': 'Logo, palette and footer are defined once: when the brand evolves, every future PDF and export ships updated without touching document by document.',
                    'configuration': 'Central branding template consumed by every document and export generator.',
                    'usageFlow': 'The brand evolves → the central template is updated → every following document ships with the new identity.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'branding-open-graph',
                    'item': 'Social Link Preview Cards (Open Graph)',
                    'title': 'Shared links show a card with brand logo and image',
                    'description': 'Sharing a site link on WhatsApp, Facebook, LinkedIn or X shows a card with the brand logo, image and colors instead of a plain link — direct impact on perception and clicks.',
                    'configuration': 'Open Graph and Twitter Card metadata per public view (title, description, image), validated with the Meta and LinkedIn debuggers.',
                    'usageFlow': 'A user shares a link → the social network reads the metadata → the conversation shows the brand card.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'branding-pantallas-sistema',
                    'item': 'System Screens with Brand Identity',
                    'title': "Errors, login and loading states in the brand's voice",
                    'description': "404/500 pages, maintenance, login and loading states use the business's visual identity and messaging instead of the framework's generic screens.",
                    'configuration': 'Custom error and maintenance templates, skeletons/spinners with the corporate palette and copy in the brand voice.',
                    'usageFlow': 'The user hits an error or waits for a load → the screen keeps the identity and guides them forward.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'branding-pantallas-textos-editables',
                    'item': 'System Screens with Brand Identity',
                    'title': 'Error and maintenance copy editable without a developer',
                    'description': 'The copy on 404/500 and maintenance screens is edited from the panel, adjusting the brand tone without technical deploys.',
                    'configuration': 'System-screen copy manageable from the panel, with default fallback values.',
                    'usageFlow': 'The business wants to adjust the message → edits it in the panel → the screen shows it immediately.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'branding-metadatos-estructurados',
                    'item': 'Structured Metadata for Search & AI',
                    'title': 'The brand shows correctly on Google and AI assistants',
                    'description': 'Search engines and assistants (Google, Bing, ChatGPT, Perplexity) receive structured organization data to display the logo, contact and social profiles in panels and rich results.',
                    'configuration': "JSON-LD Organization (logo, colors, social profiles, contact data) validated with Google's rich results test.",
                    'usageFlow': 'A search engine or assistant indexes the site → reads the JSON-LD → displays the brand with its correct data.',
                    'priority': 'medium',
                },
            ],
        },
        'behavior_tracking_module': {
            'epic_title': 'Extended scope: User Behavior Tracking',
            'epic_description': (
                'Technical breakdown of the behavior module. Included scope: up to 15 '
                'tracked views, a panel with up to 8 KPIs and 4 charts, 12-month retention.'
            ),
            'requirements': [
                {
                    'flowKey': 'behavior-sesiones',
                    'item': 'Session & Open Tracking',
                    'title': 'First-party logging of every usage session',
                    'description': "Every entry is logged with date, device and whether it's a first visit or a return — all in the business's own data, with no third-party cookies or external tools.",
                    'configuration': 'First-party session event with a persistent anonymous identifier, timestamp and new-vs-returning classification.',
                    'usageFlow': 'The user enters the platform → the session is logged with its context → the data feeds KPIs and charts.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'behavior-sesiones-privacidad',
                    'item': 'Session & Open Tracking',
                    'title': 'Measurement without personal data or third-party cookies',
                    'description': 'Events use an anonymous identifier and never store names, emails or sensitive data: useful measurement that honors data-protection rules with no third parties involved.',
                    'configuration': 'Non-reversible random identifier, events free of personal data and documentation ready for the site privacy policy.',
                    'usageFlow': 'The user browses → events are logged anonymously → the business measures without exposing personal data.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'behavior-tiempo-por-vista',
                    'item': 'Views Opened & Time per View',
                    'title': 'Measurement of opened views and seconds of active time',
                    'description': 'The system records which views each user opens and how much active time they spend on each, over the up-to-15 views agreed with the client at kickoff.',
                    'configuration': 'Instrumentation of the agreed views with active-time measurement (heartbeat) and inactivity cutoff.',
                    'usageFlow': 'The user navigates between views → each open and its duration are logged → they feed the interest map and the funnel.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'behavior-tiempo-precision',
                    'item': 'Views Opened & Time per View',
                    'title': 'Measured time is real usage time',
                    'description': 'Background tabs, inactivity or a locked device never inflate the metric: only genuinely active time on the view counts.',
                    'configuration': 'Count pauses on tab visibility and inactivity, resuming automatically on return.',
                    'usageFlow': 'The user switches tabs → the count pauses → returns → the count resumes → the metric reflects real usage.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'behavior-mapa-interes',
                    'item': 'Interest Map per View',
                    'title': 'View ranking by attention received',
                    'description': 'The business sees which views concentrate attention (accumulated time and visits) and which go unnoticed, to decide where to invest improvements.',
                    'configuration': 'Per-view aggregation of total time and open count, sorted by interest.',
                    'usageFlow': 'The admin opens the behavior panel → sees the view ranking → identifies what works and what does not.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'behavior-embudo-abandonos',
                    'item': 'Journey Funnel with Drop-off',
                    'title': 'Main funnel with drop-off points',
                    'description': 'One (1) funnel defined with the client shows how users advance across the tracked views and at which exact step they leave.',
                    'configuration': 'Funnel definition over the tracked views with per-step conversion and drop-off.',
                    'usageFlow': 'The admin opens the funnel → sees the share advancing at each step → spots the biggest leak.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'behavior-embudo-comparativo',
                    'item': 'Journey Funnel with Drop-off',
                    'title': 'The funnel is compared across periods',
                    'description': 'Per-step conversion is compared against the previous period, so the business knows with data whether its changes improved the journey.',
                    'configuration': 'Funnel computed per date range with a comparison against the equivalent previous range.',
                    'usageFlow': 'The admin picks the period → sees the current funnel next to the previous one → confirms whether the improvement worked.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'behavior-panel-integrado',
                    'item': 'Built-in Behavior Panel',
                    'title': 'Own dashboard with up to 8 KPIs and 4 charts',
                    'description': 'Inside the own admin panel: sessions, average time, most-opened views and device breakdown — no external licenses or subscriptions.',
                    'configuration': 'Optimized aggregate queries over the first-party events; KPI cards and charts capped to the contracted scope (8 KPIs / 4 charts).',
                    'usageFlow': 'The admin enters the panel → sees the updated KPIs and charts → filters by date range.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'behavior-panel-exportacion',
                    'item': 'Built-in Behavior Panel',
                    'title': 'KPIs and data exportable for reports',
                    'description': 'Panel indicators export to Excel/CSV for reports or analysis outside the platform.',
                    'configuration': 'Export of the visible aggregates per date range in tabular formats.',
                    'usageFlow': 'The admin filters the period → exports → uses the file in their report.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'behavior-desglose-dispositivo',
                    'item': 'Device Breakdown',
                    'title': 'Usage by mobile, tablet and desktop',
                    'description': 'The business knows which device type its users prefer, to prioritize improvements where users actually are.',
                    'configuration': 'Device classification by user-agent on the session event, aggregated in the panel.',
                    'usageFlow': 'The admin opens the breakdown → sees the mobile/tablet/desktop share → prioritizes the dominant channel.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'behavior-retencion-datos',
                    'item': 'Own Data with 12-Month Retention',
                    'title': "Events stored in the client's database for 12 months",
                    'description': "Data lives in the business's own database and is kept for 12 months; it does not include screen recording, click heatmaps or cross-site tracking.",
                    'configuration': 'Scheduled purge of events older than 12 months and documented scope limits.',
                    'usageFlow': 'Events accumulate in the own database → the monthly purge removes what exceeds retention → the panel always queries current data.',
                    'priority': 'medium',
                },
            ],
        },
        'reports_alerts_module': {
            'epic_title': 'Extended scope: Reports & Alerts via Email or WhatsApp',
            'epic_description': (
                'Technical breakdown of the reports and alerts module. Each requirement '
                'covers one channel or capability of the module scope.'
            ),
            'requirements': [
                {
                    'flowKey': 'reports-correo-automatico',
                    'item': 'Automated Email Reports',
                    'title': 'Periodic summaries with key metrics in the inbox',
                    'description': 'The owner receives the business summary (sales, sign-ups, activity) by email without logging in, at the frequency they choose.',
                    'configuration': 'Scheduled report generation with the brand template and the agreed metrics; delivery log.',
                    'usageFlow': 'The scheduled time arrives → the system builds the report with the period data → sends it to the configured email.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'reports-correo-adjuntos',
                    'item': 'Automated Email Reports',
                    'title': 'The report detail travels attached',
                    'description': 'Besides the summary in the email body, the report attaches the detail (Excel/CSV or PDF) for deep review or archiving.',
                    'configuration': 'Per-report attachment generation with the period detail and the brand template.',
                    'usageFlow': 'The report arrives → the owner opens the attachment → reviews the full detail without logging in.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'reports-alertas-personalizadas',
                    'item': 'Custom Alerts',
                    'title': 'Alerts on business-defined events and thresholds',
                    'description': 'New sales, user registrations, low stock or any defined metric trigger an immediate notice to the responsible person.',
                    'configuration': 'Configurable event/threshold rules; evaluation on event occurrence and immediate dispatch to the chosen channel.',
                    'usageFlow': 'The event happens (e.g. low stock) → the rule evaluates → the notice arrives on the configured channel with the detail.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'reports-alertas-antirruido',
                    'item': 'Custom Alerts',
                    'title': 'Alerts without spam: grouping and quiet periods',
                    'description': 'The same condition never fires notices in a chain: repetitions group into a single notice and each rule has its own quiet period.',
                    'configuration': 'Configurable per-rule quiet window and grouping of repeated occurrences into one notice.',
                    'usageFlow': 'Stock stays low all morning → ONE grouped notice arrives → the next one only fires after the quiet period ends.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'reports-whatsapp',
                    'item': 'WhatsApp Integration',
                    'title': 'Alerts and reports on WhatsApp via the official API',
                    'description': "Notices reach the business's WhatsApp number on the same channel where it already serves customers, using the official API.",
                    'configuration': 'Official WhatsApp API (Cloud API) with approved templates, verified business number and delivery-failure handling.',
                    'usageFlow': 'A report or alert fires → the system sends the approved template via WhatsApp → the owner receives it in chat.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'reports-whatsapp-respaldo-correo',
                    'item': 'WhatsApp Integration',
                    'title': 'If WhatsApp fails, the notice arrives by email',
                    'description': 'A delivery failure or an unavailable template never leaves the business without its notice: the system falls back to email and logs the reason.',
                    'configuration': 'Delivery-failure detection with automatic email fallback and a record of the channel finally used.',
                    'usageFlow': 'The WhatsApp send fails → the system resends by email → the owner still gets the notice and the failure is logged.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'reports-programacion',
                    'item': 'Scheduled Delivery',
                    'title': 'Configurable report frequency and timing',
                    'description': "Each report is scheduled daily, weekly, monthly or real-time, in the business's preferred time and timezone.",
                    'configuration': 'Scheduled tasks (Huey) per report with frequency, time and timezone configurable from the panel.',
                    'usageFlow': 'The admin sets frequency and time → the system honors the schedule → they can pause or adjust anytime.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'reports-historial-envios',
                    'item': 'Scheduled Delivery',
                    'title': 'Delivery history with per-send status',
                    'description': 'Every sent report and alert lands in a history with date, channel and status (delivered or failed), consultable at any time.',
                    'configuration': 'Send log per rule and per report with its final delivery status.',
                    'usageFlow': 'The admin doubts whether the report went out → opens the history → confirms date, channel and status.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'reports-resumen-ejecutivo',
                    'item': 'Periodic Executive Summary',
                    'title': 'Consolidated report for fast decisions',
                    'description': "A report with the project's most relevant metrics, designed to be read in minutes and to decide with data.",
                    'configuration': 'Key metrics agreed with the client and an executive format (headlines + deltas vs previous period).',
                    'usageFlow': 'The configured period arrives → the executive report consolidates → the owner reads it and acts on relevant changes.',
                    'priority': 'medium',
                },
            ],
        },
        'email_marketing_module': {
            'epic_title': 'Extended scope: Email Marketing Integration',
            'epic_description': (
                'Technical breakdown of the email marketing module. Each requirement '
                'covers one capability of the module scope.'
            ),
            'requirements': [
                {
                    'flowKey': 'email-mkt-captura-leads',
                    'item': 'Lead Capture',
                    'title': 'Forms and pop-ups capturing interested visitors',
                    'description': 'Interested visitors leave their email on optimized forms and non-invasive pop-ups, with validation and subscription confirmation.',
                    'configuration': 'Email-validated forms, pop-up display rules (time/scroll/exit) and duplicate-safe registration.',
                    'usageFlow': "The visitor sees the form or pop-up → leaves their email → receives confirmation → joins the business's list.",
                    'priority': 'high',
                },
                {
                    'flowKey': 'email-mkt-captura-doble-optin',
                    'item': 'Lead Capture',
                    'title': 'Subscriptions confirmed with double opt-in',
                    'description': 'Subscribers confirm their email before joining the list: clean lists, fewer bounces and compliance with permission best practices.',
                    'configuration': 'Confirmation email with an activation link and a pending state until confirmed.',
                    'usageFlow': 'The visitor subscribes → receives the confirmation email → confirms → only then joins the active list.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'email-mkt-automatizaciones',
                    'item': 'Email Automations',
                    'title': 'Automatic welcome, cart and re-engagement sequences',
                    'description': 'Subscribers receive sequences with no manual steps: welcome on sign-up, abandoned-cart reminder, post-purchase follow-up and inactive-user reactivation.',
                    'configuration': "Event triggers (sign-up, cart, purchase, inactivity) wired to the chosen provider's automations.",
                    'usageFlow': 'The event happens → the matching sequence fires → the emails go out at the defined intervals.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'email-mkt-automatizaciones-salida',
                    'item': 'Email Automations',
                    'title': 'Sequences know when to stop',
                    'description': 'Buying exits the abandoned-cart flow and unsubscribing cuts every sequence: nobody receives out-of-context emails.',
                    'configuration': 'Per-sequence exit conditions (purchase, unsubscribe, conversion) evaluated before every send.',
                    'usageFlow': 'The customer buys mid cart-sequence → the sequence stops → only the communications that still apply continue.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'email-mkt-segmentacion',
                    'item': 'Audience Segmentation',
                    'title': 'Subscribers classified by behavior and interests',
                    'description': 'Lists are segmented by behavior, interests and demographics so every message reaches the people it is relevant to.',
                    'configuration': 'Attribute and tag sync from the platform to the provider (purchases, viewed categories, lead source).',
                    'usageFlow': 'The subscriber interacts with the site → their attributes update → campaigns target the right segment.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'email-mkt-segmentacion-dinamica',
                    'item': 'Audience Segmentation',
                    'title': 'Segments update themselves with behavior',
                    'description': 'Subscribers enter and leave segments automatically as their behavior changes, with no manual list maintenance.',
                    'configuration': 'Segment membership recomputed whenever synced attributes update.',
                    'usageFlow': 'The subscriber makes their first purchase → leaves «prospects» and joins «customers» → the next campaigns speak to them as a customer.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'email-mkt-analitica',
                    'item': 'Campaign Analytics',
                    'title': 'Open, click and conversion metrics per campaign',
                    'description': 'Every campaign reports opens, clicks, conversions and ROI to optimize the communication strategy with real data.',
                    'configuration': "Metric reads via the provider's API and conversion attribution with UTM parameters on links.",
                    'usageFlow': 'The campaign is sent → metrics are checked from the panel → the business adjusts content and segments by results.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'email-mkt-analitica-salud-lista',
                    'item': 'Campaign Analytics',
                    'title': 'List health: bounces, unsubscribes and complaints visible',
                    'description': 'Bounce rate, unsubscribes and spam complaints are monitored to protect sender reputation and clean the list in time.',
                    'configuration': "List-health metric reads via the provider's API with configured alert thresholds.",
                    'usageFlow': 'A campaign spikes bounces → the indicator shows it → the business cleans the list before hurting its sender.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'email-mkt-integracion-plataformas',
                    'item': 'Platform Integration',
                    'title': 'Native connection with the chosen provider (Mailchimp, SendGrid, Brevo…)',
                    'description': 'The platform is wired to the email marketing provider the business uses or chooses, with synced lists and events.',
                    'configuration': 'Provider API credentials, list/audience mapping and sync of sign-ups, unsubscribes and bounces.',
                    'usageFlow': 'Credentials are configured → the connection is validated with a test list → sign-ups and events flow automatically.',
                    'priority': 'high',
                },
            ],
        },
        'qr_generator_module': {
            'epic_title': 'Extended scope: QR Code Generator',
            'epic_description': (
                'Technical breakdown of the QR module. Each requirement covers one '
                'capability of the generator and its lifecycle.'
            ),
            'requirements': [
                {
                    'flowKey': 'qr-generacion-instantanea',
                    'item': 'Instant Generation',
                    'title': 'QR from URLs, text, vCard, WiFi or WhatsApp in seconds',
                    'description': 'Any link, text, vCard contact, WiFi network or WhatsApp number becomes a ready-to-use QR, generated instantly from the panel.',
                    'configuration': 'Server-side generation with configurable error correction and supported content types (URL, text, vCard, WiFi, wa.me).',
                    'usageFlow': 'The admin picks the content type → enters the data → the QR is generated and ready to download or share.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'qr-generacion-validacion',
                    'item': 'Instant Generation',
                    'title': 'Content is validated before the code is generated',
                    'description': 'Malformed URLs, incomplete vCards or over-limit texts are caught before generating: no printed QR ever ships pointing at a broken destination.',
                    'configuration': 'Per-content-type validation (URL format, vCard fields, maximum length) with clear correction messages.',
                    'usageFlow': 'The admin pastes the data → the system validates → fixes any error → generates the already-verified QR.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'qr-personalizacion-marca',
                    'item': 'Branded Customization',
                    'title': 'QR with corporate colors, logo and print formats',
                    'description': "Each code can carry the brand's colors and the logo at the center, exported as PNG, SVG or PDF in high resolution without losing scannability.",
                    'configuration': 'Corporate palette applied with contrast/scannability verification and vector exports for print.',
                    'usageFlow': 'The admin applies the brand style → previews and test-scans → downloads the needed format.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'qr-codigos-dinamicos',
                    'item': 'Editable Dynamic Codes',
                    'title': 'Change where a printed QR points without reprinting',
                    'description': 'Dynamic QRs point to an own editable link: the business changes the destination (seasonal menu, promo, event) and the printed code keeps working.',
                    'configuration': 'Own redirector with a short slug per code and destination editing from the panel; the printed QR always points to the redirector.',
                    'usageFlow': 'The admin edits the code destination → saves → every following scan lands on the new destination.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'qr-dinamicos-historial',
                    'item': 'Editable Dynamic Codes',
                    'title': 'Destination history for every dynamic code',
                    'description': 'Every destination change is recorded (when, and where it pointed), so the business knows what each scan saw at any given time.',
                    'configuration': 'Per-code destination log with its validity dates.',
                    'usageFlow': 'The admin checks a code → sees the destination timeline → understands which campaign was live on each date.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'qr-tracking-escaneos',
                    'item': 'Scan Tracking',
                    'title': 'Scan counts per code, device and moment',
                    'description': 'Each code reports how many times it was scanned, from which device type and when — to measure physical campaigns with data.',
                    'configuration': 'Scan logging at the redirector (timestamp, device) with aggregates per code and campaign.',
                    'usageFlow': 'Someone scans the code → the redirector logs the event and redirects → metrics show in the panel.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'qr-tracking-exportacion',
                    'item': 'Scan Tracking',
                    'title': 'Scan metrics exportable per campaign',
                    'description': 'Scans export to Excel/CSV per code or campaign, to report the outcome of physical pieces with data.',
                    'configuration': 'Export of aggregated events per code, campaign and date range.',
                    'usageFlow': 'The campaign ends → the admin exports the scans → presents the outcome with data.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'qr-biblioteca',
                    'item': 'Code Library',
                    'title': 'Every QR organized by campaign or purpose',
                    'description': 'Generated codes live in an organized library, ready to reuse, re-download or deactivate once no longer needed.',
                    'configuration': 'Listing grouped by campaign/purpose, active/inactive states and download regeneration.',
                    'usageFlow': 'The admin opens the library → filters by campaign → reuses, downloads or deactivates the code they need.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'qr-casos-de-uso',
                    'item': 'Ready-to-Use Cases',
                    'title': 'Preconfigured templates: menu, WhatsApp, events, reviews',
                    'description': 'Common cases ready to launch the same day: digital menu, WhatsApp link, event check-in, catalog download, surveys, tipping or reviews.',
                    'configuration': 'Per-case templates with the content type and style predefined, editable before generating.',
                    'usageFlow': 'The admin picks the case template → adjusts the specific data → the QR is operational immediately.',
                    'priority': 'low',
                },
            ],
        },
        'content_generator_module': {
            'epic_title': 'Extended scope: AI Content Generator with Editorial Calendar',
            'epic_description': (
                'Technical breakdown of the content module. Each requirement covers one '
                'capability of the generator or the editorial calendar.'
            ),
            'requirements': [
                {
                    'flowKey': 'content-redaccion-ia',
                    'item': 'AI-Assisted Writing',
                    'title': 'Drafts for blogs, emails and posts from a simple brief',
                    'description': 'From a short idea, the AI delivers drafts for blogs, newsletters and posts, with tone, length and format controlled in a couple of clicks.',
                    'configuration': 'Generation via AI provider with per-piece prompt templates and tone/length parameters.',
                    'usageFlow': 'The user writes the brief → picks piece type and tone → receives the draft → edits and approves it.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'content-redaccion-aprobacion',
                    'item': 'AI-Assisted Writing',
                    'title': 'Nothing publishes without human approval',
                    'description': 'Every generated draft goes through review: only content approved by a person can be scheduled or published.',
                    'configuration': 'Draft → in review → approved states, with publishing restricted to approved pieces.',
                    'usageFlow': 'The AI delivers the draft → the owner reviews and adjusts → approves it → only then can it be scheduled.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'content-voz-de-marca',
                    'item': 'Brand Voice & Templates',
                    'title': 'The editorial identity is defined once and always honored',
                    'description': 'Tone, style, banned words and calls to action are configured once; every generated piece honors that voice.',
                    'configuration': 'Persistent editorial profile (tone, style, banned vocabulary, CTAs) injected into every generation.',
                    'usageFlow': 'The business defines its voice once → every new piece comes out aligned → the profile can evolve with the brand.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'content-multicanal',
                    'item': 'Multichannel: Blog, Email & Social',
                    'title': "One idea adapted to each channel's format",
                    'description': 'The same idea becomes a long blog post, an email subject and body, and short copy for Instagram, LinkedIn or X — without rewriting from scratch.',
                    'configuration': 'Per-channel transformations with platform-specific length and format limits.',
                    'usageFlow': 'The user picks the base piece → requests the channel variants → receives each adapted version ready to schedule.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'content-multicanal-vista-previa',
                    'item': 'Multichannel: Blog, Email & Social',
                    'title': 'Faithful per-channel preview before scheduling',
                    'description': 'Each variant previews exactly as it will look on its channel (lengths, cuts, format) before being scheduled — no surprises at publish time.',
                    'configuration': 'Per-channel preview with each platform length and format limits applied.',
                    'usageFlow': 'The user generates the variants → previews each channel → fixes the one that clips → schedules with confidence.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'content-calendario-editorial',
                    'item': 'Visual Editorial Calendar',
                    'title': 'Monthly and weekly views with drag and drop',
                    'description': 'Every piece (draft, scheduled, published) shows on a monthly or weekly calendar; rearranging dates is drag and drop.',
                    'configuration': 'Calendar with per-piece states and drag-&-drop rescheduling persisted on drop.',
                    'usageFlow': "The user opens the calendar → sees the month's plan → drags a piece to another date → the change is saved.",
                    'priority': 'high',
                },
                {
                    'flowKey': 'content-programacion-automatica',
                    'item': 'Scheduling & Auto-Publishing',
                    'title': 'Publishing happens on its own at the scheduled date and time',
                    'description': 'Each scheduled piece publishes with no intervention: the blog posts it, the email is sent and connected networks receive the post at the defined moment.',
                    'configuration': 'Scheduled publishing queue (Huey) per channel with failure handling and notified retry.',
                    'usageFlow': 'The user schedules the piece → the date/time arrives → the system publishes to the channel → the state turns "published".',
                    'priority': 'high',
                },
                {
                    'flowKey': 'content-programacion-fallos',
                    'item': 'Scheduling & Auto-Publishing',
                    'title': 'A failed publication notifies and retries without duplicating',
                    'description': 'If a channel fails to publish, the owner gets the notice with the reason, and the retry never duplicates an already-published piece.',
                    'configuration': 'Retry with prior-publication verification and failure notification with its cause.',
                    'usageFlow': 'The social network rejects the post → the notice arrives → the user retries → the piece goes out exactly once.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'content-panel-seguimiento',
                    'item': 'Tracking Panel',
                    'title': 'Status and performance of every publication in one place',
                    'description': 'Draft, scheduled, published or failed: each piece shows its state and basic metrics, with reschedule or duplicate one click away.',
                    'configuration': 'Per-piece states with basic per-channel metrics and quick actions (reschedule, duplicate).',
                    'usageFlow': 'The user opens the panel → reviews states and performance → retries a failed piece or duplicates the one that worked.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'content-integracion-canales',
                    'item': 'Channel Integrations',
                    'title': 'Blog, email provider and social networks wired to the calendar',
                    'description': "What's planned on the calendar gets published on the business's real channels: its blog, its email provider and its connected social networks.",
                    'configuration': 'Per-channel API connection (own blog, email provider, social) with credential validation and a visible connection status.',
                    'usageFlow': 'The business connects its channels once → the calendar publishes to them → the connection status warns if re-authorization is needed.',
                    'priority': 'medium',
                },
            ],
        },
        'i18n_module': {
            'epic_title': 'Extended scope: Multi-language & Regional Localization',
            'epic_description': (
                'Technical breakdown of the internationalization module. Each requirement '
                'covers one capability of the multi-language scope.'
            ),
            'requirements': [
                {
                    'flowKey': 'i18n-multi-idioma',
                    'item': 'Native Multi-language Support',
                    'title': 'All content served in two or more languages',
                    'description': "The site serves its complete content in the defined languages, with a visible selector and the user's preference remembered between visits.",
                    'configuration': 'Native i18n structure (per-language routes or prefixes), persistent selector and bilingual content per section.',
                    'usageFlow': 'The visitor switches language in the selector → all content switches → the preference is remembered for the next visit.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'i18n-seo-hreflang',
                    'item': 'Native Multi-language Support',
                    'title': 'Each language ranks separately on Google',
                    'description': 'Every language version has its own URL with hreflang tags: search engines show each user the version in their language.',
                    'configuration': 'Per-language URLs with reciprocal hreflang and a multilingual sitemap.',
                    'usageFlow': 'Google indexes the site → detects the language versions → Spanish speakers see the Spanish result and English speakers the English one.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'i18n-formatos-regionales',
                    'item': 'Regional Currency & Date Formats',
                    'title': "Currencies, numbers and dates in each region's format",
                    'description': 'Amounts, numbers and dates display in the correct format for the active region or language, with no ambiguity for the visitor.',
                    'configuration': 'Locale-based formatting (separators, currency symbol, date order) applied on every data view.',
                    'usageFlow': 'The visitor browses in their language → prices and dates appear in their regional format → no amount or date confusion.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'i18n-zona-horaria',
                    'item': 'Regional Currency & Date Formats',
                    'title': "Dates and times in the visitor's timezone",
                    'description': 'Event times, publications and expirations display in the local time of whoever is looking, with no timezone confusion.',
                    'configuration': 'UTC storage with conversion to the browser timezone at display time.',
                    'usageFlow': 'The business schedules an event for 7 pm Bogotá → the visitor in Madrid sees it in their local time → nobody shows up at the wrong hour.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'i18n-catalogos-por-pais',
                    'item': 'Catalogs & Pricing by Country',
                    'title': 'Products, prices and availability differentiated by market',
                    'description': "The business can show different catalogs, prices and availability depending on the visitor's country or target market.",
                    'configuration': 'Per-region visibility and pricing rules over the catalog, with a default fallback market.',
                    'usageFlow': "The visitor enters from a configured market → sees their region's catalog and prices → buys under the right conditions.",
                    'priority': 'medium',
                },
                {
                    'flowKey': 'i18n-catalogos-fallback',
                    'item': 'Catalogs & Pricing by Country',
                    'title': 'Unconfigured markets fall back to the default catalog',
                    'description': 'A visitor from an unconfigured country sees the full default market, and a product without a regional price uses its base price — never an empty page.',
                    'configuration': 'Mandatory default market and per-product fallback rules (base price, global availability).',
                    'usageFlow': 'A visitor arrives from an unconfigured country → sees the default catalog → buys under base conditions with no errors.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'i18n-flujo-traduccion',
                    'item': 'Integrated Translation Workflow',
                    'title': 'Panel to manage translations without technical help',
                    'description': "The business team manages each section's translations from the panel, with a clear indicator of content pending translation.",
                    'configuration': 'Per-section translation editor with state (translated/pending) and per-language preview.',
                    'usageFlow': 'The admin opens the translations panel → sees what is pending → completes the translation → publishes the updated language.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'i18n-deteccion-idioma',
                    'item': 'Automatic Language Detection',
                    'title': 'Visitors land directly on their language version',
                    'description': "The site detects the browser's preferred language and automatically redirects to the matching version from the first visit.",
                    'configuration': 'Browser-header detection with redirection to the right variant, honoring later manual choices.',
                    'usageFlow': 'The visitor opens the site → is taken to their language automatically → a manual switch takes precedence afterwards.',
                    'priority': 'medium',
                },
            ],
        },
        'live_chat_module': {
            'epic_title': 'Extended scope: First-Party Live Chat',
            'epic_description': (
                'Technical breakdown of the chat module. Each requirement covers one '
                "capability of the chat hosted on the client's infrastructure."
            ),
            'requirements': [
                {
                    'flowKey': 'chat-widget-embebido',
                    'item': 'Embedded Chat Widget',
                    'title': 'Real-time conversation without leaving the page',
                    'description': 'A floating component on the site lets the visitor start and continue a conversation while still browsing the page.',
                    'configuration': 'Own widget (no external services) with persistent open/minimized state and business branding.',
                    'usageFlow': 'The visitor opens the widget → writes their message → chats in real time without leaving the page.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'chat-widget-sin-agentes',
                    'item': 'Embedded Chat Widget',
                    'title': 'With no agents online, the widget captures the contact',
                    'description': 'If nobody is available, the visitor leaves name, email and message; the conversation is created in the inbox and the business replies on return.',
                    'configuration': 'Contact form in the widget when no agents are online, creating the conversation with the visitor data.',
                    'usageFlow': 'The visitor writes with no agents online → leaves their details → the agent replies on connecting → the visitor receives the answer.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'chat-panel-agente',
                    'item': 'Agent Panel in Admin',
                    'title': "Agents respond from the site's own admin panel",
                    'description': "Conversations are handled from the site's own panel: no external apps, extra accounts or per-seat costs.",
                    'configuration': "Conversation inbox with states (new, active, closed), agent assignment and the visitor's history view.",
                    'usageFlow': 'The agent opens the inbox → takes a conversation → replies and closes it on resolution.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'chat-agente-traspaso',
                    'item': 'Agent Panel in Admin',
                    'title': 'Conversation handover between agents with context',
                    'description': 'A conversation is reassigned to another agent without losing the thread: the receiver sees the full history and the visitor repeats nothing.',
                    'configuration': 'Reassignment from the inbox with the full history visible and a record of which agent handled each stretch.',
                    'usageFlow': 'The agent must leave → reassigns the conversation → the new agent reads the full thread → support continues without cuts.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'chat-websocket',
                    'item': 'Real-time Communication (WebSocket)',
                    'title': 'Instant messages in both directions',
                    'description': 'Visitor and agent read each other instantly, with no page reloads or perceptible delays, even in long conversations.',
                    'configuration': 'Persistent WebSocket connection with automatic reconnection and confirmed message delivery.',
                    'usageFlow': 'Either side writes → the message appears instantly on the other side → a dropped connection re-establishes itself.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'chat-websocket-presencia',
                    'item': 'Real-time Communication (WebSocket)',
                    'title': 'Presence and typing indicators in real time',
                    'description': 'The visitor sees when the agent is online and typing, and vice versa: the conversation feels attended and alive.',
                    'configuration': 'Presence and typing events over the existing WebSocket connection.',
                    'usageFlow': 'The agent starts typing → the visitor sees the typing indicator → the wait feels attended.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'chat-historial-propio',
                    'item': 'Owned Conversation History',
                    'title': "All conversations stored in the client's database",
                    'description': "The full history lives in the business's database, with search, date filters and export — the data is 100% owned.",
                    'configuration': 'Conversation and message persistence with text search, date/state filters and export.',
                    'usageFlow': 'The admin searches a conversation → finds it by text or date → reviews or exports it when needed.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'chat-respuestas-automaticas',
                    'item': 'Configurable Auto-responses',
                    'title': 'Welcome, after-hours and FAQ with no agent available',
                    'description': 'The chat answers on its own with welcome messages, after-hours notices and frequent answers, keeping support active 24/7.',
                    'configuration': 'Automatic messages configurable by business hours and a frequent-answers catalog.',
                    'usageFlow': "The visitor writes after hours → receives the notice and FAQ options → their message waits in the inbox for the next shift.",
                    'priority': 'medium',
                },
                {
                    'flowKey': 'chat-notificaciones',
                    'item': 'New Chat Notifications',
                    'title': 'Agents learn of every new message instantly',
                    'description': 'Every new conversation or incoming message notifies the agent in real time, guaranteeing minimal response times.',
                    'configuration': 'Panel alerts (sound/counter) on conversation creation or new message, with an unread indicator.',
                    'usageFlow': 'The visitor writes → the agent sees the alert and counter → enters the conversation and replies.',
                    'priority': 'medium',
                },
            ],
        },
        'dark_mode_module': {
            'epic_title': 'Extended scope: Dark & Light Mode',
            'epic_description': (
                'Technical breakdown of the visual theme module. Each requirement covers '
                'one capability of the light/dark system.'
            ),
            'requirements': [
                {
                    'flowKey': 'dark-paleta-dual',
                    'item': 'Dual Color Palette',
                    'title': 'Two complete, coherent color systems',
                    'description': 'Light and dark each have a full palette: readable text, correct contrast and visual coherence across every view.',
                    'configuration': 'Semantic CSS variables per theme with contrast verification on key components.',
                    'usageFlow': 'The user toggles the theme → the whole interface switches instantly → nothing becomes unreadable or off-style.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'dark-contraste-accesible',
                    'item': 'Dual Color Palette',
                    'title': 'Accessible contrast verified in both modes',
                    'description': 'Key text and controls meet AA contrast in light and dark alike: readability guaranteed, including for low-vision users.',
                    'configuration': 'WCAG AA contrast verification over the main components in both themes.',
                    'usageFlow': 'The user picks either mode → every text and button reads effortlessly → the experience stays accessible.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'dark-deteccion-sistema',
                    'item': 'Automatic System Preference Detection',
                    'title': "The initial theme honors the device's preference",
                    'description': 'From the first visit, the site applies the mode the user already uses on their operating system, with no configuration needed.',
                    'configuration': 'prefers-color-scheme read at load, before first render, to avoid a theme flash.',
                    'usageFlow': 'A visitor with a dark system opens the site → sees it directly in dark → with no light flash in between.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'dark-persistencia',
                    'item': 'User Choice Persistence',
                    'title': 'Manual choice wins over the system and is remembered',
                    'description': 'If the user picks a mode manually, that choice is stored and prevails on future visits over the operating system setting.',
                    'configuration': 'Preference stored in the browser with priority over prefers-color-scheme.',
                    'usageFlow': 'The user switches the theme manually → returns another day → the site opens in the theme they chose.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'dark-persistencia-pestanas',
                    'item': 'User Choice Persistence',
                    'title': 'The theme change applies across every open tab',
                    'description': 'Switching the theme in one tab applies it to the other open tabs of the site: two different looks never coexist.',
                    'configuration': 'Preference-change propagation across tabs of the same browser.',
                    'usageFlow': 'The user has two tabs open → switches the theme in one → the other updates by itself.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'dark-transicion',
                    'item': 'Smooth Mode Transition',
                    'title': 'Smooth theme switch, no flashes',
                    'description': 'Switching between light and dark feels elegant: a smooth transition with no visual jumps or flashes interrupting navigation.',
                    'configuration': 'CSS transitions limited to colors/backgrounds with short duration, avoiding expensive properties.',
                    'usageFlow': 'The user taps the toggle → the interface fades from one theme to the other → they keep browsing uninterrupted.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'dark-adaptacion-medios',
                    'item': 'Image & Media Adaptation',
                    'title': 'Images and icons readable in both modes',
                    'description': 'Logos, icons and graphics adjust to the active mode to keep contrast and readability, with no elements "disappearing" in dark.',
                    'configuration': 'Per-theme asset variants where needed and icons inheriting the theme color.',
                    'usageFlow': 'The user toggles the theme → graphic elements adapt → everything stays visible with good contrast.',
                    'priority': 'medium',
                },
            ],
        },
        'gift_cards_module': {
            'epic_title': 'Extended scope: Gift Cards & Digital Vouchers',
            'epic_description': (
                'Technical breakdown of the gift cards module. Each requirement covers '
                "one stage of the gift card's lifecycle."
            ),
            'requirements': [
                {
                    'flowKey': 'gift-creacion-venta',
                    'item': 'Gift Card Creation & Sales',
                    'title': 'Gift card purchase with configurable balance',
                    'description': 'Customers buy digital gift cards with the balance they choose directly on the site, with integrated payment and immediate delivery to the recipient.',
                    'configuration': 'Configurable amounts (fixed or free within a range), payment through the active gateway and email delivery to the recipient.',
                    'usageFlow': 'The buyer picks amount and recipient → pays → the recipient receives the card with its code by email.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'gift-creacion-envio-programado',
                    'item': 'Gift Card Creation & Sales',
                    'title': 'Scheduled delivery for the occasion date',
                    'description': 'The buyer picks the delivery date (birthday, anniversary) and the card reaches the recipient exactly that day, with a confirmation to the buyer.',
                    'configuration': 'Optional delivery date with scheduled sending and buyer confirmation once delivered.',
                    'usageFlow': 'The buyer pays today → picks the date → the recipient receives the card that day → the buyer gets the confirmation.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'gift-canje-checkout',
                    'item': 'Checkout Redemption with Unique Code',
                    'title': 'The code applies as partial or full payment at checkout',
                    'description': 'The recipient enters their unique code at checkout and the balance is discounted from the total, as partial or full payment, validated on the spot.',
                    'configuration': 'Unique verifiable codes with validity and balance validation at checkout; discount applied atomically.',
                    'usageFlow': 'The recipient shops → enters the code at checkout → the system validates balance and validity → the total is discounted and the remaining balance recorded.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'gift-canje-combinacion-pagos',
                    'item': 'Checkout Redemption with Unique Code',
                    'title': 'The balance combines with other payment methods',
                    'description': 'If the total exceeds the card balance, the rest is paid through the active gateway in the same purchase; any leftover balance stays for next time.',
                    'configuration': 'Balance applied as a discount and the excess charged through the gateway in a single checkout transaction.',
                    'usageFlow': 'The total exceeds the balance → the customer pays the difference with their card → the purchase closes complete and the balance hits zero.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'gift-canje-proteccion-codigos',
                    'item': 'Checkout Redemption with Unique Code',
                    'title': 'Codes protected against guessing and reuse',
                    'description': 'Codes are not guessable, every redemption deducts the balance atomically and repeated failed attempts are temporarily blocked.',
                    'configuration': 'High-entropy codes, atomic balance deduction and a failed-attempt limit per session.',
                    'usageFlow': 'Someone tries random codes → the attempts get blocked → real codes keep their balance intact.',
                    'priority': 'high',
                },
                {
                    'flowKey': 'gift-historial-saldo',
                    'item': 'Balance & Transaction History',
                    'title': 'Balance and movements visible to both parties',
                    'description': 'Buyer and recipient can check the available balance, redemptions made and the expiration date of each card.',
                    'configuration': 'Per-card movement log (purchase, redemptions, adjustments) queryable by code.',
                    'usageFlow': 'The user checks their card → sees balance, movements and expiration → knows exactly how much they can redeem.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'gift-diseno-marca',
                    'item': 'Custom Branded Design',
                    'title': "Cards with the business's identity and a personal message",
                    'description': "Every gift card ships with the brand's logo and colors, plus a customizable message from the buyer to the recipient.",
                    'configuration': "Card template with the business's visual identity and a personal-message field for the buyer.",
                    'usageFlow': 'The buyer writes their message → the card is generated with the brand and message → the recipient receives a polished piece.',
                    'priority': 'medium',
                },
                {
                    'flowKey': 'gift-diseno-vista-previa',
                    'item': 'Custom Branded Design',
                    'title': 'Card preview before paying',
                    'description': 'The buyer sees the final card (design and message) before paying, avoiding mistakes in a gift that matters.',
                    'configuration': 'Rendered preview with the brand design and the message entered by the buyer.',
                    'usageFlow': 'The buyer writes the message → previews the card → fixes anything off → pays with confidence.',
                    'priority': 'low',
                },
                {
                    'flowKey': 'gift-vencimiento',
                    'item': 'Configurable Expiration',
                    'title': 'Per-card-type expiration policies with notices',
                    'description': 'The business defines expiration per card type (no expiration, 6 months, 1 year or custom) and the recipient gets notices before it expires.',
                    'configuration': 'Per-type expiration policy with automatic notifications scheduled before expiry.',
                    'usageFlow': 'The card approaches expiry → the recipient receives the notice → redeems in time or the business decides to extend.',
                    'priority': 'medium',
                },
            ],
        },
    },
}


def _norm_id_list(raw: Any) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [str(v).strip() for v in raw if isinstance(v, str) and str(v).strip()]


def _epic_key_for(module_id: str) -> str:
    return f"mod-{slugify(str(module_id)).replace('_', '-')}"


def _module_match_keys(module_id: str) -> set[str]:
    return {module_id, f'module-{module_id}', _epic_key_for(module_id)}


def _epic_requirements(epic: dict) -> list:
    reqs = epic.get('requirements')
    return reqs if isinstance(reqs, list) else []


def _epic_matches_module(epic: dict, keys: set[str]) -> bool:
    ids = set(_norm_id_list(epic.get('linked_module_ids') or epic.get('linkedModuleIds')))
    if ids & keys:
        return True
    epic_key = str(epic.get('epicKey') or '').strip()
    return bool(epic_key) and epic_key in keys


def _module_covered(epics: list, keys: set[str]) -> bool:
    """A module is covered when seller/LLM content already speaks for it."""
    for epic in epics:
        if not isinstance(epic, dict):
            continue
        reqs = [r for r in _epic_requirements(epic) if isinstance(r, dict)]
        if _epic_matches_module(epic, keys) and reqs:
            return True
        for req in reqs:
            ids = set(_norm_id_list(req.get('linked_module_ids') or req.get('linkedModuleIds')))
            if ids & keys:
                return True
    return False


def _matching_empty_epic(epics: list, keys: set[str]) -> dict | None:
    for epic in epics:
        if (
            isinstance(epic, dict)
            and _epic_matches_module(epic, keys)
            and not _epic_requirements(epic)
        ):
            return epic
    return None


def _collect_live_item_ids(fr_content: Any) -> set[str]:
    ids: set[str] = set()
    if not isinstance(fr_content, dict):
        return ids
    for arr_key in ('groups', 'additionalModules'):
        for group in fr_content.get(arr_key) or []:
            if not isinstance(group, dict):
                continue
            for item in group.get('items') or []:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get('id') or '').strip() or build_item_id(
                    group.get('id'), item.get('name'),
                )
                if item_id:
                    ids.add(item_id)
    return ids


def _collect_flow_keys(epics: list) -> set[str]:
    keys: set[str] = set()
    for epic in epics:
        if not isinstance(epic, dict):
            continue
        for req in _epic_requirements(epic):
            if isinstance(req, dict):
                flow_key = str(req.get('flowKey') or '').strip()
                if flow_key:
                    keys.add(flow_key)
    return keys


def _dedupe_flow_key(base: str, taken: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in taken:
        candidate = f'{base}-{suffix}'
        suffix += 1
    return candidate


def seed_module_technical_requirements(
    technical_content_json: Any,
    sections: list[dict] | None,
    language: str = 'es',
) -> dict[str, Any]:
    """Seed default technical requirements for uncovered catalog modules.

    Pure function (no ORM): takes the technical_document content_json plus the
    proposal's section payloads (``[{'section_type', 'content_json'}]``) and
    returns a deep copy where every visible, non-invite additionalModule that
    has a catalog entry and no epic/requirement of its own gets its default
    epic appended (or an existing empty matching epic filled).

    Seeded rows carry raw ``linked_module_ids`` — callers run
    ``normalize_technical_document_module_links`` right after so the stored
    document uses canonical ``module-<id>`` links and stays selection-gated.
    """
    out = copy.deepcopy(technical_content_json) if isinstance(technical_content_json, dict) else {}
    catalog = MODULE_REQUIREMENTS_CATALOG.get('en' if language == 'en' else 'es') or {}

    fr = next(
        (
            s for s in (sections or [])
            if isinstance(s, dict) and s.get('section_type') == 'functional_requirements'
        ),
        None,
    )
    fr_content = (fr or {}).get('content_json')
    if not isinstance(fr_content, dict):
        return out

    epics = out.get('epics')
    if not isinstance(epics, list):
        epics = []
        out['epics'] = epics

    live_item_ids = _collect_live_item_ids(fr_content)
    taken_flow_keys = _collect_flow_keys(epics)

    for module in fr_content.get('additionalModules') or []:
        if not isinstance(module, dict):
            continue
        module_id = str(module.get('id') or '').strip()
        entry = catalog.get(module_id)
        if not entry:
            continue
        if module.get('is_visible') is False or module.get('is_invite'):
            continue
        keys = _module_match_keys(module_id)
        if _module_covered(epics, keys):
            continue

        # Existing ids are opaque and can outlive a rename. Index the live
        # items once, keeping the first match when legacy names repeat.
        ids_by_name = {}
        for item in module.get('items') or []:
            if isinstance(item, dict):
                name_key = build_item_id(module_id, item.get('name'))
                ids_by_name.setdefault(name_key, str(item.get('id') or '').strip() or name_key)

        seeded = []
        for req in entry['requirements']:
            flow_key = _dedupe_flow_key(req['flowKey'], taken_flow_keys)
            taken_flow_keys.add(flow_key)
            catalog_id = build_item_id(module_id, req.get('item'))
            item_id = ids_by_name.get(catalog_id, catalog_id)
            seeded.append({
                'flowKey': flow_key,
                'title': req['title'],
                'description': req.get('description', ''),
                'configuration': req.get('configuration', ''),
                'usageFlow': req.get('usageFlow', ''),
                'priority': req.get('priority', 'medium'),
                'linked_module_ids': [module_id],
                'linked_item_ids': [item_id] if item_id in live_item_ids else [],
            })

        target = _matching_empty_epic(epics, keys)
        if target is not None:
            target['requirements'] = seeded
            existing_ids = _norm_id_list(
                target.get('linked_module_ids') or target.get('linkedModuleIds'),
            )
            if not set(existing_ids) & keys:
                target['linked_module_ids'] = existing_ids + [module_id]
        else:
            epics.append({
                'epicKey': _epic_key_for(module_id),
                'title': entry['epic_title'],
                'description': entry.get('epic_description', ''),
                'linked_module_ids': [module_id],
                'requirements': seeded,
            })

    return out
