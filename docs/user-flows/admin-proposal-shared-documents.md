# Documentos compartidos de una propuesta

| Clase | Interacción | Resultado |
|---|---|---|
| success | Revisar y confirmar un nuevo paquete | Ambos módulos muestran la nueva versión y conservan el historial |
| success | Guardar un adjunto habilitado en borrador | Misma identidad; archivo aprobado conservado hasta reconfirmar |
| error | Confirmar con una versión desactualizada | Conflicto visible; formulario y archivo conservados |
| error | Guardar un adjunto con una huella antigua y consultar la versión actual | El archivo elegido se conserva; la versión solo cambia tras una revisión explícita |
| failure | El servidor falla al confirmar o guardar un adjunto | Mensaje visible; archivo y formulario conservados para reintentar |
| display | Abrir el historial | Títulos, versión vigente y revisiones descargables del recurso |

Los documentos estructurados abren el mismo editor de origen desde el gestor. Confirmar una revisión conserva el cliente y proyecto vinculados; cambiar de proyecto usa el flujo de reasignación. La aprobación inicial y los históricos usan la revisión interna, sin aceptación pública ni posposición del proyecto al aprobar.

Las garantías de bytes e identidad se verifican además con pruebas de servicios reales y operaciones MCP autenticadas: consulta del recurso, sustitución de borrador, validación del archivo subido y confirmación de otra revisión. Los mocks del navegador cubren interacción y presentación.
