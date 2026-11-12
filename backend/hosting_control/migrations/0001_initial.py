from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [('monitoring', '0005_alter_delivery_milestone'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Control', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('mode', models.CharField(choices=[('normal', 'Normal'), ('suspended', 'Pantalla de suspensión'), ('banner', 'Banner de aviso')], default='normal', max_length=12)),
            ('suspension_title', models.CharField(default='Servicio suspendido', max_length=200)),
            ('suspension_text', models.TextField(default='Comunícate con tu proveedor de hosting, mantenimiento y soporte para gestionar la reactivación del servicio.', max_length=2000)),
            ('banner_title', models.CharField(default='Pago pendiente del servicio', max_length=200)),
            ('banner_text', models.TextField(default='El servicio de hosting, mantenimiento y soporte tiene un pago pendiente. Por favor, comunícate con tu proveedor.', max_length=2000)),
            ('version', models.PositiveIntegerField(default=0)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('resource', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='hosting_control', to='monitoring.resource')),
        ], options={'constraints': [models.CheckConstraint(condition=models.Q(mode__in=['normal', 'suspended', 'banner']), name='hosting_control_valid_mode')]}),
        migrations.CreateModel(name='Target', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('key', models.SlugField(max_length=100, unique=True)),
            ('origins', models.JSONField(default=list)),
            ('lifecycle', models.CharField(choices=[('active', 'Activo'), ('suspended', 'Servicios suspendidos'), ('removed', 'Retirado')], default='active', max_length=12)),
            ('adapter', models.CharField(max_length=40)),
            ('acknowledged_version', models.PositiveIntegerField(null=True)),
            ('acknowledged_digest', models.CharField(blank=True, max_length=64)),
            ('acknowledged_at', models.DateTimeField(null=True)),
            ('last_seen_at', models.DateTimeField(null=True)),
            ('last_error', models.CharField(blank=True, max_length=300)),
            ('control', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='targets', to='hosting_control.control')),
        ]),
        migrations.CreateModel(name='Event', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('actor_name', models.CharField(max_length=150)),
            ('source', models.CharField(max_length=100)),
            ('before', models.JSONField()), ('after', models.JSONField()),
            ('version', models.PositiveIntegerField()), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ('control', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='events', to='hosting_control.control')),
        ], options={'ordering': ['-id']}),
        migrations.CreateModel(name='RuntimeCredential', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('label', models.CharField(max_length=150)),
            ('token_hash', models.CharField(max_length=64, unique=True)),
            ('revoked_at', models.DateTimeField(null=True)),
            ('targets', models.ManyToManyField(to='hosting_control.target')),
        ]),
    ]
