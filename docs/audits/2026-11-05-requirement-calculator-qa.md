# Calculadora de requerimientos — validación de implementación

Fecha: 2026-11-05. Rama: `feat/05112026-requirement-calculator`. Entrega: [PR #555](https://github.com/WeAreProjectApp/projectapp/pull/555). Este registro no acredita despliegue ni calibración económica con datos reales.

## Alcance verificado

- La definición general crea revisiones inmutables y sincroniza su documento y los precios XS/S/M compartidos con Paquetes. Las ofertas emitidas conservan sus valores.
- Una variante de proyecto conserva su revisión de origen. Sólo permite ajustar parámetros existentes; aprobar congela definición, documento y bytes del PDF. Las modificaciones posteriores requieren otro borrador.
- El chat externo obtiene la definición aplicable por MCP y registra la clasificación explicada XS–XL o Proyecto. ProjectApp no ejecuta un modelo de IA. El documento del cliente omite horas, costos y valores unitarios internos.
- Los cierres y sus correcciones conservan evidencia. La calibración separa las definiciones efectivas, usa mínimos de muestra y umbrales configurables y propone revisiones sin cambiar precios automáticamente. Los valores permanecen provisionales si falta evidencia.

## Evidencia local

| Verificación | Resultado |
|---|---|
| Servicios de calculadora | Lote de 16 casos aprobado; los cambios posteriores en esos casos fueron de forma. |
| Vistas, MCP y consultas | Lote de 12 casos aprobado; incluye validación, permisos y aprobación con confirmación MCP. |
| Guardas y privacidad finales | 3 casos aprobados: documento sin parámetros internos, copia cargada antes de adoptar el documento y actualización masiva del contenido. |
| Presupuestos de consulta y respuesta | 3 casos aprobados; listados sin definiciones/PDF completos, evidencia resumida y detalle paginado. |
| Renovación de datos de prueba | 2 casos de integración y 1 contrato aprobados: preservación de la definición general, limpieza del grafo de proyecto con corrección de cierre y clasificación de los seis modelos nuevos. |
| Contratos MCP existentes | 6 casos focales aprobados para Comercial, Proyectos y Documentos. |
| Componentes y estado de interfaz | 2 archivos, 6 casos aprobados: concurrencia, transporte y edición limitada de parámetros. |
| Navegador | 27 casos distintos aprobados por lotes: definición, restauración confirmada, calibración, borradores, aprobación y documento administrado; incluye cinco perfiles de pantalla. |
| Compilación Nuxt | `npm --prefix frontend run build`: exit 0. |
| Registro de recorridos | Comprobación de sincronización aprobada: 465 referencias, 493 definiciones. |
| Calidad de pruebas | Gate canónico sin errores ni advertencias; retiró su marcador automáticamente. El gate backend final detecta 32 pruebas; este conteo estático no equivale a una ejecución conjunta de esos 32 casos. |

Las pruebas backend se ejecutaron por lotes acotados, con SQLite y los ajustes aislados de pytest, usando `--nomigrations`. La compatibilidad de migraciones completas se valida aparte en CI; el primer envío pasó sus dos trabajos MySQL. No se ejecutaron escrituras, migraciones ni renovación de datos de prueba sobre la base del servicio.

El navegador detectó un enlace documental que no generaba navegación: los botones con destino ahora usan el modo `NuxtLink`. La verificación sobre la compilación corregida aprobó proyecto y cinco perfiles de pantalla sin reintentos, el documento administrado y el caso focal de restauración. Los demás casos generales se validaron en su lote y focales previos. Un selector duplicado de la prueba se corrigió y su ejecución posterior quedó limpia.

## Límites y cierre

La validación local está completa. El cierre remoto exige CI verde en la última revisión del PR; su estado se consulta en GitHub. El controlador QA completo no pudo usar el registro del fleet porque su identidad del repositorio está desactualizada; las pruebas focales y el gate canónico se ejecutaron sin modificar ese registro ni eludir sus guardas.
