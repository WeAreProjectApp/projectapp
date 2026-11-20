### FLOW: `admin-financing-agreement-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/partnership-program?tab=agreements`, `/panel/partnership-program/new`, `/panel/partnership-program/:id`
- **Interaction:** Crear un borrador de otrosí desde el registro administrativo.

| Outcome | Inicio → acción → resultado observable |
|---|---|
| `display` | Abrir **Financiación → Otrosíes** → ver métricas y registros vigentes o el estado vacío. Usar búsqueda y los desplegables Estado, Modalidad y Alcance. Pulsar **Filtrar** para aplicar la selección. |
| `success` | Pulsar **Nuevo otrosí** → seleccionar un cliente → verificar su identidad precargada → completar contrato, alcance, monto elegible y abono inicial → crear → abrir el borrador con el calendario de cuotas definido por la política vigente. |
| `error` | Enviar datos incompletos o inválidos → el API y el formulario señalan los campos → los datos ya escritos permanecen disponibles. |
| `failure` | Fallar la carga del registro → mostrar un estado de error explícito sin presentar una lista vacía engañosa. |

- **Reglas:** el cliente debe estar activo; propuesta y proyecto opcionales deben pertenecerle; el valor equivalente debe quedar dentro del rango inclusivo vigente; el abono debe respetar el mínimo derivado del análisis de riesgo; las cuotas deben sumar exactamente el saldo y usar la cantidad y ventana de vencimiento de la revisión congelada.
- **Coverage:** ✅ Covered
- **Modalidad:** seleccionar cinco años muestra el compromiso de exclusividad conceptual de Project App. y pide delimitar sector, nicho, producto y conceptos en el alcance. Tres años excluye ese compromiso adicional. Los borradores resuelven el texto según la selección; los documentos preparados conservan su snapshot.
- **E2E Spec:** `e2e/admin/admin-financing-agreements.spec.js`
- **Backend Tests:** `content/tests/views/test_financing_agreements.py`, `content/tests/services/test_financing_agreement_service.py`
