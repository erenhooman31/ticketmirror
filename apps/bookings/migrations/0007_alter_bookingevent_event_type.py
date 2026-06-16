from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0006_alter_reviewqueueitem_issue_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookingevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("email_new_booking", "Email new booking"),
                    ("email_booking_request", "Email booking request"),
                    ("email_update", "Email update"),
                    ("email_cancellation", "Email cancellation"),
                    ("manual_edit", "Manual edit"),
                    ("manual_status_change", "Manual status change"),
                    ("parser_review_resolved", "Parser review resolved"),
                    ("provider_alias_changed", "Provider alias changed"),
                    ("conflict_detected", "Conflict detected"),
                    ("bookeo_history_import", "Bookeo history import"),
                ],
                max_length=40,
            ),
        ),
    ]
