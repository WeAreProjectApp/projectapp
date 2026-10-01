### FLOW: `platform-project-hosting-context`

- **Módulo:** platform
- **Prioridad:** P1
- **Descripción:** Consulta el único contexto de hosting del proyecto, fuentes contables, suscripción, pagos, ciclos y grupos de evidencia. Identifica fuentes pendientes sin sumarlas ni crear cobros; navega a cuentas de hosting y permite reintentar la lectura.
- **Resultados:** display, success, error.
- **Permisos:** cliente aislado por servidor y administrador Platform en lectura; sesión de superusuario y CSRF para asociación/conciliación Panel. MCP administrativo reutiliza las mismas validaciones.
- **Invariantes:** no deducir contrato por proyecto o PDF; no confirmar pagos, duplicar ciclos ni reemplazar el PDF emitido al cambiar una asociación.
- **Validación:** pruebas dedicadas de API y UI; la ejecución se declara en el PR, no por registrar tags.
