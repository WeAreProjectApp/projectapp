from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import content.storage


class Migration(migrations.Migration):
    dependencies = [('content', '0277_merge_vat_and_economic_conditions'), ('accounts', '0075_p4_platform_domains_merge'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AlterField(model_name='businessproposal', name='platform_onboarding_completed_at', field=models.DateTimeField(blank=True, null=True, help_text='Set when the confirmed project package finished resource synchronization.')),
        migrations.AddField(model_name='businessproposal', name='platform_approval_manifest', field=models.JSONField(blank=True, default=dict)),
        migrations.CreateModel(name='ProposalApprovalFile', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('source_key', models.CharField(max_length=100)), ('title', models.CharField(max_length=300)),
            ('document_type', models.CharField(max_length=30)), ('filename', models.CharField(max_length=255)),
            ('file', models.FileField(max_length=500, storage=content.storage.get_private_storage, upload_to='proposal_approvals/%Y/%m/')),
            ('sha256', models.CharField(max_length=64)), ('size', models.PositiveIntegerField()),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ('deliverable', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='proposal_approval_files', to='accounts.deliverable')),
            ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='proposal_approval_files', to='accounts.project')),
            ('proposal', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='approval_files', to='content.businessproposal')),
        ], options={'verbose_name': 'documento del cierre de propuesta', 'verbose_name_plural': 'Documentos del cierre de propuestas', 'ordering': ['id'], 'constraints': [models.UniqueConstraint(fields=('proposal', 'source_key'), name='unique_proposal_approval_source')]}),
    ]
