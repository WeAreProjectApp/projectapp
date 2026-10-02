import content.storage
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0065_immutable_portal_contract_signature')]

    operations = [
        migrations.CreateModel(
            name='DeliveryReviewDocumentEvidence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('file', models.FileField(max_length=500, storage=content.storage.get_private_storage, upload_to='delivery/reviews/%Y/%m/')),
                ('sha256', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='delivery_review_evidence', to='content.document')),
                ('review', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='document_evidence', to='accounts.requirementreview')),
            ],
            options={
                'ordering': ['id'],
                'constraints': [models.UniqueConstraint(fields=('review', 'document'), name='delivery_review_document_unique')],
            },
        ),
    ]
