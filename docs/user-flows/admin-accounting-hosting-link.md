### FLOW: `admin-accounting-hosting-link`

- **Módulo:** admin
- **Prioridad:** P1
- **Descripción:** Desde Ingresos o Cuentas de cobro, elegir y confirmar hosting reconocible por dominio y periodicidad, vincular un registro elegible o crear uno del mismo cliente y proyecto sin perder el formulario. Si faltan decisiones, explicar las referencias pendientes y volver de conciliación recuperando el borrador.
- **Resultados:** display, success, error, failure.
- **Permisos:** superusuario con sesión y CSRF. La lectura de opciones no escribe asociaciones ni concede acceso adicional.
- **Invariantes:** el vínculo es explícito, conserva pagos, cobros, ciclos y PDF históricos; la obligación de suscripción sigue seleccionándose explícitamente. Los cambios concurrentes exigen volver a revisar.
- **Validación:** automatizadas exclusivamente en CI, con URL y SHA; Chrome y cotejo técnico en el turno acordado con DevQA.
