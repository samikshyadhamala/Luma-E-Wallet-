from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.transactions.models import Budget, BudgetGoal, ExpenseCategory, LedgerEntry, RefundRequest, Transaction
from apps.users.models import KYCProfile
from apps.wallets.models import Wallet


class Command(BaseCommand):
    help = "Create or refresh the demo admin, customer, and finance dashboard data."

    admin_username = "admin_demo"
    customer_username = "demo_user"
    admin_password = "DemoAdmin@12345"
    customer_password = "DemoUser@12345"
    demo_pin = "2468"

    def handle(self, *args, **options):
        with db_transaction.atomic():
            admin = self._user(self.admin_username, "admin@example.com", self.admin_password, is_staff=True, is_superuser=True)
            customer = self._user(self.customer_username, "demo@example.com", self.customer_password)
            self._verify(admin, "Demo Administrator", "9800000001", "ADMIN-DEMO-001")
            self._verify(customer, "Demo Customer", "9800000002", "CUSTOMER-DEMO-001")
            categories = self._categories()
            self._clear_demo_data(customer, admin)
            self._seed_transactions(customer, admin, categories)
            self._seed_budgets(customer, categories)
            self._seed_goals(customer)
            self._seed_refunds(customer, admin, categories)

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self.stdout.write(f"Admin: {self.admin_username} / {self.admin_password}")
        self.stdout.write(f"User:  {self.customer_username} / {self.customer_password}")

    def _user(self, username, email, password, is_staff=False, is_superuser=False):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        user.email = email
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.is_active = True
        user.set_password(password)
        user.save()
        if created:
            self.stdout.write(f"Created {username}")
        return user

    def _verify(self, user, full_name, phone, id_number):
        profile = user.kycprofile
        profile.full_name = full_name
        profile.phone_number = phone
        profile.id_number = id_number
        profile.status = KYCProfile.Status.VERIFIED
        profile.verified_by = user
        profile.verified_at = timezone.now()
        profile.transaction_pin_hash = make_password(self.demo_pin)
        profile.transaction_pin_failed_attempts = 0
        profile.save()

    def _categories(self):
        names = ["Food & dining", "Transport", "Bills & utilities", "Shopping", "Health", "Entertainment", "Education", "Other"]
        return {name: ExpenseCategory.objects.get_or_create(owner=None, name=name)[0] for name in names}

    def _clear_demo_data(self, customer, admin):
        demo_transactions = Transaction.objects.filter(description__startswith="DEMO:")
        RefundRequest.objects.filter(transaction__in=demo_transactions).delete()
        LedgerEntry.objects.filter(transaction__in=demo_transactions).delete()
        demo_transactions.delete()
        Budget.objects.filter(owner=customer).delete()
        BudgetGoal.objects.filter(owner=customer).delete()

    def _when(self, days_ago):
        return timezone.now() - timedelta(days=days_ago)

    def _transaction(self, *, owner_wallet, other_wallet=None, amount, kind, description, category=None, status=Transaction.Status.SUCCESS, risk=Transaction.RiskStatus.CLEAR, score=None, days_ago=0, incoming=False):
        created_at = self._when(days_ago)
        record = Transaction.objects.create(
            transaction_type=kind,
            status=status,
            risk_status=risk,
            risk_score=score,
            risk_reason="DEMO: manual review example" if risk in {Transaction.RiskStatus.FLAGGED, Transaction.RiskStatus.BLOCKED} else "DEMO: seeded sample",
            amount=amount,
            currency="NPR",
            category=category,
            sender_wallet=None if incoming else owner_wallet,
            receiver_wallet=owner_wallet if incoming else other_wallet,
            description=f"DEMO: {description}",
            processed_at=created_at if status == Transaction.Status.SUCCESS else None,
        )
        Transaction.objects.filter(pk=record.pk).update(created_at=created_at, updated_at=created_at)
        entry_type = LedgerEntry.EntryType.CREDIT if incoming else LedgerEntry.EntryType.DEBIT
        LedgerEntry.objects.create(
            transaction=record,
            wallet=owner_wallet,
            entry_type=entry_type,
            amount=amount,
            balance_before=Decimal("0.00"),
            balance_after=Decimal("0.00"),
        )
        return record

    def _seed_transactions(self, customer, admin, categories):
        customer_wallet = customer.wallet
        admin_wallet = admin.wallet
        records = [
            dict(amount=Decimal("25000"), kind=Transaction.Type.TOP_UP, description="Monthly salary top-up", category=None, days_ago=45, incoming=True),
            dict(amount=Decimal("18000"), kind=Transaction.Type.TOP_UP, description="Current month income", category=None, days_ago=8, incoming=True),
            dict(amount=Decimal("2200"), kind=Transaction.Type.WITHDRAW, description="Groceries and dining", category=categories["Food & dining"], days_ago=2),
            dict(amount=Decimal("950"), kind=Transaction.Type.WITHDRAW, description="Bus and rides", category=categories["Transport"], days_ago=5),
            dict(amount=Decimal("3200"), kind=Transaction.Type.WITHDRAW, description="Electricity bill", category=categories["Bills & utilities"], days_ago=12),
            dict(amount=Decimal("7800"), kind=Transaction.Type.WITHDRAW, description="Large online purchase", category=categories["Shopping"], days_ago=1, risk=Transaction.RiskStatus.FLAGGED, score=Decimal("0.9200")),
            dict(amount=Decimal("4500"), kind=Transaction.Type.TRANSFER, description="Rent transfer", category=categories["Bills & utilities"], days_ago=18),
            dict(amount=Decimal("1250"), kind=Transaction.Type.TRANSFER, description="Blocked unusual transfer", category=categories["Other"], days_ago=3, status=Transaction.Status.REJECTED, risk=Transaction.RiskStatus.BLOCKED, score=Decimal("0.9700")),
            dict(amount=Decimal("400"), kind=Transaction.Type.WITHDRAW, description="Pending cash withdrawal", category=categories["Other"], days_ago=0, status=Transaction.Status.PENDING, risk=Transaction.RiskStatus.NOT_REVIEWED, score=None),
            dict(amount=Decimal("300"), kind=Transaction.Type.WITHDRAW, description="Failed ATM attempt", category=categories["Other"], days_ago=22, status=Transaction.Status.FAILED, risk=Transaction.RiskStatus.CLEAR, score=Decimal("0.0400")),
        ]
        for data in records:
            self._transaction(owner_wallet=customer_wallet, other_wallet=admin_wallet, **data)

        self._transaction(
            owner_wallet=customer_wallet,
            other_wallet=admin_wallet,
            amount=Decimal("1500"),
            kind=Transaction.Type.TRANSFER,
            description="Incoming reimbursement",
            category=categories["Other"],
            days_ago=6,
            incoming=True,
        )
        customer_wallet.balance = Decimal("27300.00")
        customer_wallet.save(update_fields=["balance", "updated_at"])
        admin_wallet.balance = Decimal("0.00")
        admin_wallet.save(update_fields=["balance", "updated_at"])

    def _seed_budgets(self, customer, categories):
        current = date.today().replace(day=1)
        previous = (current - timedelta(days=1)).replace(day=1)
        following = (current + timedelta(days=32)).replace(day=1)
        budgets = [
            (categories["Food & dining"], current, Decimal("1800")),
            (categories["Transport"], current, Decimal("1200")),
            (categories["Shopping"], current, Decimal("5000")),
            (categories["Bills & utilities"], current, Decimal("2500")),
            (categories["Food & dining"], previous, Decimal("4500")),
            (categories["Entertainment"], following, Decimal("3000")),
        ]
        for category, month, amount in budgets:
            Budget.objects.create(owner=customer, category=category, month=month, amount=amount)

    def _seed_goals(self, customer):
        today = date.today()
        BudgetGoal.objects.bulk_create([
            BudgetGoal(owner=customer, name="Emergency fund", target_amount=Decimal("50000"), saved_amount=Decimal("31500"), target_date=today + timedelta(days=180), notes="DEMO: in progress"),
            BudgetGoal(owner=customer, name="New laptop", target_amount=Decimal("85000"), saved_amount=Decimal("85000"), target_date=today - timedelta(days=20), notes="DEMO: completed"),
            BudgetGoal(owner=customer, name="Festival travel", target_amount=Decimal("30000"), saved_amount=Decimal("0"), target_date=today + timedelta(days=90), notes="DEMO: not started"),
        ])

    def _seed_refunds(self, customer, admin, categories):
        pending_transaction = self._transaction(owner_wallet=customer.wallet, other_wallet=admin.wallet, amount=Decimal("7800"), kind=Transaction.Type.WITHDRAW, description="Refund requested purchase", category=categories["Shopping"], days_ago=4, risk=Transaction.RiskStatus.FLAGGED, score=Decimal("0.6700"))
        rejected_transaction = self._transaction(owner_wallet=customer.wallet, other_wallet=admin.wallet, amount=Decimal("950"), kind=Transaction.Type.WITHDRAW, description="Refund rejected example", category=categories["Transport"], days_ago=30)
        completed_transaction = self._transaction(owner_wallet=customer.wallet, other_wallet=admin.wallet, amount=Decimal("1200"), kind=Transaction.Type.WITHDRAW, description="Refund completed purchase", category=categories["Shopping"], days_ago=40)
        RefundRequest.objects.create(transaction=pending_transaction, requested_by=customer, reason="DEMO: item was returned", status=RefundRequest.Status.PENDING)
        RefundRequest.objects.create(transaction=rejected_transaction, requested_by=customer, reason="DEMO: outside refund window", status=RefundRequest.Status.REJECTED, reviewed_by=admin, staff_comment="DEMO: request was submitted after the allowed period.", reviewed_at=self._when(20))
        refund = self._transaction(owner_wallet=customer.wallet, other_wallet=admin.wallet, amount=Decimal("1200"), kind=Transaction.Type.REFUND, description="Completed refund credit", category=categories["Shopping"], days_ago=35, incoming=True)
        RefundRequest.objects.create(transaction=completed_transaction, refund_transaction=refund, requested_by=customer, reason="DEMO: duplicate charge", status=RefundRequest.Status.COMPLETED, reviewed_by=admin, staff_comment="DEMO: approved and credited.", reviewed_at=self._when(34))
