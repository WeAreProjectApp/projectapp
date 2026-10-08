"""Change future storage; historical names are converted by a verified manifest."""
from django.db import migrations, models

from accounts.platform_media_storage import get_platform_resource_storage


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0080_delivery_activity_notices'),
        ('content', '0285_merge_platform_manager_retention'),
    ]

    operations = [
        migrations.AlterField(model_name='deliverable', name='file',
            field=models.FileField(storage=get_platform_resource_storage,
                upload_to='platform-resources/current/', max_length=500, blank=True, null=True)),
        migrations.AlterField(model_name='deliverableversion', name='file',
            field=models.FileField(storage=get_platform_resource_storage,
                upload_to='platform-resources/versions/', max_length=500)),
        migrations.AlterField(model_name='deliverablefile', name='file',
            field=models.FileField(storage=get_platform_resource_storage,
                upload_to='platform-resources/attachments/', max_length=500)),
        migrations.AlterField(model_name='deliverableclientupload', name='file',
            field=models.FileField(storage=get_platform_resource_storage,
                upload_to='platform-resources/client_uploads/', max_length=500)),
    ]
