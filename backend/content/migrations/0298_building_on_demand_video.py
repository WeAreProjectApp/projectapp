from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('content', '0297_shared_binary_drafts')]

    operations = [
        migrations.AddField(
            model_name='explainervideosettings',
            name='show_building_on_demand_video',
            field=models.BooleanField(default=True),
        ),
    ]
