# Respuestas contractuales a tickets

El núcleo de entregas conserva fuentes y verifica citas para etapas y tickets.
El dominio de bugs/cambios mantiene sus modelos, permisos, respuestas,
notificaciones y estados. Preparar o previsualizar una respuesta no publica,
envía, convierte un bug en cambio ni modifica guías o aprobaciones.

## Interfaz publicada

Módulo: `accounts.services.delivery_contract_reply`.

```python
create_contract_reply_context(project_id, actor, data, *, target_provider)
preview_contract_reply(project_id, actor, payload, *, expected_version,
                       expected_ticket_version, target_provider)
validate_contract_reply_for_publish(project_id, actor, data, *, target_provider)
```

El proveedor es un callable del dominio de tickets:

```python
target_provider(project=project, actor=actor,
                destination={"kind": "bug", "id": 42}, lock=False)
```

Devuelve un diccionario desde registros reales del servidor, nunca desde el
snapshot enviado por un cliente. Con `lock=True` bloquea el ticket después del
proyecto; devuelve su propietario y versión actuales. Las claves obligatorias
son `kind` (`bug` o `change`), `id`, `project_id`, `project_client_id`,
`ticket_version`, `is_archived` (booleano), `origin` (dict) y `conversation`
(dict/list). `ticket` es un dict opcional con los campos del reporte. El origen
es la copia original guardada al reportar, con `origin_kind` y, si corresponde,
`contract_id` y `amendment_id`; no se reconstruye desde una guía editable.

La conversación contiene únicamente eventos públicos relevantes, con autores,
fechas y versiones. El proveedor conserva el orden y la identidad de adjuntos
originales; las notas internas no se incluyen. El motor copia y calcula hashes
del origen y la conversación, conservándolos en el contexto inmutable.

## Preparación

```json
{
  "mode": "reply",
  "request_id": "preparar-ticket-42",
  "expected_version": 9,
  "expected_ticket_version": 4,
  "destination": {"kind": "bug", "id": 42},
  "contract_id": 18,
  "amendment_ids": [6],
  "sources": [],
  "missing_sources": [],
  "uncertainties": [],
  "instructions": "Responder en lenguaje sencillo."
}
```

`expected_version` es la versión del workspace de entregas;
`expected_ticket_version` es independiente. No se admite seleccionar otra etapa
o alcance: el origen permanece congelado. Un ticket que provenga de una guía
publicada conserva su contrato y su otrosí; uno general permite seleccionar
explícitamente un contrato del proyecto. `contract_id: null` captura el reporte
y conserva la clasificación indeterminada; no impide reportar un bug general.

La salida usa el contexto, plantilla, esquema JSON v2, fuentes y descargas
privadas del motor existente. Los contextos de tickets no aparecen en el
historial de preparación de etapas. No se realiza una llamada a un modelo IA.

## Preview y publicación

El payload de preview es el mismo JSON v2 de respuestas a etapas:
`schema_version`, `context_id`, `response_text`, `classifications`.
Cada clasificación contiene `request`, `classification`, `rationale` y
`citations` verificadas (`source_key`, `locator`, `quote`). El preview revalida
actor, cliente del proyecto, versión del workspace, versión del ticket y hashes
de origen/conversación, sin escrituras.

Si falta contrato, texto legible o evidencia completa, la clasificación es
`indeterminate`. `inside_scope` y `outside_scope` requieren fuentes completas y
una cita real del contrato u otrosí. Una guía, declaración del cliente o anexo
asociado administrativamente no sustituye esa cláusula. Verificar la cita prueba
su existencia; el equipo revisa la interpretación.

Antes de insertar `IssueResponse`, el wrapper de P1 llama a
`validate_contract_reply_for_publish` **dentro de su mutación bloqueada
proyecto → ticket**. Pasa:

```python
{
    "context_id": context_id,
    "message": texto_final,
    "classifications": clasificaciones,
    "source_references": citas_verificadas,
    "human_reviewed": True,
    "expected_version": version_workspace,
    "expected_ticket_version": version_ticket,
    "destination": {"kind": "bug", "id": ticket_id},
}
```

La salida separa procedencia privada (`context`, `context_id`,
`source_references`, `classifications`) de `review_evidence`, el DTO seguro para
el cliente. P1 **no serializa el contexto ni las citas privadas** en su JSON
público. `scope_result` traduce `inside_scope` a `within_scope`; clasificaciones
mixtas tienen agregado `indeterminate`. P1 guarda la respuesta mediante su
flujo normal; el núcleo no la inserta ni cambia estados.

## Guarda de transferencia del proyecto

`accounts.services.delivery_client_transfer.assert_delivery_client_transfer_safe(
project, new_client, *, actor=None)` relee y bloquea el proyecto. Permite el mismo
cliente y proyectos sin historia pública/fuentes congeladas; rechaza un cambio
que expondría publicaciones, firmas, contextos o mensajes públicos anteriores.
No modifica registros, accesos ni auditoría. Con actor explícito exige un
administrador activo. Devuelve el proyecto bloqueado actual.

Orden conjunto al cambiar cliente:
`lock Project → finance P2 → delivery P3 → tickets P1 → revoke P4 → save/cascada`.
El puente de servicio pertenece a P3; P2 integra la misma guarda en su recheck de
Django Admin. Los otros guardas no se sustituyen.

El esquema nuevo está en `accounts/0071_delivery_followup`, con padre `0067` y
dependencias content ya publicadas. La misma migración declara las preparaciones
de correo del siguiente incremento; no altera migraciones previas. Sólo el
despliegue aplica migraciones.
