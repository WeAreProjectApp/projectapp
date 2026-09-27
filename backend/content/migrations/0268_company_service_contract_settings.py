from typing import ClassVar

from django.db import migrations, models

import content.models.company_settings


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [('content', '0267_add_provider_dependency_paragraph')]

    operations: ClassVar[list] = [
        migrations.AddField(
            model_name='companysettings',
            name='service_contract_settings',
            field=models.JSONField(
                default=content.models.company_settings.default_service_contract_settings,
            ),
        ),
    ]
