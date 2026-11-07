# Dirección del cliente en la aprobación de propuestas

Comercial pasa de 6.4.0 a 6.5.0 y Propuestas de 6.2.0 a 6.3.0. Ambos publican
`new_client.address` en `review_proposal_approval`, a partir del mismo serializer
que valida el Panel. La dirección introducida al crear un cliente se conserva
en el perfil vinculado a la propuesta.

El campo es opcional, permite vacío y admite hasta 512 caracteres. Omitirlo
conserva el comportamiento anterior; una dirección nula o de más de 512 caracteres
se rechaza antes de crear entidades. Las confirmaciones sensibles y sus reintentos
mantienen sus reglas vigentes. No se modifican los campos de los clientes ya
existentes, no se activa ninguna cuenta y no se envían invitaciones.

No requiere migraciones. Documentos y los demás catálogos conservan sus versiones
y huellas. La cobertura de persistencia y errores de Panel/MCP se ejecuta sólo en CI.
