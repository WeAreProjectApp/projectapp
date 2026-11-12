from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0090_pending_billing_document'),
        ('content', '0304_uploaded_pdf_documents'),
    ]

    operations = [
        migrations.AddField(
            model_name='billingcontextevent', name='retention_context',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='%(app_label)s_%(class)s_records', to='content.projectretentioncontext',
            ),
        ),
        migrations.AlterField(
            model_name='billingcontextevent', name='project',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='billing_context_events', to='accounts.project',
            ),
        ),
        migrations.AddConstraint(
            model_name='billingcontextevent',
            constraint=models.CheckConstraint(
                condition=(models.Q(project__isnull=False, retention_context__isnull=True)
                           | models.Q(project__isnull=True, retention_context__isnull=False)),
                name='billing_event_has_owner',
            ),
        ),
    ]
