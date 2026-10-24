"""Branded booklet built exclusively from the current public program payload."""
import io
from xml.sax.saxutils import escape
from content.services.editorial_projection import editorial_projection, editorial_paragraph

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from content.services.building_on_demand_program_service import serialize_public_program
from content.services.financing_pdf_service import FinancingPdfService
from content.services.pdf_utils import BONE, ESMERALD_LIGHT, GRAY_300, _format_cop, _register_fonts


LABELS = {
    'es': {
        'good_for': 'Te conviene si', 'not_for': 'No es la opción para',
        'bag_hours': '{hours} horas al mes', 'roles': 'Roles disponibles',
        'server': 'Servidor incluido', 'transfer': 'de transferencia',
        'term': 'Plazo', 'discount': 'Descuento', 'monthly': 'Al mes', 'total': 'Total del plazo',
        'vat': '+ IVA', 'hours_range': '{minimum}–{maximum} horas de referencia',
        'min_tier': 'Desde {tier}',
    },
    'en': {
        'good_for': 'A good fit if', 'not_for': 'Not the option for',
        'bag_hours': '{hours} hours per month', 'roles': 'Available roles',
        'server': 'Included server', 'transfer': 'transfer',
        'term': 'Term', 'discount': 'Discount', 'monthly': 'Per month', 'total': 'Term total',
        'vat': '+ VAT', 'hours_range': '{minimum}–{maximum} reference hours',
        'min_tier': 'From {tier}',
    },
}


class BuildingOnDemandPdfService(FinancingPdfService):
    """Render the same localized offer and derived prices as the public API."""

    @classmethod
    def build(cls, *, language):
        payload = serialize_public_program(language)
        payload = editorial_projection(payload)
        labels = LABELS[payload['language']]
        _register_fonts()
        output = io.BytesIO()
        document = SimpleDocTemplate(
            output, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=18 * mm, bottomMargin=18 * mm,
            title=payload['seo']['title'], author='ProjectApp',
        )
        styles = cls._styles()
        hero = payload['hero']
        story = [
            Spacer(1, 30 * mm), Paragraph('ProjectApp', styles['eyebrow']),
            editorial_paragraph(hero['eyebrow'], styles['eyebrow']),
            editorial_paragraph(hero['title'], styles['cover_title']),
            editorial_paragraph(hero['subtitle'], styles['cover_body']), Spacer(1, 8 * mm),
            editorial_paragraph(hero['positioning'], styles['cover_body']), Spacer(1, 8 * mm),
            editorial_paragraph(hero['note'], styles['cover_body']), PageBreak(),
        ]
        story.extend(cls._card_section(payload['cell'], 'roles', styles))
        story.extend(cls._section_heading(payload['fit'], styles))
        for collection in ('good_for', 'not_for'):
            story.append(Paragraph(labels[collection], styles['heading']))
            story.extend(cls._cards(payload['fit'][collection], styles))
        story.append(Spacer(1, 6 * mm))
        story.extend(cls._section_heading(payload['tiers'], styles))
        terms = {item['id']: item['label'] for item in payload['terms']['items']}
        for tier in payload['tiers']['items']:
            story.extend([
                cls._tier_card(tier, terms, payload['offer']['prices_include_vat'], styles, labels),
                Spacer(1, 6 * mm),
            ])
        story.extend(cls._section_heading(payload['terms'], styles))
        story.extend([
            editorial_paragraph(payload['terms']['note'], styles['muted']), Spacer(1, 6 * mm),
        ])
        story.extend(cls._card_section(payload['bag'], 'rules', styles))
        story.extend(cls._estimator(payload, styles, labels))
        story.extend(cls._card_section(payload['hosting'], 'features', styles))
        story.append(editorial_paragraph(payload['faq']['title'], styles['section']))
        for item in payload['faq']['items']:
            story.append(KeepTogether([
                cls._text_card(item['question'], item['answer'], styles, background=BONE),
                Spacer(1, 4 * mm),
            ]))
        cta = payload['cta']
        story.extend([
            Spacer(1, 6 * mm),
            cls._text_card(cta['title'], cta['body'], styles, background=ESMERALD_LIGHT),
            editorial_paragraph(cta['button_label'], styles['heading']),
            editorial_paragraph(cta['whatsapp_url'], styles['body']), Spacer(1, 4 * mm),
            editorial_paragraph(payload['legal']['disclaimer'], styles['muted']),
        ])
        document.build(story, onFirstPage=cls._page_footer, onLaterPages=cls._page_footer)
        return output.getvalue()

    @staticmethod
    def _section_heading(section, styles):
        return [
            editorial_paragraph(section['title'], styles['section']),
            editorial_paragraph(section['summary'], styles['body']),
        ]

    @classmethod
    def _cards(cls, items, styles):
        return [
            KeepTogether([
                cls._text_card(item['title'], item['summary'], styles, background=BONE),
                Spacer(1, 4 * mm),
            ])
            for item in items
        ]

    @classmethod
    def _card_section(cls, section, collection, styles):
        return [
            *cls._section_heading(section, styles),
            *cls._cards(section[collection], styles),
            editorial_paragraph(section['note'], styles['muted']), Spacer(1, 6 * mm),
        ]

    @classmethod
    def _tier_card(cls, tier, terms, prices_include_vat, styles, labels):
        server = tier['server']
        server_line = (
            f"{server['vcpu']} vCPU · {server['ram_gb']} GB RAM · "
            f"{server['disk_gb']} GB NVMe · {server['transfer_tb']} TB {labels['transfer']}"
        )
        content = [
            editorial_paragraph(tier['badge'], styles['muted']),
            editorial_paragraph(tier['name'], styles['heading']),
            editorial_paragraph(tier['pace_label'], styles['small_heading']),
            editorial_paragraph(tier['pace_summary'], styles['body']),
            Paragraph(labels['bag_hours'].format(hours=tier['bag_hours']), styles['number']),
            editorial_paragraph(tier['ideal_for'], styles['body']),
            Paragraph(labels['roles'], styles['small_heading']), cls._bullet_list(tier['roles'], styles),
            Paragraph(labels['server'], styles['small_heading']), editorial_paragraph(server_line, styles['body']),
            cls._bullet_list(tier['highlights'], styles), Spacer(1, 3 * mm),
            cls._price_table(tier['prices'], terms, prices_include_vat, styles, labels),
            Spacer(1, 3 * mm), editorial_paragraph(tier['cta_label'], styles['small_heading']),
        ]
        card = cls._content_table(content, ESMERALD_LIGHT)
        # Long valid tier copy must remain printable when a card spans pages.
        card.splitInRow = 1
        return card

    @staticmethod
    def _price_table(prices, terms, prices_include_vat, styles, labels):
        suffix = '' if prices_include_vat else f" {labels['vat']}"
        rows = [[
            Paragraph(labels[key], styles['small_heading'])
            for key in ('term', 'discount', 'monthly', 'total')
        ]]
        for price in prices:
            rows.append([
                editorial_paragraph(terms[price['term']], styles['muted']),
                Paragraph(f"{price['discount_percent']} %", styles['muted']),
                Paragraph(f"{_format_cop(price['monthly_price'])} COP{suffix}", styles['muted']),
                Paragraph(f"{_format_cop(price['total'])} COP{suffix}", styles['muted']),
            ])
        table = Table(rows, colWidths=[31 * mm, 21 * mm, 46 * mm, 46 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BONE),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, GRAY_300),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        return table

    @classmethod
    def _estimator(cls, payload, styles, labels):
        section = payload['estimator']
        story = cls._section_heading(section, styles)
        sizes = {item['id']: item for item in section['sizes']}
        tiers = {item['id']: item['name'] for item in payload['tiers']['items']}
        for task in section['tasks']:
            size = sizes[task['size']]
            reference = labels['hours_range'].format(minimum=size['hours_min'], maximum=size['hours_max'])
            minimum_tier = labels['min_tier'].format(tier=tiers[task['min_tier']])
            story.append(KeepTogether([
                cls._text_card(task['label'], f"{reference}. {minimum_tier}. {task['hint']}", styles, background=BONE),
                Spacer(1, 4 * mm),
            ]))
        story.extend([
            editorial_paragraph(section['disclaimer'], styles['muted']), Spacer(1, 6 * mm),
        ])
        return story
