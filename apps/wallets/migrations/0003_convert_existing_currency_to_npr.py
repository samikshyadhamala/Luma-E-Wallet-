from django.db import migrations


def convert_wallet_currency(apps, schema_editor):
    Wallet = apps.get_model("wallets", "Wallet")
    Wallet.objects.filter(currency="USD").update(currency="NPR")


class Migration(migrations.Migration):
    dependencies = [("wallets", "0002_alter_wallet_currency")]

    operations = [migrations.RunPython(convert_wallet_currency, migrations.RunPython.noop)]