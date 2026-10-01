import pickle
import math
from pathlib import Path

from django.conf import settings
from apps.transactions.models import Transaction


MODEL_PATH = Path(settings.BASE_DIR) / "behavioral_model_v2.pkl"
_model = None
FRAUD_FLAG_THRESHOLD = 0.5


def score_behavior(features):
    """Return the fraud probability for a row matching the trained model schema."""
    global _model
    if _model is None:
        try:
            with MODEL_PATH.open("rb") as model_file:
                _model = pickle.load(model_file)
        except (FileNotFoundError, ImportError, ModuleNotFoundError):
            return None
    try:
        return float(_model.predict_proba(features)[0][1])
    except (AttributeError, IndexError, TypeError, ValueError):
        return None


def assess_transaction(transaction_type, amount, receiver_wallet=None):
    """Build model features from wallet history and return a review decision."""
    try:
        import pandas as pd

        amount = float(amount)
        log_amount = math.log1p(amount)
        history = Transaction.objects.filter(transaction_type=transaction_type).values_list("amount", flat=True)
        amounts = [float(value) for value in history]
        average = sum(amounts) / len(amounts) if amounts else amount
        deviations = [abs(value - average) for value in amounts]
        median_deviation = sorted(deviations)[len(deviations) // 2] if deviations else 0
        robust_z = (amount - average) / (1.4826 * median_deviation) if median_deviation else 0
        destination_amounts = []
        if receiver_wallet is not None:
            destination_amounts = [
                float(value)
                for value in Transaction.objects.filter(receiver_wallet=receiver_wallet).values_list("amount", flat=True)
            ]
        destination_average = sum(destination_amounts) / len(destination_amounts) if destination_amounts else amount
        features = pd.DataFrame([{
            "type": transaction_type,
            "log_amount": log_amount,
            "amount_type_robust_z": robust_z,
            "log_dest_smoothed_avg": math.log1p(destination_average),
            "log_amount_vs_smoothed_dest_avg": log_amount - math.log1p(destination_average),
        }])
        score = score_behavior(features)
        if score is None:
            return Transaction.RiskStatus.NOT_REVIEWED, None, "Automatic scoring unavailable"
        if score >= FRAUD_FLAG_THRESHOLD:
            return Transaction.RiskStatus.FLAGGED, score, "Behavioral model flagged this transaction"
        return Transaction.RiskStatus.CLEAR, score, "Behavioral model found no unusual behavior"
    except (ImportError, OSError, ValueError, TypeError):
        return Transaction.RiskStatus.NOT_REVIEWED, None, "Automatic scoring unavailable"