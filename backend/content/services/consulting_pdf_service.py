"""Branded booklet built exclusively from the current public presentation."""
import io
from xml.sax.saxutils import escape
from content.services.editorial_projection import editorial_projection, editorial_paragraph

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from content.services.consulting_content import SECTION_KEYS
from content.services.consulting_program_service import serialize_public_program
from content.services.financing_pdf_service import FinancingPdfService
from content.services.pdf_utils import BONE, ESMERALD_LIGHT, _register_fonts


class ConsultingPdfService(FinancingPdfService):
    @classmethod
    def build(cls, *, language):
        payload = serialize_public_program(language)
        payload = editorial_projection(payload)
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
            Spacer(1, 35 * mm), Paragraph('ProjectApp', styles['eyebrow']),
            editorial_paragraph(hero['eyebrow'], styles['eyebrow']),
            editorial_paragraph(hero['title'], styles['cover_title']),
            editorial_paragraph(hero['subtitle'], styles['cover_body']), Spacer(1, 8 * mm),
            editorial_paragraph(hero['note'], styles['cover_body']), PageBreak(),
        ]
        for key in SECTION_KEYS:
            if key in ('seo', 'hero', 'cta', 'legal'):
                continue
            story.extend(cls._program_section(key, payload[key], styles, language))
        cta = payload['cta']
        story.extend([
            cls._text_card(cta['title'], cta['body'], styles, background=ESMERALD_LIGHT),
            editorial_paragraph(cta['button_label'], styles['heading']),
            editorial_paragraph(cta['whatsapp_url'], styles['body']), Spacer(1, 4 * mm),
            editorial_paragraph(payload['legal']['disclaimer'], styles['muted']),
        ])
        document.build(story, onFirstPage=cls._page_footer, onLaterPages=cls._page_footer)
        return output.getvalue()

    @classmethod
    def _program_section(cls, key, section, styles, language):
        story = [editorial_paragraph(section['title'], styles['section'])]
        if 'summary' in section:
            story.append(editorial_paragraph(section['summary'], styles['body']))
        for item in section.get('items', []):
            title = item['question'] if key == 'faq' else item['title']
            body = item['answer'] if key == 'faq' else item['summary']
            story.append(KeepTogether([cls._text_card(title, body, styles, background=BONE), Spacer(1, 4 * mm)]))
        if 'note' in section:
            story.append(editorial_paragraph(section['note'], styles['muted']))
        story.append(Spacer(1, 6 * mm))
        return story
