"""Explicit, deterministic projection of proposal data into formal annexes.

No rendering or catalog refresh runs here. Unknown fields and sales
sections cannot enter the documents through a generic raw-text fallback.
"""
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import re

from content.services.proposal_pdf_service import default_selected_modules_from_content
from content.services.proposal_module_links import ensure_functional_requirements_item_ids
from content.services.proposal_totals_service import effective_total_for_proposal, safe_decimal
from content.services.technical_document_filter import get_filtered_technical_document


class FormalizationError(ValueError):
    def __init__(self, message, code='invalid_formalization', status=400):
        super().__init__(message)
        self.code = code
        self.status = status


def rows(value):
    return [item for item in value or [] if isinstance(item, dict)]


def text(value):
    if isinstance(value, list):
        return '\n'.join(text(item) for item in value)
    return str(value or '').strip()


@dataclass(frozen=True)
class PdfSection:
    """Captured, curated input to the shared section renderers (never an ORM row)."""

    section_type: str
    title: str
    order: int
    content_json: dict


def project_fields(source, fields):
    """Project a closed set of printable fields, including legacy list values."""
    return {key: text(source.get(key)) for key in fields}


def project_rows(source, fields):
    return [project_fields(item, fields) for item in rows(source)]


class FormalContent:
    """One captured proposal supplies scope and money to both documents."""

    def __init__(self, proposal):
        self.proposal = proposal
        self.sections = [
            {'section_type': sec.section_type, 'title': sec.title, 'order': sec.order,
             'content_json': deepcopy(sec.content_json or {})}
            for sec in proposal.sections.all() if sec.is_enabled
        ]
        for section in self.sections:
            if section['section_type'] == 'functional_requirements':
                section['content_json'] = ensure_functional_requirements_item_ids(section['content_json'])
        self.data = {sec['section_type']: sec['content_json'] for sec in self.sections}
        self.selected = default_selected_modules_from_content(proposal)
        self.total = effective_total_for_proposal(proposal)
        # Legacy priced items are subtractive; calculator modules are additive.
        for module in rows(self.data.get('investment', {}).get('modules')):
            if module.get('id') not in self.selected:
                self.total -= safe_decimal(module.get('price'))
        fr = self.data.get('functional_requirements', {})
        for group in rows(fr.get('groups')) + rows(fr.get('additionalModules')):
            gid = group.get('id') or group.get('title') or ''
            for item in rows(group.get('items')):
                fid = re.sub(r'\s+', '-', f"fr-{gid}-{item.get('name', '')}").lower()
                if item.get('is_required') is not True and fid not in self.selected:
                    self.total -= safe_decimal(item.get('price'))
        self.currency = proposal.currency or 'COP'
        self.english = proposal.language == 'en'

    def label(self, es, en):
        return en if self.english else es

    def money(self, value):
        amount = safe_decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        formatted = f'{amount:,.2f}'
        if not self.english:
            formatted = formatted.translate(str.maketrans(',.', '.,'))
        return f'{formatted} {self.currency}'

    def structured(self, key):
        data = self.data.get(key, {})
        if data.get('_editMode') == 'paste' and data.get('rawText'):
            raise FormalizationError(
                f'Completa los campos estructurados de {key}; el texto pegado no se incluye en la formalización.',
                'unstructured_content',
            )
        return data

    def table(self, title, source, columns, paragraphs=()):
        return {
            'title': title,
            'paragraphs': [text(p) for p in paragraphs if text(p)],
            'headers': [label for _, label in columns],
            'rows': [[text(item.get(key)) for key, _ in columns] for item in rows(source)],
        }

    def block(self, title, paragraphs):
        return self.table(title, [], [], paragraphs)

    def technical_data(self):
        data = self.structured('technical_document')
        if not data:
            raise FormalizationError('Completa y habilita el detalle técnico.', 'technical_missing')
        filtered = get_filtered_technical_document(data, self.sections, self.selected)
        if not any(epic.get('requirements') for epic in rows(filtered.get('epics'))):
            raise FormalizationError('El detalle técnico necesita requerimientos del alcance seleccionado.', 'technical_scope_missing')
        return filtered

    def scope(self):
        data = self.structured('functional_requirements')
        included = []
        for group in rows(data.get('groups')) + rows(data.get('additionalModules')):
            gid = text(group.get('id') or group.get('title'))
            if group.get('is_visible') is False:
                continue
            if group.get('is_calculator_module') and f'module-{gid}' not in self.selected:
                continue
            if group in rows(data.get('additionalModules')) and not group.get('is_calculator_module'):
                if f'group-{gid}' not in self.selected and f'module-{gid}' not in self.selected:
                    continue
            if group.get('_editMode') == 'paste' and group.get('rawText'):
                raise FormalizationError(f'Completa los items estructurados de {gid}.', 'unstructured_content')
            for item in rows(group.get('items')):
                configurable = item.get('price') or item.get('is_required') is False
                fid = re.sub(r'\s+', '-', f"fr-{gid}-{item.get('name', '')}").lower()
                if item.get('is_required') is not True and configurable and fid not in self.selected:
                    continue
                included.append({
                    'module': group.get('title') or gid,
                    'id': item.get('id') or fid,
                    'name': item.get('name'),
                    'description': item.get('description'),
                })
        if not included:
            raise FormalizationError('Completa y habilita el alcance funcional de la propuesta.', 'commercial_scope_missing')
        return included

    def contract_note(self):
        """Point the annex at the contract(s) the deal closes with."""
        if getattr(self.proposal, 'contract_modality', '') == 'split':
            return self.label(
                'Las garantías y obligaciones se rigen por el contrato de producto (desarrollo e implementación del software) y el contrato de servicio (hosting, mantenimiento y soporte) asociados a esta propuesta.',
                'Warranties and obligations are governed by the product contract (software development and implementation) and the service contract (hosting, maintenance and support) associated with this proposal.',
            )
        return self.label(
            'Las garantías y obligaciones se rigen por el contrato de desarrollo de software asociado a esta propuesta.',
            'Warranties and obligations are governed by the software development contract associated with this proposal.',
        )

    def commercial(self):
        inv = self.structured('investment')
        if not inv or self.total <= 0:
            raise FormalizationError('Completa la inversión de la propuesta.', 'investment_missing')
        payments = rows(inv.get('paymentOptions'))
        if not payments:
            raise FormalizationError('Completa los hitos de pago.', 'payments_missing')
        schedule = []
        for payment in payments:
            match = re.search(r'(\d+(?:[.,]\d+)?)\s*%', text(payment.get('label')))
            schedule.append({
                'milestone': payment.get('label'),
                'amount': self.money(self.total * Decimal(match[1].replace(',', '.')) / 100) if match else payment.get('description'),
            })
        groups = {}
        for item in self.scope():
            group = groups.setdefault(text(item['module']), {'title': text(item['module']), 'items': []})
            group['items'].append(project_fields(item, ('id', 'name', 'description')))
        design = self.structured('design_ux')
        creative = self.structured('creative_support')
        timeline = self.structured('timeline')
        method = self.structured('process_methodology')
        stages = self.structured('development_stages')
        conditions = self.structured('commercial_conditions')
        l = self.label

        def provisions(values):
            return [text(v.get('description') or v.get('title')) if isinstance(v, dict) else text(v)
                    for v in values or []]

        phases = project_rows(timeline.get('phases'), ('title', 'duration', 'description', 'milestone'))
        for phase, original in zip(phases, rows(timeline.get('phases'))):
            phase['tasks'] = [text(t) for t in original.get('tasks') or []] if isinstance(original.get('tasks'), list) else [text(original.get('tasks'))]
        payloads = {
            'functional_requirements': {
                'intro': l('Las especificaciones y criterios verificables se detallan en el anexo técnico de esta propuesta.', 'Specifications and verifiable criteria are detailed in the technical annex to this proposal.'),
                'groups': list(groups.values()),
            },
            'design_ux': {'focusItems': provisions(design.get('focusItems'))},
            'creative_support': {'includes': provisions(creative.get('includes'))},
            'timeline': {'phases': phases, 'totalDuration': text(timeline.get('totalDuration'))},
            'process_methodology': {'steps': project_rows(method.get('steps'), ('title', 'description', 'clientAction'))},
            'development_stages': {'stages': [] if method.get('steps') else project_rows(stages.get('stages'), ('title', 'description'))},
            # Resolved money is consumed verbatim. The renderer must never normalize
            # hosting, reseed a catalog or run a second pricing calculation here.
            'investment': {
                'resolved': {
                    'total': self.money(self.total),
                    'tax': ' + IVA' if self.currency == 'COP' else '',
                    'payments': project_rows(schedule, ('milestone', 'amount')),
                    'paymentMethods': text(inv.get('paymentMethods')),
                    'paymentNote': l('Los importes conservan el tratamiento tributario de la inversión.', 'Amounts follow the tax treatment of the investment.'),
                    'hosting': self.hosting(inv),
                },
            },
            'value_added_modules': {'terms': self.included_terms()},
            'commercial_conditions': {
                'hourPackagesEnabled': False,
                'scopeParagraphs': [text(p) for p in conditions.get('scopeParagraphs') or []],
                'contractNote': self.contract_note(),
            },
        }
        labels = {
            'functional_requirements': l('Alcance y entregables', 'Scope and deliverables'),
            'design_ux': l('Diseño incluido', 'Included design'),
            'creative_support': l('Acompañamiento incluido', 'Included support'),
            'timeline': l('Cronograma', 'Schedule'),
            'process_methodology': l('Ejecución y aportes del cliente', 'Execution and client inputs'),
            'development_stages': l('Etapas de desarrollo', 'Development stages'),
            'investment': l('Inversión', 'Investment'),
            'value_added_modules': l('Condiciones de módulos incluidos', 'Terms for included modules'),
            'commercial_conditions': l('Límites y cambios de alcance', 'Scope limits and changes'),
        }
        ordered = sorted(self.sections, key=lambda section: section['order'])
        result = []
        for section in ordered:
            key = section['section_type']
            data = payloads.pop(key, None)
            if data is not None and any(data.values()):
                result.append(PdfSection(key, text(section['title']) or labels[key], len(result), data))
        # The contract reference belongs to every formal commercial annex even
        # when the optional commercial_conditions section is disabled/missing.
        if 'commercial_conditions' in payloads:
            result.append(PdfSection('commercial_conditions', labels['commercial_conditions'], len(result), payloads['commercial_conditions']))
        return result

    def included_terms(self):
        data = self.structured('value_added_modules')
        fr = self.structured('functional_requirements')
        catalog = {g.get('id'): g for g in rows(fr.get('groups')) + rows(fr.get('additionalModules'))}
        result = []
        for mid in data.get('module_ids') or []:
            module = catalog.get(mid)
            if not module or module.get('is_visible') is False:
                continue
            cond = (data.get('conditions') or {}).get(mid) or {}
            minimum = safe_decimal(cond.get('min_price_cop' if self.currency == 'COP' else 'min_price_usd'))
            if self.total < minimum:
                continue
            if module.get('is_calculator_module') and f'module-{mid}' not in self.selected:
                continue
            clauses = [text(c.get('label')) + ': ' + text(c.get('text')) for c in rows(cond.get('terms_clauses'))]
            if not clauses and cond.get('terms'):
                clauses = [text(cond['terms'])]
            if cond.get('duration_months'):
                clauses.insert(0, self.label('Meses de vigencia: ', 'Term in months: ') + text(cond['duration_months']))
            if cond.get('discretionary_note'):
                clauses.append(text(cond['discretionary_note']))
            result.append(self.block(self.label('Condiciones de ', 'Terms for ') + text(module.get('title') or mid), clauses))
        general = data.get('general_terms') or {}
        if result:
            result.append(self.block(self.label('Condiciones generales de los módulos incluidos', 'General terms for included modules'), [text(c.get('label')) + ': ' + text(c.get('text')) for c in rows(general.get('clauses'))]))
        return result

    def hosting(self, inv):
        hosting = inv.get('hostingPlan') or {}
        if not hosting.get('title'):
            return []
        # Freeze existing proposal terms; never reseed tiers or packages from catalogs.
        percent = self.proposal.hosting_percent
        if percent is None:
            percent = hosting.get('hostingPercent', 0)
        reference = self.total * safe_decimal(percent) / 100
        monthly = (reference / 12).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        tariffs = []
        for tier in rows(hosting.get('billingTiers')):
            months = safe_decimal(tier.get('months'))
            price = (monthly * (100 - safe_decimal(tier.get('discountPercent'))) / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            if months > 0:
                tariffs.append({'period': tier.get('label') or str(months), 'amount': self.money(price * months)})
        if not tariffs:
            tariffs = [{'period': key, 'amount': hosting[key]} for key in ('monthlyPrice', 'annualPrice') if hosting.get(key)]
        paragraphs = [hosting.get('coverageNote'), hosting.get('renewalNote')]
        if hosting.get('freeMonthsVisible', bool(hosting.get('freeMonths'))) and hosting.get('freeMonths'):
            paragraphs.append(self.label('Meses incluidos sin costo: ', 'Included months at no charge: ') + text(hosting['freeMonths']))
        if len(tariffs) > 1:
            paragraphs.append(self.label('Modalidades disponibles; esta tabla no registra una elección de periodicidad.', 'Available billing options; this table does not record a selected billing period.'))
        return [self.table(self.label('Hosting, mantenimiento y soporte', 'Hosting, maintenance and support'), tariffs, [
            ('period', self.label('Periodicidad', 'Billing period')), ('amount', self.label('Importe por período', 'Amount per period')),
        ], paragraphs), self.table(self.label('Infraestructura incluida', 'Included infrastructure'), hosting.get('specs'), [
            ('label', self.label('Recurso', 'Resource')), ('value', self.label('Especificación', 'Specification')),
        ])]

    def technical(self):
        """Keep the public renderer's schema, with a closed field projection."""
        d = self.technical_data()
        result = project_fields(d, ('purpose', 'apiSummary', 'backupsNote'))
        for key, fields in {
            'stack': ('layer', 'technology', 'rationale'),
            'apiDomains': ('domain', 'summary'),
            'environments': ('name', 'purpose', 'whoAccesses'),
            'security': ('aspect', 'implementation'),
            'decisions': ('decision', 'alternative', 'reason'),
        }.items():
            result[key] = project_rows(d.get(key), fields)
        for key, fields, collections in (
            ('architecture', ('summary', 'diagramNote'), {'patterns': ('component', 'pattern', 'description')}),
            ('dataModel', ('summary', 'relationships'), {'entities': ('name', 'description', 'keyFields')}),
            ('growthReadiness', (), {'strategies': ('dimension', 'preparation')}),
            ('integrations', ('notes',), {'included': ('service', 'provider', 'connection', 'dataExchange', 'accountOwner'), 'excluded': ('service', 'reason')}),
            ('performanceQuality', (), {'metrics': ('metric', 'target', 'howMeasured'), 'practices': ('strategy', 'description')}),
            ('quality', ('criticalFlowsNote',), {'dimensions': ('dimension', 'evaluates', 'standard'), 'testTypes': ('type', 'validates', 'tool', 'whenRun')}),
        ):
            source = d.get(key) or {}
            result[key] = project_fields(source, fields)
            for collection, columns in collections.items():
                result[key][collection] = project_rows(source.get(collection), columns)
        result['epics'] = []
        for epic in rows(d.get('epics')):
            projected = project_fields(epic, ('epicKey', 'title', 'description'))
            projected['requirements'] = project_rows(epic.get('requirements'), ('flowKey', 'title', 'description', 'configuration', 'usageFlow', 'linked_item_ids'))
            result['epics'].append(projected)
        return result


def formal_document_title(content, kind):
    if kind == 'commercial':
        return content.label('Propuesta comercial formal', 'Formal commercial proposal')
    if kind == 'technical':
        return content.label('Detalle técnico formal', 'Formal technical specification')
    raise FormalizationError('Tipo de documento inválido.', 'invalid_document')
