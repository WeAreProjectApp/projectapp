# PA-227 · Correcciones tras el rechazo de DEVQA-001

El recorrido real de qa2 en Chrome rechazó el SHA `2b0de3a93e36cd71a52114104a5756edabdf9741` del [PR #558](https://github.com/WeAreProjectApp/projectapp/pull/558). Sus tres corridas CI estaban aprobadas (91/91 controles); ese resultado no sustituye la aceptación funcional. La devolución y las capturas originales se conservan en `/mnt/c/Users/carlos/.codex/tmp/projectapp-qa/devqa-mensajes/qa2-DEVQA-001-resultado.md` y `PA-227-capturas/qa2-2b0de3a9/` del mismo directorio compartido.

## Hallazgos de aceptación y corrección

| Tipo | Hallazgo reproducido en Chrome | Cambio preparado | Reprueba |
|---|---|---|---|
| Control ausente | Plataforma no ofrece una acción visible para cambiar entre claro y oscuro; el cambio de la muestra requirió una ayuda de DEV. | Botón con texto y nombre accesible en la barra lateral y el menú móvil, conectado a la preferencia persistida existente. La barra colapsada conserva icono y título. Traducciones es-CO/en-US. | Administrador17 y cliente13, `/es-co/platform/projects/31`, cinco anchos; alternar por la UI, recargar y volver a alternar. Comprobar etiquetas, superficies, diálogos y navegación. |
| Persistencia de personalización | Administrador17, proyecto31, claro, 1440×900: Quitar oculta la portada; tras recargar reaparece el archivo personalizado del perfil. | La retirada envía ambas portadas vacías, con `custom_cover_image: null`; la API guarda la retirada explícita. Elegir una imagen de galería también sustituye el archivo personalizado. Un guardado fallido mantiene la portada visible. | Subir una imagen ficticia, quitarla, cerrar y recargar. Repetir en oscuro. DevQA coteja perfil y GET de recarga; no basta con ocultar la vista. Comprobar también sustitución por galería y conservar el color independiente. |
| Contraste | Superadministrador15, Gestor Documental, documento56, Vista previa Profesional, claro, 1440×900: «enlace al Gestor Documental» da 3,77:1. En oscuro da 10,29:1. | El enlace claro usa `#047857` y al pasar el puntero `#065f46`; Profesional hereda los mismos colores. El modo oscuro conserva sus colores propios. | Documento56, Amigable y Profesional, claro/oscuro; medir el enlace normal y al pasar el puntero contra su fondo real. Referencia ≥4,5:1. |

## Regresiones para CI

- `backend/accounts/tests/test_profile_cover.py`: retirada persistente después de un nuevo GET, sustitución por galería y conservación de portada ante cambios ajenos; administrador y cliente con base de test aislada.
- `frontend/test/components/PlatformSidebar.test.js` y `PlatformMobileDrawer.test.js`: acción accesible en ambos sentidos, barra expandida/colapsada y evento del menú móvil. El cierre de sesión usa su selector real.
- `frontend/test/composables/usePlatformCustomTheme.test.js`: retirada de las dos fuentes de portada y conservación de la imagen cuando la actualización falla o devuelve rechazo.
- `frontend/e2e/platform/platform-dark-mode.spec.js`: cambiar tema usando el control visible y recargar, ambos roles y sentidos en los cinco tamaños; retirar una portada guardada y recargar sin que reaparezca. Se conserva la matriz de contraste anterior.
- `frontend/e2e/admin/admin-document-edit.spec.js`: abrir Vista previa y elegir Amigable/Profesional, con enlace normal y hover medidos en claro y oscuro; captura por variante.

Los nuevos tests no se ejecutan en local. El SHA exacto, las corridas y su resultado se comunicarán en la ficha de reprueba de DevQA y en el PR cuando existan. El verde anterior acredita únicamente el corte rechazado.

## Mapa y flujos revisados

`/panel/views`: se amplían las notas de Perfil y el resumen de su capacidad para incluir elección de tema y retirada de portada. No cambian rutas, tipos, nodos ni conteos. El control es transversal a las páginas autenticadas de Plataforma; no se añade una URL ficticia al catálogo.

| Interacción | Éxito | Error de entrada | Fallo operativo | Visualización |
|---|---|---|---|---|
| Elegir claro/oscuro | Elección persistente tras recarga; E2E por rol/ancho. | No aplica: dos opciones válidas, sin entrada libre. | No aplica: preferencia local, sin petición de servidor. | Texto de la acción y superficies del tema; matriz existente. |
| Quitar portada | Retirada persistente; API real y E2E de recarga. | No aplica: acción sin entrada editable. | El rechazo conserva la imagen; cubierto en el composable. Falta cobertura E2E del aviso de error, que este flujo actualmente no presenta. | Desaparecen portada y acción Quitar; se mantiene el color. |
| Enlace en Vista previa | No cambia el destino del enlace. | No aplica: la fuente pasa por el renderer/sanitizador existente. | No cambia el tratamiento de carga del documento. | E2E de ambas plantillas/temas y estado hover. |

Se extienden los flujos existentes `platform-sidebar-navigation` y `admin-document-edit`; no se inventa un flujo nuevo para elevar cobertura. Los resultados del gate, catálogo y contrato responsive se verifican en CI.

## Coordinación y límites

Revisión adicional de la paleta Markdown: los títulos pequeños h3–h6 de
Amigable declaraban el mismo #059669 del enlace rechazado. Se unifica su
color claro con #047857 y se amplía el contenido de las cuatro regresiones
del renderer para medir esos títulos con la misma referencia de 4,5:1. Es
una observación de código; no se presenta como una medición nueva en Chrome.
La reprueba de R3 debe medir también esos encabezados en ambas apariencias.

Sólo DevQA opera el entorno. No iniciar otro servidor, cambiar el corte servido, escribir datos de su turno o aplicar parches durante el recorrido. DEVQA-001 está cerrado; la reprueba requiere nuevo SHA, CI verde, ficha y nueva concesión de la dupla qa2/dev-qa2 sin interrumpir DEVQA-002.

Los hallazgos de foco detrás de modales, validación en inglés y desbordamientos responsive conservan su seguimiento separado. No se incluyen en estos tres fixes ni se declara aprobado el barrido completo por los resultados anteriores. La aceptación de Chrome del nuevo corte sigue pendiente.
