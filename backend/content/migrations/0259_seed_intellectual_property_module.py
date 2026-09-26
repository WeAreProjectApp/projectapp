from django.db import migrations
from django.db.models import Max


MODULES = [
    {
        'category': 'identity-access',
        'slug': 'intellectual-property-protection',
        'icon': '🛡️',
        'name_es': 'Protección de propiedad intelectual',
        'name_en': 'Intellectual property protection',
        'summary_es': 'Dificulta que bots y agentes de inteligencia artificial copien tus secretos empresariales: el código, los contenidos y los datos que hacen único a tu negocio.',
        'summary_en': 'Makes it hard for bots and AI agents to copy your trade secrets: the code, content, and data that make your business unique.',
        'what_is_es': 'Un sistema de protección por capas que se instala dentro de tu plataforma: entrega ofuscado el código que llega al navegador, resguarda en el servidor la lógica sensible, pone límites y permisos al acceso a tus datos y controla qué pueden ver y usar los bots y agentes de inteligencia artificial, sin sacar tus páginas públicas de los buscadores.',
        'what_is_en': 'A layered protection system installed inside your platform: it obfuscates the code delivered to the browser, keeps sensitive logic on the server, puts limits and permissions on access to your data, and controls what bots and AI agents can see and use, without removing your public pages from search engines.',
        'purpose_es': 'Proteger lo que te costó construir —algoritmos, reglas de negocio, precios, catálogos y contenidos— haciendo que copiarlo cueste más de lo que vale y que cada intento detectado quede registrado como evidencia para actuar.',
        'purpose_en': 'Protect what it took to build—algorithms, business rules, prices, catalogs, and content—by making copying cost more than it is worth and recording every detected attempt as evidence to act on.',
        'problems_solved_es': [
            'Dificulta que un competidor o un agente de inteligencia artificial replique tu plataforma a partir del código que se descarga en el navegador.',
            'Frena la extracción masiva de catálogos, precios, contenidos y datos por parte de bots y rastreadores automatizados.',
            'Detecta los accesos automatizados sospechosos y deja registro de cada intento para identificar su origen.',
        ],
        'problems_solved_en': [
            'Makes it hard for a competitor or an AI agent to replicate your platform from the code downloaded to the browser.',
            'Curbs mass extraction of catalogs, prices, content, and data by bots and automated crawlers.',
            'Detects suspicious automated access and records every attempt to identify its source.',
        ],
        'integrations_es': [
            'Frontend web, aplicaciones y paneles de tu plataforma, con un build de producción protegido.',
            'APIs, servidor y base de datos, con límites de consulta, permisos por recurso y respuestas con sólo los datos necesarios.',
            'Hosting, dominio y red de distribución, con reglas para rastreadores y gestión de bots.',
        ],
        'integrations_en': [
            'Your platform’s web frontend, apps, and dashboards, with a protected production build.',
            'APIs, server, and database, with query limits, per-resource permissions, and responses carrying only the data needed.',
            'Hosting, domain, and delivery network, with crawler rules and bot management.',
        ],
        'implementation_requirements_es': [
            'Inventario de lo que se quiere proteger: algoritmos, reglas de negocio, contenidos, catálogos o datos clave.',
            'Acceso al código fuente, al hosting y a la configuración del dominio.',
            'Lista del tráfico legítimo que no debe bloquearse: buscadores, aliados, integraciones y aplicaciones propias.',
            'Diagnóstico técnico previo cuando la plataforma no fue desarrollada por nuestro equipo.',
            'Responsable designado para recibir los reportes de intentos detectados y aprobar ajustes.',
            'Capas y alcance definidos con el representante comercial en la propuesta.',
        ],
        'implementation_requirements_en': [
            'An inventory of what needs protection: algorithms, business rules, content, catalogs, or key data.',
            'Access to the source code, hosting, and domain configuration.',
            'A list of legitimate traffic that must not be blocked: search engines, partners, integrations, and in-house apps.',
            'A prior technical assessment when the platform was not built by our team.',
            'A designated owner to receive reports of detected attempts and approve adjustments.',
            'Layers and scope defined with the sales representative in the proposal.',
        ],
    },
]


def seed_intellectual_property_module(apps, _schema_editor):
    Category = apps.get_model('content', 'AdditionalModuleCategory')
    Module = apps.get_model('content', 'AdditionalModule')
    categories = {
        category.slug: category
        for category in Category.objects.filter(
            slug__in={row['category'] for row in MODULES},
        )
    }
    missing = {row['category'] for row in MODULES} - set(categories)
    if missing:
        raise RuntimeError(
            'Cannot seed intellectual property module; '
            f'missing categories: {sorted(missing)}',
        )

    next_orders = {}
    for category in categories.values():
        maximum = Module.objects.filter(category=category).aggregate(
            value=Max('order'),
        )['value']
        next_orders[category.pk] = (maximum if maximum is not None else -1) + 1

    for row in MODULES:
        values = dict(row)
        category = categories[values.pop('category')]
        slug = values.pop('slug')
        if Module.objects.filter(slug=slug).exists():
            continue
        Module.objects.create(
            category=category,
            slug=slug,
            order=next_orders[category.pk],
            is_active=True,
            **values,
        )
        next_orders[category.pk] += 1


def unseed_intellectual_property_module(apps, _schema_editor):
    Module = apps.get_model('content', 'AdditionalModule')
    Module.objects.filter(slug__in=[row['slug'] for row in MODULES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0258_communication_folders'),
    ]

    operations = [
        migrations.RunPython(
            seed_intellectual_property_module,
            unseed_intellectual_property_module,
        ),
    ]
