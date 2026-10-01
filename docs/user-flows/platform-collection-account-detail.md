### FLOW: `platform-collection-account-detail`

- **Módulo:** platform
- **Prioridad:** P1
- **Descripción:** Consulta snapshot, importes, líneas, instrucciones de pago y contexto explícito de una cuenta permitida; descarga el PDF emitido y recupera errores del documento o archivo sin modificarlo.
- **Resultados:** display, success, error.
- **Permisos:** cliente aislado por servidor y administrador Platform en lectura; sesión de superusuario y CSRF para asociación/conciliación Panel. MCP administrativo reutiliza las mismas validaciones.
- **Invariantes:** no deducir contrato por proyecto o PDF; no confirmar pagos, duplicar ciclos ni reemplazar el PDF emitido al cambiar una asociación.
- **Validación:** pruebas dedicadas de API y UI; la ejecución se declara en el PR, no por registrar tags.
