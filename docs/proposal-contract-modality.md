# Cambio de modalidad contractual

El panel permite cambiar contrato único por producto y servicio, o volver al
contrato único, en cualquier estado comercial. El estado de la propuesta no
cambia. Sólo usuarios administrativos y credenciales MCP autorizadas pueden
hacerlo; cada cambio queda atribuido al usuario o actor del conector.

Fuera de negociación, **Documentos** abre una revisión con nota obligatoria.
La vista previa identifica contratos que se crean, trasladan y archivan,
fuentes personalizadas o de plantilla, parámetros del servicio y documentos
históricos vinculados. **Cancelar** conserva el estado actual. La confirmación
vence a los diez minutos y rechaza cambios posteriores a la vista previa.

## Contenido y documentos anteriores

- Un contrato único personalizado pasa literalmente al contrato de producto,
  incluido su PDF. Un producto personalizado vuelve literalmente al único.
- Si el origen usa plantilla, el destino usa la plantilla vigente de su variante.
- El servicio usa su plantilla y los parámetros actuales. Se exigen el plazo
  inicial y los preavisos de renovación y terminación guardados en la propuesta
  o enviados en la llamada; no se completan con valores globales.
- Un servicio personalizado existente conserva su Markdown y PDF. Un destino
  personalizado diferente exige resolver el conflicto expresamente; su copia
  anterior queda en la instantánea.
- Los documentos y firmas enviados o aprobados se conservan. El resultado
  relaciona documentos históricos identificables con las variantes activas.
  Cambiar modalidad no envía documentos ni inicia nuevas firmas.

## MCP

`update_proposal_contract_modality` acepta `proposal_id`, `contract_modality`,
`change_note` y, opcionalmente, `contract_params` con estas tres claves:
`service_initial_term`, `service_renewal_notice_days`,
`service_termination_notice_days`. Los valores numéricos se convierten a su
representación contractual habitual; también se admite redacción personalizada.
La nota es opcional durante negociación y obligatoria en los demás estados.
El schema publicado exige `proposal_id` y `contract_modality` como campos planos.
El formato anterior de argumentos anidados en `data` está obsoleto, pero se
sigue aceptando y se registra como `deprecated_envelope`.

Una respuesta con `confirmation_required` contiene `confirmation_id` e
`impact`. Después de revisar, usar `confirm_action` o `cancel_action` con ese
identificador y la misma credencial. La confirmación devuelve el resultado final
en `result.contract_change`: modalidad, instantánea, documentos activos y
fuente de cada variante. Repetir una confirmación aplicada devuelve su resultado
sin duplicar documentos o instantáneas.

Para un conflicto deliberadamente revisado, repetir la preparación con
`conflict_resolution: "use_origin"`; la confirmación conserva primero el
personalizado anterior del destino.

## Instantáneas y restauración

Las instantáneas se conservan permanentemente, con Markdown, parámetros y
copias PDF inmutables. Se consultan y descargan desde **Seguimiento → Historial
→ Instantáneas de contratos**. **Restaurar** requiere nota y una nueva revisión;
antes de recuperar el contenido guarda otra instantánea del estado actual.

Por MCP: `list_proposal_contract_snapshots` pagina de veinte en veinte mediante
`offset`; `read_proposal_contract_snapshot` lee una copia mediante `proposal_id`
y `snapshot_id`; `restore_proposal_contract_snapshot` requiere ambos
identificadores y `change_note`, seguido de la confirmación habitual.

## Aceptación pendiente con la propuesta 118

Ejecutar después de integrar y desplegar esta rama, con los tres plazos de
servicio acordados. Esta implementación no modifica la propuesta real.

1. Guardar el Markdown y PDF actuales del contrato único de Littigio Fase 2,
   y verificar que corresponden al contrato firmado el 30 de septiembre de 2026.
2. Preparar `update_proposal_contract_modality` con `proposal_id: 118`,
   `contract_modality: "split"`, nota y los tres parámetros del servicio.
3. Revisar el traslado personalizado, la creación del servicio y las referencias
   a documentos históricos; confirmar con la misma credencial.
4. Leer la variante de producto y comparar el Markdown y los bytes del PDF
   exactamente con los guardados en el paso 1, sin normalizar espacios.
5. Leer la variante de servicio y comprobar la plantilla vigente y los plazos
   enviados. Verificar modalidad split, fuentes custom/default y estado accepted.
6. Leer la instantánea y el historial; verificar actor, fecha, nota y contenido
   anterior. Comprobar que otras propuestas y las plantillas conservan su estado,
   y ejecutar la verificación de consistencia de plantillas sin hallazgos.
