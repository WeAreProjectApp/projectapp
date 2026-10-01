### FLOW: `platform-hosting-project-list`

- **Módulo:** platform
- **Prioridad:** P2
- **Descripción:** Lista los proyectos con hosting en /platform/payments y abre cada proyecto mediante una fila real; ofrece vacío y reintento de lectura.
- **Resultados:** display, success, error.
- **Permisos:** cliente aislado por servidor y administrador Platform en lectura; sesión de superusuario y CSRF para asociación/conciliación Panel. MCP administrativo reutiliza las mismas validaciones.
- **Invariantes:** no deducir contrato por proyecto o PDF; no confirmar pagos, duplicar ciclos ni reemplazar el PDF emitido al cambiar una asociación.
- **Validación:** pruebas dedicadas de API y UI; la ejecución se declara en el PR, no por registrar tags.
