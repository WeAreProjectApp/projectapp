from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0064_delivery_review_workflow')]
    operations = [
        migrations.AddField(model_name='contractsignatureevidence', name='method', field=models.CharField(choices=[('portal', 'Platform'), ('external', 'Firma externa')], default='external', max_length=20)),
        migrations.AddField(model_name='contractsignatureevidence', name='source_sha256', field=models.CharField(blank=True, default='', max_length=64)),
        migrations.AddField(model_name='contractsignatureevidence', name='source_snapshot', field=models.JSONField(default=dict)),
    ]
