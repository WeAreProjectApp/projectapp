### FLOW: `public-additional-modules-explainer`

- **Módulo:** public
- **Rol:** invitado
- **Prioridad:** P2
- **Rutas:** `/:locale/additional-modules` y
  `/:locale/additional-modules/share/:uuid`
- **Interacción:** Encontrar la tarjeta del video explicativo debajo del título
  (primer bloque antes del primer módulo), reproducirlo en el mismo lugar con
  sonido y controles nativos, y usar el enlace directo al archivo si el
  navegador no puede reproducirlo. En inglés la tarjeta no aparece hasta tener
  el render en ese idioma. Si el interruptor del panel lo oculta (o, en un
  enlace compartido, el interruptor de ese enlace), la tarjeta no aparece y el
  encabezado se compacta.
- **Outcomes:** `display`, `success`, `failure`
- **Evidencia:** `ExplainerVideoCard.vue`, `useExplainerVideos.js`,
  `AdditionalModules/CatalogView.vue` (`showExplainer`), el flag
  `show_explainer_video` del payload público y
  `e2e/public/additional-modules.spec.js`.

- **Contenido audiovisual:** edición brag v2, 60 segundos en español con voz,
  música y subtítulos integrados. Fuentes originales conservadas.

- **Control de reproducción compartido:** el video sólo comienza al pulsar
  reproducir. Cambiar de ventana, ocultar la pestaña o salir de la página lo
  pausa; regresar no lo reanuda. Los controles nativos permiten continuar
  manualmente. Una carga tardía no reactiva una reproducción cancelada.
  La misma regla aplica a Alianza y propuestas, tanto en público como en panel.
- **Regresión:** `keeps the explainer paused after returning to its window`
  comprueba pausa y continuación manual con el MP4 real. Las pruebas unitarias
  del reproductor cubren pestaña oculta, restauración, carga tardía, cambio de
  fuente y retiro del componente.
