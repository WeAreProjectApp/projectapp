# PA-227 — Auditoría de modo oscuro de Panel y Plataforma

**Estado: implementación en PR; aceptación de navegador pendiente de DevQA.**
No se presenta el barrido como terminado. El operador centralizó el servidor de
DEV durante el recorrido: esta sesión apagó sus dos pares de servidores y los
navegadores que conducía. DevQA tiene la solicitud para continuar después de su
QA responsive. Las pruebas automatizadas se ejecutan exclusivamente en CI.

## Corte, entorno y alcance

- Main inicial: `b01448a2d01a50dfb712f18c14cbc348b875621a`.
- Rama: `fix/06112026-pa227-dark-mode`; [PR #558](https://github.com/WeAreProjectApp/projectapp/pull/558).
- [Inventario](inventory.json): 106 páginas, 70 Panel y 36 Plataforma, reconciliadas
  una a una con `viewCatalog.js`, los menús y `frontend/pages/`. Las redirecciones
  siguen en el inventario; no cuentan como una segunda vista aprobada.
- DEV desechable: SQLite, media privada propia, correo capturado, caché local y
  datos ficticios. Seed 227, fecha ancla 2026-11-06: 32 proyectos y 17 perfiles.
  El proyecto 31, sin fases, reproduce el estado del proyecto 71 del triaje.
- Roles: superusuario y staff de Panel, administrador y cliente de Plataforma.
- Tamaños: 412×915, 835×1195, 1195×835, 1440×900 y 2560×1440.
- Navegador de la evidencia complementaria: Chromium 151.0.7922.34. Esta sesión
  no dispone de la extensión de Chrome de ChatGPT; el conector de navegador
  tampoco encontró su instalación de Chrome. DevQA debe confirmar su propio
  acceso. Chromium no acredita la validación solicitada en esa extensión.

## Cómo leer la evidencia

| Archivo | Contenido |
|---|---|
| [coverage.csv](coverage.csv) | Cada ruta, rol y tamaño esperado; captura anterior/intermedia y validación final pendiente. |
| [matrix.csv](matrix.csv) | 2385 registros de observación: superficie, módulo, ruta solicitada/real, rol, tamaño, modo, estado, resultado, bloqueo y captura. |
| [findings.csv](findings.csv), [findings.json](findings.json) | 13 grupos de contraste o herencia del tema, con rutas observadas y ejemplos. |
| [Galería](gallery.html), [índice](evidence-index.json) | 27 capturas representativas versionadas, anteriores e intermedias. |
| [Resumen](evidence-summary.json) | Conteos y límites de la evidencia. |

Se conservaron **2393 capturas JPG y los JSON originales** en
`/home/dev-env/.local/state/projectapp-qa/PA-227/evidence/`, agrupados por fase y
superficie. La matriz referencia ese archivo local completo; las 27 capturas de
la galería viajan con el PR. El worktree y el archivo de evidencia se conservan
para el turno de DevQA.

`no-solid-text-finding` significa que el medidor no encontró texto bajo su umbral
sobre un fondo calculable en esa observación; **no significa aprobado final**.
Las observaciones posteriores se hicieron mientras cambiaba el código y deben
repetirse sobre el SHA que sirva DevQA. `redirect` registra el destino real;
`blocked` exige volver a entrar con el dato, rol o runtime necesario.

El medidor compone colores sRGB y sus opacidades. Los JSON conservan resultados
crudos, incluidos elementos en transición y fondos no inferibles. La matriz
separa fondos de imagen/degradado que requieren inspección y descarta como texto
los valores de inputs nativos de color/checkbox. Las capturas iniciales señalan
con contorno naranja hasta doce hallazgos por pantalla. Los resultados crudos no
son una certificación WCAG ni una lista de defectos confirmados sin revisión.

## Hallazgos reproducidos y corrección

Referencia para texto normal: **4,5:1**, [WCAG 2.2, 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
Los fallos de herencia se registran aparte del contraste.

| Grupo | Reproducción y problema | Cambio |
|---|---|---|
| C01 | Plataforma → Proyectos → Resumen, admin/cliente: rótulos 3,10:1; aviso sin fases y ayuda de Acciones 2,63:1. También tablas, ayudas y estados secundarios. | Tokens de texto del tema en lugar de verdes con opacidad fija. |
| T01 | En Resumen, abrir Personalizar interfaz o Agregar fases: portal en body fuera del contenedor oscuro. Revisar también Editar proyecto y menús. | El documento lleva el modo activo; los portales reciben los mismos tokens. Al salir se retiran sus colores personalizados. |
| C02–C03 | Panel → Proyectos: «Plataforma» de la miga 2,85:1; rótulos débiles en menús de ambas superficies. | Colores secundarios del tema, sin opacidad adicional. |
| C04 | Número seleccionado en paginación: texto claro sobre el acento claro, 1,45:1. | Par fondo/primer plano de selección en ambos modos. |
| C05 | Propuestas: estado Activa/Activas/Visible, badges de calor y ayudas de precios de hosting. | Pares de colores de estado y ayudas sin opacidad fija. |
| C06 | Seleccionar un color muy claro u oscuro: acciones, avatar o enlaces heredan un primer plano incompatible. | Cálculo WCAG de primer plano y tono de enlace; hover mantiene el contraste de la acción. |
| C07 | Fondo claro en oscuro reduce el contraste; fondo oscuro fuerza blanco sobre avatar y badge claros (≈1,05:1 y 1,09:1). | La portada conserva superficies opacas del modo; se elimina la regla que forzaba blanco en todos los elementos. |
| C08–C09 | Formularios de bugs/solicitudes del cliente: placeholders de baja opacidad y contadores del filtro activo. | Texto secundario legible y contadores sin opacidad adicional. |
| C10 | Contabilidad → Extractos: «No aplica» y «Antes del inicio de extractos» con opacidad. | Se conserva el color secundario sin rebajarlo otra vez. |
| C11 | Comparación en claro: texto secundario sobre el fondo de página y placeholders. | Tokens claros más legibles. |
| T02 | Building with Us → Contrato: títulos 2,86:1 y párrafos 1,52:1 en oscuro. | Selector del renderer Markdown corregido para alcanzar el contenido. Revalidación pendiente. |

El recorrido intermedio de Resumen registró 50 capturas con cinco paletas y 20
con portadas sólidas claras/oscuras, en ambos modos y cinco tamaños, sin hallazgos
de texto sólido tras esos cambios. Esto no reemplaza el retorno de DevQA sobre
la versión final, los controles ni los estados restantes.

## Pendientes y requisitos para desbloquear

1. DevQA confirma recepción/turno y sirve el SHA indicado en la solicitud.
2. Completar las vistas y estados que quedaron interrumpidos: pestañas,
   filtros vacíos, formularios, validación, rechazo de servidor, menús y modales.
   La matriz no convierte los timeouts ni el cierre del runtime en fallos del producto.
3. Volver a probar cada grupo en su ruta/rol original y comparar en claro,
   incluidos placeholders, Markdown, hover/foco, portada + color y salida a otro layout.
4. Los detalles por ID requieren un registro ficticio que pertenezca al rol.
   Los formularios de bugs/cambios necesitan un requerimiento asociado; el
   proyecto 31 reproduce cero fases y no sirve para completar ese envío.
   Las rutas restringidas requieren superusuario/administrador según el módulo.
5. Resolver en esta rama cualquier fallo informado y repetir CI/QA afectados.

Solicitud compartida:
`/home/dev-env/.local/state/projectapp/devqa/requests/pa227-dark-mode.md`.
Respuesta esperada:
`/home/dev-env/.local/state/projectapp/devqa/results/pa227-dark-mode.md`.
Sólo DevQA confirma el turno; una solicitud en la cola no equivale a recepción.

## Pruebas y registro de CI

No se ejecutaron Jest, pytest ni specs Playwright localmente. El navegador
complementario recorrió el DEV aislado sin usar un runner de tests.

Se añadieron regresiones de contraste para Resumen por rol, diálogos,
personalización, portadas, miga de Proyectos y Markdown. La navegación entra por
la interfaz y verifica datos ficticios. Los casos visuales adjuntan capturas en
CI; las utilidades verifican el cálculo de contraste y la elección de primer plano.

La primera ejecución del quality gate rechazó la entrada directa de los nuevos
casos display; se corrigió para entrar por la portada y abrir el proyecto por UI.
El [quality gate posterior](https://github.com/WeAreProjectApp/projectapp/actions/runs/42234806413)
aprobó `c48a9fd1cb411f382e927b4b8deb3c0f0d0f4869`. Las suites de ese corte
quedaron en cola y serán sustituidas por la ejecución del nuevo HEAD. El enlace,
SHA probado y resultado definitivo se registran en el PR y en el informe de
cierre; **aún no se afirma CI completo verde**.

La auditoría estática de flujos encontró cubiertos los cuatro flujos afectados
(Resumen, navegación de Plataforma, Proyectos del Panel y Contrato). El inventario
global conserva 31 flujos parciales previos; no se certifica cobertura total del
producto. Los estilos no añaden rutas ni capacidades al Mapa de vistas.
