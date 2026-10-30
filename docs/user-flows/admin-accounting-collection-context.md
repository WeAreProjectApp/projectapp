### FLOW: `admin-accounting-collection-context`

- **Módulo:** admin
- **Prioridad:** P1
- **Descripción:** Asocia una cuenta de proyecto a contrato y otrosí opcional del mismo contrato, o al único hosting, con razón, control de versión y validación de coherencia; conserva snapshot, PDF, importes y pagos.
- **Resultados:** display, success, error, failure.
- **Permisos:** cliente aislado por servidor y administrador Platform en lectura; sesión de superusuario y CSRF para asociación/conciliación Panel. MCP administrativo reutiliza las mismas validaciones.
- **Invariantes:** no deducir contrato por proyecto o PDF; no confirmar pagos, duplicar ciclos ni reemplazar el PDF emitido al cambiar una asociación.
- **Validación:** pruebas dedicadas de API y UI; la ejecución se declara en el PR, no por registrar tags.

## Documento vinculado pendiente

Una cuenta explícitamente pendiente se completa con tipo, vínculo válido, motivo y versión. Retira el ícono del listado/detalle, filtro y radar sin borrar autor/fecha originales, ni modificar PDF, importes o pagos. Los conflictos conservan la marca. La protección de respuestas tardías del enlace se compone con la sesión de búsqueda de contratos.
