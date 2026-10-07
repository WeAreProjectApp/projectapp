# Corrección de relaciones de Littigio — 2026-10-07

> **Superado el 07-10-2026.** Después de este procedimiento se eliminaron con
> eliminación forzada los proyectos 14 y 15 y se conservó el 16. La recuperación
> vigente está en `littigio-retained-data-recovery.md`.

Este procedimiento separa la entrega de código de la reparación de producción.
No elimina las propuestas ni emite documentos contables.

## Fase 1 — Herramientas y validación

- Publicar el editor redistribuido y las operaciones MCP compartidas con Panel.
- Aplicar mediante el deploy las migraciones `content.0283` y `accounts.0078`.
- Verificar `tools/list` en los conectores vigentes: vista previa y confirmación
  de reasignación, actividad paginada, historial, detalle y fases de proyecto,
  branding y registro de contrato para facturación.
- Confirmar que el parche de dependencias por sí solo no introduce migraciones.

## Fase 2 — Inventario previo por MCP

Guardar fuera de Git las respuestas completas con fecha, IDs y huellas:

| Registro | Relación esperada |
| --- | --- |
| Cliente | Perfil 61, usuario 62 |
| Proyecto definitivo | 14, Littigio; carpeta raíz 129 |
| Propuestas que se conservan | 117 y 118 |
| Proyectos creados por el comportamiento anterior | 15 y 16 |
| Documentos que se conservan | 201, 202, 203, 208, 209, 227 y 236 |
| Ingresos que se conservan | 245–249; ya ligados al cliente 61 y proyecto 14 |

Releer las relaciones actuales antes de cada escritura. Los títulos no sustituyen
los IDs ni prueban que un contrato esté firmado. No cambiar el estado de los
documentos, sus textos, firmas, importes, IVA ni visibilidad durante esta reparación.

## Fase 3 — Traslado de propuestas

1. Ejecutar `preview_proposal_project_reassignment` para cada propuesta con
   `target_project_id: 14`.
2. Si aparecen bloqueos, conservar los proyectos y resolver esa dependencia;
   nunca forzar el traslado ni atribuir recursos técnicos ambiguos.
3. Ejecutar `reassign_proposal_project` con la huella vigente, motivo y un
   `request_id` estable; revisar y confirmar la intención MCP.
4. Verificar los mismos IDs de entregables, fases y archivos, el cliente y el
   proyecto nuevos. Reintentar una respuesta perdida con la misma intención.

El servicio guarda una auditoría durable, conserva el paquete de aprobación
original y mueve relaciones existentes. Los recursos técnicos distinguen su
propuesta de origen, incluso cuando dos propuestas reutilizan la misma clave.
La migración sólo atribuye recursos cuyo proyecto tiene una única propuesta
comprobable; los demás requieren revisión y bloquean el traslado automático.

## Fase 4 — Carpeta y contexto de facturación

1. Mediante Documentos, actualizar explícitamente cliente/usuario/proyecto de
   los siete documentos y moverlos de la carpeta 80 a la raíz existente 129.
   No crear otra raíz ni moverlos directamente a las carpetas del sistema.
2. Consultar `get_project_billing_options` del proyecto 14.
3. Registrar únicamente el contrato de desarrollo 208 mediante
   `link_project_billing_contract`, usando versión vigente y `request_id`.
   Revisar y confirmar su intención. El contrato de hosting 236 permanece
   separado; no se selecciona por semejanza de título.
4. Verificar que Inicio Fase 1 (ingreso 245) ofrece el tipo de cobro y el
   contrato vinculado. No generar, emitir, enviar ni liquidar una cuenta.

## Fase 5 — Retiro seguro y cierre

Consultar un inventario de eliminación nuevo para 15 y 16. Sólo eliminarlos
mediante la operación de proyecto vacío si no quedan dependencias. No usar
eliminación forzada ni seleccionar categorías para borrar. Registrar por separado
qué se aplicó, qué se verificó y qué quedó bloqueado; conservar las respuestas
previas y posteriores fuera del repositorio.

Estado al escribir este procedimiento: código en validación; reparación de
producción pendiente de publicación y acceso. Este documento no es un recibo
de cambios aplicados.

## Verificación parcial de datos — 2026-10-07, 01:35 UTC

El conector documental existente permitió corregir los documentos 201, 202, 203,
208, 209, 227 y 236 sin esperar las herramientas nuevas. Cada escritura utilizó
el ETag vigente y fijó perfil de cliente 61, proyecto 14 y carpeta 129. La lectura
posterior confirmó esos tres vínculos y la igualdad del Markdown, título, slug,
estado, visibilidad, idioma, tags, estados activos, notas y copias de comunicación.
Se conservaron copias completas y huellas del contenido en un directorio privado
del servidor; el repositorio no contiene textos ni credenciales de esos recibos.

Siguen pendientes la reasignación de 117/118, el registro contable del contrato
208 y las vistas previas nuevas de eliminación de 15/16. No se crearon ni emitieron
cuentas de cobro y no se ejecutó una liquidación durante esta reparación.
