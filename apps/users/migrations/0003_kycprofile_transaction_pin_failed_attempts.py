from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0002_kycprofile_transaction_pin_hash")]

    operations = [
        migrations.AddField(
            model_name="kycprofile",
            name="transaction_pin_failed_attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]