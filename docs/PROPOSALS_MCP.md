# MCP de Propuestas

El conector `proposals` administra las opciones del módulo de Propuestas. El
conector agregado `commercial` reutiliza el mismo registro y las mismas reglas.
Los contratos y correos no tienen una copia independiente de su lógica de negocio.

## Cobertura del panel

| Capacidad | Herramientas principales |
|---|---|
| Lista, detalle, creación y duplicación | `list_proposals`, `get_proposal`, `create_proposal`, `duplicate_proposal` |
| Importación y exportación JSON | `get_proposal_template`, `export_proposal_json`, `update_proposal`, `update_proposal_from_json` |
| Ajustes parciales de propuesta | `update_proposal_settings` |
| Secciones y sincronización | `create_proposal_section`, `update_proposal_section`, `delete_proposal_section`, `reorder_proposal_sections`, `preview_proposal_section_sync`, `apply_proposal_section_sync` |
| Defaults por idioma | `get_proposal_defaults`, `update_proposal_defaults`, `reset_proposal_defaults` |
| Contratos y modalidad de cierre | `update_proposal_contract`, `update_proposal_contract_modality`, `save_proposal_contract_negotiation` |
| Datos contractuales y opciones del servicio | `get_proposal_company_settings`, `update_proposal_service_settings`, `get_proposal_contract_template` |
| Lectura de contratos | `read_proposal_contract_markdown`, `render_proposal_contract_pdf`, `render_proposal_draft_contract_pdf` |
| Adjuntos | `list_proposal_documents`, `upload_proposal_document`, `read_proposal_document_markdown`, `download_proposal_document`, `delete_proposal_document` |
| Correos y plantillas | `preview_proposal_email`, `send_proposal`, `resend_proposal`, `send_multi_proposal`, `send_proposal_documents`, `send_proposal_discount_offer`, `send_branded_email`, `send_custom_proposal_email`, defaults/historial y herramientas de templates |
| Adjuntos Markdown de correo | `render_proposal_email_markdown_pdf` |
| Formalización | `get_proposal_formalization_options`, `render_proposal_formalization_pdf`, `read_proposal_formalization_markdown`, `prepare_proposal_formalization`, `get_proposal_formalization`, `download_proposal_formalization_file`, `send_proposal_formalization` |
| Seguimiento comercial | `get_proposal_scorecard`, `get_proposal_analytics`, `export_proposal_analytics_csv`, `get_proposal_dashboard`, alertas y `log_proposal_activity` |
| Estado y ejecución | `update_proposal_status`, `toggle_proposal_active`, `bulk_action_proposals`, `update_proposal_stage`, `complete_proposal_stage` |
| Revisión y vinculación explícita | `get_proposal_approval`, `review_proposal_approval`, `launch_proposal_to_platform`, `download_proposal_approval_file` |
| Videos | Consulta, sustitución, retiro y restauración del video genérico; consulta, sustitución y retiro del personalizado; visibilidad global y por propuesta |

`tools/list` y `describe_capabilities` publican los campos y el riesgo de cada
herramienta, filtrados por el alcance de la credencial. Los argumentos existentes
siguen funcionando; los adaptadores aceptan campos planos o un objeto `data`.
No repetir el mismo campo en ambas formas. El lanzamiento requiere ahora una
revisión explícita; no admite el antiguo reinicio con `force`. Las lecturas aceptan parámetros planos
o `query`. `update_proposal` conserva su contrato de importación JSON completo;
para un ajuste aislado usar `update_proposal_settings`.

Los campos calculados, las respuestas privadas del cliente y los timestamps de
automatización no admiten escritura directa. Los datos de empresa y la plantilla
contractual son de consulta; las opciones de duración y preavisos del servicio
son editables, igual que en el panel. No se amplían los permisos de credenciales
con una lista restringida de herramientas.

## Revisar la aprobación y vincular el proyecto

Aceptar sólo registra el estado comercial, sin crear clientes o proyectos.
Consultar `get_proposal_approval` y revisar el cliente, proyecto, condiciones,
documentos disponibles y `source_hash` antes de confirmar.

`review_proposal_approval` admite `confirm`, `defer` y `retry`.
Para confirmar, indicar el cliente/proyecto existente o sus datos de creación,
`request_id`, `source_hash` y la selección de documentos. El switch
`use_proposal_contracts` activo usa los contratos vigentes de la modalidad;
desactivado requiere uno o más `custom_asset_ids` completados y sus
`custom_documents` (título y tipo), en el mismo orden. Los detalles comercial
y técnico se incluyen siempre; otros documentos se eligen explícitamente.

La operación es sensible: revisar el impacto y confirmar mediante
`confirm_action`. Assets, hashes, tamaño, origen, vencimiento y pertenencia
a la credencial se revalidan al aplicar. Posponer no crea recursos; reintentar
envía sólo `action: retry` y conserva el vínculo y paquete confirmado.
`launch_proposal_to_platform` comparte esta revisión, con
`accept_proposal: false` para vincular una propuesta en negociación o aceptada.
No existe relanzamiento destructivo. Las copias privadas se descargan con
`download_proposal_approval_file`, mediante assets de la credencial autorizada.

Contrato completo: [Aprobación y vinculación](PROPOSAL_APPROVAL.md).

## Guardar un contrato personalizado

Consultar primero `get_proposal` para conocer `contract_modality` y
`contract_params`. En modalidad `split`, indicar `product` o `service` tanto al
editar como al leer o descargar; `combined` corresponde a la modalidad `single`.

Ejemplo de argumentos de `update_proposal_contract` (con los datos comunes
obligatorios del contrato ya guardados; si faltan, incluirlos en `contract_params`):

```json
{
  "proposal_id": 123,
  "variant": "product",
  "contract_params": {
    "product_contract_source": "custom",
    "product_custom_contract_markdown": "# Contrato de producto\n\nTexto acordado."
  }
}
```

| Variante | Origen (`default` / `custom`) | Markdown |
|---|---|---|
| `combined` | `contract_source` | `custom_contract_markdown` |
| `product` | `product_contract_source` | `product_custom_contract_markdown` |
| `service` | `service_contract_source` | `service_custom_contract_markdown` |

La edición conserva los campos omitidos y regenera los documentos de la modalidad
activa. Para volver a la plantilla, cambiar sólo el origen a `default`, completando
los datos requeridos por el panel. El contrato de servicio predeterminado requiere
sus tres términos; admite enteros de 1 a 999 y conserva los textos históricos.
`read_proposal_contract_markdown` devuelve el texto del documento generado;
`get_proposal` devuelve los parámetros guardados.

Los defaults de propuesta usan `language` al guardar y `lang` al consultar.
Enviar `base_updated_at` con el valor leído antes de reemplazar `sections_json`
permite detectar una edición concurrente y recibir un conflicto.

## Preparar, revisar y confirmar Formalización

1. Consultar `get_proposal_formalization_options` con `proposal_id`.
2. Llamar a `prepare_proposal_formalization` con la selección de documentos,
   asunto, destinatarios y contenido del correo. No envía nada.
3. Revisar `html_preview`, `text_preview`, destinatarios y la lista de archivos.
   Cada archivo incluye `file_id`, nombre, tamaño y SHA-256; descargarlo con
   `download_proposal_formalization_file` si hace falta revisarlo.
4. Solicitar `send_proposal_formalization` con `proposal_id` y `preparation_id`.
   La respuesta contiene el impacto exacto y `confirmation_id`.
5. Tras la confirmación del operador, ejecutar `confirm_action` con ese ID.

Las preparaciones duran 24 horas y pertenecen a la credencial que las creó,
incluso cuando varias credenciales comparten usuario técnico. Las creadas desde
el panel conservan su privacidad y no se exponen por MCP. Los archivos se entregan
mediante assets temporales, nunca mediante rutas del almacén privado.

Un cambio en los datos de origen o un adjunto alterado impide el envío. Una
confirmación repetida devuelve el resultado anterior sin reenviar. Antes de llamar
al proveedor de correo se persiste un comprobante consumido: si falla el guardado
posterior, el reintento conserva ese comprobante y exige consultar el paquete.
`failed` y
`unknown` son resultados persistidos: revisar el historial antes de preparar otro
paquete; no reintentar automáticamente una entrega incierta.

Los correos de propuesta y de marca admiten `attachment_asset_ids`: archivos
completados con el flujo de carga MCP, junto a `doc_refs` para documentos existentes.
Se conserva `recipient_email` para clientes antiguos; las integraciones nuevas
usan `recipient_emails` y `cc_emails`. Los campos anidados se convierten a JSON
cuando se construye el multipart del panel.

## Despliegue y compatibilidad

La migración `0272_proposal_formalization_mcp_owner` añade la relación opcional
con la credencial y actualiza la descripción de Propuestas. No cambia propietarios
ni credenciales existentes. El despliegue aplica la migración antes de activar
el código nuevo; no se aplica desde un worktree.

Las operaciones sensibles del conector Propuestas pasan por confirmación,
incluidos envíos, borrados, cambios de estado con efectos y creación de enlaces
que notifican por correo. Los clientes deben manejar `confirmation_required`.

## Plantillas contractuales predeterminadas

El conector ofrece lectura por variante, preview, actualización confirmada, historial, restauración y coherencia bloqueante. `describe_capabilities` publica sus argumentos y riesgos. El MCP documental lista los tres espejos de lectura. Contratos nuevos o regenerados usan la plantilla vigente; los guardados permanecen intactos. Contrato completo y primer uso: [CONTRACT_TEMPLATE_MCP.md](CONTRACT_TEMPLATE_MCP.md).
