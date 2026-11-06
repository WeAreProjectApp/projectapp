### Platform: consultar los proyectos asignados

Entrada autenticada: `/es-co/platform/projects`. El cliente ve sus proyectos;
el administrador conserva las columnas de cliente y solicitudes.

| Resultado | Interacción | Evidencia esperada |
|---|---|---|
| display | Consultar nombres de 175 caracteres, con y sin espacios, junto a otro corto. | Nombre completo en varias líneas; progreso, bugs, importe, actividad y acceso al detalle alcanzables. A 1440 × 900 todas las columnas caben desde la posición inicial. |
| success | Abrir un proyecto desde su tarjeta o fila. | El detalle corresponde al proyecto seleccionado. |
| display | Consultar el listado sin registros. | Se muestra el estado vacío correspondiente al rol. |

PA-229 se prueba en los cinco perfiles canónicos del proyecto. Las tarjetas de
412 × 915 y 835 × 1195 conservan los mismos datos; las tablas de 1195 × 835,
1440 × 900 y 2560 × 1440 no crecen por el nombre. Las pruebas automatizadas se
ejecutan exclusivamente en CI; la reprueba en Chrome corresponde al turno de
dev-qa sobre un SHA declarado.
