"""The versioned rule catalog and the fixer registry.

Rules register with ``@rule(...)`` in ``rules/<domain>.py``; fixers with
``register_fixer`` (usually next to their rule, merges in ``fixes/``). The
catalog imports every module once, so adding a rule never edits this file
unless it adds a module.
"""
from dataclasses import dataclass
from importlib import import_module

from django.core.exceptions import ImproperlyConfigured

from content.services.data_integrity.types import DOMAIN_LABELS, DOMAINS, EXISTING_TOOL, FIX_KINDS, REPORT_ONLY, SEVERITIES

CATALOG_VERSION = '1.2.1'
RULE_MODULES = tuple(f'content.services.data_integrity.rules.{name}' for name in (
    'clients', 'projects', 'documents', 'communications', 'accounting', 'proposals', 'naming',
))
FIXER_MODULES = (
    'content.services.data_integrity.fixes.merge_clients',
    'content.services.data_integrity.fixes.merge_folders',
    'content.services.data_integrity.fixes.organize_documents',
)

_RULES = {}
_FIXERS = {}
_loaded = False


@dataclass(frozen=True)
class Rule:
    id: str
    domain: str
    severity: str
    title: str
    description: str
    fix_kinds: tuple
    detect: object
    group: bool = False
    full_sweep_only: bool = False
    version: int = 1

    def payload(self):
        return {
            'id': self.id, 'version': self.version, 'domain': self.domain,
            'domain_label': DOMAIN_LABELS[self.domain], 'severity': self.severity,
            'title': self.title, 'description': self.description,
            'fix_kinds': list(self.fix_kinds), 'group': self.group,
            'full_sweep_only': self.full_sweep_only,
            'resolution': resolution(self.id),
        }


def rule(*, id, domain, severity, title, description, fix_kinds, group=False,
         full_sweep_only=False, version=1):
    """Register ``detect(scope) -> iterable[Finding]`` as a catalog rule."""
    if domain not in DOMAINS or severity not in SEVERITIES:
        raise ImproperlyConfigured(f'Rule {id}: unknown domain or severity')
    unknown = set(fix_kinds) - set(FIX_KINDS) - {REPORT_ONLY, EXISTING_TOOL}
    if unknown or not fix_kinds:
        raise ImproperlyConfigured(f'Rule {id}: invalid fix kinds {sorted(unknown)}')

    def register(detect):
        if id in _RULES:
            raise ImproperlyConfigured(f'Rule {id} is registered twice')
        _RULES[id] = Rule(id=id, domain=domain, severity=severity, title=title,
                          description=description, fix_kinds=tuple(fix_kinds), detect=detect,
                          group=group, full_sweep_only=full_sweep_only, version=version)
        return detect
    return register


def register_fixer(rule_ids, fixer):
    """Attach one fixer instance to the (rule, fixer.kind) pairs it handles."""
    if fixer.kind not in FIX_KINDS:
        raise ImproperlyConfigured(f'Fixer {type(fixer).__name__}: unknown kind {fixer.kind}')
    for rule_id in ([rule_ids] if isinstance(rule_ids, str) else rule_ids):
        key = (rule_id, fixer.kind)
        if key in _FIXERS:
            raise ImproperlyConfigured(f'Fixer for {key} is registered twice')
        _FIXERS[key] = fixer
    return fixer


def _load():
    global _loaded
    if not _loaded:
        for module in RULE_MODULES + FIXER_MODULES:
            import_module(module)
        _loaded = True


def rules():
    _load()
    order = {domain: index for index, domain in enumerate(DOMAINS)}
    return sorted(_RULES.values(), key=lambda item: (order[item.domain], item.id))


def get_rule(rule_id):
    _load()
    return _RULES.get(rule_id)


def get_fixer(rule_id, kind):
    _load()
    return _FIXERS.get((rule_id, kind))


def catalog_payload():
    return {'catalog_version': CATALOG_VERSION, 'rules': [
        {**item.payload(), 'fixable_kinds': sorted(kind for (rule_id, kind) in _FIXERS if rule_id == item.id)}
        for item in rules()
    ]}


RESOLUTIONS = {
    'CL4': ('manual', 'Clientes: revisar el borrado y sus bloqueos.'),
    'CL6': ('manual', 'Clientes: revisar las relaciones y rastros conservados.'),
    'CL5': ('manual', 'Proyectos: revisar y elegir un propietario de rol cliente.'),
    'CM5': ('manual', 'Enlaces seguros: revisar cliente y proyecto sin leer el secreto.'),
    'CM6': ('report_only', 'El mensaje enviado y sus adjuntos son evidencia; no se reescriben.'),
    'DC3': ('existing_tool', 'Documentos: usar la vista previa de asociación de carpeta.'),
    'DC6': ('existing_tool', 'Documentos: usar el flujo de restauración del archivado.'),
    'DC8': ('manual', 'Documentos: revisar los integrantes y el cliente del hilo.'),
    'DC12': ('report_only', 'Conservar la numeración emitida; revisar el origen de la duplicación.'),
    'PJ2': ('manual', 'Revisar el traslado auditado y la procedencia conservada.'),
    'PJ3': ('existing_tool', 'Proyectos: adoptar registros o limpiar contenedores con su vista previa.'),
    'PJ5': ('manual', 'Usar el aprovisionamiento controlado; consultar no crea raíces.'),
    'PJ8': ('manual', 'Revisar cliente, proyecto y evidencia sin reescribir historia.'),
    'PJ9': ('manual', 'Revisar el índice original del borrado y la procedencia.'),
    'AC3': ('manual', 'Contabilidad: identificar el ingreso válido antes de actuar.'),
    'AC4': ('manual', 'Contabilidad: identificar el recurrente válido antes de archivarlo.'),
    'AC8': ('existing_tool', 'Contabilidad: asociar el contexto de facturación con su vista previa.'),
    'AC9': ('manual', 'Contabilidad: anular la cuenta incorrecta mediante su flujo.'),
    'AC10': ('manual', 'Contabilidad: editar el borrador o anular y sustituir la cuenta emitida.'),
    'AC11': ('manual', 'Contabilidad: editar el reparto con validación e historial.'),
    'AC12': ('manual', 'Contabilidad: revisar la liquidación, reversión o residuo.'),
    'AC13': ('manual', 'Contabilidad: revisar el movimiento y su registro; no reconstruir importes.'),
    'PR2': ('manual', 'Propuestas: asociar explícitamente el cliente correcto.'),
    'PR3': ('existing_tool', 'Comercial: usar la reasignación auditada del proyecto de la propuesta.'),
    'PR4': ('manual', 'Propuestas: revisar la aprobación y su proyecto.'),
    'PR5': ('existing_tool', 'Comercial: reasignar al proyecto vigente del mismo cliente.'),
    'PR8': ('manual', 'Propuestas: identificar la propuesta válida antes de archivarla.'),
    'PR9': ('report_only', 'El precio histórico es evidencia; no se reconstruye por inferencia.'),
}


def resolution(rule_id):
    via, reason = RESOLUTIONS.get(rule_id, ('engine', 'Corrección reversible con vista previa, motivo e historial.'))
    return {'via': via, 'reason': reason}
