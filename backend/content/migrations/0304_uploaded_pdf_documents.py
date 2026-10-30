from django.db import migrations, models
import content.storage


class Migration(migrations.Migration):
    dependencies = [('content', '0303_merge_editorial_requirement_packages')]

    operations = [
        migrations.AddField(model_name='document', name='content_format', field=models.CharField(choices=[('markdown', 'Markdown'), ('pdf', 'PDF')], default='markdown', max_length=16)),
        migrations.AddField(model_name='document', name='uploaded_pdf', field=models.FileField(blank=True, max_length=500, storage=content.storage.get_private_storage, upload_to='documents/uploaded/%Y/%m/')),
        migrations.AddField(model_name='document', name='pdf_filename', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='document', name='pdf_size', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='document', name='pdf_sha256', field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name='document', name='pdf_version', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='document', name='pdf_search_text', field=models.TextField(blank=True)),
        migrations.AddField(model_name='document', name='pdf_text_status', field=models.CharField(blank=True, max_length=16)),
    ]
