"""Freeze legacy totals before retiring module pricing. Historical models only."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from django.db import migrations


def decimal(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else Decimal('0')
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def clean_content(value):
    if isinstance(value, list):
        return [clean_content(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: clean_content(item) for key, item in value.items() if key != 'price_percent'}
    if 'price_percent' in value:
        result['is_always_included'] = decimal(value['price_percent']) == 0 and not (value.get('is_calculator_module') and value.get('is_invite'))
    return result


def migrate_prices(apps, schema_editor):
    Proposal = apps.get_model('content', 'BusinessProposal')
    Section = apps.get_model('content', 'ProposalSection')
    Log = apps.get_model('content', 'ProposalChangeLog')
    Defaults = apps.get_model('content', 'ProposalDefaultConfig')
    db = schema_editor.connection.alias
    confirmed = set(Log.objects.using(db).filter(change_type='calc_confirmed').values_list('proposal_id', flat=True))
    for proposal in Proposal.objects.using(db).iterator(chunk_size=200):
        sections = list(Section.objects.using(db).filter(proposal_id=proposal.pk))
        fr = next((s.content_json for s in sections if s.section_type == 'functional_requirements'), {}) or {}
        if not isinstance(fr, dict):
            fr = {}
        groups = [g for g in list(fr.get('groups') or []) + list(fr.get('additionalModules') or []) if isinstance(g, dict)]
        # Match the retired service: confirmed scope plus explicit admin pins,
        # or visible admin defaults before the first client confirmation.
        selected = set()
        if proposal.pk in confirmed:
            selected = {re.sub(r'^(module-|group-)', '', str(raw).strip()) for raw in proposal.selected_modules or [] if raw is not None}
        for group in groups:
            if not group.get('is_calculator_module') or group.get('is_visible') is False:
                continue
            flag = group.get('selected')
            include = flag is True if proposal.pk in confirmed else (flag if flag is not None else group.get('default_selected'))
            if include:
                selected.add(str(group.get('id') or '').strip())
        # Later duplicate ids replace earlier percentages, as in the old service.
        percentages = {}
        for group in groups:
            pct = decimal(group.get('price_percent'))
            gid = str(group.get('id') or '').strip()
            if group.get('is_calculator_module') and gid and pct > 0:
                percentages[gid] = pct
        base = decimal(proposal.total_investment).quantize(Decimal('.01'))
        total = base + sum(((base * percentages[gid] / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP) for gid in selected if gid in percentages), Decimal('0'))
        if total != base:
            if total > Decimal('9999999999.99'):
                raise ValueError(f'Proposal {proposal.pk}: investment exceeds supported precision')
            snapshot = {
                'original_investment': str(base), 'total_investment': str(total),
                'discount_percent': proposal.discount_percent, 'currency': proposal.currency,
                'discounted_investment': str(round(base * (100 - proposal.discount_percent) / 100, 2)) if proposal.discount_percent else None,
            }
            Proposal.objects.using(db).filter(pk=proposal.pk).update(total_investment=total, legacy_pricing_snapshot=snapshot)
        for section in sections:
            content = clean_content(section.content_json)
            if section.section_type == 'investment' and isinstance(content, dict):
                content['totalInvestment'] = f'${int(total):,}'.replace(',', '.')
                content['currency'] = proposal.currency
                for option in content.get('paymentOptions') or []:
                    match = re.search(r'(\d+)\s*%', str(option.get('label', '')))
                    if match:
                        amount = int(total * Decimal(match.group(1)) / 100)
                        option['description'] = f'${amount:,}'.replace(',', '.') + f' {proposal.currency}'
            if content != section.content_json:
                Section.objects.using(db).filter(pk=section.pk).update(content_json=content)
    for config in Defaults.objects.using(db).iterator():
        cleaned = clean_content(config.sections_json)
        if cleaned != config.sections_json:
            Defaults.objects.using(db).filter(pk=config.pk).update(sections_json=cleaned)


class Migration(migrations.Migration):
    dependencies = [('content', '0274_proposal_module_interests')]
    operations = [migrations.RunPython(migrate_prices)]
