from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingestion", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="gmailsyncstate",
            name="poll_lock_token",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="gmailsyncstate",
            name="poll_lock_acquired_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
