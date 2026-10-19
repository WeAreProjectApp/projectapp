# Confirmación al copiar — revisión del panel (2026-10-19)

## Corrección entregada

En Enlaces seguros, «Enlace para clientes» conserva su texto. Tras copiar la
URL pública devuelta por el servidor, el icono pasa a check y aparece «Copiado»
en un tooltip flotante durante 2 segundos. Una región viva anuncia el resultado
sin cambiar el nombre del botón. El fallo conserva el icono de copiar, muestra
el error durante 3 segundos y permite reintentar. Los mensajes afectados están
traducidos a ES/EN. Se reutilizan los primitives existentes; no cambia su API.
El grupo de acciones reserva su ancho natural para mantener ambos botones en
la misma fila también en tableta vertical, sin asignar un ancho fijo al botón.

Validación local: 12 escenarios Playwright aprobados en lotes focales y 5
pruebas existentes del portapapeles en verde. Las mediciones comparan posición
y dimensiones de los dos botones, descripción, encabezado, pestañas y primera
fila antes de copiar, durante la confirmación y al terminar, con tolerancia de
1 px y sin desbordamiento horizontal. Incluyen fallo, reintento, copia pendiente,
activaciones consecutivas, teclado, inglés y movimiento reducido. El quality
gate focal obtiene 100/100, sin errores ni advertencias; los registros de vistas
y flujos conservan su estructura y están sincronizados.

## Otros controles con texto variable

Revisión estática de las páginas del panel y sus componentes alcanzables.
Son candidatos a una corrección posterior, no defectos geométricos confirmados:
no se midió su disposición en navegador y no se modificaron. Tanto crecer como
encogerse puede mover controles vecinos en un contenedor flexible.

| Superficie | Control / cambio de texto | Ubicación |
|---|---|---|
| Enlaces seguros · enlace creado | «Copiar mensaje sugerido» → «Mensaje copiado»; «Copiar enlace» → «Enlace copiado» | `frontend/pages/panel/secure-links/index.vue`, footer del modal de creación |
| Enlaces seguros · detalle | «Copiar enlace» → «Enlace copiado» o error | `frontend/components/secureLinks/SecureLinkDetailModal.vue` |
| Diagnósticos · listado | «Copiar enlace» → «¡Enlace copiado!» dentro de una acción de ancho completo; revisar sólo posible altura | `frontend/pages/panel/diagnostics/index.vue` |
| Diagnósticos · edición | JSON: «Copiar» → «¡Copiado!» | `frontend/pages/panel/diagnostics/[id]/edit.vue` |
| Diagnósticos · prompts | «Copiar» → «¡Copiado!» en el editor compartido | `frontend/components/WebAppDiagnostic/admin/PromptEditor.vue` |
| Diagnósticos · documentos | «Copiar contenido» → «¡Copiado!» | `frontend/components/WebAppDiagnostic/DiagnosticDocumentsTab.vue` |
| Adjuntos de comunicaciones de diagnósticos | «Copiar {nombre}» → «¡Copiado!» | `frontend/components/MarkdownAttachmentModal.vue` |
| Documentos · edición | «Copiar Markdown» o «Copiar» → «Copiado» | `frontend/pages/panel/documents/[id]/edit.vue` |
| Propuestas · listado | «Copiar enlace» → «¡Enlace copiado!» en el modal de acciones; revisar posible altura | `frontend/pages/panel/proposals/index.vue` |
| Propuestas · creación | Plantilla, prompt comercial y prompt técnico: «Copiar» → «¡Copiado!» | `frontend/pages/panel/proposals/create.vue` |
| Propuestas · edición | Prompts, checklist y JSON: «Copiar» → «¡Copiado!» | `frontend/components/panel/proposal/ProposalPromptTab.vue`, `DevChecklistTab.vue`, `ProposalJsonTab.vue` |
| Defaults de propuestas | Prompts y JSON: «Copiar» → «¡Copiado!» | `frontend/components/panel/defaults/ProposalDefaultsPanel.vue` |
| Módulos adicionales · compartir selección | Texto traducido de copiar → copiado | `frontend/components/AdditionalModules/CatalogSelectionModal.vue` |
| MCPs · credencial recién creada | «Copiar URL» → «Copiada» | `frontend/pages/panel/mcps/index.vue` |

Los controles que usan `BaseActionButton` con `statusLabel` (por ejemplo,
accesos de proyectos, QR, Linktrees y campos del contenido seguro) ya presentan
el estado fuera del flujo: el cambio de su nombre accesible no ensancha el
botón. Los componentes públicos y de Platform quedan fuera del alcance de
esta revisión del panel.

## Criterio para la revisión futura

Conservar el texto de la acción y confirmar mediante icono y mensaje flotante
cuando un resultado transitorio pueda alterar el layout. Antes de modificar
otro control, medir posición y dimensiones de sus vecinos durante éxito y
error, incluyendo los cinco perfiles del panel. Esta tarea sólo corrige el
encabezado acordado; no extiende PA-119 a otros controles.
