from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('content', '0267_add_provider_dependency_paragraph')]

    operations = [
        migrations.AddField(
            model_name='businessproposal',
            name='show_explainer_video',
            field=models.BooleanField(
                default=True,
                help_text='Show the welcome video when the four public options are available.',
            ),
        ),
        migrations.AddField(
            model_name='explainervideosettings',
            name='show_proposal_video',
            field=models.BooleanField(default=True),
        ),
    ]
