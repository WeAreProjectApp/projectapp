# Rendimiento del camino editorial

Fecha: 23 de octubre de 2026. Auditoría delegada de `$implement` / `$perf-pass`, modo A. Alcance: utilidades y componentes editoriales nuevos, servicios `editorial_*` y serializer editorial. Sin acceso a datos de producción, cambios de infraestructura ni consultas SQL durante el perfil de conversión. El conductor conserva la gestión del ledger, Git y verificación independiente.

## Perfil y presupuestos

Fuente: `perf-ledger.sh --show projectapp --projdir=/home/dev_env/webapps/.wt/projectapp_staging/editorial-rich-text`. Se usa el estándar canónico del toolkit, `workflows/testing/PERFORMANCE_STANDARDS.md` 1.1.0; el helper marca `standard=stale` para la copia local del proyecto.

| Dato | Perfil confirmado |
| --- | --- |
| Servidor | `vps-projectapp-prod`, 4 vCPU, 15 GB, calibración 2026-09-14 |
| Servicio | 2 workers, 1 thread, `CPUQuota=40%`, `MemoryMax=350M` |
| CPU por API / página | 100 ms / 200 ms |
| Memoria transitoria por petición | 29 MB |
| JSON por página | 256 KB sin comprimir |
| JavaScript | 300 KB gzip inicial, 150 KB gzip por chunk de ruta |

El host de medición local es x86_64, Python 3.12.3 y 6 CPU lógicas. Los resultados siguientes cuentan operaciones y bytes; no certifican la latencia, CPU o memoria del servidor de producción.

## 1. Reutilización de validaciones de fuente

**Estado: corrección aplicada, revisión independiente del conductor y 15 regresiones enfocadas verdes.**

Antes del cambio se volvía a renderizar la misma pareja `(fuente, formato)` por cada anotación concordante y, en documentos, por la combinación de formato explícito y Markdown implícito. El caso local y raíz de 141.919 bytes está por debajo del presupuesto JSON incluso usando 256.000 bytes como interpretación conservadora de 256 KB.

Medición con `cProfile.Profile.runcall`, recorriendo `getstats()` para contar llamadas reales. Se envolvió cada operación con `connection.execute_wrapper` que lanza una excepción ante cualquier SQL. Se conservaron los mismos objetos de entrada antes y después; todos los campos repetidos de los tres primeros casos usan `Paragraph **bold** with _italic_.`.

| Entrada | JSON bytes | `render_source` antes → después | `html5lib.parseFragment` antes → después | SQL |
| --- | ---: | ---: | ---: | ---: |
| Documento con `/content_markdown` explícito | 116 | 2 → 1 | 4 → 2 | 0 |
| 1.000 hojas locales con la misma fuente | 100.011 | 1.000 → 1 | 2.000 → 2 | 0 |
| Las mismas hojas con anotación local y raíz concordante | 141.919 | 2.000 → 1 | 4.000 → 2 | 0 |

Controles posteriores adicionales: documento sin metadata, 1 render y 2 parseos; 1.000 fuentes distintas con anotación local y raíz, 1.000 renders y 2.000 parseos para 140.809 bytes. Se mantiene el trabajo necesario para cada fuente distinta.

La implementación en `backend/content/services/editorial_format.py:548` guarda únicamente parejas validadas con éxito, hasta 1.000 entradas, en un conjunto local a la operación. No conserva HTML renderizado, no comparte datos entre peticiones y no mantiene una caché global. Al llenarse sigue validando sin guardar más entradas. Las validaciones de rutas, perfiles, acuerdos entre anotaciones, ciclos y profundidad se ejecutan aunque la fuente ya haya sido validada. `validate_editorial_values`, `validate_formats` y `validate_nested_formats` comparten el conjunto sólo durante esa validación.

Beneficio: elimina trabajo de parser demostrado sin cambiar contenido, errores o permisos. Coste: una búsqueda de conjunto por fuente y hasta 1.000 parejas con referencias a las cadenas de la entrada. Riesgo principal: autorizar otra fuente, otro formato o un conflicto por reutilización incorrecta; cubierto por resultados persistidos y rechazos concretos. No se afirma que esta corrección baste para cumplir 100 ms con 1.000 fuentes distintas.

Pruebas nuevas: `backend/content/tests/services/test_editorial_validation_reuse.py`, 7 casos. Comprueban persistencia de fuente y anotaciones duplicadas, rechazo sin guardar contenido inseguro, conflictos posteriores, rutas obsoletas, distinción entre texto plano y HTML, y aceptación/rechazo después de llenar la capacidad de reutilización.

Comando enfocado, desde `backend/`, con settings de test y SQLite aislado:

```bash
../.venv/bin/pytest content/tests/services/test_editorial_validation_reuse.py content/tests/services/test_editorial_annotation_conflicts.py content/tests/serializers/test_editorial_serializers.py -q --no-cov --nomigrations
```

Resultado: 15/15 verdes. Gate estricto del archivo nuevo: 100/100, cero errores y advertencias, `/tmp/projectapp-editorial-reuse-quality.json`. No se añadieron aserciones de tiempo ni tests que únicamente comprueben el contador interno.

## 2. Conversión y editores montados en el navegador

**Estado: hipótesis respaldada por el recorrido de código; no optimizada sin perfil de interacción.**

Cada actualización visual ejecuta `htmlToSource`, que verifica su representación mediante `sourceToHtml` y dos normalizaciones semánticas; el componente vuelve a ejecutar `sourceToHtml` y el parser del esquema antes de publicar. Referencias: `frontend/utils/editorialFormat.js:259` y `frontend/components/base/BaseRichTextEditor.vue:166`. Estas comprobaciones protegen la coexistencia entre modos; eliminarlas cambiaría las garantías del editor.

El componente crea un `Editor` al montarse (`BaseRichTextEditor.vue:148`), y el editor de listas monta uno por elemento (`BaseRichTextListEditor.vue:70`). Cambiar de pestaña usa `v-show`, por lo que ocultarlo no libera el editor. El historial propio limita cada editor a 50 instantáneas y 2.000.000 de caracteres (`BaseRichTextEditor.vue:66`), sin cota global para todos los campos de una página.

Una mejora futura podría reutilizar el HTML ya comprobado en la misma actualización, manteniendo ambas comprobaciones semánticas. El montaje por demanda requiere comprobar foco, borrador e historial. Beneficio posible: menos recorridos DOM y menos editores vivos; coste medio y riesgo de pérdida de contenido si se aborda sin la matriz de ida y vuelta. No se aplicó ningún cambio frontend por este hallazgo. Falta medir una interacción real con número concreto de campos y tamaño de fuente para decidir si supera el umbral material.

## 3. Distribución del runtime en el build

**Estado: distribución del build real medida; no se cambia la carga frontend en este cierre.**

`BaseRichTextEditor.vue:3` importa Tiptap estáticamente; `editorialExtensions.js` incorpora el conjunto de extensiones. Se compiló en memoria un punto de entrada aislado con esbuild: `Editor`, `EditorContent`, parser del esquema, extensiones y funciones de conversión; Vue se declaró externo. Opciones: `bundle=true`, `minify=true`, `format=esm`, `platform=browser`, `target=es2022`, `treeShaking=true`, `write=false`. Compresión: `gzipSync(buffer, { level: 9 })`.

Resultado del inventario: 59 módulos, 531.116 bytes minificados, **168.743 bytes gzip**. Esto justifica revisar el reparto, pero no demuestra que un chunk o el JavaScript inicial de Nuxt excedan el presupuesto: el build puede extraer dependencias compartidas. Los 20 segundos observados en una ruta fría de desarrollo tampoco prueban una regresión de producción. El lector `BaseRichTextContent.vue` importa sólo la utilidad de conversión, sin requerir Tiptap directamente.

La segunda compilación del conductor, registrada en `/tmp/editorial-rich-text-build-final.log`, produjo `frontend/.nuxt/dist/server/client.manifest.mjs`. Se importó ese manifiesto como datos, se recorrió únicamente `imports` estáticos, se contaron archivos JavaScript únicos y se comprimió cada archivo con `gzipSync(..., { level: 9 })`. El detalle local de la medición está en `/tmp/editorial-build-final-metrics.json`. Esta medición precede a dos ajustes posteriores de foco y entrada WhatsApp vacía; no se presenta como medición exacta de los bytes del commit final.

| Artefacto del build | Bytes gzip |
| --- | ---: |
| Chunk `BaseRichTextEditor`, `B7KJXwBz.js` | 139.845 |
| Chunk `editorialFormat`, `ButUJOqD.js` | 16.780 |
| Chunk lector `BaseRichTextContent`, `CRtsm4wG.js` | 500 |
| Entrada Nuxt con sus dependencias estáticas únicas | 221.070 |
| Editor y dependencias todavía no presentes tras cargar entrada y lector | 140.949 |

El chunk editorial de 139.845 bytes queda por debajo de 150 KB tanto con interpretación decimal como binaria. La entrada con dependencias estáticas queda por debajo de 300 KB. El chunk mayor señalado inicialmente, `B2dRCrmh.js` de 168.787 bytes gzip, se identifica en el manifiesto como `apexcharts-chart-types`; no se atribuye al editor.

El estándar §3 prescribe «chunk de ruta ≤150 KB», mientras que su resumen §10 abrevia «por ruta» sin definir un presupuesto agregado para todos los archivos compartidos. Para evitar ocultar costes se informa también el cierre estático de cada ruta:

| Ruta | Entrada + ruta, archivos únicos gzip | Incremento con entrada ya cacheada | Incluye editor |
| --- | ---: | ---: | --- |
| Artículo público del blog | 268.091 | 47.021 | No |
| Building With Us público | 284.759 | 63.689 | No |
| Consulting público | 282.517 | 61.447 | No |
| Propuesta pública | 383.080 | 162.010 | No |
| Lista de documentos del panel | 581.625 | 360.555 | Sí |
| Edición de documento del panel | 560.634 | 339.564 | Sí |
| Comunicaciones del panel | 594.034 | 372.964 | Sí |
| Edición de blog del panel | 433.033 | 211.963 | Sí |

Estas sumas son un **mínimo estático**, no una captura de red completa: excluyen layouts, traducciones y otros imports dinámicos que no sean alcanzables por el grafo estático. El escenario caliente parte sólo de la entrada cacheada; navegar después de otra página puede reutilizar más archivos. Las rutas públicas de lectura examinadas ya mantienen fuera el editor pesado.

Decisión del conductor: no introducir otro cambio frontend por la ambigüedad de las sumas compartidas, sin comparación con la base ni medida de la interacción. Cargar el editor al abrir creación, notas o respuestas podría ahorrar descarga inicial en listas, pero requiere comprobar esa acción, foco y borradores frente a la base. No se trocean archivos para aparentar cumplimiento del presupuesto. Los nombres con hash corresponden a este build y deben regenerarse si cambia el frontend.

## Cotas reales y límites de la conclusión

| Cota existente | Alcance real |
| --- | --- |
| 500.000 caracteres por fuente | Backend, `editorial_format.py:456`; no limita los bytes UTF-8 agregados de una petición |
| 1.000 anotaciones | Por mapa local; pueden existir varios mapas en el mismo JSON |
| 50 niveles | Recorrido del JSON; no equivale a una cota global de hojas, bytes o coste de HTML |
| 1.000 parejas reutilizables | Memoria de validación local; al llenarse continúa la validación completa |

Una fuente ASCII de 500.000 caracteres con metadata explícita produce un JSON de 500.083 bytes, por encima del presupuesto orientativo de 256 KB. Es una diferencia entre contrato y presupuesto que debe registrar el conductor; este pase no reduce límites de producto ni trunca contenido. Tampoco se detectó una cota equivalente previa al parser del frontend. No se ha medido memoria máxima, CPU bajo saturación ni comportamiento con tráfico concurrente, por lo que no se declara una certificación global de rendimiento.

## Brief para QA y conductor

1. Revisión independiente del cambio backend: confirmar que el conjunto tiene vida local y capacidad fija, que sólo retiene validaciones exitosas y que comprobar rutas/conflictos no depende de encontrar la fuente en el conjunto.
2. Repetir el lote de 15 regresiones anterior si cambia el servicio. En el perfil estructural deben mantenerse 1 render/2 parseos para el documento explícito y para las 1.000 hojas con fuente idéntica; 1.000/2.000 para las 1.000 fuentes distintas. Mantener cero SQL y comparar las mismas entradas.
3. Conservar la matriz funcional Visual/Markdown/WhatsApp de la entrega: el ahorro de parser no permite omitir validación ni eliminar sintaxis admitida. Las pruebas de fuente insegura deben comprobar que el contenido previo sigue guardado.
4. Si se cambia la carga frontend, regenerar el inventario del build real y compararlo con la base: bytes gzip iniciales y por chunk de ruta, dependencias compartidas incluidas una sola vez, rutas de lectura sin editor y acción real de apertura en listas. Decidir carga por demanda sólo con esa evidencia. Este cierre conserva la carga actual.
5. Registrar por separado la diferencia entre el límite de fuente y el presupuesto de payload. No cambiar contratos, infraestructura ni permisos dentro de esta mejora.

El candidato backend tiene beneficio estructural medido y fue aplicado por autorización del conductor. Los otros dos quedan como diagnóstico; no justifican optimizaciones adicionales antes del cierre de esta entrega.
