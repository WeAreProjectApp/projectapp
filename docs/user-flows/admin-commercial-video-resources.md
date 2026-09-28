### FLOW: `admin-commercial-video-resources`

- **Módulo:** admin / comercial
- **Rol:** admin
- **Prioridad:** P1
- **Rutas:** Alianza → Configuración; Módulos adicionales → Recursos; Propuestas → Configuraciones; editor de propuesta → Recursos.
- **Interacción:** consultar el archivo vigente, elegir idioma ES/EN para genéricos, cargar/sustituir un MP4, quitar con confirmación o restaurar el predeterminado. Progreso y errores junto al archivo. Personalizados sin predeterminado.
- **Outcomes:** display (recurso o ausencia al entrar por UI), success (carga/sustitución/baja/restauración), error (archivo ausente, inválido o mayor de 250 MiB), failure (consulta/carga fallida, cancelación o revisión desactualizada con consulta posterior).
- **Evidencia:** `components/resources/VideoResourceManager.vue` y sus cuatro páginas huésped; `views/video_resources.py` y `services/video_resource_service.py`.
- **E2E Spec:** `e2e/admin/admin-video-resources.spec.js`.
