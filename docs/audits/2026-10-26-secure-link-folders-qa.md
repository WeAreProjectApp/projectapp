# Jerarquía de Enlaces seguros — verificación de implementación

Fecha: 2026-10-26. Entrega y checks de la revisión final: [PR #545](https://github.com/WeAreProjectApp/projectapp/pull/545).
Este registro describe código y pruebas; no acredita un despliegue.

## Contrato entregado

Árbol propio de Enlaces seguros, con raíces automáticas de proyecto, carpetas
manuales y subcarpetas. Documentos y Enlaces seguros usan el mismo lateral y
breadcrumb mediante adaptadores; Comunicaciones reutiliza el breadcrumb y el
recorrido común del árbol. Se mantienen separados los datos de los tres módulos.

Crear sin destino clasifica por el proyecto real; sin proyecto queda en raíz.
Elegir carpeta al crear permite heredar su contexto inicial. Mover conserva las
asociaciones, propietario y permisos. La búsqueda, pestañas y conteos abarcan el
subárbol seleccionado. Archivar oculta sin revocar; restaurar conserva los
archivos independientes y eliminar exige una carpeta vacía.

Comunicaciones MCP 3.2.0 añade diez herramientas de jerarquía. El catálogo de 60
herramientas conserva autenticación, alcances, confirmaciones y secreto efímero.
Los argumentos nuevos tienen descripciones y esquemas cerrados; la huella de
contrato está actualizada, sin ampliar el backlog de excepciones.

## Evidencia focal

| Área | Evidencia |
|---|---|
| Reglas de carpetas y API | 18 casos en `secure_links/tests/test_folders.py`: clasificación, herencia inicial, movimiento independiente, ciclos, archivo, restauración, permisos y revisión obsoleta. |
| MCP | Casos de creación, lectura, cambio, permisos, eliminación confirmada y archivo; pruebas adicionales de revisión antigua y fecha con zona `Z`. Inventario y reporte de esquemas sin diferencias. |
| Migración y archivo | Regresiones de clasificación histórica por FK real y restauración de enlaces movidos tras archivar. No se infiere cliente por correo ni se convierte el árbol de otros módulos. |
| Rendimiento | El inventario de carpetas mantiene un máximo de seis consultas con uno y doce proyectos; REST y MCP comparten consulta y conteos. |
| Propiedad | Regresión focal de Platform: organizar y archivar no concede acceso ni altera propietario, reemplazos o consumo. |
| Datos ficticios | Dos pruebas independientes del árbol representativo y reinicio: se retiran las carpetas del proyecto y se conserva un enlace independiente movido dentro, devolviéndolo a raíz. |
| Conservación | Borrado de raíz vacía y conservación del árbol no seleccionado al eliminar un proyecto, con sus carpetas ligadas al mismo contexto de consulta. |
| Stores y componentes | 18 pruebas de stores; regresiones focales del lateral y breadcrumb de Documentos; dos casos de ordenación usan el límite público del componente de arrastre. |
| Navegador | Tres casos nuevos: creación en subcarpeta con contexto, conflicto de revisión y fallo del servidor sin cerrar el formulario. |
| Responsive | Navegación de carpeta a subcarpeta y apertura del contenido en 412×915, 835×1195, 1195×835, 1440×900 y 2560×1440. Una única celda canónica por perfil. |
| Integraciones vecinas | Políticas de relaciones de clientes, alcance de integridad, raíces afectadas por renombrado y snapshots para fusión/deshacer incluyen las carpetas nuevas. |

Los gates focales de pruebas nuevas pasan con 100/100. Los archivos históricos
del lateral y conservación mantienen advertencias anteriores, fuera de los
casos añadidos. Catálogo de vistas, registro de flujos, contrato responsive y
control de cambios de migraciones están sincronizados.

## Alcance de la validación

Se ejecutaron archivos o casos concretos, sin lanzar manualmente la suite
completa. La ejecución local usó SQLite y almacenamiento temporal de tests.
Las pruebas que requieren catálogos históricos se verifican con esos catálogos;
`--nomigrations` por sí solo no los crea. El CI del PR incluye migraciones y las
comprobaciones aisladas de compatibilidad con MySQL.

Nuxt local tuvo cargas frías prolongadas y timeouts antes de montar rutas. Los
resultados positivos citados corresponden a aserciones ejecutadas; no se toma
una página HTML vacía como validación. Las regresiones completas de
Comunicaciones y el modal histórico se confirman mediante los checks de la
revisión final del PR, que son la evidencia de entrega.

## Despliegue

Aplicar `secure_links.0006` y `0007` mediante el procedimiento de despliegue. La
sesión no ejecutó migraciones ni un reinicio de datos ficticios contra la base
del servicio. Los alcances MCP personalizados deben habilitar explícitamente
las herramientas nuevas que necesiten.
