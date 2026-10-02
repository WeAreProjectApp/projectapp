# Intereses en módulos y portada de propuestas

El cliente puede explorar el catálogo vigente desde **Inversión → Explorar módulos adicionales**. El modal muestra el video disponible, categorías y detalles; **Guardar mi interés** registra una selección pendiente. No modifica el alcance contratado, los PDF, el precio ni el plazo.

En **Panel → Propuestas → General** se consulta la lista y su última actualización. Actividad conserva cada cambio. Después de conversar con el cliente, el administrador edita el alcance y la inversión con las herramientas existentes. No se envían correos nuevos ni se aprueban módulos automáticamente.

La portada con tarjetas muestra una guía inicial, repetible desde el botón de ayuda, y dos accesos abajo a la derecha: **Módulos adicionales** y **Programa de alianza**. Abren las vistas generales en otra pestaña y desaparecen al entrar en una tarjeta.

## Contrato de datos

- El catálogo público devuelve un `id` estable por módulo junto al contenido localizado existente.
- `GET/PUT /api/proposals/<uuid>/module-interests/`: consulta o reemplaza la selección con `{ "module_ids": [1, 2] }`; devuelve `modules` (instantáneas bilingües) y `updated_at`.
- Selección vacía retira intereses. Guardados idénticos no crean eventos. Módulos desactivados ya guardados se pueden conservar o retirar; no se admiten intereses nuevos en módulos inactivos.
- Propuestas inactivas devuelven 404; vencidas, 410. Las vistas previas administrativas no escriben. Se conserva el throttling público.
- `track-calculator/` devuelve 410. Los PDF se basan en el alcance guardado y rechazan sobreescrituras públicas por `selected_modules`.

## Transición de precios

Las migraciones 0274–0275 agregan los intereses y materializan los recargos existentes en `total_investment`. La 0275 usa modelos históricos y conserva las selecciones contratadas, los documentos emitidos y los registros anteriores. El importe especial y la referencia original de un descuento anterior se conservan mediante una instantánea hasta editar la inversión, la moneda o el descuento. Los porcentajes de cuotas, hosting y descuentos siguen vigentes.

La migración de datos es irreversible: no reconstruye porcentajes retirados al bajar de versión. El despliegue debe conservar el backup previo y aplicar las migraciones antes de servir el código nuevo; nunca se ejecutan en el worktree. Ante una reversión operativa se restaura el backup siguiendo el procedimiento de despliegue, sin intentar deducir el importe base desde el nuevo total.

## Limpieza y compatibilidad

Se retiraron el multiplicador de recargos y los avisos de un total personalizado
del panel, las propiedades de la calculadora en resumen/cierre y las ramas de
reescritura formal de PDF que ya no tenían consumidores. Pagos y hosting usan
la inversión manual. Los nombres históricos `selected_modules` e
`is_calculator_module` siguen siendo necesarios para interpretar el alcance
guardado; no representan intereses nuevos ni recalculan precios. El total
efectivo de la API permanece como alias compatible del importe acordado.

## Verificación

Pruebas focales de API, migración, importes manuales, modal, errores recuperables, guía y accesos exclusivos de portada. El generador de propuestas ficticias usa intereses del catálogo activo. Las pruebas crean sus datos en SQLite aislado. No se usan bases reales ni se envían mensajes.
