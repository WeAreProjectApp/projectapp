# PA-265 — Historial de documentos

## Comportamiento

El historial documental usa una lista compacta, un dropdown de orden y una sola
paginación de veinte registros. Consultar abre inmediatamente el panel de cambios
entre la revisión anterior y la consultada. Dos casillas permiten comparar
revisiones de páginas distintas, siempre de menor a mayor número. Las selecciones
se conservan al ordenar y paginar; cambiarlas invalida el resultado anterior.

Desde 1024 px la lista y la consulta conviven. En móvil y tableta vertical la
consulta ocupa el área de lectura y Volver al historial recupera el contexto.
Ver versión completa permite leer el destino y regresar al mismo par sin volver
a consultar la API. Carga, error recuperable, revisión inicial, evento incompleto
y ausencia de diferencias tienen mensajes propios.

El diff alinea párrafos, elementos de lista y filas de tabla renderizados con un
bloque vecino de contexto; una celda editada no repite la tabla completa. Las bajas
llevan − Eliminado y rojo; las altas + Agregado y verde. Los cambios sólo de
formato se identifican. La comparación descarta delimitadores equivalentes y
envolturas de tablas, conservando estilos, enlaces y estructuras significativas.
La alineación limita su matriz a 250 000 celdas, tras recortar prefijos/sufijos
iguales; si se supera, conserva todos los bloques con comparación simplificada.

Se utiliza exclusivamente el contenido de las instantáneas, sus anotaciones de
formato y el renderizador saneado existente. Los JSON antiguos se leen por sus
tipos de bloque; un tipo desconocido permanece como texto escapado. Los PDF se
consultan en su archivo histórico y sus páginas no tienen diff visual.

## Contrato y conservación

Sin cambios de esquema, modelos, migraciones ni endpoints. El listado, la lectura
de revisiones y la comparación siguen usando entity-history con sesión del panel.
Las instantáneas sólo viven en el contexto de consulta activo; no se persisten
en Pinia ni almacenamiento del navegador. Consultar no edita ni regenera contenido.
Propuestas, Proyectos, Clientes y Contabilidad conservan su visor existente.

MCP mantiene las operaciones `list_document_history`,
`get_document_history_version` y `compare_document_history` del adaptador
`content/mcp/entity_history_tools.py`, con los permisos y el filtrado existentes.
La presentación enriquecida es una capacidad del navegador y no requiere otro
contrato de escritura o una herramienta nueva.

## Traspaso de validación

La pausa de QA manual y servicios sigue vigente. No acredita reproducción en DEV
ni validación visual. Las pruebas automatizadas añadidas se ejecutan sólo en CI;
el PR y su SHA identifican la evidencia de cada corrida.

Cuando se autorice el recorrido, usar un documento ficticio con más de veinte
revisiones y otro con una sola. Incluir altas, bajas, sustituciones, cambios sólo
de formato, ausencia de diferencias, JSON antiguo, PDF y un documento extenso.
Comprobar orden y retorno a página 1; selección entre páginas; resultado visible;
reintento; lectura completa y regreso sin perder el par. Contrastar instantáneas
y contenido actual antes/después y permisos de administrador, cliente y registros.

La matriz canónica de `frontend/config/responsive.js` es 412×915, 835×1195,
1195×835, 1440×900 y 2560×1440, en claro y oscuro. La altura canónica de tableta
es 1195, aunque el estándar documental anterior indica 1194. Registrar versión,
entorno, rol, datos ficticios y capturas antes/después. La validación dedicada de
teclado queda fuera por el acuerdo vigente; se conservan las funciones existentes.
