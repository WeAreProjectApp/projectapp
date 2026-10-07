import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0283_proposal_project_reassignment'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectRetentionOperation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation', models.CharField(choices=[('adopt', 'Traslado a un proyecto vigente'), ('undo', 'Deshacer un traslado'), ('discard', 'Descarte de contenedores vacíos'), ('proposal_reassignment', 'Reasignación de propuesta')], max_length=24)),
                ('origin', models.CharField(max_length=40)),
                ('target_project_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('target_project_name', models.CharField(blank=True, default='', max_length=200)),
                ('request_id', models.CharField(max_length=100, unique=True)),
                ('payload_hash', models.CharField(blank=True, default='', max_length=64)),
                ('reason', models.TextField(blank=True, default='')),
                ('items', models.JSONField(default=list)),
                ('removed_records', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('context', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='operations', to='content.projectretentioncontext')),
                ('reverts', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reverted_by', to='content.projectretentionoperation')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
