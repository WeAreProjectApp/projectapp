# Unificación MCP por módulo — registro de cambios

Cambio incompatible de catálogo, con adaptación temporal por credencial y slug.

| Conector | Versión anterior | Versión nueva | Estado / destino |
|---|---|---|---|
| accounting | 1.3.0 | 2.0.0 | canonical → accounting |
| accounting-billing | 2.1.1 | 3.0.0 | deprecated → accounting |
| accounting-cards | 2.1.1 | 3.0.0 | deprecated → accounting |
| accounting-ledger | 2.3.0 | 3.0.0 | deprecated → accounting |
| additional-modules | 2.1.1 | 3.0.0 | deprecated → commercial |
| blog | 1.1.0 | 2.0.0 | deprecated → content |
| building-on-demand | 1.0.0 | 2.0.0 | deprecated → commercial |
| building-with-us | 1.0.0 | 2.0.0 | deprecated → commercial |
| clients | 1.1.0 | 2.0.0 | deprecated → commercial |
| commercial | 2.1.1 | 3.0.0 | canonical → commercial |
| communications | 2.1.1 | 3.0.0 | canonical → communications |
| content | 2.1.1 | 3.0.0 | canonical → content |
| diagnostics | 1.1.0 | 2.0.0 | deprecated → commercial |
| documents | 4.0.0 | 5.0.0 | canonical → documents |
| linkedin-personal | 1.1.0 | 2.0.0 | deprecated → content |
| operations | 2.1.0 | 3.0.0 | canonical → operations |
| partnership-program | 2.1.1 | 3.0.0 | deprecated → commercial |
| projects | 3.0.0 | 4.0.0 | canonical → projects |
| proposals | 2.2.1 | 3.0.0 | deprecated → commercial |
| tasks | 2.1.0 | 3.0.0 | canonical → tasks |

## Cambios

- Ocho catálogos canónicos: General, Comercial, Plataforma, Documentos, Comunicaciones, Contenido, Contable y Tareas.
- Hosting, suscripciones, conciliación, contexto de cuentas y contratos de facturación se publican en Contable; el origen Proyectos permanece únicamente como compatibilidad por credencial.
- Una familia de ingresos conserva IVA, reparto, períodos, restricciones de pagos/cuentas, concurrencia y confirmación; las listas se paginan y los alcances específicos de esperados conservan su límite.
- Se califican los nombres de carpetas documentales y de comunicaciones y se pluralizan los listados contables. Los nombres anteriores no se anuncian en catálogos canónicos.
- Configuración e historial contable tienen un solo nombre canónico; el tablero anual y las estadísticas descriptivas se conservan porque sus resultados son distintos.
- Crear/editar contenido de blog o LinkedIn requiere confirmación porque puede publicar o programar; las vías anteriores conservan esa protección. La confirmación se consume antes de llamar al proveedor y conserva el estado de fallo para evitar publicaciones repetidas.
- Credenciales existentes conservan el catálogo anterior y permisos efectivos. Las nuevas pueden derivar un alcance equivalente, actor y vencimiento desde una credencial de origen; cada secreto se muestra una sola vez.
- El panel separa conectores canónicos de los que están en retirada. Muestra reemplazo, uso antiguo y verificación de consumidores; permite revocar accesos retirados, pero no emitir tokens inservibles.
- Inventario y chequeos de propiedad, duplicación, esquemas y versiones en CI; evidencia diaria de uso con 90 días de conservación y observación periódica.

## Compatibilidad y retiro

No se elimina ningún conector por fecha de commit. La migración 0293 inicia la ventana al desplegarse: mínimo 30 días desde publicación y 14 días continuos sin llamadas antiguas, con consumidores inventariados/migrados y sin confirmaciones pendientes. Un fallo de observación reinicia la ventana. El retiro se previsualiza y aplica explícitamente; devuelve CONNECTOR_RETIRED y conserva auditoría.

Esta entrega prepara el retiro; no acredita despliegue ni migración de Claude web u otros hosts. Guion completo: [MCP_MODULE_UNIFICATION.md](../MCP_MODULE_UNIFICATION.md).
