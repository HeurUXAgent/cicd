"""
store_metrics.py — Stores and retrieves model evaluation metrics in MongoDB.

Used by validate.py to:
1. Store new model evaluation results after validation
2. Retrieve the current production model's score for comparison
"""

import os
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv

load_dotenv()

DB_NAME = "heuruxagent_db"
METRICS_COLLECTION = "model_metrics"


def get_db():
    client = MongoClient(os.getenv("MONGODB_URI"))
    return client[DB_NAME]


def store_model_metrics(
    model_id: str,
    base_model: str,
    scores: list[dict],
    threshold: float,
    passed: bool,
):
    """Store evaluation metrics for a model run."""
    db = get_db()
    collection = db[METRICS_COLLECTION]

    # Calculate averages from individual scores
    avg = lambda key: sum(s.get(key, 0) for s in scores) / len(scores) if scores else 0

    doc = {
        "model_id": model_id,
        "base_model": base_model,
        "evaluated_at": datetime.now(timezone.utc),
        "sample_count": len(scores),
        "avg_factual_accuracy": round(avg("factual_accuracy"), 2),
        "avg_formatting": round(avg("formatting"), 2),
        "avg_completeness": round(avg("completeness"), 2),
        "avg_overall_score": round(avg("overall_score"), 2),
        "individual_scores": scores,
        "passed_threshold": passed,
        "threshold": threshold,
        "is_production": False,  # Set to True after deployment
    }

    result = collection.insert_one(doc)
    print(f"Stored metrics in MongoDB (id: {result.inserted_id})")
    return doc


def get_current_production_score() -> float | None:
    """Get the average overall score of the latest production model."""
    db = get_db()
    collection = db[METRICS_COLLECTION]

    latest = collection.find_one(
        {"passed_threshold": True},
        sort=[("evaluated_at", DESCENDING)],
    )

    if latest:
        print(
            f"Current production model: {latest['model_id']} "
            f"(score: {latest['avg_overall_score']}, "
            f"evaluated: {latest['evaluated_at']})"
        )
        return latest["avg_overall_score"]

    print("No previous production metrics found in MongoDB.")
    return None


def mark_as_production(model_id: str):
    """Mark a model as the current production model."""
    db = get_db()
    collection = db[METRICS_COLLECTION]

    # Unmark all previous production models
    collection.update_many(
        {"is_production": True},
        {"$set": {"is_production": False}},
    )

    # Mark the new one
    collection.update_one(
        {"model_id": model_id},
        {"$set": {"is_production": True}},
    )
    print(f"Marked {model_id} as production model.")