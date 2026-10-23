"""Seeding of proposal commercial conditions from the hour-package catalog.

The ``commercial_conditions`` section of a proposal (PDF-only appendix) lists
post-delivery hour packages. Historically its packages were hardcoded in
``proposal_service`` defaults; the :class:`content.models.HourPackage` catalog
makes them administrable per nationality (COL/EXT/USA). This service replaces
the default packages with catalog data at proposal-creation time, falling back
to the hardcoded defaults when the catalog has no active packages for the
proposal's nationality.
"""

import copy

from django.utils import timezone

from content.models import (
    BASE_RATE_FIELD_BY_NATIONALITY,
    CURRENCY_BY_NATIONALITY,
    HourPackage,
    HourPackageSettings,
)

# Canonical catalog defaults per nationality. The «restore defaults» panel
# action and the data migration that reset the catalog both derive from this
# table. Rates (July 2026): COL base $30.000 COP/h, EXT $18 USD/h,
# USA $30 USD/h; the discount ladder is shared.
DEFAULT_PACKAGES = {
    'COL': [
        {'name_es': 'Hora Puntual', 'name_en': 'Single Hour',
         'note_es': 'Para un ajuste express.', 'note_en': 'For a quick one-off tweak.',
         'hours': 1, 'hourly_rate': 30000, 'discount_percent': 0, 'order': 1},
        {'name_es': 'Paquete Ágil', 'name_en': 'Agile Pack',
         'note_es': 'Para iteraciones cortas.', 'note_en': 'For short iterations.',
         'hours': 20, 'hourly_rate': 30000, 'discount_percent': 10, 'order': 2},
        {'name_es': 'Paquete Pro', 'name_en': 'Pro Pack',
         'note_es': 'Para mejoras continuas.', 'note_en': 'For continuous improvements.',
         'hours': 60, 'hourly_rate': 30000, 'discount_percent': 20, 'order': 3},
        {'name_es': 'Paquete Premium', 'name_en': 'Premium Pack',
         'note_es': 'Para la evolución sostenida del producto.',
         'note_en': 'For sustained product evolution.',
         'hours': 180, 'hourly_rate': 30000, 'discount_percent': 30, 'order': 4},
    ],
}
_LADDER = [(1, 0), (20, 10), (60, 20), (180, 30)]
for _nat, _rate in (('EXT', 18), ('USA', 30)):
    DEFAULT_PACKAGES[_nat] = [
        {**pkg, 'hourly_rate': _rate, 'discount_percent': disc}
        for pkg, (_hours, disc) in zip(DEFAULT_PACKAGES['COL'], _LADDER)
    ]


def restore_default_packages(nationality):
    """Replace the ``nationality`` catalog with :data:`DEFAULT_PACKAGES` rows.

    Destructive on purpose: the panel action asks for confirmation before
    calling this. Also resets that nationality's base rate in
    :class:`HourPackageSettings` so the Configuración inputs stay consistent
    with the restored catalog. Returns the freshly created packages.
    """
    HourPackage.objects.filter(nationality=nationality).delete()
    created = HourPackage.objects.bulk_create(
        HourPackage(nationality=nationality, is_active=True, **fields)
        for fields in DEFAULT_PACKAGES[nationality]
    )
    settings = HourPackageSettings.load()
    setattr(
        settings,
        BASE_RATE_FIELD_BY_NATIONALITY[nationality],
        DEFAULT_PACKAGES[nationality][0]['hourly_rate'],
    )
    settings.save()
    return created


def apply_base_rates_to_catalog(changed_rates):
    """Propagate base hourly rates to every package of each nationality.

    ``changed_rates`` maps nationality → new rate. All rows of the
    nationality are updated — active and inactive — so a re-activated
    package never carries a stale rate. ``queryset.update()`` bypasses
    ``auto_now``, hence the explicit ``updated_at``. Callers wanting
    atomicity with other writes must wrap this in a transaction.

    Returns a dict nationality → number of packages updated.
    """
    now = timezone.now()
    return {
        nationality: HourPackage.objects.filter(nationality=nationality).update(
            hourly_rate=rate, updated_at=now,
        )
        for nationality, rate in changed_rates.items()
    }


def seed_commercial_conditions_from_catalog(content_json, *, nationality, language):
    """Return a copy of ``content_json`` seeded from the hour-package catalog.

    Replaces ``currency``, ``hourlyRate`` and ``packages`` with the active
    catalog packages for ``nationality`` (names/notes localized by
    ``language``). Every seeded package carries its own ``hourlyRate`` so
    per-package pricing survives even when rates differ; the section-level
    ``hourlyRate`` keeps the first package's rate as the editor baseline.

    When the catalog has no active packages for ``nationality``, the input is
    returned untouched (hardcoded defaults remain in effect). Titles, intro
    texts, effort badge and scope clause are never modified — they belong to
    the language defaults, not to the catalog.
    """
    packages = list(
        HourPackage.objects.filter(
            nationality=nationality, is_active=True,
        ).order_by('order', 'hours')
    )
    if not packages:
        return content_json

    seeded = copy.deepcopy(content_json)
    seeded['currency'] = CURRENCY_BY_NATIONALITY[nationality]
    seeded['hourlyRate'] = float(packages[0].hourly_rate)
    seeded['packages'] = [
        {
            # The catalog pk is the stable key per-proposal manual rate
            # overrides bind to, so reordering or renaming the catalog never
            # reassigns an override to the wrong package.
            'id': pkg.pk,
            'name': pkg.name_en if language == 'en' else pkg.name_es,
            'hours': pkg.hours,
            'discountPercent': pkg.discount_percent,
            'note': pkg.note_en if language == 'en' else pkg.note_es,
            **({'text_formats': {'/note': pkg.text_formats['/note_' + language]}} if '/note_' + language in pkg.text_formats else {}),
            'hourlyRate': float(pkg.hourly_rate),
        }
        for pkg in packages
    ]
    return seeded


def _positive_number(value):
    """Return ``value`` as a positive float, or ``None`` when unusable.

    The section schema is type-only, so a manual rate can arrive as ``''``,
    ``None``, ``0`` or a non-numeric string. Every one of those must fall back
    to the catalog rather than render a $0 package in the PDF.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def apply_manual_hour_rates(content_json):
    """Overlay the *legacy* manual-rate keys onto a manual proposal's snapshot.

    Manual proposals own their package list outright — the panel edits names,
    hours, discounts and rates directly in ``packages`` — so this is no longer
    the mechanism that prices them. It exists for proposals saved before that
    change, which carry ``manualHourlyRate`` (a base rate) and optionally
    ``manualPackageRates`` (``[{'packageId': pk, 'hourlyRate': n}]``, keyed by
    catalog pk) instead of per-package rates. A package resolves to its own
    override, else the manual base, else whatever rate it already had.

    Returns ``content_json`` unchanged when the mode is not ``'manual'`` or the
    legacy keys are absent — which is the case for every proposal re-saved from
    the panel.
    """
    if not isinstance(content_json, dict):
        return content_json
    if content_json.get('hourPackagesMode') != 'manual':
        return content_json

    base_rate = _positive_number(content_json.get('manualHourlyRate'))
    overrides = {}
    for entry in content_json.get('manualPackageRates') or []:
        if not isinstance(entry, dict):
            continue
        rate = _positive_number(entry.get('hourlyRate'))
        if rate is None or entry.get('packageId') is None:
            continue
        # JSON round-trips can turn the pk into a string; normalize both sides
        # of the lookup so an override never silently stops matching.
        overrides[str(entry['packageId'])] = rate

    if base_rate is None and not overrides:
        return content_json

    # The empty-catalog path of the seeder returns its input *unchanged* — in
    # the PDF path that is the live ``section.content_json``. Copy before
    # writing so generating a PDF never mutates the stored section.
    applied = copy.deepcopy(content_json)
    if base_rate is not None:
        applied['hourlyRate'] = base_rate
    for pkg in applied.get('packages') or []:
        if not isinstance(pkg, dict):
            continue
        rate = overrides.get(str(pkg.get('id')))
        if rate is None:
            rate = base_rate
        if rate is not None:
            pkg['hourlyRate'] = rate
    return applied


