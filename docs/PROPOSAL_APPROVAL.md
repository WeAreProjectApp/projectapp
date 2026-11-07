# Aprobación y vinculación de propuestas

Aceptar una propuesta cierra la decisión comercial. El equipo revisa después
el cliente, el proyecto y los documentos que deben incorporarse al proyecto.
La aprobación interna diferida no crea proyectos ni clientes automáticamente.
La aceptación pública sigue deshabilitada y el cambio genérico de estado exige
abrir la revisión interna.

## Recorrido del equipo

Desde el listado, el estado en línea, el editor o una propuesta expandida en
Clientes, **Aprobar** abre el mismo
modal. Una propuesta aceptada sin proyecto muestra **Pendiente de revisión**
y permite retomar la revisión. El equipo puede seleccionar cliente y proyecto
existentes o preparar su creación en el formulario; se guardan al confirmar.
Los proyectos existentes conservan dueño, estado, finanzas y recursos.

El resumen de alcance, inversión, moneda, pagos y hosting es de lectura. Las
correcciones se realizan en la propuesta antes de confirmar. **Aprobar y revisar
después** acepta sin vincular; **Cancelar** conserva el estado anterior.

## Documentos del cierre

El switch **¿Adjuntar los contratos de la propuesta?** comienza activado.

| Selección | Paquete contractual |
|---|---|
| Activado | Contrato único o contratos separados de producto y servicio, según la modalidad vigente |
| Desactivado | Uno o varios archivos aportados por el equipo: contrato, anexo, otrosí u otro documento |

El detalle comercial y el detalle técnico se incluyen siempre. Los adjuntos
personalizados sustituyen los contratos de la propuesta únicamente en el nuevo
paquete. Los originales, firmas y archivos históricos se conservan. Otros
adjuntos de la propuesta se incorporan sólo por selección explícita.

La carga reutiliza los formatos permitidos para documentos y el límite de
15 MB por archivo y 36 MB para el paquete completo. Si falta un archivo requerido, tiene un formato inválido
o el contrato vigente necesita revisión, el modal explica qué corregir.
Posponer sigue disponible. Aportar un contrato por correo no registra una
firma electrónica ni crea un contrato de seguimiento de entregas.

## Contrato técnico

`GET /api/proposals/:id/approval/` devuelve cliente, proyecto vinculado,
resumen comercial, modalidad y documentos disponibles, archivos confirmados,
`selected_document_ids` y `source_hash`. La respuesta incluye la fecha de sincronización y las
transiciones vigentes para actualizar el siguiente paso del editor sin recargar.
`POST` usa las acciones `confirm`, `defer` y `retry`.

Para confirmar se envían `client_profile_id` o `new_client`, `project_id` o
`new_project`, `use_proposal_contracts`, `selected_document_ids`, `source_hash`
y `request_id`. Los archivos personalizados viajan como `custom_files` y
su descripción como `custom_documents`. En multipart la metadata se envía
en el campo JSON `payload`.

Al crear un cliente en esta revisión, `new_client.address` es opcional y admite
hasta 512 caracteres, igual que el perfil. La confirmación conserva la dirección
introducida; omitirla o dejarla vacía mantiene una dirección vacía. Panel y MCP
aplican la misma validación antes de crear entidades. Esto no activa la cuenta
del cliente ni envía una invitación.

El servidor valida cliente, pertenencia del proyecto, documentos y versión
antes de guardar, incluidas las condiciones automáticas resueltas desde el
catálogo de horas. Los clientes comerciales no archivados pueden vincularse
sin activar sus cuentas de acceso. La confirmación atómica conserva un manifiesto y copias
privadas duraderas, junto con el cliente y las condiciones comerciales
confirmadas. Editar la propuesta después no modifica ese paquete. Un reintento reutiliza el mismo vínculo y paquete, sin
duplicar proyectos, clientes, archivos ni correos de aceptación. En revisiones se recupera
la selección confirmada; ningún anexo nuevo queda marcado automáticamente. Los recursos
técnicos existentes se conservan durante la sincronización de aprobación.

El Panel usa `SessionAuthentication`, permisos administrativos y CSRF.
Platform usa `SessionJWTAuthentication` y la autorización del proyecto.
Las descargas de las copias privadas requieren autorización; no se publican
rutas de almacenamiento. MCP comparte el servicio, el paquete explícito,
la validación de assets y la confirmación sensible.

En el Gestor, un conflicto al sustituir un adjunto conserva el archivo elegido.
Revisar versión actual aplica los datos de la fuente devueltos por el servidor
sin desmontar el editor. El reintento explícito usa el mismo archivo y la huella
revisada; una consulta fallida conserva el archivo y la huella anterior. El
archivo aprobado sólo cambia mediante la confirmación de otra revisión.

La migración nueva `content/0278` depende de
`0277_merge_vat_and_economic_conditions` y de la migración existente
`accounts/0075_p4_platform_domains_merge`; se aplica durante el despliegue,
nunca desde el worktree. Las propuestas y proyectos ya vinculados se
conservan sin reprovisión ni modificación automática de sus documentos.

## Validación

La entrega debe comprobar aceptación sin aprovisionamiento, posposición,
creación al vuelo, ambas modalidades contractuales, múltiples adjuntos,
errores sin efectos, conservación de originales, reintentos, permisos de
descarga y el recorrido del modal. Los resultados ejecutados se registran en
el PR de la sesión; autoría de un test no equivale a ejecución.
