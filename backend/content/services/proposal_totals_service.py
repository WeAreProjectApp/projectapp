"""Manually agreed proposal totals shared by public and admin consumers."""

import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from content.models import ProposalSection


PAYMENT_PERCENT = re.compile(r'(\d+(?:[.,]\d+)?)\s*%')


def safe_decimal(value, default=Decimal('0')):
    """Safely coerce unknown numeric input to Decimal."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def effective_total_for_proposal(proposal):
    """The manually agreed investment is the sole monetary source of truth."""
    return safe_decimal(proposal.total_investment).quantize(Decimal('0.01'))


def build_effective_totals_map(proposals):
    """Compatibility field for panel metrics; no section/log queries needed."""
    return {proposal.id: effective_total_for_proposal(proposal) for proposal in proposals}


def discount_original_for_proposal(proposal):
    """Keep the original reference price of a migrated discount offer."""
    snapshot = proposal.legacy_pricing_snapshot
    if proposal.discount_percent and snapshot:
        return safe_decimal(snapshot['original_investment'])
    return safe_decimal(proposal.total_investment)


def discounted_total_for_proposal(proposal):
    """Preserve a migrated offer until the seller edits its financial terms."""
    if not proposal.discount_percent:
        return None
    snapshot = proposal.legacy_pricing_snapshot
    if snapshot and snapshot.get('discounted_investment') is not None:
        return safe_decimal(snapshot['discounted_investment'])
    return (safe_decimal(proposal.total_investment)
            * (Decimal(100) - proposal.discount_percent) / Decimal(100)).quantize(Decimal('0.01'))


def editable_payment_options(content):
    """Return percentage-bearing rows in the order used by the General form."""
    options = content.get('paymentOptions') if isinstance(content, dict) else None
    for option in options if isinstance(options, list) else ():
        label = option.get('label') if isinstance(option, dict) else None
        match = PAYMENT_PERCENT.search(label) if isinstance(label, str) else None
        if match:
            yield option, match


def sync_manual_investment(
    proposal, *, recalculate_totals=True, payment_percentages=None, sync_hosting_percent=False,
):
    """Update only the investment values affected by the confirmed proposal edits."""
    inv_section = proposal.sections.filter(section_type=ProposalSection.SectionType.INVESTMENT).first()
    if not inv_section or not isinstance(inv_section.content_json, dict) or not inv_section.content_json:
        return
    content = deepcopy(inv_section.content_json)
    effective = effective_total_for_proposal(proposal)
    if recalculate_totals:
        content['totalInvestment'] = f'${int(effective):,}'.replace(',', '.')
        content['currency'] = proposal.currency

    hosting_plan = content.get('hostingPlan')
    if sync_hosting_percent and isinstance(hosting_plan, dict):
        hosting_plan['hostingPercent'] = proposal.hosting_percent

    if recalculate_totals or payment_percentages is not None:
        for index, (option, match) in enumerate(editable_payment_options(content)):
            current = Decimal(match[1].replace(',', '.'))
            percent = payment_percentages[index] if payment_percentages is not None else current
            # Compare to the value shown by General for old labels with extra precision.
            editable = min(current, Decimal(100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            edited = payment_percentages is not None and percent != editable
            if edited:
                label = option['label']
                option['label'] = f'{label[:match.start()]}{percent.normalize():f}%{label[match.end():]}'
            if edited or recalculate_totals:
                amount = effective * (percent if edited else current) / 100
                if edited:
                    amount = amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                amount = int(amount)
                option['description'] = f'${amount:,}'.replace(',', '.') + f' {proposal.currency}'

    if content == inv_section.content_json:
        return
    inv_section.content_json = content
    inv_section.save(update_fields=['content_json'])
