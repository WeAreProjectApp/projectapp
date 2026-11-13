from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('monitoring', '0005_alter_delivery_milestone'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.AddField(model_name='case', name='summary', field=models.CharField(blank=True, max_length=500)),
        migrations.CreateModel(name='TelemetrySample', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('observed_at', models.DateTimeField()),
            ('cpu_percent', models.FloatField(null=True)),
            ('cpu_count', models.PositiveIntegerField()),
            ('load_1m', models.FloatField()),
            ('ram_total_bytes', models.PositiveBigIntegerField()),
            ('ram_used_bytes', models.PositiveBigIntegerField()),
            ('disk_total_bytes', models.PositiveBigIntegerField()),
            ('disk_used_bytes', models.PositiveBigIntegerField()),
            ('delivery', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='sample', to='monitoring.delivery')),
            ('resource', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='samples', to='monitoring.resource')),
        ], options={'ordering': ['observed_at', 'pk'], 'indexes': [models.Index(fields=['resource', 'observed_at'], name='monitor_sample_resource_time')]}),
        migrations.CreateModel(name='CapacityAllocation', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('cpu_mode', models.CharField(choices=[('unknown', 'Sin configurar'), ('shared', 'Compartida'), ('assigned', 'Asignada')], default='unknown', max_length=10)),
            ('cpu_vcpu', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True)),
            ('ram_mode', models.CharField(choices=[('unknown', 'Sin configurar'), ('shared', 'Compartida'), ('assigned', 'Asignada')], default='unknown', max_length=10)),
            ('ram_bytes', models.PositiveBigIntegerField(blank=True, null=True)),
            ('storage_mode', models.CharField(choices=[('unknown', 'Sin configurar'), ('shared', 'Compartida'), ('assigned', 'Asignada')], default='unknown', max_length=10)),
            ('storage_bytes', models.PositiveBigIntegerField(blank=True, null=True)),
            ('version', models.PositiveIntegerField(default=1)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('resource', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='allocation', to='monitoring.resource')),
        ]),
        migrations.CreateModel(name='CapacityChange', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('actor_name', models.CharField(max_length=150)),
            ('before', models.JSONField(default=dict)),
            ('after', models.JSONField(default=dict)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ('allocation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='changes', to='monitoring.capacityallocation')),
        ], options={'ordering': ['-created_at', '-pk']}),
    ]
