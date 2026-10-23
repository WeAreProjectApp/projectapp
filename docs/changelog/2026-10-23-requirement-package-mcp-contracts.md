# Paquetes por talla — contratos MCP

| Conector | Versión anterior | Versión nueva |
|---|---|---|
| commercial | 6.1.0 | 6.2.0 |
| offerings | 1.0.0 | 2.0.0 |
| programs | 2.0.0 | 3.0.0 |

`offerings` cambia la escritura del catálogo: cupos `xs_count`, `s_count`,
`m_count`, vigencia y descuento sustituyen horas y tarifa por hora. Los ajustes
incluyen valores internos COP por talla, factores de mercado y cupos propios de
Alianza. Los campos históricos de horas permanecen de sólo lectura en el
contrato del modelo. Se conservan los nombres técnicos de las herramientas y
las rutas para mantener su identidad.

`programs` presenta el beneficio mensual de Alianza por tallas, independiente
del catálogo de paquetes. La composición de los acuerdos nuevos se guarda en
`requirement_allowance`; los acuerdos históricos retienen sus condiciones.
Los clientes que procesaban el beneficio como horas deben leer ahora los
cupos XS/S/M. La modalidad de tres años no incluye ese beneficio.

`commercial` incorpora la terminología y las condiciones de paquetes por talla
en propuestas. Los campos nuevos de sección conviven con la lectura histórica.
El contexto interno de cambio y factor se excluye del contrato público.

Las versiones se declaran en `CATALOG_VERSIONS`, sin alterar los catálogos
fuente históricos. Las huellas se regeneran mediante
`mcp_schema_report --slug commercial --slug offerings --slug programs --write-fingerprints`
con `projectapp.settings_test`. El diff sólo actualiza estos tres conectores.
La prueba parametrizada del registro comprueba cada versión y SHA-256.

Guía funcional: [paquetes de requerimientos](../REQUIREMENT_PACKAGES.md).
