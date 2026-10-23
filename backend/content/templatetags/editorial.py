"""Channel-aware rendering; unannotated historical variables are unchanged."""
from django import template
from django.template.defaultfilters import linebreaksbr
from django.utils.safestring import mark_safe
from content.services.editorial_format import FORMAT, render_source, plain_text
from content.services.email_markdown import editorial_email_html

register = template.Library()


@register.filter
def editorial_email(value, format=None):
    if format not in (FORMAT, 'markdown', 'whatsapp_v1'):
        return value
    return mark_safe(editorial_email_html(render_source(str(value), format=format, strict=False)))


@register.filter
def editorial_plain(value, format=None):
    if format not in (FORMAT, 'markdown', 'whatsapp_v1'):
        return value
    return plain_text(str(value), format=format)


@register.simple_tag(takes_context=True)
def editorial_email_value(context, value, key):
    format_name = (context.get('editorial_formats') or {}).get(key)
    if format_name in (FORMAT, 'markdown', 'whatsapp_v1'):
        return editorial_email(value, format_name)
    return linebreaksbr(value or '')


@register.simple_tag(takes_context=True)
def editorial_plain_value(context, value, key):
    return editorial_plain(value, (context.get('editorial_formats') or {}).get(key))
