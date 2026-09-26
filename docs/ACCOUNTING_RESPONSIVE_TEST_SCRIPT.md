# Guion repetible — módulo contable responsivo

> **Documento histórico de PA-77.** El guion operativo vigente y consolidado
> está en [`RESPONSIVE_QA_TEST_SCRIPT.md`](RESPONSIVE_QA_TEST_SCRIPT.md), que
> incorpora esta matriz junto con los otros doce módulos. No mantener dos
> resultados de ejecución separados.

Este guion es el criterio de aceptación de PA-77. Se ejecuta completo después
de cualquier cambio en componentes base, tablas, filtros, navegación o modales
del panel. El resultado son **60 recorridos mínimos**: 12 secciones por los 5
anchos oficiales. No se reemplaza un ancho por “se ve parecido”.

## Preparación

1. Usar un superusuario con datos en los doce tabs.
2. Incluir, como mínimo:
   - un ingreso esperado parcial, uno líquido y uno perdido;
   - un ingreso sin cliente y otro sin proyecto;
   - un gasto de empresa, uno personal y una deducción;
   - un hosting vigente con ciclos y correo de facturación;
   - una cuenta de cobro emitida con notas;
   - pagos recurrentes en COP y USD, repartidos en dos categorías;
   - dos movimientos de Bolsillo, uno IN y uno OUT;
   - un extracto con transacciones, alias y PDF;
   - registros en Historial de cambios y de correos.
3. Abrir DevTools, desactivar zoom y fijarlo en 100 %.
4. Empezar cada recorrido arriba de la página (`scrollY = 0`) y sin un modal
   abierto. Probar en tema claro y repetir al menos Celular en tema oscuro.

## Anchos oficiales

| Perfil | Viewport | Navegación esperada |
|---|---:|---|
| Celular | 412 × 915 | selector de sección y selector de filtros guardados |
| Tableta vertical | 835 × 1195 | selector de sección y selector de filtros guardados |
| Tableta horizontal | 1195 × 835 | tira de 12 secciones y tira de filtros |
| Portátil | 1440 × 900 | tiras completas; columnas de escritorio según espacio |
| Monitor 27″ | 2560 × 1440 | contenido centrado, sin estirarse más allá del máximo |

## Comprobaciones comunes en cada recorrido

Marcar el recorrido como fallido si cualquiera de estas condiciones no se
cumple:

- No existe scroll horizontal en la página. En consola:
  `document.documentElement.scrollWidth <= document.documentElement.clientWidth`.
- La sección activa se reconoce y se puede cambiar con teclado y táctil.
- En Celular y Tableta vertical no aparecen las doce pastillas de navegación.
- En Tableta horizontal, Portátil y Monitor no aparece el selector móvil.
- La tira de filtros guardados no corta, pierde ni vuelve inalcanzable una
  opción; en angosto se usa un selector.
- Buscador, filtros, exportación y CTA principal no se solapan.
- Texto, montos, badges y acciones no se recortan. Una columna agrupada se lee
  bajo la identidad de su fila con su etiqueta de negocio.
- Toda acción alcanzable por hover también se alcanza con click/tap y teclado.
- Los controles táctiles tienen, como mínimo, 44 × 44 px.
- Al abrir un modal en Celular ocupa la pantalla completa; su título, contenido,
  errores y acciones finales siguen alcanzables. En los otros perfiles conserva
  el ancho semántico y no supera el alto visible.
- Al cerrar un modal, el foco vuelve a un control útil y la página recupera el
  scroll.
- En Monitor el contenido permanece relacionado y centrado: no debe repartirse
  por los 2560 px completos.

## Matriz de los 60 recorridos

Ejecutar cada fila en este orden para los cinco perfiles anteriores. Registrar
`OK`, `Falla` o `N/A` —este último exige una explicación— en una copia de las
cinco columnas de resultado.

| # | Sección | Decisión de negocio que debe comprobarse |
|---:|---|---|
| 1 | Resumen | La utilidad líquida sigue siendo el indicador principal. En angosto se ven, como máximo, los tres indicadores de decisión; “Ver todos los indicadores” revela el resto. La tabla mensual conserva Mes y Utilidad, y agrupa Esperado, Líquido y Gastos bajo Mes. Tarjetas conserva Tarjeta y Deuda. |
| 2 | Bolsillo | En Celular no se renderiza una tabla: cada movimiento es una tarjeta con acción de 44 px al inicio, Concepto, Valor, Fecha, Tipo y **Saldo después**; con filtros muestra **Acumulado filtrado**. Los distintivos conservan palabras enteras, las tarjetas mantienen el ordenamiento y no introducen scroll horizontal ni superposición. Desde Tableta vertical vuelve la tabla priorizada y la columna independiente de saldo aparece desde Tableta horizontal. El saldo general entra en la primera pantalla del Celular. |
| 3 | Ingresos | Concepto y Total permanecen. Cliente, tipo de ingreso, cobro, mes, origen y proyecto se agrupan según el perfil. Los distintivos de tipo permanecen enteros y la acción única queda al inicio tanto en Lista como en Agrupada. Los siete indicadores muestran tres prioridades y un detalle desplegable en angosto. Alternar Lista/Agrupada no introduce scroll horizontal. |
| 4 | Gastos | Concepto y Total permanecen. Período, categoría, contabilidad y repartos se agrupan. Los indicadores prioritarios son total anual, mes actual y deducciones; el detalle revela gasto principal y reparto empresa/personal. Cada fila empieza con una sola acción de 44 px cuyo menú ofrece Detalle e historial, Ver nota (si la hay), Editar y Eliminar. |
| 5 | Hostings | Cliente y Estado permanecen; Valor/mes se agrupa bajo Cliente en Celular (la fila no cabía con la casilla, la acción y el selector de Estado) y vuelve como columna desde Tableta vertical. Dominio y Vigencia vuelven como columnas desde Tableta horizontal; Proyecto, Modalidad, Ciclos y Total pagado se agrupan. En todos los perfiles hay una sola acción de 44 px al inicio (después de la casilla); su menú ofrece Detalle e historial, Ver nota (si la hay), ciclos, cobro, correos, editar y eliminar. El estado y «Cobro enviado» se apilan sin empujar la fila fuera del borde. |
| 6 | Cuentas de cobro | Número, Total y Estado permanecen. Cliente y Vence vuelven desde Tableta horizontal; origen, proyecto y emisión se agrupan. En Lista y Agrupada hay una sola acción de 44 px al inicio; abre el mismo menú completo, permanece dentro de la fila y los distintivos de estado/origen no se parten. |
| 7 | Recurrentes | Nombre y equivalente COP mensual permanecen. Los demás datos se agrupan. El encabezado de categoría pone el nombre en su propia línea en angosto y conserva subtotal y participación legibles. Lista y vista agrupada mantienen las mismas prioridades. |
| 8 | Ads | Plataforma y Valor permanecen. Fecha, tarjeta, participación y acumulado se agrupan. El indicador anual, buscador, filtros y CTA caben sin solaparse. La acción única al inicio abre Detalle e historial, Ver nota (si la hay), Editar y Eliminar. |
| 9 | Tarjetas | Tarjeta y Deuda permanecen. Fecha, disponible, uso y notas se agrupan; la nota se abre con «Ver nota» y nunca estira la fila. La acción única al inicio abre Detalle e historial, Editar y Eliminar. Las columnas visibles llegan al borde derecho de la tabla, sin franja en blanco. Catálogo y formulario apilan sus campos y acciones en orden previsible. |
| 10 | Extractos | La cuadrícula mensual usa 2/3/4 columnas según perfil. En el detalle, la acción de 44 px encabeza cada transacción angosta junto a Comercio y Valor; fecha, descripción, categoría y cuota quedan debajo. Su menú ofrece Detalle e historial, Ver nota (si la hay), Editar y Eliminar (sólo en borrador). El menú móvil del encabezado conserva editar encabezado, agregar, finalizar/reabrir y eliminar. Alias usa una fila compacta editable con la misma acción inicial. |
| 11 | Historial | Los dos ámbitos —Cambios y Correos— siguen alcanzables junto con sus filtros guardados. Registro/Acción y Destinatario/Estado son las identidades; fecha, usuario, entidad, aviso y asunto se agrupan sin duplicar texto en el DOM. Expandir una fila conserva el contexto. En Correos, un envío con acciones empieza con una acción de 44 px cuyo menú ofrece ver el correo y reintentar (deshabilitado con su motivo); abrirla no expande la fila. |
| 12 | Configuración | Destinatarios, plantillas y tarjetas apilan sus formularios sin cortar campos. Agregar email, guardar y restablecer filtros son acciones de ancho completo en Celular y vuelven a su ancho natural desde Tableta vertical. Cada destinatario empieza con su acción de 44 px (Detalle e historial, Ver nota, Quitar) y conserva el interruptor en la fila; cada tarjeta guardada abre con la suya (Detalle e historial, Ver nota, Eliminar). |

## Recorrido de modales largos

Ejecutar los siguientes casos en los cinco perfiles oficiales. Portátil y
Monitor forman parte de la regresión obligatoria y no se reemplazan con el
resultado de los tres anchos angostos.

| Caso | Pasos y resultado esperado |
|---|---|
| Nueva cuenta de cobro | Completar cliente e ingreso, llegar a Previsualizar, alternar Correo/PDF en angosto, volver a editar y regresar al paso 2. Nunca aparecen dos paneles ilegibles lado a lado por debajo de 1024 px. Confirmar y enviar permanece alcanzable. |
| Liquidar ingreso | Abrir un esperado, registrar abono parcial, desplegar bloques condicionales y agregar un siguiente ingreso esperado. Fechas, valores, errores y CTA no se cortan. |
| Registrar abono múltiple | Seleccionar varios ingresos, repartir un valor, provocar una suma inválida y corregirla. El motivo de bloqueo y las acciones se leen sin scroll lateral. |
| Nuevo ingreso | Cambiar entre Esperado, Líquido y Perdido; alternar origen, cliente/proyecto, reparto de socios y registro en Bolsillo. Los campos aparecen en un orden estable y no desplazan las acciones fuera del modal. |
| Hosting | Crear/editar, crear cliente dentro del modal y recorrer los campos de vigencia, modalidad y cobro. Las acciones apilan en Celular. |
| Extracto | Crear un extracto, editar encabezado y agregar una transacción. El formulario, la carga de PDF y los botones se mantienen dentro del viewport. |

## Evidencia de ejecución

Guardar una fila por hallazgo en la ficha o PR:

| Fecha | Commit | Perfil | Sección/modal | Resultado | Evidencia o defecto |
|---|---|---|---|---|---|
| AAAA-MM-DD | SHA | 412 × 915 | Bolsillo | OK/Falla | captura, video o enlace al issue |

### Trazabilidad focalizada PA-103 — defecto de Bolsillo

Esta ejecución focalizada registra el hallazgo que surgió del recorrido móvil
de PA-103. No sustituye la matriz completa de 60 recorridos ni afirma resultados
para tabs que no se ejecutaron en esta corrección.

| Fecha | Commit | Perfil | Sección/modal | Resultado | Evidencia o defecto |
|---|---|---|---|---|---|
| 2026-08-28 | `fix/28082026-responsive-accounting-pocket` | 412 × 915 | Bolsillo | OK automatizado | Tarjetas sin tabla ni scroll lateral; chips atómicos; acción inicial de 44 px sin superposición; editar, borrar, ordenar y acumulado filtrado cubiertos por Playwright. |
| 2026-08-28 | `fix/28082026-responsive-accounting-pocket` | 412 × 915 | Ingresos Lista/Agrupada | OK automatizado | La fila compacta cabe sin scroll; el tipo no se parte y el menú inicial abre en ambas vistas. |
| 2026-08-28 | `fix/28082026-responsive-accounting-pocket` | 412 × 915 | Cuentas de cobro Lista/Agrupada | OK automatizado | La fila compacta cabe sin scroll; estado/origen no se parten y el menú inicial abre en ambas vistas. |
| 2026-08-28 | `fix/28082026-responsive-accounting-pocket` | 835/1195/1440/2560 | Bolsillo | OK automatizado | La tabla priorizada conserva el saldo corrido y no desborda en los cuatro perfiles superiores. |
| 2026-08-28 | `fix/28082026-responsive-accounting-pocket` | Auditoría de código | Otros nueve tabs contables | Revisado, ejecución pendiente | Resumen, Gastos, Hostings, Recurrentes, Ads y Tarjetas ya declaran prioridad `compact/portrait/landscape`; Extractos, Historial y Configuración usan layouts especializados. No se confirmó en ellos la tabla rígida de ocho columnas de Bolsillo. Conservan pendiente su recorrido visual dentro de la matriz PA-103 completa. |
| 2026-09-26 | `fix/26092026-accounting-row-actions-notes` | 412 × 915 y 835 × 1195 | Tarjetas, Cuentas de cobro, Ingresos, Hostings | OK automatizado | Las tablas `menu-start` dejan de reservar ancho a columnas ocultas: sin franja en blanco a la derecha, sin scroll lateral en Tarjetas, Ingresos y Cuentas de cobro compactas, kebab de 44 px en su track de 56 px y el menú de Hostings abre con Detalle e historial a 412 px (Playwright). |
| 2026-09-26 | `fix/26092026-accounting-row-actions-notes` | 5 perfiles | Extractos (detalle) y Hostings (alta de cliente) | OK automatizado | La transacción angosta encabeza con su acción inicial y conserva la compra agregada; el CTA de Hostings sigue alcanzable (especiales responsive). |
| 2026-09-26 | `fix/26092026-accounting-row-actions-notes` | 412 × 915 | Hostings y Extractos | Corregido y automatizado | Hostings desbordaba y partía el nombre del cliente letra por letra: Valor/mes pasa al detalle agrupado y la fila cabe sin scroll. En la tarjeta de transacción el monto se partía en dos líneas; ahora ocupa una (Playwright). |

Una ejecución se considera completa cuando existen 60 resultados de sección y
los seis casos de modal en los cinco perfiles obligatorios. Si se corrige una
falla, repetir la fila afectada y una fila vecina que use el mismo componente.
