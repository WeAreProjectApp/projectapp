### FLOW: `admin-accounting-project-hosting-reconciliation`

- **Módulo:** admin
- **Prioridad:** P1
- **Descripción:** Inventaría y asocia explícitamente suscripción y orígenes contables al único hosting del proyecto, elige origen operativo y concilia referencias financieras con resumen legible, motivo y versión. Explica las referencias pendientes y ofrece volver a la cuenta recuperando el formulario; separa asociación, conciliación histórica y trazabilidad. No registra dinero ni elige por texto o importe.
- **Resultados:** display, success, error, failure.
- **Permisos:** cliente aislado por servidor y administrador Platform en lectura; sesión de superusuario y CSRF para asociación/conciliación Panel. MCP administrativo reutiliza las mismas validaciones.
- **Invariantes:** no deducir contrato por proyecto o PDF; no confirmar pagos, duplicar ciclos ni reemplazar el PDF emitido al cambiar una asociación.
- **Validación:** pruebas dedicadas de API y UI; la ejecución se declara en el PR, no por registrar tags.
