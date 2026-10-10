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

CATALOG_VERSION = '1.0.0'
RULE_MODULES = tuple(f'content.services.data_integrity.rules.{name}' for name in (
    'clients', 'projects', 'documents', 'communications', 'accounting', 'proposals', 'naming',
))
FIXER_MODULES = (
    'content.services.data_integrity.fixes.merge_clients',
    'content.services.data_integrity.fixes.merge_folders',
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
