import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.transactions.models import Transaction


logger = logging.getLogger(__name__)


def send_transaction_email(record):
    recipients = set()
    for wallet in (record.sender_wallet, record.receiver_wallet):
        if wallet and wallet.user.email:
            recipients.add(wallet.user.email)
    if not recipients:
        return
    direction = "received" if record.receiver_wallet else "sent"
    subject = f"Luma transaction {record.status.lower()}: {record.amount} {record.currency}"
    body = (
        f"Your Luma wallet transaction was {direction}.\n\n"
        f"Type: {record.get_transaction_type_display()}\n"
        f"Amount: {record.amount} {record.currency}\n"
        f"Status: {record.get_status_display()}\n"
        f"Reference: {record.transaction_id}\n"
        f"Description: {record.description or 'No description'}\n"
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, sorted(recipients), fail_silently=False)
    except Exception:
        logger.exception("Unable to send transaction email for %s", record.transaction_id)
