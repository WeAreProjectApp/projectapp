# Paquetes de requerimientos por talla

La oferta permite implementar cambios acotados sobre un producto existente sin
cotizar horas por solicitud. Se describe el cambio, se acuerda el resultado y se
confirma su talla antes de programarlo. Un requerimiento aprobado dentro de un
paquete ya contratado no necesita una cotización individual. L y XL requieren un levantamiento y una
cotización independientes.

## Oferta inicial para Colombia

Todos los importes siguientes son COP, más IVA.

| Paquete | XS | S | M | Referencia por composición | Descuento | Total | Ahorro |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ágil | 30 | 0 | 0 | $1.500.000 | 10 % | $1.350.000 | $150.000 |
| Pro | 30 | 20 | 0 | $4.000.000 | 15 % | $3.400.000 | $600.000 |
| Premium | 30 | 20 | 10 | $7.600.000 | 25 % | $5.700.000 | $1.900.000 |

La referencia se calcula a partir de valores internos iniciales de $50.000 por
XS, $125.000 por S y $360.000 por M. No es un precio histórico ni una promoción
con fecha de vencimiento. El cliente ve cupos, vigencia, referencia, descuento,
ahorro y total, sin los valores individuales por talla.

## Condiciones de uso

- Compra única, sin renovación automática. Vigencia inicial: doce meses desde
  el pago para solicitar y validar los requerimientos; ejecución según agenda
  acordada. Los cupos no utilizados vencen.
- Cada requerimiento usa un cupo de su propia talla. No hay equivalencias ni
  intercambio entre tallas.
- Las correcciones cubiertas por garantía no consumen cupos. Hosting,
  infraestructura y licencias no se incorporan por comprar el paquete.
- Esta versión configura y presenta la oferta; el control de compras y consumos
  por cliente se mantiene fuera del sistema.

## Cómo configurar

Abrir **Nuestra oferta → Paquetes de requerimientos**. En Catálogo se crean o
editan nombres y notas ES/EN, cupos XS/S/M, vigencia, descuento, mercado, orden y
estado. Tabla, Tarjetas y Comparativa presentan la misma oferta; el mayor
descuento entre paquetes activos se destaca en Comparativa.

En **Configuración** se ajustan los valores internos COP por talla, los factores
por mercado y el cupo mensual de Alianza. Restaurar un catálogo repone Ágil, Pro
y Premium para ese mercado; conserva los valores internos configurados y los
compromisos históricos.

## Precios en USD

La tasa COP por USD es la configurada en Contabilidad. Los factores iniciales
son 1,4 para extranjeros y 1,8 para EE. UU.; ambos son editables.

`Total USD = referencia COP ÷ tasa COP/USD × factor × (1 − descuento)`

Backend calcula con decimales. Referencia y total se redondean al final: COP a
pesos enteros y USD a centavos. El PDF y las vistas respetan el total calculado,
sin volver a descontar una referencia ya redondeada. Una tasa inválida impide
cotizar USD; no se inventa una tasa alternativa.

Ejemplo ilustrativo, **no consulta de la tasa vigente**: con 4.000 COP/USD, los
totales extranjeros son USD 472,50 / 1.190 / 1.995; EE. UU. USD 607,50 / 1.530 /
2.565, antes de impuestos según la convención de la propuesta.

## Propuestas y documentos

La pestaña **Paquetes de requerimientos** permite usar el catálogo automático o
una composición y referencia manuales. Se puede ocultar el bloque de paquetes
sin retirar la cláusula general de alcance.

Una propuesta histórica conserva horas y precios. Sólo un borrador puede
**Revisar nuevos paquetes**: muestra la oferta actual y exige Guardar para
adoptarla. No se convierte un número de horas en cupos.

Al emitir se guardan composición, referencia, descuento, total y condiciones;
la tasa y el factor se conservan como contexto privado del servidor. Una
actualización del catálogo no recotiza esa oferta. Actualizar desde el catálogo
prepara una revisión explícita. Los archivos enviados y aprobados permanecen
inmutables en el historial.

Las configuraciones comerciales guardadas también se actualizan para las propuestas
nuevas; las demás secciones y las ofertas ya creadas se conservan.

La transición incluye propuestas/PDF, detalle comercial, plantillas
contractuales vigentes y sus espejos, MCP, defaults, fake data y guías de
operación. Las migraciones se aplican mediante el despliegue, nunca desde el
worktree de una sesión contra la base del servicio.

## Programa de Alianza

La alianza de cinco años incluye un cupo mensual independiente, inicialmente
**4 XS + 2 S + 1 M**, desde producción y mientras el acuerdo esté vigente y al
día. No se acumula ni intercambia entre tallas. Se edita desde Configuración de
Paquetes de requerimientos y cada acuerdo nuevo conserva su composición.

La alianza de tres años no incluye ese beneficio. Los acuerdos históricos
mantienen sus condiciones previas y un segundo ciclo conserva la composición
del acuerdo de origen.

El video predeterminado de Alianza presenta XS/S/M sin fijar cantidades que
puedan cambiar en Configuración. Se regeneró la narración y el MP4 de 60 s
(1920 × 1080, 30 fps); los videos personalizados mantienen su configuración.
