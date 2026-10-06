from accounts.retention import RetainedProjectModel
import uuid

from django.core.validators import RegexValidator
from django.db import models

COLOR_VALIDATOR = RegexValidator(
    r'^#[0-9a-fA-F]{6}$', 'Usa un color hexadecimal de 6 dígitos.',
)

HANDLE_VALIDATOR = RegexValidator(
    regex=r'^[a-z0-9][a-z0-9_.-]{2,29}$',
    message=(
        'El handle debe tener entre 3 y 30 caracteres: minúsculas, números, '
        'guion, guion bajo o punto, y empezar con letra o número.'
    ),
)

# Handles that would shadow (or be confused with) real routes of the site.
RESERVED_HANDLES = frozenset({
    'admin', 'api', 'app', 'blog', 'contact', 'lk', 'login', 'media',
    'panel', 'platform', 'portfolio', 'projectapp', 'proposal', 'static',
    'sitemap', 't', 'www',
})

# Catalog of button actions: Lucide icon + behavior kind. Mirrors the design's
# links.config.json `actions` block; `custom` lets the admin pick a free icon.
LINKTREE_ACTIONS = {
    'linkedin': {'icon': 'linkedin', 'kind': 'url'},
    'whatsapp': {'icon': 'whatsapp', 'kind': 'url'},
    'email': {'icon': 'mail', 'kind': 'mailto'},
    'web': {'icon': 'globe', 'kind': 'url'},
    'instagram': {'icon': 'instagram', 'kind': 'url'},
    'vcard': {'icon': 'user-round-plus', 'kind': 'download-vcard'},
    'install': {'icon': 'smartphone', 'kind': 'pwa-install'},
    'custom': {'icon': 'globe', 'kind': 'url'},
}


class Linktree(RetainedProjectModel, models.Model):
    """
    A public, customizable link-in-bio page served at /lk/@<handle>.
    It is the second destination type a QRCard can point to: the printed
    QR keeps encoding the stable /t/<uuid>/ shortlink and the redirect
    resolves here.
    """

    class Kind(models.TextChoices):
        PERSONAL = 'personal', 'Personal'
        COMPANY = 'company', 'Empresa'

    project = models.ForeignKey('accounts.Project', null=True, blank=True, on_delete=models.PROTECT, related_name='linktrees')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    handle = models.CharField(
        max_length=30, unique=True, validators=[HANDLE_VALIDATOR],
        help_text='Identificador público de la URL: projectapp.co/lk/@<handle>',
    )
    name = models.CharField(max_length=255, help_text='Nombre interno en el panel')
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PERSONAL)

    active_template_version = models.ForeignKey(
        "content.LinktreeTemplateVersion", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    # Identity block
    display_name = models.CharField(max_length=120, blank=True, default='')
    role = models.CharField(max_length=120, blank=True, default='')
    bio = models.TextField(blank=True, default='')
    # Avatar photo; when absent the public page renders the display_name
    # initials inside the circle instead.
    avatar = models.ImageField(upload_to='linktrees/avatars/', null=True, blank=True)
    claim_line_1 = models.CharField(max_length=120, blank=True, default='')
    claim_line_2 = models.CharField(max_length=120, blank=True, default='')
    badge_text = models.CharField(max_length=40, blank=True, default='')
    footer_tagline = models.CharField(
        max_length=80, blank=True, default='DISEÑO · CÓDIGO · RESULTADOS'
    )
    show_brand_header = models.BooleanField(default=True)

    # Per-card branding; defaults preserve existing published cards.
    logo = models.ImageField(upload_to='linktrees/logos/', null=True, blank=True)
    background_color = models.CharField(
        max_length=7, default='#001713', validators=[COLOR_VALIDATOR],
    )
    accent_color = models.CharField(
        max_length=7, default='#f0ff3d', validators=[COLOR_VALIDATOR],
    )
    text_color = models.CharField(
        max_length=7, default='#ffffff', validators=[COLOR_VALIDATOR],
    )
    muted_color = models.CharField(
        max_length=7, default='#809490', validators=[COLOR_VALIDATOR],
    )
    button_text_color = models.CharField(
        max_length=7, default='#001713', validators=[COLOR_VALIDATOR],
    )
    font_family = models.CharField(
        max_length=100, default='Ubuntu', validators=[RegexValidator(
            r'^[A-Za-z][A-Za-z0-9 -]{0,99}$',
            'Usa el nombre de una familia de Google Fonts.',
        )],
    )

    # "Save the card on your phone" block
    pwa_enabled = models.BooleanField(default=True)
    pwa_title = models.CharField(
        max_length=120, blank=True, default='Guarda la tarjeta en tu teléfono'
    )
    pwa_description = models.CharField(
        max_length=200, blank=True,
        default='Queda como un ícono en tu pantalla de inicio, sin instalar nada de la tienda.',
    )

    # vCard download data (only confirmed fields, per the design spec)
    vcard_first_name = models.CharField(max_length=80, blank=True, default='')
    vcard_last_name = models.CharField(max_length=80, blank=True, default='')
    vcard_org = models.CharField(max_length=120, blank=True, default='ProjectApp.')
    vcard_email = models.EmailField(blank=True, default='')
    vcard_tel = models.CharField(max_length=30, blank=True, default='')
    vcard_url = models.URLField(blank=True, default='')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Linktree'
        verbose_name_plural = 'Linktrees'

    def __str__(self):
        return f'{self.name} (@{self.handle})'

    @property
    def public_path(self):
        return f'/lk/@{self.handle}'


class LinktreeButton(models.Model):
    """
    One button of a linktree. The four tiers mirror the design system's
    hierarchy; cardinality rules (1 primary, ≤1 featured, pair in twos,
    ≤6 rows) are enforced in the serializer, not at the DB level.
    An empty href renders as the dashed "PENDIENTE" state.
    """

    class Tier(models.TextChoices):
        PRIMARY = 'primary', 'Principal'
        FEATURED = 'featured', 'Destacado'
        PAIR = 'pair', 'Par'
        ROW = 'row', 'Fila'

    class Action(models.TextChoices):
        LINKEDIN = 'linkedin', 'LinkedIn'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        EMAIL = 'email', 'Correo'
        WEB = 'web', 'Web'
        INSTAGRAM = 'instagram', 'Instagram'
        VCARD = 'vcard', 'Guardar contacto'
        INSTALL = 'install', 'Instalar'
        CUSTOM = 'custom', 'Personalizado'

    linktree = models.ForeignKey(
        Linktree, on_delete=models.CASCADE, related_name='buttons'
    )
    tier = models.CharField(max_length=10, choices=Tier.choices, default=Tier.ROW)
    action = models.CharField(max_length=12, choices=Action.choices, default=Action.WEB)
    label = models.CharField(max_length=80)
    href = models.CharField(max_length=500, blank=True, default='')
    icon = models.CharField(
        max_length=40, blank=True, default='',
        help_text='Nombre de ícono Lucide; solo aplica cuando action=custom',
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Linktree Button'
        verbose_name_plural = 'Linktree Buttons'

    def __str__(self):
        return f'{self.label} [{self.tier}] → {self.linktree.handle}'

    @property
    def resolved_icon(self):
        if self.action == self.Action.CUSTOM and self.icon:
            return self.icon
        return LINKTREE_ACTIONS.get(self.action, LINKTREE_ACTIONS['custom'])['icon']

    @property
    def kind(self):
        return LINKTREE_ACTIONS.get(self.action, LINKTREE_ACTIONS['custom'])['kind']

    @property
    def is_pending(self):
        """A URL-like button with no destination renders as PENDIENTE."""
        return self.kind in ('url', 'mailto') and not self.href
