"""PDF chapter selection and order, independent of the editable web order."""

COMMERCIAL_SECTION_ORDER = (
    'executive_summary',
    'context_diagnostic',
    'conversion_strategy',
    'roi_projection',
    'design_ux',
    'creative_support',
    'process_methodology',
    'timeline',
    'investment',
    'functional_requirements',
    'value_added_modules',
    'development_stages',
    'final_note',
    'next_steps',
    'commercial_conditions',
)

FORMAL_COMMERCIAL_SECTIONS = frozenset({
    'executive_summary', 'conversion_strategy', 'design_ux',
    'creative_support', 'process_methodology', 'timeline', 'investment',
    'functional_requirements', 'value_added_modules', 'commercial_conditions',
})

FORMAL_TECHNICAL_SECTIONS = ('stack', 'dataModel', 'epics')


def ordered_commercial_sections(sections):
    """Return printable chapters; greeting and technical links stay auxiliary."""
    positions = {kind: index for index, kind in enumerate(COMMERCIAL_SECTION_ORDER)}
    return sorted(
        (section for section in sections if section.section_type in positions),
        key=lambda section: positions[section.section_type],
    )
