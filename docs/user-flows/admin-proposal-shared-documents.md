# Documentos compartidos de una propuesta

| Clase | Interacción | Resultado |
|---|---|---|
| success | Confirmar otra revisión con servicio apagado o aprobado | El paquete incluye sólo producto o producto y servicio respectivamente, junto a los anexos elegidos explícitamente |
| success | Revisar y confirmar un nuevo paquete | Ambos módulos muestran la nueva versión y conservan el historial |
| success | Guardar un adjunto habilitado en borrador | Misma identidad; archivo aprobado conservado hasta reconfirmar |
| error | Confirmar con una versión desactualizada | Conflicto visible; formulario y archivo conservados |
| error | Guardar un adjunto con una huella antigua y consultar la versión actual | El archivo elegido se conserva al actualizar los datos de la fuente; el reintento explícito envía el mismo archivo con la huella revisada |
| failure | Falla la consulta de la versión actual | El archivo y la huella previa se conservan, con un mensaje que permite volver a consultar |
| failure | El servidor falla al confirmar o guardar un adjunto | Mensaje visible; archivo y formulario conservados para reintentar |
| display | Abrir el historial y recargar propuesta y gestor | Título descriptivo conservado al pasar a Histórico, misma identidad y revisiones descargables |

Los documentos estructurados abren el mismo editor de origen desde el gestor. Confirmar una revisión conserva el cliente y proyecto vinculados; cambiar de proyecto usa el flujo de reasignación. La aprobación inicial y los históricos usan la revisión interna, sin aceptación pública. Aprobar y revisar después conserva la decisión comercial sin crear cliente, proyecto ni paquete automáticamente.

Las garantías de bytes e identidad se verifican además con pruebas de servicios reales y operaciones MCP autenticadas: consulta del recurso, sustitución de borrador, validación del archivo subido y confirmación de otra revisión. Los mocks del navegador cubren interacción y presentación.

El switch de servicio sólo aparece con contratos separados y se guarda con la
huella de origen. No cambia el paquete aprobado hasta confirmar otra revisión.
La vista previa exige sólo los contratos aprobados; un conflicto o fallo conserva
el switch, formulario, adjuntos y evidencia vigente. Las operaciones MCP/CLI de
recuperación no son flujos de navegador: sus pruebas de integración verifican los
archivos y vínculos reales sin regeneración.

La recuperación del adjunto se recorre además por Panel → Propuestas →
Documentos → recurso compartido en `admin-proposal-shared-binary.spec.js`.
El navegador usa la página y el store reales, con HTTP simulado: reproduce 409,
consulta de la versión actual y guardado del mismo PDF sin reseleccionarlo.
Otro caso cubre el fallo de esa consulta. No son ejecuciones sobre DEV ni
acreditan persistencia real por sí solos; su resultado se registra en CI.
