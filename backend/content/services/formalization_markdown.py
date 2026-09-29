"""Copy the actual annex text so Markdown cannot diverge from its PDF."""
from content.services.attachment_markdown import pdf_markdown
from content.services.formalization_content import formal_document_title
from content.services.formalization_pdf import generate_formal_pdf
from content.services.markdown_export import export_payload


def generate_formal_markdown(content, kind, issued_at, reference):
    title = formal_document_title(content, kind)
    pdf = generate_formal_pdf(content, kind, issued_at, reference)
    markdown, warnings = pdf_markdown(pdf)
    return export_payload(title, markdown, warnings)
