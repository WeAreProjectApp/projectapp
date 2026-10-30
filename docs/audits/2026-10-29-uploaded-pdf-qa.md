# Validación focal — documentos PDF subidos

PR: https://github.com/WeAreProjectApp/projectapp/pull/549. Worktree de sesión `pdf-documents`. Sin merge, migraciones aplicadas ni despliegue. PA-125 y la incorporación automática de contratos firmados permanecen separados.

## Comportamiento verificado

| Capa | Resultado | Qué protege |
| --- | --- | --- |
| API PDF | 17 casos aprobados | Creación y asociaciones, archivo inválido/cifrado/vacío, límite exacto de 25 MiB y exceso, bytes originales, historial, versión obsoleta, metadatos y búsqueda |
| Integridad PDF | 17 casos aprobados; el caso de firma se reejecutó tras corregir su URL de consulta | Rollback exterior y savepoint, conservación del archivo anterior, extracción separada, privacidad física, publicación al cliente y aislamiento, evidencia firmada/publicada, guardas de entrega, PATCH obsoleto, callback fallido posterior al commit y prioridad de evidencia generada |
| Historial previo | 3 casos aprobados | Descarga de archivos históricos de documento, propuesta y extracto después de desvincular o borrar el registro vivo |
| MCP PDF | 14 casos aprobados | Carga por partes, creación, lectura, descarga, reemplazo, metadatos, rechazo de texto, assets ajenos/incompletos/tipo incorrecto, consumo fallido e historial privado |
| Compatibilidad de serialización y renderer | 5 casos aprobados | Tres fallos detectados por CI más dos contratos semánticos: modalidad/metadatos/capacidades PDF sin ruta privada y render de documento efímero sin persistir |
| Unit frontend | 10 casos aprobados | Multipart y asociaciones/notas, versión revisada, errores 409/413, visor/descarga, selección retenida y restricción de reemplazo |
| E2E | 8 casos aprobados, un worker, sin retries | Selección y arrastre, error de archivo, navegación desde panel, visor y descarga real, reemplazo/historial, concurrencia rechazada, metadatos sin Markdown y visor fallido |

Los lotes backend se ejecutaron con `python -m pytest ... --no-cov -q --tb=short` desde el backend del worktree, con `settings_test`, SQLite temporal y migraciones reales. Ningún lote excedió 20 casos. La tanda inicial de integridad tuvo un error en la URL de una prueba; su reejecución, la prioridad de evidencia generada y las tres regresiones de historial pasaron en un lote de cinco. No se ejecutó la suite completa local.

Los E2E usan Node 22, Chromium, servidor propio en 4313 y `E2E_WORKERS=1`. Se corrigieron selectores accesibles y la captura del primer request de descarga en una ventana nueva mediante `context.route`; no se omitieron pruebas ni se desactivó el warmup. Los ocho escenarios pasaron en la corrida final.

## Guardas y contratos

- Validación estructural y extracción separadas en hijos con 128 MiB, 3 segundos CPU y 5 segundos de espera por fase. Un fallo de extracción conserva el original previamente validado. Sin OCR; búsqueda del texto vigente.
- El reemplazo y los metadatos usan locks de proyectos antes del documento. Se relee el documento y se valida la petición original para impedir que un PATCH antiguo restaure otra versión binaria.
- La compensación comparte el estado de commit del historial. Una excepción de un callback posterior al commit no borra archivos ya confirmados. Fallos anteriores conservan los originales y no consumen el asset.
- Firma/snapshots tienen prioridad sobre fuentes vivas; un PDF protegido rechaza sustitución. Entrega/firma mantienen 10 MiB y captura de fuentes 15 MiB.
- Contrato MCP documents 8.2.0, 84 herramientas, sin diferencias de descubrimiento. `makemigrations content --check --dry-run` sin drift.
- Mapa de vistas válido, 136 páginas/entradas; guard de diseño sin errores; registro de flujos generado sin drift. Auditoría del flujo `admin-document-pdf`: cuatro outcomes cubiertos. Los parciales de otros flujos no se modificaron.
- Gate focal con reglas semánticas strict, junk como error y lint externo sobre los tests tocados; sin excepciones para esconder fallos.

Los resultados y logs completos de esta sesión se conservan en `/home/dev-env/.local/state/projectapp-merge-queue/29102026/pdf-*.log`; el estado persistente está en `pdf-status.md`. El estado del CI remoto se verifica sobre el head final del PR, sin inferirlo de estas pruebas locales.

## Requisito de deploy e integración

La migración `content.0304_uploaded_pdf_documents` depende de `0303_merge_editorial_requirement_packages`. La excepción Nginx versionada permite 26M sólo en creación/reemplazo PDF, con 25 MiB reales de archivo. Debe aplicarla y validarla el deploy posterior: esta sesión no cambia Nginx vivo ni acredita su aplicación. La queue integra y valida la combinación con buscador contractual y cobros pendientes; la sesión no mergea.
