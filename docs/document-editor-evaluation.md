# PA-211 — Evaluación y mejora del editor documental

## Decisión

Mejorar la interfaz de Tiptap y mantener Markdown extendido como fuente de los
contenidos. La decisión comprende el cuerpo de Nuevo Documento y edición del
Gestor Documental. Los editores de notas, correos, WhatsApp y otros módulos
conservan su barra anterior.

El operador eligió conservar los estilos existentes y priorizar una barra clara
con controles contextuales. No se incorpora un segundo motor de edición.

## Comparación verificada el 6 de noviembre de 2026

| Criterio | Tiptap 3.32.0, instalado | Milkdown Crepe 7.23.0, evaluado |
| --- | --- | --- |
| Controles | La barra propia necesitaba agrupar herramientas y reflejar la selección | Incluye barra flotante, edición de bloques, menús y tablas |
| Edición | Integración existente con Vue 3, historial y modos Visual/Fuente | Integración oficial con Vue 3 y fuente Markdown |
| Formatos | Ya conserva HTML limitado para color, resaltado, subrayado, alineación, tablas combinadas y extensiones propias | Su orientación Markdown es atractiva; preservar el vocabulario propio requiere adaptar y verificar su esquema y serialización |
| Integración | Esfuerzo acotado a controles, presentación y pruebas de regresión | Esfuerzo mayor: ciclo de vida, sincronización, selección, historial, temas y compatibilidad completa |
| Mantenimiento | Paquetes fijados publicados el 13-10-2026; el registro ya ofrece 3.33.0 | Crepe, Vue y Kit 7.23.0 publicados el 27-10-2026 |
| Licencia | MIT en cada paquete Tiptap instalado | MIT en Crepe, Vue y Kit |

Las fechas son evidencia de mantenimiento, no una garantía de ausencia de bugs.
No se ha demostrado incompatibilidad absoluta de Milkdown: el mayor esfuerzo es
una inferencia a partir de su integración distinta y de las extensiones propias
que hoy exige el contrato. No se presenta un prototipo Milkdown como validado.

Fuentes primarias:

- [Licencia Tiptap](https://github.com/ueberdosis/tiptap/blob/main/LICENSE.md).
- [Releases Tiptap](https://github.com/ueberdosis/tiptap/releases).
- [Licencia Milkdown](https://github.com/Milkdown/milkdown/blob/main/LICENSE).
- [Crepe: versión, licencia y dependencias](https://github.com/Milkdown/milkdown/blob/main/packages/crepe/package.json).
- [Milkdown con Vue 3](https://milkdown.dev/docs/recipes/vue).
- [Funciones Crepe](https://milkdown.dev/docs/api/crepe).
- [Releases Milkdown](https://github.com/Milkdown/milkdown/releases).
- Metadatos de publicación y licencia contrastados por paquete en el registro npm:
  `@tiptap/core`, `@tiptap/vue-3`, `@tiptap/pm`, `@tiptap/starter-kit`,
  `@tiptap/extension-table`, `@tiptap/extension-text-style`,
  `@tiptap/extension-text-align`, `@tiptap/extension-highlight` y
  `@tiptap/extension-placeholder`, todos 3.32.0; `@milkdown/crepe`,
  `@milkdown/vue` y `@milkdown/kit`, todos 7.23.0. Sus licencias declaran MIT.

Se mantienen únicamente las extensiones abiertas ya instaladas. Índice y avisos
usan los nodos propios existentes; código y separador ya forman parte de
StarterKit; combinar y separar celdas son comandos de la extensión Table. No se
requieren paquetes Pro. No se adopta la [extensión Markdown beta de Tiptap](https://tiptap.dev/docs/editor/markdown).

## Mejoras incluidas

- Herramientas agrupadas de texto, párrafo/listas y alineación; iconos, ayudas,
  selección activa y nombres traducidos. Controles compartidos del panel para
  foco, teclado y respuesta táctil.
- Enlaces con URL actual, aplicar, quitar y cancelar; rechazo de protocolos
  inseguros sin modificar el documento.
- Acciones de tabla visibles dentro de una tabla, con combinación/separación
  disponibles sólo para selecciones compatibles.
- Inserción de los cinco tipos de aviso, índice, código y separador; los avisos
  se pueden convertir de nuevo en texto normal.
- Color y resaltado con valor de selección y acción para retirarlos.
- Visual con tipografía de lectura, Fuente monoespaciada y tablas desplazables.
  La vista previa construye el índice con los encabezados reales y diferencia
  los avisos. Las etiquetas e identificadores de lectura no se guardan.

Imágenes, colaboración, IA y edición por bloques quedan fuera de esta entrega.

## Compatibilidad

Rige [Formato editorial v1](EDITORIAL_FORMAT.md). Una única cadena se guarda en
`content_markdown`; creación envía `markdown`, actualización envía
`content_markdown`. El mapa `text_formats` conserva la anotación del cuerpo y las
anotaciones ajenas. No se cambia el esquema, no se migran documentos ni se
reescribe contenido sólo por abrirlo o alternar modos.

El contenido plano sigue siendo literal también en Vista previa. Los formatos
Markdown y Markdown extendido mantienen sus interpretaciones y el saneamiento.
El índice y los avisos se decoran en una proyección de lectura; no introducen
un nuevo formato de persistencia. Las conversiones inseguras conservan la
fuente para corregirla y los guardados rechazados mantienen el borrador.

## Validación exigida

Las pruebas automatizadas de este ticket se ejecutan exclusivamente en CI.
Se cubren las interacciones nuevas, regresiones de fuente/visual, guardado y
reapertura, persistencia API real con una DB de test, formatos históricos y
rechazo seguro. Los resultados se registran con URL de corrida y SHA probado.

La sesión `dev-qa` realizará el recorrido manual con la extensión Chrome de
ChatGPT, usuario staff y datos de prueba del entorno de desarrollo. Debe incluir
un documento existente de prueba, el corpus editorial, crear/editar, ambos
modos, Vista previa, guardar/reabrir y fallos recuperables. No se copian datos
sensibles de clientes a fixtures ni a evidencia pública.

Matriz vigente del proyecto: 412×915, **835×1195**, 1195×835, 1440×900 y
2560×1440; temas claro y oscuro. La altura de la tableta sigue el override de
`.testquality.yml`, que prevalece sobre el valor genérico del fleet.

El cierre requiere PR abierto, CI verde y evidencia manual del mismo código.
La autoría de pruebas y este informe no acreditan por sí solos validación ni
un despliegue.
