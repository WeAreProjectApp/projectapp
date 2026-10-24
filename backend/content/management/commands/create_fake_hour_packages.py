from django.core.management.base import BaseCommand

from content.models import HourPackage
from content.fake_data import add_seed_arguments, ensure_fake_data_allowed
from content.services.requirement_package_service import DEFAULT_PACKAGES

# All three nationalities are normally seeded by migration 0302 from the
# canonical requirement tiers; this command only refills a nationality
# whose catalog was emptied (e.g. after delete_fake_data or manual cleanup)
# so the panel tabs and proposal seeding stay exercisable in dev/staging.


class Command(BaseCommand):
    help = (
        'Seed the default requirement packages for any nationality whose catalog '
        'is empty (COL/EXT/USA). Idempotent: non-empty catalogs are kept.'
    )

    def add_arguments(self, parser):
        add_seed_arguments(parser)

    def handle(self, *args, **options):
        ensure_fake_data_allowed('create_fake_hour_packages')
        created = 0
        for nationality in ('COL', 'EXT', 'USA'):
            if HourPackage.objects.filter(nationality=nationality, pricing_model='requirements').exists():
                continue
            HourPackage.objects.bulk_create(
                HourPackage(nationality=nationality, pricing_model='requirements', is_active=True, **fields)
                for fields in DEFAULT_PACKAGES
            )
            created += len(DEFAULT_PACKAGES)
        self.stdout.write(self.style.SUCCESS(
            f'Requirement packages: {created} created from defaults.'
        ))
