# Documentos 8.3.0 — contratos de programas editables

PA-255/PA-256: `update_document` permite actualizar los contratos privados de
Building with Us y Células con `if_match` y `change_note` obligatorios. Admite
Markdown y presentación, comparte escritor con el Panel y los MCP de Programas,
y actualiza revisión, PDF e historial en una transacción. Conserva la identidad
y ubicación del documento y las restricciones de los demás espejos.

Las lecturas publican capacidades correctas y el ETag incluye la revisión
contractual vigente. `template_style` y `change_note` se documentan para esta
operación. No se agregan herramientas, migraciones ni aprobaciones jurídicas.
Programas 3.1.1 y las compatibilidades Building with Us 3.1.2 / Building on Demand
4.1.2 actualizan las descripciones del documento compartido, conservando sus
operaciones y confirmaciones existentes.
Contrato de uso y escenarios: [Contratos de programas](../PROGRAM_CONTRACT_DOCUMENTS.md).
