# IVA configurable al liquidar — contratos MCP

| Conector | Versión anterior | Versión nueva |
|---|---|---|
| accounting | 2.0.0 | 2.1.0 |
| accounting-ledger | 3.0.0 | 3.1.0 |

Las herramientas de liquidación, vista previa y corrección admiten la lista
opcional `vat_updates`: ingreso original, porcentaje y captura opcional antes
de IVA o con IVA incluido. Las respuestas de vista previa incluyen el desglose
efectivo y los bloqueos de edición por ingreso. Los contratos anteriores que
omiten la lista conservan su comportamiento y los pagos heredan el IVA del
original. Se mantienen permisos, confirmaciones, concurrencia y reversión.

Las versiones públicas posteriores a la consolidación se declaran sin alterar
las versiones históricas de sus catálogos fuente. Las huellas se regeneran con
`mcp_schema_report --write-fingerprints` y se verifican mediante las pruebas del
registro. Contrato funcional: [liquidación](../accounting-settlement.md).
