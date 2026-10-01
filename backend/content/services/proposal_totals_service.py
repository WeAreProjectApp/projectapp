"""Manually agreed proposal totals shared by public and admin consumers."""

import re
from decimal import Decimal, InvalidOperation

from content.models import ProposalSection


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


def sync_manual_investment(proposal):
    """Mirror the manually agreed investment into section/payment copy."""
    effective = effective_total_for_proposal(proposal)
    inv_section = proposal.sections.filter(section_type=ProposalSection.SectionType.INVESTMENT).first()
    if not inv_section or not inv_section.content_json:
        return
    base_total = int(safe_decimal(proposal.total_investment))
    base_formatted = f'${base_total:,}'.replace(',', '.')
    cj = dict(inv_section.content_json)
    currency_changed = cj.get('currency') != proposal.currency
    total_changed = cj.get('totalInvestment') != base_formatted

    # paymentOptions descriptions depend on the effective total; rebuild
    # unconditionally when paymentOptions exist so outdated amounts from a
    # prior selection do not leak through.
    payment_changed = False
    if cj.get('paymentOptions'):
        for opt in cj['paymentOptions']:
            pct_match = re.search(r'(\d+)%', opt.get('label', ''))
            if not pct_match:
                continue
            pct = Decimal(pct_match.group(1)) / Decimal(100)
            amount = int(effective * pct)
            new_desc = f'${amount:,}'.replace(',', '.') + f' {proposal.currency}'
            if opt.get('description') != new_desc:
                opt['description'] = new_desc
                payment_changed = True

    if not currency_changed and not total_changed and not payment_changed:
        return
    cj['totalInvestment'] = base_formatted
    cj['currency'] = proposal.currency
    inv_section.content_json = cj
    inv_section.save(update_fields=['content_json'])
