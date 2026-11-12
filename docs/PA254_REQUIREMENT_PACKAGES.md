# PA-254 — Paquetes por tallas

## Flujo y superficies

Panel → Plataforma → Solicitudes por tallas (`/panel/requirement-packages`)
reúne pendientes, búsqueda, filtros y entrada al proyecto. En Plataforma, cada
proyecto tiene **Paquetes de requerimientos** (`/platform/projects/:id/packages`).
Los ejemplos y el catálogo se pueden consultar antes de comprar. Solicitar una
evaluación no consume ni exige seleccionar una entrega anterior.

El equipo puede indicar que comenzó la evaluación, o publicar directamente una
propuesta manual con talla, señales, alcance, explicación y rango orientativo de
fechas. Publicar no consume. El titular acepta o explica su objeción; después
de una objeción el equipo vuelve a responder y el cliente debe aceptar la nueva
propuesta. La aceptación y el débito se registran en una única transacción.
La aprobación interna ni una sesión suplantada sustituyen ese consentimiento.

## Ejemplos y clasificación

Hay ejemplos genéricos ES/EN y revisiones por proyecto. La personalización
prevalece **por talla**; al retirar una talla particular reaparece su ejemplo
genérico. Un proyecto no tiene que personalizarlas todas. El editor presenta
la vista previa, requiere motivo y conserva autoría e historial. Publicar
ejemplos no modifica parámetros económicos, revisiones de calculadora ni PDF
aprobados. La propuesta conserva los ejemplos exactos que recibió el cliente.

El catálogo de compra cubre XS/S/M. L y XL siguen siendo tallas válidas de
clasificación, pero no consumibles de estos paquetes; requieren cotización
independiente. Proyecto queda fuera del paquete. Las horas y costos permanecen
internos. Las fechas se proponen manualmente, sin convertir horas en plazos.

## Compra y saldo

Una orden pertenece a un proyecto y a su titular. Congela composición,
referencia, descuento, subtotal, impuesto, total, moneda y condiciones. El
servidor compara la huella de la oferta revisada antes de crear la orden para
evitar cobrar otra oferta si cambió el catálogo. Mercado e impuesto se
administran por proyecto para compras futuras; valores iniciales COL/19 %,
siguiendo la convención de cuenta de cobro existente. Deben revisarse antes
de ofrecer paquetes a proyectos de otros mercados.

La compra online COP usa un link de Wompi de uso único y monto fijo. No crea
suscripciones ni pagos de hosting. La respuesta del proveedor se verifica por
identidad, vínculo con la orden, moneda, importe y estado. El webhook comparte
esa acreditación con la verificación posterior al retorno del navegador.
Regresar a Plataforma por sí solo no activa cupos. En otras monedas se ofrece
pago externo, que el administrador confirma con fecha real y referencia.
Confirmar un pago acredita una sola vez, aunque se repita la notificación.

Contrato externo contrastado con [Links de pago de Wompi](https://docs.wompi.co/docs/colombia/links-de-pago/):
monto fijo, moneda COP, uso único y URL de retorno. El proveedor sólo se
sustituye en su frontera en las pruebas; no se realizan cobros reales en QA.

Cada aceptación usa un cupo de su talla. Se elige la compra vigente que vence
primero, luego fecha de compra e ID, y se presenta su identidad al cliente.
La aceptación verifica otra vez origen, vigencia y saldo bajo el candado del
proyecto. No hay intercambios, sobregiros ni traslados entre proyectos.
La vigencia comienza en la fecha del pago; un requerimiento aceptado durante
ella puede ejecutarse después. Las garantías identificadas por el equipo no
consumen. Una reversión administrativa exige motivo, vuelve a la compra
original y no extiende su vencimiento ni devuelve dinero automáticamente.

Modificar una propuesta aceptada requiere otra revisión y nueva aceptación.
Al aceptar el reemplazo, el consumo anterior se revierte y el nuevo se aplica
atómicamente; si la operación falla, el consumo original permanece intacto.
Las compras y solicitudes bloquean el traslado automático a otro cliente y
se conservan mediante relaciones protegidas.

## API y MCP

API compartida: `/api/requirement-packages/`. Plataforma usa su cliente JWT;
Panel conserva sesión y CSRF. La autoridad se resuelve por canal y por proyecto.

- `projects/:id/`: catálogo, ejemplos efectivos, saldos y colecciones paginadas.
- `examples/` y `projects/:id/examples/`: consulta y publicación; `history/`
  conserva las revisiones. `language=es|en` selecciona el idioma.
- `projects/:id/orders/`: crea una orden; acciones `checkout`,
  `confirm-external` y `verify` conservan su vínculo.
- `projects/:id/requests/`: crea solicitudes generales; detalle y acciones
  `evaluate`, `offer`, `decide` conservan versiones y consentimiento.
- `projects/:id/movements/:id/reverse/` y `settings/`: gestión administrativa.
- `admin/requests/` y `admin/projects/`: bandeja y buscador del equipo.

Las escrituras incluyen un UUID estable `request_id`; reutilizarlo con otro
contenido produce conflicto. Las propuestas/decisiones/configuración requieren
la versión consultada, y ejemplos la revisión vigente. Las colecciones de
compras, solicitudes y movimientos usan desplazamientos de 20 registros.

MCP Comercial administra ejemplos genéricos. MCP Proyectos consulta saldos y
solicitudes y administra ejemplos particulares, compras, pagos externos,
evaluaciones, configuración y reversiones. Las operaciones sensibles requieren
su confirmación MCP. Ninguna credencial administrativa puede aceptar por el
cliente. Contratos de campos y huellas viajan con la implementación.

## Corpus inicial y límites de calibración

Se seleccionan doce casos de ProjectApp, con revisión de referencia
`295b65efb77af8303ec28b269ae1935a995a6f0e`. Las tallas son **hipótesis para
revisión humana**: no constituyen resultados aprobados ni horas reales.

| Hipótesis | Capacidad acotada | Fuente |
|---|---|---|
| XS | Mostrar título documental ya disponible | PA-246 en `tasks/active_context.md` |
| XS | Limitar descripción del estimador | `frontend/components/BuildingOnDemand/BagEstimator.vue` |
| S | Confirmación visual al copiar URL | `docs/audits/secure-link-copy-feedback-2026-10-19.md` |
| S | Creación contextual reutilizando formulario | `docs/user-flows/admin-document-folder-manage.md` |
| M | Filtros sobre listado documental existente | `docs/user-flows/admin-document-state-filters.md` |
| M | Consultar historial ya registrado | `docs/user-flows/admin-document-change-history.md` |
| L | Jerarquía propia de carpetas de Enlaces seguros | `docs/audits/2026-10-26-secure-link-folders-qa.md` |
| L | Construir registro de eventos y consulta | `backend/content/services/entity_history.py` |
| XL | Integración de pagos con pasarela | `backend/accounts/services/wompi.py` |
| XL | Google/código con revocación de acceso | `docs/AUTHORIZED_ACCESS.md` |
| Proyecto | Appi completo y sus capacidades independientes | `docs/APPI.md` |
| Proyecto | Contratación estatal completa | `docs/PROCUREMENT.md` |

El equipo administrador revisará alcance, preexistencias, señales y talla de
referencia antes de cargar `expected_size`. Los contrastes construidos para
límites de talla se identifican como ejemplos y no como entregas. Ningún
generador carga horas reales ni fabrica calibración económica.

Se conserva provisionalmente la regla existente de tres cierres por talla y
definición y alerta por desvío superior al 30 %. Cambiar parámetros requiere
evidencia y publicación explícita. Los estimados históricos y fechas de PR no
demuestran costo real. Células conserva sus planes y contratos horarios;
Alianza mantiene su beneficio mensual independiente.

## Validación y operación

Pruebas automatizadas exclusivamente en CI. El generador canónico añade
compras externas ficticias, saldo, solicitudes pendientes y ejemplos de dos
proyectos para contrastar permisos; no llama proveedores. Su limpieza protegida
se ejecuta antes de retirar tickets y estimaciones, y preserva ejemplos globales.
Preparar escenarios de objeción, propuesta, garantía, expiración y competencia
por el último cupo en el entorno QA aislado. No ejecutar el generador ni
migraciones sobre el servicio desde el worktree.

Este documento describe el contrato implementado, no acredita CI verde,
despliegue, aprobación manual ni calibración económica con evidencia real.
