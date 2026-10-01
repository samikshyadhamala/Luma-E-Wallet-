from django import forms

from apps.transactions.models import Budget, BudgetGoal, ExpenseCategory, RefundRequest, Transaction


class AmountForm(forms.Form):
    amount = forms.DecimalField(min_value=0.01, max_digits=12, decimal_places=2)
    description = forms.CharField(required=False, max_length=255)
    transaction_pin = forms.CharField(min_length=4, max_length=6, widget=forms.PasswordInput, label="Transaction PIN")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"] = forms.ModelChoiceField(
            queryset=ExpenseCategory.objects.filter(owner__isnull=True),
            required=False,
            empty_label="Uncategorized",
        )
        if user is not None:
            self.fields["category"].queryset = ExpenseCategory.objects.filter(owner__isnull=True) | ExpenseCategory.objects.filter(owner=user)


class TransferForm(AmountForm):
    recipient = forms.CharField(max_length=150, label="Recipient username or wallet ID")


class RefundForm(forms.ModelForm):
    class Meta:
        model = RefundRequest
        fields = ("reason",)


class TransactionFilterForm(forms.Form):
    status = forms.ChoiceField(required=False, choices=[("", "All statuses"), *Transaction.Status.choices])
    category = forms.ModelChoiceField(queryset=ExpenseCategory.objects.none(), required=False, empty_label="All categories")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["category"].queryset = ExpenseCategory.objects.filter(owner__isnull=True) | ExpenseCategory.objects.filter(owner=user)


class BudgetForm(forms.ModelForm):
    month = forms.DateField(widget=forms.DateInput(attrs={"type": "month"}), input_formats=["%Y-%m"])

    class Meta:
        model = Budget
        fields = ("category", "month", "amount")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ExpenseCategory.objects.filter(owner__isnull=True) | ExpenseCategory.objects.filter(owner=user)


class BudgetGoalForm(forms.ModelForm):
    class Meta:
        model = BudgetGoal
        fields = ("name", "target_amount", "saved_amount", "target_date", "notes")
        widgets = {"target_date": forms.DateInput(attrs={"type": "date"})}


class AddSavingsForm(forms.Form):
    amount = forms.DecimalField(min_value=0.01, max_digits=12, decimal_places=2, label="Amount to save")
    transaction_pin = forms.CharField(min_length=4, max_length=6, widget=forms.PasswordInput, label="Transaction PIN")