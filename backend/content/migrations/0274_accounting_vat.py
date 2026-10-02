from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('content', '0273_merge_document_provenance_and_proposal_owner')]
    operations = [
        migrations.AddField(
            model_name=name, name='vat_rate',
            field=models.DecimalField(
                max_digits=5, decimal_places=2, null=True, blank=True,
                validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
            ),
        )
        for name in ('incomerecord', 'expenserecord', 'hostingrecord', 'documentcollectionaccount')
    ]
