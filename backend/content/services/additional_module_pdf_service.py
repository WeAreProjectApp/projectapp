import io
from xml.sax.saxutils import escape
from content.services.editorial_projection import editorial_projection, editorial_paragraph

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from content.services.additional_module_catalog_service import (
    serialize_public_catalog,
)
from content.services.pdf_utils import (
    BONE,
    ESMERALD,
    ESMERALD_LIGHT,
    GRAY_300,
    GRAY_500,
    GREEN_LIGHT,
    LEMON,
    _font,
    _register_fonts,
)


class AdditionalModulePdfService:
    """Build the same no-price catalog used by panel and public links."""

    @classmethod
    def build(cls, *, language, module_ids=None, recipient_label=''):
        payload = serialize_public_catalog(
            language=language,
            module_ids=module_ids,
        )
        payload = editorial_projection(payload)
        if payload['total_modules'] == 0:
            raise ValueError('No hay módulos activos para generar el PDF.')

        _register_fonts()
        output = io.BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title=(
                'Additional Modules Catalog'
                if language == 'en'
                else 'Catálogo de módulos adicionales'
            ),
            author='Project App.',
        )
        styles = cls._styles()
        story = cls._cover(
            payload,
            styles,
            recipient_label=str(recipient_label or '').strip(),
        )
        story.extend(cls._index(payload, styles))
        story.extend(cls._catalog(payload, styles))
        document.build(
            story,
            onFirstPage=cls._page_footer,
            onLaterPages=cls._page_footer,
        )
        return output.getvalue()

    @staticmethod
    def _styles():
        sample = getSampleStyleSheet()
        return {
            'cover_eyebrow': ParagraphStyle(
                'CatalogCoverEyebrow',
                parent=sample['BodyText'],
                fontName=_font('medium'),
                fontSize=10,
                leading=14,
                textColor=GREEN_LIGHT,
                alignment=TA_CENTER,
                spaceAfter=10,
            ),
            'cover_title': ParagraphStyle(
                'CatalogCoverTitle',
                parent=sample['Title'],
                fontName=_font('light'),
                fontSize=30,
                leading=36,
                textColor=ESMERALD,
                alignment=TA_CENTER,
                spaceAfter=14,
            ),
            'cover_body': ParagraphStyle(
                'CatalogCoverBody',
                parent=sample['BodyText'],
                fontName=_font('regular'),
                fontSize=11,
                leading=17,
                textColor=GRAY_500,
                alignment=TA_CENTER,
            ),
            'cover_recipient': ParagraphStyle(
                'CatalogCoverRecipient',
                parent=sample['Heading2'],
                fontName=_font('light'),
                fontSize=18,
                leading=23,
                textColor=ESMERALD,
                alignment=TA_CENTER,
                spaceAfter=10,
            ),
            'section': ParagraphStyle(
                'CatalogSection',
                parent=sample['Heading1'],
                fontName=_font('light'),
                fontSize=23,
                leading=28,
                textColor=ESMERALD,
                spaceAfter=12,
            ),
            'module': ParagraphStyle(
                'CatalogModule',
                parent=sample['Heading2'],
                fontName=_font('medium'),
                fontSize=15,
                leading=20,
                textColor=ESMERALD,
                spaceAfter=5,
            ),
            'summary': ParagraphStyle(
                'CatalogSummary',
                parent=sample['BodyText'],
                fontName=_font('regular'),
                fontSize=10,
                leading=15,
                textColor=GRAY_500,
                spaceAfter=8,
            ),
            'card_title': ParagraphStyle(
                'CatalogCardTitle',
                parent=sample['BodyText'],
                fontName=_font('medium'),
                fontSize=9,
                leading=12,
                textColor=ESMERALD,
                spaceAfter=4,
            ),
            'body': ParagraphStyle(
                'CatalogBody',
                parent=sample['BodyText'],
                fontName=_font('regular'),
                fontSize=9,
                leading=13,
                textColor=colors.HexColor('#335550'),
            ),
            'index': ParagraphStyle(
                'CatalogIndex',
                parent=sample['BodyText'],
                fontName=_font('regular'),
                fontSize=10,
                leading=15,
                textColor=ESMERALD,
            ),
        }

    @classmethod
    def _cover(cls, payload, styles, *, recipient_label=''):
        english = payload['language'] == 'en'
        story = [
            Spacer(1, 48 * mm),
            Paragraph('PROJECT APP.', styles['cover_eyebrow']),
            Paragraph(
                'Additional Modules Catalog'
                if english else 'Catálogo de módulos adicionales',
                styles['cover_title'],
            ),
            Table(
                [['']],
                colWidths=[34 * mm],
                rowHeights=[2],
                style=TableStyle([('BACKGROUND', (0, 0), (-1, -1), LEMON)]),
                hAlign='CENTER',
            ),
            Spacer(1, 8 * mm),
            Paragraph(
                (
                    'Explore capabilities that can be added to a digital platform. '
                    'This document explains their value and implementation inputs; '
                    'scope and pricing are defined separately in a proposal.'
                ) if english else (
                    'Explora capacidades que se pueden sumar a una plataforma digital. '
                    'Este documento explica su valor y los insumos de implementación; '
                    'el alcance y el precio se definen por separado en una propuesta.'
                ),
                styles['cover_body'],
            ),
        ]
        if recipient_label:
            story.extend([
                Spacer(1, 10 * mm),
                Paragraph(
                    'PREPARED FOR' if english else 'PREPARADO PARA',
                    styles['cover_eyebrow'],
                ),
                editorial_paragraph(recipient_label[:255], styles['cover_recipient']),
            ])
        story.extend([
            Spacer(1, 8 * mm if recipient_label else 12 * mm),
            Paragraph(
                (
                    f'{payload["total_modules"]} modules · '
                    f'{len(payload["categories"])} categories'
                ) if english else (
                    f'{payload["total_modules"]} módulos · '
                    f'{len(payload["categories"])} categorías'
                ),
                styles['cover_eyebrow'],
            ),
            PageBreak(),
        ])
        return story

    @classmethod
    def _index(cls, payload, styles):
        english = payload['language'] == 'en'
        story = [
            Paragraph('Index' if english else 'Índice', styles['section']),
            Spacer(1, 2 * mm),
        ]
        for category in payload['categories']:
            story.append(editorial_paragraph(category['name'], styles['module']))
            bullets = [
                ListItem(
                    editorial_paragraph(module['name'], styles['index']),
                    leftIndent=8,
                )
                for module in category['modules']
            ]
            story.append(ListFlowable(
                bullets,
                bulletType='bullet',
                start='circle',
                leftIndent=14,
                bulletColor=GREEN_LIGHT,
            ))
            story.append(Spacer(1, 4 * mm))
        story.append(PageBreak())
        return story

    @classmethod
    def _catalog(cls, payload, styles):
        story = []
        english = payload['language'] == 'en'
        labels = {
            'what_is': 'What it is' if english else 'Qué es',
            'purpose': 'What it is for' if english else 'Para qué sirve',
            'problems_solved': 'What it solves' if english else 'Qué resuelve',
            'integrations': 'What it integrates with' if english else 'Qué se integra',
            'implementation_requirements': (
                'What implementation requires'
                if english else 'Qué hace falta para implementarlo'
            ),
        }
        for category_index, category in enumerate(payload['categories']):
            if category_index:
                story.append(PageBreak())
            story.append(editorial_paragraph(category['name'], styles['section']))
            for module in category['modules']:
                heading = f'{escape(module["icon"])} {escape(module["name"])}'.strip()
                story.append(KeepTogether([
                    Paragraph(heading, styles['module']),
                    editorial_paragraph(module['summary'], styles['summary']),
                ]))
                for field in ('what_is', 'purpose'):
                    story.append(cls._text_card(
                        labels[field],
                        module[field],
                        styles,
                    ))
                for field in (
                    'problems_solved',
                    'integrations',
                    'implementation_requirements',
                ):
                    story.append(cls._list_card(
                        labels[field],
                        module[field],
                        styles,
                    ))
                story.append(Spacer(1, 7 * mm))
        return story

    @staticmethod
    def _text_card(title, text, styles):
        content = [
            editorial_paragraph(title, styles['card_title']),
            editorial_paragraph(text, styles['body']),
        ]
        table = Table([[content]], colWidths=[164 * mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), ESMERALD_LIGHT),
            ('BOX', (0, 0), (-1, -1), 0.5, GRAY_300),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))
        return KeepTogether([table, Spacer(1, 2 * mm)])

    @staticmethod
    def _list_card(title, items, styles):
        bullets = ListFlowable(
            [
                ListItem(
                    editorial_paragraph(item, styles['body']),
                    leftIndent=8,
                )
                for item in items
            ],
            bulletType='bullet',
            leftIndent=13,
            bulletColor=GREEN_LIGHT,
        )
        content = [editorial_paragraph(title, styles['card_title']), bullets]
        table = Table([[content]], colWidths=[164 * mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), BONE),
            ('BOX', (0, 0), (-1, -1), 0.5, GRAY_300),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))
        return KeepTogether([table, Spacer(1, 2 * mm)])

    @staticmethod
    def _page_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(GRAY_300)
        canvas.line(18 * mm, 12 * mm, A4[0] - 18 * mm, 12 * mm)
        canvas.setFont(_font('regular'), 7)
        canvas.setFillColor(GRAY_500)
        canvas.drawString(18 * mm, 7 * mm, 'Project App. · projectapp.co')
        canvas.drawRightString(
            A4[0] - 18 * mm,
            7 * mm,
            str(document.page),
        )
        canvas.restoreState()
