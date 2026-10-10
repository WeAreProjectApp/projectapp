from django.db import migrations
from django.db.models import Max


MODULES = [
    {
        'category': 'public-sector',
        'slug': 'government-procurement',
        'icon': '🏛️',
        'name_es': 'Contratación estatal',
        'name_en': 'Government procurement',
        'summary_es': 'Encuentra en el SECOP II los procesos de contratación pública que le sirven a tu empresa, recibe alertas por correo y haz el seguimiento con tu equipo.',
        'summary_en': 'Find the SECOP II public procurement processes that fit your company, get email alerts, and track them with your team.',
        'what_is_es': 'Un módulo que se instala dentro de tu plataforma y se conecta a los datos abiertos del SECOP II, el sistema donde las entidades públicas de Colombia publican sus procesos de contratación. Cada día trae los procesos abiertos y los deja listos para buscarlos, filtrarlos, guardar las búsquedas frecuentes, recibir alertas y hacerles seguimiento, sin entrar al portal a revisarlos uno por uno.',
        'what_is_en': 'A module installed inside your platform that connects to SECOP II open data, the system where Colombian public entities publish their procurement processes. Every day it brings in the open processes and gets them ready to search, filter, save frequent searches, receive alerts, and track, without going into the portal to review them one by one.',
        'purpose_es': 'Que las empresas que le venden al Estado —proveedores y contratistas, constructoras, firmas de ingeniería civil e interventoría y consultoras de servicios profesionales— y sus áreas comerciales y de licitaciones encuentren a tiempo los procesos que les sirven y decidan en equipo a cuáles presentarse. También sirve a las firmas de abogados que asesoran en contratación pública y a los gremios que siguen lo que se abre en su sector.',
        'purpose_en': 'Help companies that sell to the government—suppliers and contractors, construction companies, civil engineering and construction supervision firms, and professional services consultancies—and their sales and bid teams find the processes that fit them in time and decide together which ones to bid on. It also serves law firms that advise on public procurement and trade associations that follow what opens up in their sector.',
        'problems_solved_es': [
            'Las áreas comerciales y de licitaciones dejan de revisar el SECOP II a mano: los procesos nuevos que cumplen sus criterios les llegan por correo apenas se detectan, o en un resumen diario o semanal.',
            'Reduce el riesgo de enterarse tarde: cada proceso muestra cuántos días faltan para su cierre, se resalta cuando quedan tres o menos y enlaza a su publicación oficial.',
            'Saca el seguimiento de las hojas de cálculo sueltas: cada persona marca los procesos como interesantes, en revisión, aplicados o descartados, con notas que ve el resto del equipo.',
        ],
        'problems_solved_en': [
            'Sales and bid teams stop checking SECOP II by hand: new processes that match their criteria arrive by email as soon as they are detected, or in a daily or weekly digest.',
            'Lowers the risk of finding out too late: each process shows how many days are left until it closes, is highlighted when three or fewer remain, and links to its official listing.',
            'Takes tracking out of scattered spreadsheets: each person marks processes as interesting, under review, applied, or discarded, with notes the rest of the team can see.',
        ],
        'integrations_es': [
            'Datos abiertos del SECOP II que publica Colombia Compra Eficiente, actualizados una vez al día.',
            'Correo electrónico del equipo para las alertas inmediatas, diarias o semanales.',
            'Usuarios y roles de tu plataforma, y exportación a Excel para reportes y comités de licitaciones.',
        ],
        'integrations_en': [
            'SECOP II open data published by Colombia Compra Eficiente, updated once a day.',
            'Your team’s email for immediate, daily, or weekly alerts.',
            'Your platform’s users and roles, plus Excel export for reports and bid committees.',
        ],
        'implementation_requirements_es': [
            'Criterios de búsqueda iniciales: palabras clave, entidades, departamentos, rangos de presupuesto y códigos UNSPSC, el clasificador de bienes y servicios que usa el Estado.',
            'Lista de las personas que van a usar el módulo y qué puede hacer cada una.',
            'Correos que recibirán las alertas y la frecuencia de cada una: inmediata, diaria o semanal.',
            'Identidad de marca y remitente para los correos de alerta.',
            'Diagnóstico técnico previo cuando la plataforma no fue desarrollada por nuestro equipo.',
            'Alcance definido con el representante comercial en la propuesta.',
        ],
        'implementation_requirements_en': [
            'Initial search criteria: keywords, entities, departments, budget ranges, and UNSPSC codes, the goods and services classification used by the government.',
            'A list of the people who will use the module and what each one can do.',
            'The emails that will receive alerts and how often each one: immediate, daily, or weekly.',
            'Brand identity and sender for the alert emails.',
            'A prior technical assessment when the platform was not built by our team.',
            'Scope defined with the sales representative in the proposal.',
        ],
    },
]


def seed_government_procurement_module(apps, _schema_editor):
    Category = apps.get_model('content', 'AdditionalModuleCategory')
    Module = apps.get_model('content', 'AdditionalModule')
    category = Category.objects.filter(slug='public-sector').first()
    if category is None:
        maximum = Category.objects.aggregate(value=Max('order'))['value']
        category = Category.objects.create(
            slug='public-sector',
            name_es='Sector público',
            name_en='Public sector',
            order=(maximum if maximum is not None else -1) + 1,
            is_active=True,
        )

    maximum = Module.objects.filter(category=category).aggregate(
        value=Max('order'),
    )['value']
    next_order = (maximum if maximum is not None else -1) + 1

    for row in MODULES:
        values = dict(row)
        values.pop('category')
        slug = values.pop('slug')
        if Module.objects.filter(slug=slug).exists():
            continue
        Module.objects.create(
            category=category,
            slug=slug,
            order=next_order,
            is_active=category.is_active,
            **values,
        )
        next_order += 1


def unseed_government_procurement_module(apps, _schema_editor):
    Category = apps.get_model('content', 'AdditionalModuleCategory')
    Module = apps.get_model('content', 'AdditionalModule')
    Module.objects.filter(slug__in=[row['slug'] for row in MODULES]).delete()
    category = Category.objects.filter(slug='public-sector').first()
    if category is not None and not Module.objects.filter(category=category).exists():
        category.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0285_merge_platform_manager_retention'),
    ]

    operations = [
        migrations.RunPython(
            seed_government_procurement_module,
            unseed_government_procurement_module,
        ),
    ]
