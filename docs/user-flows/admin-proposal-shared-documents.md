# Documentos compartidos de una propuesta

| Clase | Interacción | Resultado |
|---|---|---|
| success | Revisar y confirmar un nuevo paquete | Ambos módulos muestran la nueva versión y conservan el historial |
| success | Guardar un adjunto habilitado en borrador | Misma identidad; archivo aprobado conservado hasta reconfirmar |
| error | Confirmar con una versión desactualizada | Conflicto visible; formulario y archivo conservados |
| failure | El servidor falla al confirmar | Mensaje visible; se puede reintentar |
| display | Abrir el historial | Títulos, versión vigente y revisiones descargables del recurso |

Los documentos estructurados abren el mismo editor de origen desde el gestor. La aprobación inicial y los históricos usan la revisión interna, sin aceptación pública ni posposición del proyecto al aprobar.

Las garantías de bytes e identidad se verifican además con pruebas de servicios reales; los mocks del navegador cubren interacción y presentación.
