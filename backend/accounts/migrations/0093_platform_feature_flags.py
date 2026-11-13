from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('accounts', '0092_merge_parallel_features'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='PlatformFeatureSettings', fields=[
            ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
            ('values', models.JSONField(default=dict)),
            ('version', models.PositiveIntegerField(default=0)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name='ClientPlatformFeatureSettings', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('values', models.JSONField(default=dict)),
            ('version', models.PositiveIntegerField(default=0)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='platform_feature_settings', to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='PlatformFeatureEvent', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('scope', models.CharField(max_length=10)),
            ('changes', models.JSONField(default=dict)),
            ('version', models.PositiveIntegerField()),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ('client', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['-id']}),
    ]
