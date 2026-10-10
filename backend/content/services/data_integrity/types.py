"""Shapes shared by rules, fixers and the engine."""
from dataclasses import dataclass, field

from rest_framework.exceptions import ValidationError

DOMAINS = ('clients', 'projects', 'documents', 'communications', 'accounting', 'proposals', 'naming')
DOMAIN_LABELS = {
    'clients': 'Clientes', 'projects': 'Proyectos', 'documents': 'Documentos',
    'communications': 'Comunicaciones', 'accounting': 'Contabilidad',
    'proposals': 'Propuestas', 'naming': 'Nombres',
}
SEVERITIES = ('high', 'medium', 'low')

# Fix kinds a fixer can implement. Every finding lists the kinds it offers;
# REPORT_ONLY and EXISTING_TOOL never write through the engine.
RELINK, RENAME, REORDER, SYNC_COPY, ARCHIVE = 'relink', 'rename', 'reorder', 'sync_copy', 'archive'
MERGE_CLIENTS, MERGE_FOLDERS = 'merge_clients', 'merge_folders'
FIX_KINDS = (RELINK, RENAME, REORDER, SYNC_COPY, ARCHIVE, MERGE_CLIENTS, MERGE_FOLDERS)
REPORT_ONLY = 'report_only'
EXISTING_TOOL = 'existing_tool'


class IntegrityConflict(ValidationError):
    """A 409 with a stable ``code``. Raised, never returned, once writes began."""

    status_code = 409

    def __init__(self, message, *, code, **details):
        super().__init__({'detail': message, 'code': code, **details})


@dataclass(frozen=True)
class RecordRef:
    """A row a finding is about. ``label`` is for people and is never hashed."""

    model: str  # Django label_lower, e.g. 'content.document'
    pk: int
    label: str = ''

    def key(self):
        return (self.model, self.pk)

    def payload(self):
        return {'model': self.model, 'id': self.pk, 'label': self.label}


@dataclass
class Finding:
    """One detected problem.

    ``evidence`` holds only the defining facts (ids, normalized keys, raw
    values), never labels, timestamps or the scope, so the fingerprint is the
    same in every scan. ``inputs`` describes what the operator must choose
    (``{name: {'label', 'options': [{'value', 'label'}], 'required'}}``) and
    ``suggestion`` the proposed params. ``tool`` names the existing MCP tool
    for EXISTING_TOOL findings: ``{'connector', 'name', 'arguments'}``.
    """

    rule_id: str
    subjects: tuple
    evidence: dict
    message: str = ''
    fix_kinds: tuple = ()
    inputs: dict = field(default_factory=dict)
    suggestion: dict = field(default_factory=dict)
    tool: dict = None
    fingerprint: str = ''


@dataclass
class FixPlan:
    """What a fixer will do for one finding, computed without writing.

    ``closure`` lists every (model_label, pk) the writer can touch, including
    signal side effects: the engine snapshots it before and after to record
    exact items. ``changes`` is the human preview ``[{model, id, label, field,
    before, after}]``. ``guards`` are facts recorded at apply time that block
    an undo when they change. ``context`` is private to the fixer.
    """

    fix_kind: str
    params: dict
    closure: list = field(default_factory=list)
    changes: list = field(default_factory=list)
    blockers: list = field(default_factory=list)
    guards: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    context: dict = field(default_factory=dict)


def blocker(code, message, records=None):
    entry = {'code': code, 'message': message}
    if records:
        entry['records'] = [ref.payload() if isinstance(ref, RecordRef) else ref for ref in records]
    return entry
