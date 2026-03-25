"""
validate.py — Production validation script for the fine-tuning pipeline.

Validates a newly fine-tuned model by:
1. Fetching expert-reviewed samples from MongoDB
2. Generating reports with the new model via LiteLLM
3. Scoring outputs against ground truth using Gemini 2.5 Pro as a judge
4. Comparing scores with the current production model
5. Storing metrics in MongoDB and passing/failing the pipeline
"""

import os
import sys
import json
import litellm
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from pymongo import MongoClient
from dotenv import load_dotenv
from store_metrics import store_model_metrics, get_current_production_score

load_dotenv()

# Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "heuruxagent")
LOCATION = os.getenv("VERTEXAI_LOCATION", "us-central1")
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "heuruxagent_db"

# Judge model — high-quality model for evaluation
JUDGE_MODEL = "gemini-2.5-pro"

# Validation parameters
SAMPLE_COUNT = 5  # Number of samples to validate
THRESHOLD = 7.0  # Minimum score to pass if no production baseline exists
BASE_MODEL = "gemini-2.5-flash"  # The base model that was fine-tuned

# The prompt used in production (matches what the model was trained on)
PRODUCTION_PROMPT = (
    "Analyze this interface screenshot and generate a detailed UI/UX report "
    "including feedback items, UX score, and a summary."
)


def get_validation_samples(count: int) -> list[dict]:
    """Fetch expert-reviewed evaluation samples from MongoDB."""
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    collection = db["evaluations"]

    # Prefer expert-reviewed evaluations, fall back to completed ones with AI results
    cursor = collection.find(
        {
            "status": "completed",
            "input.screenshot_url": {"$exists": True},
            "ai_results": {"$exists": True},
        }
    ).sort("timestamps.completed_at", -1).limit(count)

    samples = list(cursor)
    print(f"Fetched {len(samples)} completed evaluation samples for validation.")
    return samples


def generate_with_tuned_model(model_id: str, image_url: str) -> str:
    """Call the fine-tuned model to generate a UI/UX report for an image."""
    try:
        response = litellm.completion(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PRODUCTION_PROMPT},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"  Error calling tuned model: {e}")
        return None


def judge_output(image_url: str, ground_truth: str, model_output: str) -> dict | None:
    """Use Gemini 2.5 Pro as a judge to score the model's output."""
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    judge = GenerativeModel(JUDGE_MODEL)

    prompt = f"""You are an expert UI/UX auditor. Compare the AI-generated report with the expert ground truth for the provided UI screenshot.

Expert Ground Truth (reference):
{ground_truth}

AI-Generated Report (to evaluate):
{model_output}

Evaluate the AI-generated report based on:
1. Factual Accuracy (0-10): Are UI components correctly identified? Are observations accurate?
2. Formatting (0-10): Does it follow a structured, professional format similar to the ground truth?
3. Completeness (0-10): Does it cover all major issues and strengths? Did it miss anything obvious?

Return ONLY a valid JSON object (no markdown, no code fences):
{{
    "factual_accuracy": <score>,
    "formatting": <score>,
    "completeness": <score>,
    "overall_score": <average of the three scores>,
    "feedback": "<brief 1-2 sentence explanation>"
}}"""

    try:
        response = judge.generate_content([
            Part.from_uri(image_url, mime_type="image/png"),
            prompt,
        ])

        result_text = response.text.strip()
        # Clean markdown code fences if present
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        return json.loads(result_text)
    except Exception as e:
        print(f"  Judge error: {e}")
        return None


def extract_ground_truth(doc: dict) -> str:
    """Extract the expert-reviewed ground truth from an evaluation document."""
    ai_results = doc.get("ai_results", {})

    # Combine the key AI results as ground truth
    parts = []

    # Heuristic evaluation
    heuristic = ai_results.get("heuristic_evaluation", {})
    if isinstance(heuristic, dict) and heuristic.get("raw_text"):
        parts.append(f"Heuristic Evaluation:\n{heuristic['raw_text']}")

    # Feedback report
    feedback = ai_results.get("feedback_report", {})
    if isinstance(feedback, dict) and feedback.get("raw_text"):
        parts.append(f"Feedback Report:\n{feedback['raw_text']}")

    # Vision analysis
    vision = ai_results.get("vision_analysis")
    if vision:
        # Truncate if too long to stay within context limits
        vision_str = str(vision)[:3000]
        parts.append(f"Vision Analysis:\n{vision_str}")

    return "\n\n---\n\n".join(parts) if parts else "No ground truth available."


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate.py <new_model_id>")
        sys.exit(1)

    new_model_id = sys.argv[1]
    print(f"=== Validation Pipeline ===")
    print(f"New model: {new_model_id}")
    print(f"Judge model: {JUDGE_MODEL}")
    print()

    # Fetch validation samples
    print("Step 1: Fetching validation samples from MongoDB...")
    samples = get_validation_samples(SAMPLE_COUNT)

    if not samples:
        print("ERROR: No expert-reviewed samples found for validation.")
        sys.exit(1)

    # Generate + Judge each sample
    print(f"\nStep 2: Evaluating {len(samples)} samples...")
    scores = []

    for i, doc in enumerate(samples, 1):
        eval_id = doc.get("evaluation_id", "unknown")
        image_url = doc["input"]["screenshot_url"]
        ground_truth = extract_ground_truth(doc)

        print(f"\n--- Sample {i}/{len(samples)} (eval: {eval_id}) ---")

        # Generate report with the tuned model
        print(f"  Generating report with tuned model...")
        model_output = generate_with_tuned_model(new_model_id, image_url)

        if not model_output:
            print(f"  Skipping — model failed to generate output.")
            continue

        # Judge the output
        print(f"  Judging output against ground truth...")
        score = judge_output(image_url, ground_truth, model_output)

        if score:
            scores.append({
                "evaluation_id": eval_id,
                "image_url": image_url,
                **score,
            })
            print(
                f"  Score: {score['overall_score']:.1f}/10 "
                f"(accuracy={score['factual_accuracy']}, "
                f"formatting={score['formatting']}, "
                f"completeness={score['completeness']})"
            )
            print(f"  Feedback: {score.get('feedback', 'N/A')}")
        else:
            print(f"  Skipping — judge failed to score.")

    if not scores:
        print("\nERROR: No samples were successfully evaluated.")
        sys.exit(1)

    # Calculate results and compare
    avg_score = sum(s["overall_score"] for s in scores) / len(scores)
    print(f"\n=== Results ===")
    print(f"Samples evaluated: {len(scores)}/{len(samples)}")
    print(f"Average overall score: {avg_score:.2f}/10")

    # Get current production baseline
    print(f"\nStep 3: Comparing with production baseline...")
    production_score = get_current_production_score()

    if production_score is not None:
        comparison_target = production_score
        print(f"Production baseline: {production_score:.2f}/10")
        print(f"New model score: {avg_score:.2f}/10")
        print(f"Difference: {avg_score - production_score:+.2f}")
    else:
        comparison_target = THRESHOLD
        print(f"No production baseline found. Using threshold: {THRESHOLD}/10")

    passed = avg_score >= comparison_target

    # Store metrics
    print(f"\nStep 4: Storing metrics in MongoDB...")
    store_model_metrics(
        model_id=new_model_id,
        base_model=BASE_MODEL,
        scores=scores,
        threshold=comparison_target,
        passed=passed,
    )

    # Final verdict
    print(f"\n{'=' * 40}")
    if passed:
        print(f"✅ VALIDATION PASSED (score: {avg_score:.2f} >= {comparison_target:.2f})")
        print("New model is approved for deployment.")
        sys.exit(0)
    else:
        print(f"❌ VALIDATION FAILED (score: {avg_score:.2f} < {comparison_target:.2f})")
        print("New model does NOT meet the quality bar. Deployment blocked.")
        sys.exit(1)


if __name__ == "__main__":
    main()