# Ajuste al contrato combinado (producto + servicio): cláusulas del servicio que faltan

**Objetivo:** que el contrato único (producto y servicio) regule el servicio de hosting, mantenimiento y soporte igual que el contrato de servicio separado. No es un cambio para un cliente en particular; es un ajuste de la plantilla vigente.

**Dónde aplicarlo:** en la plantilla contractual predeterminada del módulo de propuestas. El documento "Contrato de prestación de servicios — borrador vigente" del gestor documental se actualiza solo, porque muestra esa misma plantilla en vivo. Ninguna de las dos se puede editar por MCP (la plantilla es de solo lectura y el documento del gestor es un espejo).

**Comparación hecha (05-10-2026):** plantilla combinada vs. contrato de producto y contrato de servicio separados de la propuesta #117.

- El contrato de **producto** separado coincide con las cláusulas 1 a 20 del combinado. Sin ajustes.
- El contrato de **servicio** separado tiene dos cláusulas que el combinado no tiene: **Duración y Renovación** y **Terminación del servicio** (con los avisos configurables de no renovación y terminación). Además hay tres ajustes menores de concordancia.

Los campos {service_initial_term}, {service_renewal_notice_days} y {service_termination_notice_days} son los mismos que hoy usa el contrato de servicio separado (valores actuales por defecto: 9 meses, 60 y 60 días). Hay que confirmar que la plantilla combinada pueda usarlos.

---

## 1. Nuevos parágrafos en la CLÁUSULA VIGÉSIMA PRIMERA

Insertar después del Parágrafo Cuarto — Responsabilidad Operativa:

### Parágrafo Quinto — Duración y Renovación del Servicio

El servicio de hosting, mantenimiento y soporte tendrá una duración inicial de {service_initial_term}, contada a partir de la fecha de puesta en producción prevista en el PARÁGRAFO PRIMERO de la presente cláusula, y se renovará automáticamente por periodos iguales a la periodicidad de pago pactada en el Documento Propuesta Comercial, salvo que alguna de las partes manifieste por escrito su intención de no renovarlo con al menos {service_renewal_notice_days} días calendario de antelación al vencimiento del periodo en curso. La no renovación o la terminación del servicio no afecta las obligaciones relativas al desarrollo del producto software previstas en las demás cláusulas del presente contrato.

### Parágrafo Sexto — Terminación del Servicio

Sin perjuicio de lo previsto en la CLÁUSULA DÉCIMA SEXTA respecto del desarrollo del producto software, el servicio de hosting, mantenimiento y soporte podrá darse por terminado de forma independiente en los siguientes casos:

**a) Por mutuo acuerdo:** en cualquier momento, mediante acuerdo escrito en el cual se definirán la liquidación de pagos y demás aspectos pendientes.

**b) Por EL CONTRATANTE:** mediante notificación escrita con al menos {service_termination_notice_days} días calendario de antelación. Los valores correspondientes a periodos del servicio ya iniciados no serán reembolsables.

**c) Por EL CONTRATISTA:** **i)** por mora en el pago del servicio, conforme a la etapa 4 del protocolo previsto en la CLÁUSULA VIGÉSIMA CUARTA; o **ii)** cuando EL CONTRATANTE incumpla reiteradamente sus obligaciones contractuales, afectando de manera sustancial la prestación del servicio, mediante notificación escrita con al menos quince (15) días hábiles de antelación.

En caso de terminación del servicio por cualquier causa, se aplicará lo previsto en el PARÁGRAFO CUARTO de la CLÁUSULA VIGÉSIMA CUARTA respecto de la exportación y conservación de los datos operativos de EL CONTRATANTE.

---

## 2. Ajustes de concordancia

**CLÁUSULA DÉCIMA SÉPTIMA, Parágrafo Primero.** Al final, agregar: "Tratándose de las obligaciones de pago del servicio de hosting, mantenimiento y soporte, se aplicará el protocolo previsto en la CLÁUSULA VIGÉSIMA CUARTA."

*Motivo:* hoy el combinado da 10 días hábiles para subsanar cualquier pago y permite terminar todo el contrato; el contrato de servicio separado remite al protocolo de mora (90 días con etapas), que la propia Cláusula Vigésima Cuarta declara como el único procedimiento para suspender la operación.

**CLÁUSULA DÉCIMA NOVENA (Mérito ejecutivo).** Cambiar "junto con sus anexos, las actas de entrega y los comprobantes de pago" por "junto con sus anexos, las actas de entrega, las cuentas de cobro o facturas y los comprobantes de pago".

*Motivo:* el servicio se cobra con cuentas de cobro o facturas, como dice el contrato de servicio separado.

**CLÁUSULA VIGÉSIMA CUARTA, etapa 4 de la tabla.** Cambiar "y para dar por terminado el servicio o el contrato conforme a la CLÁUSULA DÉCIMA SEXTA" por "y para dar por terminado el servicio conforme al PARÁGRAFO SEXTO de la CLÁUSULA VIGÉSIMA PRIMERA, o el contrato conforme a la CLÁUSULA DÉCIMA SEXTA".

**CLÁUSULA VIGÉSIMA CUARTA, Parágrafo Quinto (Concordancia).** Después de "la suspensión y la terminación previstas en la CLÁUSULA DÉCIMA SEXTA para las obligaciones del desarrollo", agregar ", la terminación del servicio prevista en el PARÁGRAFO SEXTO de la CLÁUSULA VIGÉSIMA PRIMERA".

---

## 3. Diferencia que se deja como está

La confidencialidad del combinado (Cláusula Décima Primera, con no circunvención y parágrafos detallados) es más completa que la del contrato de servicio separado (Cláusula Novena, versión corta). Ambas tienen vigencia de 2 años. No se propone cambio en el combinado; si se quiere total igualdad, el ajuste sería llevar al contrato de servicio separado la versión completa.
