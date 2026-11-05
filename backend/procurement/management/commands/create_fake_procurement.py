from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from content.fake_data import add_seed_arguments, ensure_fake_data_allowed, seed_context
from procurement.models import Alert, Opportunity, SavedSearch
from procurement.services.records import classify


class Command(BaseCommand):
    help = 'Crea oportunidades SECOP de ejemplo sin consultar fuentes ni enviar correo.'

    def add_arguments(self, parser):
        add_seed_arguments(parser, count_default=8)

    @transaction.atomic
    def handle(self, **options):
        ensure_fake_data_allowed('create_fake_procurement')
        context = seed_context(options, 'procurement')
        owner = get_user_model().objects.filter(is_staff=True, is_active=True).order_by('pk').first()
        if owner is None:
            raise CommandError('Se requiere un administrador activo para los ejemplos.')
        for index in range(min(max(options['count'], 4), 30)):
            opportunity, _ = Opportunity.objects.update_or_create(source_id=f'DEMO.SECOP.{index+1}', defaults={
                'reference': f'DEMO-{index+1:03d}', 'title': f'Desarrollo de plataforma institucional {index+1}',
                'description': 'Proceso de ejemplo para desarrollo de software, soporte y mantenimiento.',
                'entity_name': f'Entidad pública de ejemplo {index+1}',
                'department': ['Bogotá D.C.', 'Antioquia', 'Cundinamarca'][index % 3],
                'method': 'Concurso de méritos', 'contract_type': 'Prestación de servicios',
                'source_status': 'Abierto', 'budget': 50000000 + index*10000000,
                'unspsc_code': '81111500', 'published_at': context.anchor_now-timedelta(days=index),
                'closing_at': context.anchor_now+timedelta(days=index+1),
            })
            if index < 4:
                state = ['interesting', 'reviewing', 'applied', 'discarded'][index]
                classify(opportunity.pk, {'state': state, 'notes': 'Ejemplo: revisar experiencia y requisitos; no es una recomendación real.'}, owner, owner)
        filters = {'keywords': ['software'], 'unspsc_codes': ['8111']}
        SavedSearch.objects.get_or_create(owner=owner, name='Software · ejemplo', defaults={'filters': filters})
        Alert.objects.get_or_create(name='Oportunidades software · ejemplo', created_by=owner, defaults={
            'filters': filters, 'recipients': ['procurement@example.com'], 'frequency': 'daily', 'is_active': False,
        })
        self.stdout.write('Ejemplos de contratación estatal creados; alerta inactiva y sin envíos.')
