# QA — Documents MCP 3.0.1

Alcance: errores de herramientas y transporte, atomicidad de movimientos,
descubrimiento, procedencia de carpetas y reparación de Littigio. PR #448.
Sólo backend; no se modifican flujos ni contratos de frontend.

## Validación focal

Las pruebas usan SQLite y `projectapp.settings_test`, sin leer la configuración
productiva. Los casos nuevos se ejecutaron en lotes de hasta 20 desde el worktree de sesión.

| Comportamiento | Casos nuevos |
| --- | ---: |
| Contratos MCP públicos, esquemas, versión y rechazos HTTP | 16 |
| Errores compartidos, códigos, reintento y protección de excepciones | 8 |
| Reparación: estado revisado, conservación, historial, rollback e idempotencia | 9 |
| Previsualización del comando sin escritura de base | 1 |
| Procedencia automática, admin, fallos por ID y evidencia de creación | 15 |

También se probaron regresiones de movimientos, organización, permisos,
serializadores, inicialización MCP y contratos de campos. La migración 0272
se aplicó en la base de pruebas; `makemigrations --check --dry-run` no detectó
cambios pendientes.

El auditor independiente aprobó el lote después de eliminar ramas en cuerpos
de pruebas, precisar un nombre y ubicar la prueba del comando en management.
El gate focal exige cero junk, con Ruff disponible en PATH. La configuración
de mutación no se modifica como parte de esta entrega.

## Verificación productiva

La reparación se verificó dentro de la transacción y mediante una conexión
posterior independiente: documentos 201/202/203/208/209 en 80, carpeta 124 vacía
y archivada, origen MCP recuperado. Todos los campos documentales conservados,
salvo ubicación y auditoría de modificación. Reintento sin nuevas escrituras.
Respaldo, huellas y recibos: [runbook de Littigio](../runbooks/littigio-folder-repair.md).

## Límites y antecedentes

El barrido global inicial del toolkit informó deuda histórica de frontend
(`platform-hosting-subscription`) y errores de infraestructura por falta de
Ruff en PATH. Un nombre de prueba nuevo que disparaba el detector de lote se
corrigió antes del gate focal. Esos resultados globales no representan el
veredicto de este lote ni justifican modificar pruebas ajenas.

La memoria QA compartida del toolkit ya tenía cambios de otra sesión y se
conservó intacta; los hallazgos de esta entrega quedan en este reporte. No se
modificó el motor de QA. El estado del CI remoto se consulta en el
[PR #448](https://github.com/WeAreProjectApp/projectapp/pull/448).

## Regresión detectada por CI

El grupo backend 4/6 detectó una expectativa histórica de texto plano en
`test_rename_folder_rejects_managed_project_root`. Se actualizó para comprobar
el JSON de error, su código `MANAGED_PROJECT_FOLDER`, el mismo mensaje humano
y la conservación del nombre de la raíz. Las nueve pruebas de carpetas del
archivo pasan con las migraciones reales, igual que en CI. El gate del archivo
adicional pasa: cero errores y tres advertencias de determinismo preexistentes
en pruebas de notas ajenas al cambio. No se modificó código de producción para
resolver este fallo.
