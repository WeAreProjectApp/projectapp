### FLOW: `admin-requirement-calculator-calibration`

- **Module:** commercial
- **Role:** admin
- **Priority:** P2
- **Route:** `/panel/requirement-calculator`
- **Description:** El administrador consulta cohortes, muestras insuficientes, estimaciones y cierres. Registra horas reales, evidencia y causa; un cierre posterior corrige explícitamente el último cierre. Datos inválidos, una corrección no válida y fallas de servidor quedan visibles.
- **Steps:** Abrir Calibración → consultar cohorte → seleccionar estimación → registrar esfuerzo, evidencia y causa → corregir → verificar ambos eventos.
- **Branches:** Valores no positivos, campos requeridos o supersedes incorrecto se rechazan. Un fallo conserva el formulario para reintentar.
- **Coverage:** ❌ Missing — `display`, `success`, `error`, `failure`.
