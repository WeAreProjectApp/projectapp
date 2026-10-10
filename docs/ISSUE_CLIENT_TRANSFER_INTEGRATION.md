# Integridad de tickets al cambiar el cliente

Interfaz publicada por P1:

```python
from accounts.services.issue_client_transfer import assert_issue_client_transfer_safe

assert_issue_client_transfer_safe(project, new_client)
```

`project` es una instancia de Project y `new_client` es el User de destino,
no su UserProfile; también admite None. El helper devuelve None cuando permite
la operación. Relee `Project.client_id` persistido: una instancia modificada
por ModelForm no puede hacer pasar una transferencia por un cambio al mismo dueño.

Cualquier BugReport o ChangeRequest del proyecto bloquea el cambio, incluyendo
bugs generales sin guía, reportes de staff, solicitudes legadas y archivos.
El mismo dueño y los proyectos sin tickets se permiten. La autoría del reporte
y el email no determinan el dueño. No modifica ni borra registros históricos.

El rechazo es `accounts.services.delivery_access.DeliveryConflict`, HTTP 409,
con `detail['code'] == 'issue_client_transfer_history'` y mensaje en español.
P2 puede convertirlo en error del formulario y repetir el guard bajo lock antes
del save; el formulario ProjectAdmin y su recheck pertenecen a P2.

## Evaluación compartida y vista previa (2026-10-09)

`accounts/services/project_client_transfer.py` concentra la evaluación en
`client_transfer_blockers(project, new_client, *, lock=False)`. Relee el dueño
persistido y enumera, en orden, historia financiera, entregas y tickets. Los
guards de `billing_reassignment.py`, `delivery_client_transfer.py` e
`issue_client_transfer.py` lo llaman con `lock=True`; conservan sus firmas,
excepciones, estados HTTP y mensajes, y añaden `blockers` y `blocker_counts` al
detalle del rechazo. El guard de tickets sigue usando `DeliveryConflict` y 409.

Cada blocker identifica `code`, `message`, `resource_type`, `resource_id` y
`resolution: create_new_project`. Los conteos son exactos; las listas de
entregas y tickets se limitan a 100 filas por tipo de recurso. La huella incluye
también los IDs que no caben en esas listas.

La historia financiera incluye cualquier `HostingSubscription`, `ProjectHosting`
o `HostingRecord`, sin filtrar por estado, y cuentas fuera de borrador o con
`CollectionAccountContext`. Cancelar una suscripción o anular sus cobros no
elimina este bloqueo. Las entregas incluyen publicaciones, fuentes congeladas,
firmas y mensajes públicos; los tickets incluyen todos los bugs y solicitudes,
también archivados.

`content.services.project_service.change_client_preview` y la herramienta
`preview_project_client_change` devuelven:

| Campo | Significado |
| --- | --- |
| `can_apply`, `blockers`, `blocker_counts` | Permiso efectivo y motivos de los mismos guards que ejecuta el cambio. |
| `planned.move`, `planned.detach` | Efectos de cada modo: conteos y IDs de registros movidos, desvinculados o conservados. |
| `financial_history` | Suscripciones con pagos y sus estados/vencimientos, hosting y cuentas con sus contextos. |
| `impact_hash` | Huella del dueño actual, destino, conjuntos ligados completos, historia financiera, bloqueos y planes de ambos modos. No depende del modo elegido. |

El MCP recibe argumentos planos: preview con `project_id` y `client_profile_id`;
cambio con esos IDs, `mode: move|detach` y `expected_impact_hash`. `move` aplica
la cascada prevista al nuevo cliente; `detach` conserva el cliente de los
registros que desvincula. Ambos modos desprenden las conversaciones históricas
antes de guardar el nuevo dueño, conservando su cliente original. Los detalles
de cada excepción a la cascada están en `planned`.

Un hash obsoleto al preparar la acción devuelve `STALE_VERSION`. Con hash
vigente y bloqueos, el MCP rechaza el intento con `PROJECT_CLIENT_CHANGE_BLOCKED`,
`details.can_apply: false`, `details.blockers` y `details.blocker_counts`, sin
crear una confirmación. Si el bloqueo aparece durante la confirmación o la
ejecución, añade `details.guard_code` con el error del guard original:
`VALIDATION_ERROR` para finanzas, `DELIVERY_CLIENT_HISTORY_FROZEN` para entregas
o `ISSUE_CLIENT_TRANSFER_HISTORY` para tickets. La resolución está en cada
elemento de `details.blockers`; no se ejecuta una cascada parcial.

El endpoint del Panel acepta el hash y lo recalcula bajo lock del proyecto;
conserva la compatibilidad con las listas de IDs anteriores y responde 409
`records_changed` si cambió el impacto. Proyecto terminal, mismo cliente y
cliente inexistente siguen siendo errores 400. El modal muestra los motivos de
un preview bloqueado, orienta a crear un proyecto nuevo, oculta Mover/Desvincular
y deshabilita Confirmar sin enviar POST. El camino permitido exige elegir modo
y envía `expected_impact_hash` junto con las listas anteriores.

## Integración y evidencia

El puente de P1 en `content.services.project_service.change_client_apply` toma
`Project.select_for_update()`, llama al guard publicado de entregas de P3 y
comprueba después el guard de tickets antes de toda escritura. La dependencia
P3 `cecb5b93d8cfd0b968fec3a71239323c48c7018f` (incluye el provider `30fd7ab9`
y el aislamiento `edfff19c`) está absorbida mediante merge exacto, sin copiar código mutable.
P0 coordina los bloques publicados en este orden:

`lock → financiero P2 → delivery P3 → issues P1 → access-revoke P4 → save`.

El lock debe mantenerse en la misma transacción hasta save. La creación y demás
operaciones de tickets toman el mismo lock de proyecto. Los guards financiero,
delivery y la revocación se integran en sus respectivas reservas.

Verificación focal: siete casos del dominio y diez casos del servicio de proyecto
pasaron también tras componer P3, con settings_test, SQLite y migraciones de test. El rechazo por
el servicio real conserva dueño, reportes, PDF, notas de acceso, comunicación y
auditoría; el cliente anterior mantiene lectura y el destino recibe 403/404.
Los grants futuros de P4 se verifican al integrar ese bloque publicado.

La cobertura del incremento está en
`content/tests/services/test_project_client_transfer_blockers.py`,
`content/tests/views/test_mcp_project_client_change.py` y
`content/tests/views/test_panel_projects_change_client.py`. El modal y su
transporte se cubren en `frontend/test/components/ProjectChangeClientModal.test.js`
y `frontend/e2e/admin/admin-project-change-client.spec.js` (display, success y
error), con APIs simuladas. Guion focal:
[Migración de carpetas por MCP — parte 1](MCP_VALIDATION_RUNBOOK.md#migración-de-carpetas-por-mcp--parte-1-2026-10).

## `rebase_with_history` diferido

Este modo no está disponible. El bloqueo orienta a `create_new_project` porque:

1. La suscripción conserva la tarjeta guardada del cliente anterior; el próximo
   débito cargaría esa tarjeta aunque cambie el propietario del proyecto.
2. El acceso a Platform sigue `project.client`: el cliente anterior perdería la
   consulta de su historia de pagos y el nuevo la recibiría.
3. No existe una marca de proyecto interno que permita acotar ese cambio de
   propiedad sin exponer historia de clientes.

Resolver esas tres condiciones requiere un diseño posterior; elegir `move` o
`detach` no permite saltar los guards actuales.
