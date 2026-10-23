"""Branded PDF booklet for the public financing program."""

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

from content.services.financing_program_service import serialize_financing_program
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


class FinancingPdfService:
    """Render the same canonical content exposed by the financing API."""

    @classmethod
    def build(cls, *, language):
        payload = serialize_financing_program(language=language)
        payload = editorial_projection(payload)
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
                'Partnership Program'
                if language == 'en'
                else 'Programa de Alianza'
            ),
            author='Project App.',
        )
        styles = cls._styles()
        story = cls._cover(payload, styles)
        story.extend(cls._overview(payload, styles))
        story.extend(cls._conditions(payload, styles))
        story.extend(cls._calculator(payload, styles))
        story.extend(cls._terms(payload, styles))
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
            'eyebrow': ParagraphStyle(
                'FinancingEyebrow', parent=sample['BodyText'],
                fontName=_font('medium'), fontSize=9, leading=13,
                textColor=GREEN_LIGHT, alignment=TA_CENTER, spaceAfter=9,
            ),
            'cover_title': ParagraphStyle(
                'FinancingCoverTitle', parent=sample['Title'],
                fontName=_font('light'), fontSize=30, leading=36,
                textColor=ESMERALD, alignment=TA_CENTER, spaceAfter=14,
            ),
            'cover_body': ParagraphStyle(
                'FinancingCoverBody', parent=sample['BodyText'],
                fontName=_font('regular'), fontSize=11, leading=17,
                textColor=GRAY_500, alignment=TA_CENTER,
            ),
            'section': ParagraphStyle(
                'FinancingSection', parent=sample['Heading1'],
                fontName=_font('light'), fontSize=22, leading=27,
                textColor=ESMERALD, spaceAfter=10,
            ),
            'heading': ParagraphStyle(
                'FinancingHeading', parent=sample['Heading2'],
                fontName=_font('medium'), fontSize=14, leading=19,
                textColor=ESMERALD, spaceAfter=5,
            ),
            'small_heading': ParagraphStyle(
                'FinancingSmallHeading', parent=sample['Heading3'],
                fontName=_font('medium'), fontSize=9, leading=12,
                textColor=ESMERALD, spaceAfter=4,
            ),
            'body': ParagraphStyle(
                'FinancingBody', parent=sample['BodyText'],
                fontName=_font('regular'), fontSize=9, leading=14,
                textColor=colors.HexColor('#335550'), spaceAfter=5,
            ),
            'muted': ParagraphStyle(
                'FinancingMuted', parent=sample['BodyText'],
                fontName=_font('regular'), fontSize=8, leading=12,
                textColor=GRAY_500, spaceAfter=4,
            ),
            'number': ParagraphStyle(
                'FinancingNumber', parent=sample['BodyText'],
                fontName=_font('medium'), fontSize=10, leading=13,
                textColor=GREEN_LIGHT,
            ),
        }

    @classmethod
    def _cover(cls, payload, styles):
        english = payload['language'] == 'en'
        return [
            Spacer(1, 43 * mm),
            Paragraph('PROJECT APP.', styles['eyebrow']),
            Paragraph(
                'Partnership Program' if english else 'Programa de Alianza',
                styles['cover_title'],
            ),
            Table(
                [['']], colWidths=[34 * mm], rowHeights=[2],
                style=TableStyle([('BACKGROUND', (0, 0), (-1, -1), LEMON)]),
                hAlign='CENTER',
            ),
            Spacer(1, 8 * mm),
            editorial_paragraph(payload['hero']['subtitle'], styles['cover_body']),
            Spacer(1, 9 * mm),
            editorial_paragraph(payload['hero']['trust_note'], styles['cover_body']),
            Spacer(1, 13 * mm),
            Paragraph(
                f'{payload["financing_months"]} months · 0% ordinary interest · '
                'two partnership options'
                if english
                else (
                    f'{payload["financing_months"]} meses · 0% de interés ordinario · '
                    'dos opciones de alianza'
                ),
                styles['eyebrow'],
            ),
            PageBreak(),
        ]

    @classmethod
    def _overview(cls, payload, styles):
        english = payload['language'] == 'en'
        eligibility = payload['eligibility']
        story = [
            Paragraph(
                'How the program works' if english else 'Cómo funciona el programa',
                styles['section'],
            ),
            cls._text_card(
                eligibility['title'], eligibility['summary'], styles,
                background=ESMERALD_LIGHT,
            ),
            Spacer(1, 5 * mm),
            Paragraph(
                'Choose the continuity horizon'
                if english else 'Elige el horizonte de continuidad',
                styles['heading'],
            ),
        ]
        option_cells = []
        for option in payload['options']:
            option_cells.append([
                editorial_paragraph(option['badge'], styles['number']),
                editorial_paragraph(option['name'], styles['heading']),
                editorial_paragraph(option['summary'], styles['body']),
                cls._bullet_list(option['highlights'], styles),
            ])
        table = Table([option_cells], colWidths=[80 * mm, 80 * mm])
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, 0), ESMERALD_LIGHT),
            ('BACKGROUND', (1, 0), (1, 0), BONE),
            ('BOX', (0, 0), (-1, -1), 0.5, GRAY_300),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_300),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ]))
        story.extend([table, PageBreak()])
        return story

    @classmethod
    def _conditions(cls, payload, styles):
        english = payload['language'] == 'en'
        story = [
            Paragraph(
                f'The {len(payload["conditions"])} commercial conditions'
                if english
                else f'Las {len(payload["conditions"])} condiciones comerciales',
                styles['section'],
            ),
        ]
        for condition in payload['conditions']:
            content = [
                Paragraph(
                    f'{escape(condition["number"])} · {escape(condition["title"])}',
                    styles['heading'],
                ),
                editorial_paragraph(condition['summary'], styles['body']),
                Paragraph(
                    'Why it makes sense' if english else 'Por qué tiene sentido',
                    styles['small_heading'],
                ),
                editorial_paragraph(condition['commercial_reason'], styles['body']),
                cls._bullet_list(condition['highlights'], styles),
            ]
            story.append(cls._content_table(content, BONE))
            story.append(Spacer(1, 4 * mm))
        story.append(PageBreak())
        return story

    @classmethod
    def _calculator(cls, payload, styles):
        english = payload['language'] == 'en'
        calculator = payload['calculator']
        package = payload['package']
        input_box = [
            editorial_paragraph(calculator['input']['title'], styles['heading']),
            cls._bullet_list(calculator['input']['items'], styles),
        ]
        output_box = [
            editorial_paragraph(calculator['output']['title'], styles['heading']),
            cls._bullet_list(calculator['output']['items'], styles),
        ]
        io_table = Table([[input_box, output_box]], colWidths=[80 * mm, 80 * mm])
        io_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, 0), BONE),
            ('BACKGROUND', (1, 0), (1, 0), ESMERALD_LIGHT),
            ('BOX', (0, 0), (-1, -1), 0.5, GRAY_300),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_300),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ]))
        return [
            editorial_paragraph(calculator['title'], styles['section']),
            editorial_paragraph(calculator['summary'], styles['body']),
            Spacer(1, 3 * mm),
            io_table,
            Spacer(1, 3 * mm),
            editorial_paragraph(calculator['disclaimer'], styles['muted']),
            Spacer(1, 8 * mm),
            editorial_paragraph(package['title'], styles['section']),
            cls._text_card(
                f'{package["name"]} · {package["hours"]} h',
                package['summary'],
                styles,
                background=ESMERALD_LIGHT,
            ),
            Spacer(1, 4 * mm),
            Paragraph(
                (
                    'Renews monthly · no rollover · available from production · '
                    'included only in the five-year option'
                ) if english else (
                    'Renovación mensual · no acumula horas · disponible desde '
                    'producción · incluido sólo en la opción de cinco años'
                ),
                styles['muted'],
            ),
            PageBreak(),
        ]

    @classmethod
    def _terms(cls, payload, styles):
        english = payload['language'] == 'en'
        story = [
            Paragraph(
                'Rules of the agreement' if english else 'Reglas del acuerdo',
                styles['section'],
            ),
            Paragraph(
                (
                    'These details expand the commercial summary. The signed proposal '
                    'and contract always prevail.'
                ) if english else (
                    'Estos detalles amplían el resumen comercial. La propuesta y el '
                    'contrato firmados siempre prevalecen.'
                ),
                styles['body'],
            ),
            Spacer(1, 3 * mm),
        ]
        for term in payload['legal_terms']:
            story.append(KeepTogether([
                editorial_paragraph(term['title'], styles['heading']),
                editorial_paragraph(term['summary'], styles['muted']),
                cls._bullet_list(term['items'], styles),
                Spacer(1, 4 * mm),
            ]))
        story.extend([
            Spacer(1, 4 * mm),
            cls._text_card(
                payload['cta']['title'], payload['cta']['body'], styles,
                background=ESMERALD_LIGHT,
            ),
            Spacer(1, 3 * mm),
            editorial_paragraph(payload['disclaimer'], styles['muted']),
        ])
        return story

    @staticmethod
    def _bullet_list(items, styles):
        return ListFlowable(
            [
                ListItem(editorial_paragraph(item, styles['body']), leftIndent=8)
                for item in items
            ],
            bulletType='bullet',
            leftIndent=13,
            bulletColor=GREEN_LIGHT,
        )

    @classmethod
    def _text_card(cls, title, text, styles, *, background):
        return cls._content_table([
            editorial_paragraph(title, styles['heading']),
            editorial_paragraph(text, styles['body']),
        ], background)

    @staticmethod
    def _content_table(content, background):
        table = Table([[content]], colWidths=[160 * mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), background),
            ('BOX', (0, 0), (-1, -1), 0.5, GRAY_300),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ]))
        return table

    @staticmethod
    def _page_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(GRAY_300)
        canvas.line(18 * mm, 12 * mm, A4[0] - 18 * mm, 12 * mm)
        canvas.setFont(_font('regular'), 7)
        canvas.setFillColor(GRAY_500)
        canvas.drawString(18 * mm, 7 * mm, 'Project App. · projectapp.co')
        canvas.drawRightString(A4[0] - 18 * mm, 7 * mm, str(document.page))
        canvas.restoreState()
