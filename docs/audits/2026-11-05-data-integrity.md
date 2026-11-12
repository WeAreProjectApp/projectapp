# Integridad de datos — validación de sesión

## Alcance

Módulo MCP propio, catálogo 1.2.0 (51 reglas, 23 corregibles), revisiones
persistentes y programadas, alcances contables individuales, decisiones auditadas,
panel y radar. Migraciones aditivas content.0305–0306. No acredita despliegue.

## Evidencia local

- Django check y makemigrations --check --dry-run: sin errores ni diferencias.
- Inventario MCP: un dueño canónico por módulo; Integridad publica 13 herramientas
  (10 de negocio y 3 de control), Proyectos conserva catálogos compatibles.
- Lotes focales SQLite: observaciones/organización, alcances financieros, migración,
  programación y recuperación, permisos, MCP canónico/legacy y radar en verde.
- Frontend unit: 12 pruebas nuevas y una regresión del contador de vistas en verde.
- Calidad estática focal: cero errores y cero advertencias; el control general usa
  semántica soft y el verificador conserva además su control estricto focal.
- Mapa de vistas: 137 páginas/entradas. Contrato responsivo: 121 vistas visuales,
  16 redirects, cinco perfiles. El registro E2E y sus tags están sincronizados.
- Playwright: 15 escenarios funcionales aprobados (revisión, corrección,
  aceptación, reapertura, historial y deshacer, con errores y bloqueos).
- Lote responsive canónico dashboard-visual-2: 5/5 celdas únicas aprobadas,
  cero reintentos, sin desbordamiento y con confirmación del modal alcanzable.
  Los escenarios interceptan HTTP para aislar datos, sin escrituras de producción.
- Auditoría de flujos: los cuatro flujos nuevos cubren display, success, error y
  failure con evidencia válida. Las 31 brechas parciales del resto del proyecto
  permanecen fuera de este alcance.
- El cliente HTTP real queda cubierto desde Axios; una importación incorrecta
  detectada durante la validación ya está corregida.

## Regresión de los contratos canónicos

Integridad 1.0.1 declara el filtro por huella de los hallazgos persistidos y
rechaza argumentos desconocidos antes de ejecutar también sus controles comunes.
El inventario de esquemas incluye documentos, proyectos e integridad sin ampliar
los techos ni las excepciones de drift. Su contrato coincide en los cuatro canales
de publicación y queda registrado con su nueva huella.

- 17 casos de transporte prueban los mismos escenarios de integridad sobre su
  conector canónico y el catálogo anterior de Proyectos.
- La última ronda aprobó 16 casos contables, 9 controles de esquemas y 8 casos
  canónicos/de confirmación y deshacer. Los lotes de comportamiento usan SQLite
  generado desde los modelos (`--nomigrations`); no sustituyen la evidencia
  independiente de migraciones MySQL ni la regresión documental con migraciones.
- Calidad semántica estricta en los tres archivos de comportamiento: 19 funciones
  de prueba, cero errores y cero avisos. El archivo de guardas conserva un aviso
  previo por ocho aserciones en una prueba de compatibilidad cuya lógica no cambió;
  sus aserciones permanecen completas.
- Las credenciales efímeras del fixture canónico tienen representación redactada
  para evitar que aparezcan en los diagnósticos de pytest.

## Contrato de datos de demostración

La prueba original reprodujo la falta de clasificación de los cuatro modelos
operativos nuevos. Se declaran como evidencia y bloqueo generados por ejecuciones
reales, sin inventar barridos ni decisiones durante la generación de ejemplos.
El reinicio de desarrollo libera el lease existente y elimina revisiones,
hallazgos y barridos antes de borrar usuarios, conservando la fila del mutex.
Las guardas de entorno y confirmación permanecen intactas.

La regresión focal aprobó ocho casos: clasificación completa de modelos, limpieza
del grafo de integridad, rechazo sin capacidad o confirmación, limpieza de los
grafos protegidos previos y repetibilidad de contactos. Calidad estricta de las
tres pruebas nuevas: cero errores y cero advertencias. La ejecución usa sólo
SQLite de pruebas, con `--nomigrations`; no ejecuta un reinicio del entorno.

## Condiciones operativas

El helper QA del fleet rechazó la coordenada de este entorno de desarrollo;
se aplicaron controles focales del worktree sin alterar esa guarda. El navegador
usa bibliotecas extraídas en el entorno local gitignorado porque el operador del
entorno no tiene sudo sin contraseña. No se modificaron paquetes del sistema.

Todos los administradores operan integridad financiera desde el módulo nuevo.
El Dashboard conserva su restricción sobre hallazgos contables. La revisión
interrumpida tiene un único reintento automático con otro ID; el worker antiguo
no puede publicar después. Las fallas y límites conservan el último resultado.

## Tras el despliegue

Activar el conector, migrar y verificar consumidores, comprobar una revisión real
de lectura y el barrido diario de Bogotá. El retiro del catálogo anterior requiere
su evidencia y las ventanas de 30/14 días documentadas, por separado del PR de implementación.
