"""Join P4 access/ideas models with the published P2 integration leaf."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0074_p2_platform_billing_merge'),
        ('accounts', '0070_platform_ideas_access'),
    ]

    operations = []
