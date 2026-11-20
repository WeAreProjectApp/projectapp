# PA-270 · Porcentajes de pago en el guardado de General

Comercial 6.8.0 y Propuestas 6.4.0 aceptan el campo opcional
`investment_payment_percentages` en `update_proposal_settings`. Los ajustes
de la propuesta y la sección Inversión se guardan en una transacción cuando se
envía una edición de pagos con la huella vigente en `if_match`. Los clientes
que envían ajustes de metadatos conservan su contrato.
