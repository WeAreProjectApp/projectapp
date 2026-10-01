### FLOW: `platform-collection-accounts-list`

- **Módulo:** platform
- **Prioridad:** P1
- **Descripción:** Consulta cuentas emitidas del cliente con agrupación y filtros explícitos por proyecto, naturaleza, contrato, otrosí y estado; navega al detalle y ofrece vacío y reintento de lectura.
- **Resultados:** display, success, error.
- **Permisos:** cliente aislado por servidor y administrador Platform en lectura; sesión de superusuario y CSRF para asociación/conciliación Panel. MCP administrativo reutiliza las mismas validaciones.
- **Invariantes:** no deducir contrato por proyecto o PDF; no confirmar pagos, duplicar ciclos ni reemplazar el PDF emitido al cambiar una asociación.
- **Validación:** pruebas dedicadas de API y UI; la ejecución se declara en el PR, no por registrar tags.
