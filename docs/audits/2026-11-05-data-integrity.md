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
