from django.db import migrations


def convert_transaction_currency(apps, schema_editor):
    Transaction = apps.get_model("transactions", "Transaction")
    Transaction.objects.filter(currency="USD").update(currency="NPR")


class Migration(migrations.Migration):
    dependencies = [("transactions", "0003_alter_transaction_currency")]

    operations = [migrations.RunPython(convert_transaction_currency, migrations.RunPython.noop)]