from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


DEFAULT_CATEGORIES = [
    "Food & dining",
    "Transport",
    "Bills & utilities",
    "Shopping",
    "Health",
    "Entertainment",
    "Education",
    "Other",
]


def create_default_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model("transactions", "ExpenseCategory")
    ExpenseCategory.objects.bulk_create([ExpenseCategory(name=name) for name in DEFAULT_CATEGORIES])


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0005_refundrequest_refund_transaction"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExpenseCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=80)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="expense_categories", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="Budget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("month", models.DateField(help_text="Use the first day of the budget month.")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(0.01)])),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="budgets", to="transactions.expensecategory")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="budgets", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-month", "category__name")},
        ),
        migrations.CreateModel(
            name="BudgetGoal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("target_amount", models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(0.01)])),
                ("saved_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14, validators=[django.core.validators.MinValueValidator(0)])),
                ("target_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="budget_goals", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("target_date", "-created_at")},
        ),
        migrations.AddField(
            model_name="transaction",
            name="category",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="transactions", to="transactions.expensecategory"),
        ),
        migrations.AddConstraint(
            model_name="expensecategory",
            constraint=models.UniqueConstraint(fields=("owner", "name"), name="unique_expense_category_per_owner"),
        ),
        migrations.AddConstraint(
            model_name="budget",
            constraint=models.UniqueConstraint(fields=("owner", "category", "month"), name="unique_budget_per_category_month"),
        ),
        migrations.RunPython(create_default_categories, migrations.RunPython.noop),
    ]