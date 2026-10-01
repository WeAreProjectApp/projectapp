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

El puente de P1 en `content.services.project_service.change_client_apply` toma
`Project.select_for_update()`, llama al guard publicado de entregas de P3 y
comprueba después el guard de tickets antes de toda escritura. La dependencia
P3 `30fd7ab9` está absorbida, sin copiar código mutable.
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
