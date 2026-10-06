"""Accounting units for new audit snapshots and read-only legacy projections."""
import re
from decimal import Decimal


def format_percentage(value):
    number = format(Decimal(value).normalize(), 'f')
    return f'{number} %'


def display_accounting_changes(changes):
    """Never rewrite audit facts or sent-email snapshots."""
    projected = []
    for change in changes or []:
        row = dict(change)
        if row.get('field') == 'vat_rate':
            for side in ('old', 'new'):
                value = row.get(side)
                # Old COP formatter truncated to an integer. Only this known
                # legacy shape can be repaired without guessing a decimal.
                match = re.fullmatch(r'\$([0-9]{1,3})', str(value))
                if match and int(match[1]) <= 100:
                    row[side] = format_percentage(match[1])
        projected.append(row)
    return projected
