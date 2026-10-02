"""Declarative per-section-type validation for ProposalSection.content_json.

Each entry in ``SECTION_CONTENT_SCHEMAS`` describes the expected *types* of the
known fields for one section type. The goal is to reject wrong types early
(e.g. a string where a list of steps is expected), NOT to reject legacy
content: every field is optional-when-absent and unknown keys always pass.

Spec grammar (plain Python literals, no external dependencies):

- ``str`` / ``bool``       -> isinstance check.
- ``dict`` / ``list``      -> must be a dict / list, no deeper checks.
- ``NUMERIC``              -> int/float or a Decimal-coercible numeric string
                              (mirrors ``safe_decimal`` in
                              ``content/services/proposal_totals_service.py``).
                              Rejects bool, list, dict and non-numeric strings.
- ``Nullable(inner)``      -> allows ``None``, otherwise validates ``inner``.
- ``[spec]``               -> value must be a list; every item validated
                              against ``spec`` (indices reported as ``[i]``).
- ``{'field': spec, ...}`` -> value must be a dict; ONLY listed fields are
                              checked and ONLY when present. Missing fields
                              and unknown keys always pass.

Shapes verified against ``DEFAULT_SECTIONS`` in
``content/services/proposal_service.py`` and ``formToJson`` in
``frontend/components/BusinessProposal/admin/sectionEditorUtils.js``.
"""

from decimal import Decimal, InvalidOperation


class _NumericMarker:
    """Sentinel spec: numeric value or numeric string (bool rejected)."""

    __slots__ = ()

    def __repr__(self):
        return 'NUMERIC'


#: Module-level marker meaning "int/float or Decimal-coercible numeric string".
NUMERIC = _NumericMarker()


class Nullable:
    """Spec wrapper: accepts ``None``, otherwise validates against ``inner``."""

    __slots__ = ('inner',)

    def __init__(self, inner):
        self.inner = inner

    def __repr__(self):
        return f'Nullable({self.inner!r})'


def _is_numeric(value):
    """True for int/float or a numeric string coercible via Decimal.

    Booleans are explicitly rejected (bool is a subclass of int). Numeric
    strings MUST pass: legacy content stores prices as strings and the
    backend coerces them via ``safe_decimal`` (``Decimal(str(value))``).
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            Decimal(value.strip())
        except (InvalidOperation, ValueError, ArithmeticError):
            return False
        return True
    return False


def _err(path, expected):
    return f'El campo «{path}» debe ser {expected}.'


def _validate(spec, value, path, errors):
    """Recursively validate ``value`` against ``spec``, appending errors."""
    if isinstance(spec, Nullable):
        if value is None:
            return
        _validate(spec.inner, value, path, errors)
        return

    if spec is NUMERIC:
        if not _is_numeric(value):
            errors.append(_err(path, 'numérico'))
        return

    if spec is str:
        if not isinstance(value, str):
            errors.append(_err(path, 'texto'))
        return

    if spec is bool:
        if not isinstance(value, bool):
            errors.append(_err(path, 'booleano'))
        return

    if spec is dict:
        if not isinstance(value, dict):
            errors.append(_err(path, 'un objeto'))
        return

    if spec is list:
        if not isinstance(value, list):
            errors.append(_err(path, 'una lista'))
        return

    if isinstance(spec, list):
        if not isinstance(value, list):
            errors.append(_err(path, 'una lista'))
            return
        item_spec = spec[0]
        for i, item in enumerate(value):
            _validate(item_spec, item, f'{path}[{i}]', errors)
        return

    if isinstance(spec, dict):
        if not isinstance(value, dict):
            errors.append(_err(path, 'un objeto'))
            return
        for field, field_spec in spec.items():
            if field not in value:
                continue  # missing fields always pass
            _validate(field_spec, value[field], f'{path}.{field}', errors)
        return

    raise TypeError(f'Unsupported schema spec: {spec!r}')


# ---------------------------------------------------------------------------
# Shared sub-schemas
# ---------------------------------------------------------------------------

_FR_ITEM = {
    'id': str,
    'icon': str,
    'name': str,
    'description': str,
    'price': Nullable(NUMERIC),
    'is_required': bool,
}

_FR_GROUP = {
    'id': str,
    'icon': str,
    'title': str,
    'description': str,
    'is_always_included': bool,
    'is_calculator_module': bool,
    'default_selected': bool,
    'selected': bool,
    'is_visible': bool,
    'is_invite': bool,
    'invite_note': str,
    'rawText': str,
    'items': [_FR_ITEM],
}

# Shape source: EMPTY_TECHNICAL_DOCUMENT_JSON in
# content/technical_document_defaults.py (the canonical empty technical
# document, which lives outside the view module). Note: the panel fragment
# keys in _TECHNICAL_FRAGMENT_ORDER (content/views/proposal.py) are UI
# groupings — e.g. 'intro', 'api', 'performance', 'backups' — and do NOT
# match content_json keys, so this schema follows the stored shape instead.
_TECHNICAL_DOCUMENT = {
    'purpose': str,
    'stack': list,
    'architecture': dict,
    'dataModel': dict,
    'growthReadiness': dict,
    'epics': [dict],
    'apiSummary': str,
    'apiDomains': list,
    'integrations': dict,
    'environments': list,
    'environmentsNote': str,
    'security': list,
    'performanceQuality': dict,
    'backupsNote': str,
    'quality': dict,
    'decisions': list,
}


# ---------------------------------------------------------------------------
# One schema per ProposalSection.SectionType value (17 types).
# ``index`` is intentionally never validated — the frontend injects it.
# ---------------------------------------------------------------------------

SECTION_CONTENT_SCHEMAS = {
    'greeting': {
        'proposalTitle': str,
        'clientName': str,
        'inspirationalQuote': str,
    },
    'executive_summary': {
        'title': str,
        'paragraphs': [str],
        'highlightsTitle': str,
        'highlights': [str],
    },
    'context_diagnostic': {
        'title': str,
        'paragraphs': [str],
        'issuesTitle': str,
        'issues': [str],
        'opportunityTitle': str,
        'opportunity': str,
    },
    'conversion_strategy': {
        'title': str,
        'intro': str,
        'steps': [{'title': str, 'bullets': [str]}],
        'resultTitle': str,
        'result': str,
    },
    'design_ux': {
        'title': str,
        'paragraphs': [str],
        'focusTitle': str,
        'focusItems': [str],
        'objectiveTitle': str,
        'objective': str,
    },
    'creative_support': {
        'title': str,
        'paragraphs': [str],
        'includesTitle': str,
        'includes': [str],
        'closing': str,
    },
    'development_stages': {
        'title': str,
        'intro': str,
        'currentLabel': str,
        'stages': [{
            'icon': str,
            'title': str,
            'description': str,
            'current': bool,
        }],
    },
    'process_methodology': {
        'title': str,
        'intro': str,
        'steps': [{
            'icon': str,
            'title': str,
            'description': str,
            'clientAction': str,
        }],
    },
    'functional_requirements': {
        'title': str,
        'intro': str,
        'groups': [_FR_GROUP],
        'additionalModules': [_FR_GROUP],
    },
    'timeline': {
        'title': str,
        'introText': str,
        'totalDuration': str,
        'phases': [{
            'title': str,
            'duration': str,
            'description': str,
            'tasks': [str],
            'milestone': str,
        }],
    },
    'investment': {
        'title': str,
        'introText': str,
        'totalInvestment': str,
        'currency': str,
        'whatsIncluded': [dict],
        'paymentOptions': [{'label': str, 'description': str}],
        'hostingPlan': {
            'title': str,
            'description': str,
            'specs': [dict],
            'hostingPercent': NUMERIC,
            'billingTiers': [{
                'frequency': str,
                'months': NUMERIC,
                'discountPercent': NUMERIC,
                'label': str,
                'badge': str,
            }],
            'renewalNote': str,
            'coverageNote': str,
            'freeMonths': NUMERIC,
            'freeMonthsVisible': bool,
            'freeMonthNote': str,
        },
        'modules': [{
            'id': str,
            'name': str,
            'price': NUMERIC,
            'included': bool,
            'is_required': bool,
        }],
        'paymentMethods': [str],
        'valueReasons': [str],
    },
    'proposal_summary': {
        'title': str,
        'subtitle': str,
        'kpis': [{'value': str, 'label': str, 'source': str}],
        'cards': [dict],
    },
    'final_note': {
        'title': str,
        'message': str,
        'personalNote': str,
        'teamName': str,
        'teamRole': str,
        'contactEmail': str,
        'signature': str,
        'commitmentBadges': [dict],
        'validityMessage': str,
        'thankYouMessage': str,
    },
    'next_steps': {
        'title': str,
        'introMessage': str,
        'steps': [dict],
        'ctaMessage': str,
        'primaryCTA': dict,
        'secondaryCTA': dict,
        'contactMethods': [dict],
        'validityMessage': str,
        'thankYouMessage': str,
    },
    'technical_document': _TECHNICAL_DOCUMENT,
    'value_added_modules': {
        'title': str,
        'intro': str,
        'module_ids': [str],
        'justifications': dict,
        'footer_note': str,
        # Per-module gating/terms keyed by module id. Free shape (dict) because
        # keys are dynamic module ids; each value carries {min_price_usd,
        # min_price_cop, duration_months, discretionary_note, terms_clauses,
        # terms}. `terms_clauses` is [{label, text}] and is the canonical legal
        # wording; `terms` is the flattened legacy string kept in sync from it.
        'conditions': dict,
        # Cross-cutting legal provisions for the whole section:
        # {title, clauses: [{label, text}]}.
        'general_terms': dict,
    },
    # PDF-only section (no web component): hour packages + scope-exclusion text.
    'commercial_conditions': {
        'title': str,
        'packagesTitle': str,
        'packagesIntro': str,
        # Hour-rate source: 'auto' (default — the PDF takes packages, rate and
        # currency straight from the HourPackage catalog on every generation)
        # or 'manual' (the catalog still owns names, hours, discounts and
        # currency; only the *rates* come from this proposal's manual values
        # below). Absent or unknown values behave as 'auto'. Type-only check by
        # design, like every other field here.
        'hourPackagesMode': str,
        # Whether the hour-packages block (title, intro, table and effort badge)
        # is printed at all. Absent → printed. The scope-exclusion clause is
        # never affected: it is legal boilerplate that stands on its own.
        'hourPackagesEnabled': bool,
        'hourlyRate': NUMERIC,
        'currency': str,
        # Manual base rate for this proposal only, applied to every package
        # that has no override of its own. Kept separate from `hourlyRate` so
        # the latter stays the catalog snapshot: the manual value survives a
        # switch back to 'auto' and is restored when manual is re-enabled.
        'manualHourlyRate': NUMERIC,
        # Currency the manual rate was entered in. Written by the editor, never
        # read by the renderer: it exists so a later change to the proposal's
        # nationality can be detected instead of silently reprinting a COP
        # amount as USD.
        'manualCurrency': str,
        # Per-package manual overrides, keyed by HourPackage pk (stable across
        # catalog reordering). Entries whose package no longer exists are
        # inert, so deactivating and re-activating a package restores it.
        'manualPackageRates': [{
            'packageId': NUMERIC,
            'hourlyRate': NUMERIC,
        }],
        'packages': [{
            # Catalog pk, present on seeded packages; the key manual overrides
            # bind to. Absent on legacy snapshots and hardcoded defaults.
            'id': NUMERIC,
            'name': str,
            'hours': NUMERIC,
            'discountPercent': NUMERIC,
            'note': str,
            # Optional per-package rate (catalog-seeded); falls back to the
            # section-level hourlyRate when absent.
            'hourlyRate': NUMERIC,
        }],
        'effortBadge': str,
        'scopeTitle': str,
        'scopeParagraphs': [str],
    },
    'roi_projection': {
        'title': str,
        'subtitle': str,
        'methodology': str,
        'kpis': [dict],
        'scenariosTitle': str,
        'scenarios': [{
            'name': str,
            'label': str,
            'icon': str,
            'assumptions': [str],
            'metrics': [{
                'label': str,
                'value': str,
                'basis': str,
                'emphasis': bool,
            }],
        }],
        'ctaNote': str,
    },
}


def validate_section_content(section_type, content):
    """Validate ``content`` against the declarative schema of ``section_type``.

    Returns a list of Spanish error strings (e.g.
    ``'El campo «investment.hostingPlan.hostingPercent» debe ser numérico.'``).
    Returns ``[]`` when the content is valid or when ``section_type`` has no
    registered schema. Paths are prefixed with the section type; nested
    segments are joined with dots and list indices rendered as ``[i]``.
    """
    schema = SECTION_CONTENT_SCHEMAS.get(section_type)
    if schema is None:
        return []
    errors = []
    if not isinstance(content, dict):
        return [_err(section_type, 'un objeto')]
    for field, field_spec in schema.items():
        if field not in content:
            continue
        _validate(field_spec, content[field], f'{section_type}.{field}', errors)
    return errors
