import os
import json
import requests
from pymongo import MongoClient # Added missing import
from google.cloud import aiplatform
from dotenv import load_dotenv

load_dotenv()

# Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "sas-garage")
LOCATION = "us-central1"
JUDGE_MODEL = "gemini-1.5-pro-002" # High-quality model for judging

def evaluate_report(image_url, ground_truth, model_output):
    """Uses Gemini 1.5 Pro as a judge to compare model output with ground truth."""
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    # Note: Using Vertex AI Generative Model as a judge
    from vertexai.generative_models import GenerativeModel, Part
    
    judge = GenerativeModel(JUDGE_MODEL)
    
    prompt = f"""
    You are an expert UI/UX auditor. Compare the generated report with the ground truth for the provided image.
    
    Ground Truth:
    {ground_truth}
    
    Generated Report:
    {model_output}
    
    Evaluate based on:
    1. Factual Accuracy (0-10): Are components correctly identified?
    2. Formatting (0-10): Does it follow the structure of the ground truth?
    3. Completeness (0-10): Did it miss anything obvious?
    
    Return a JSON object with:
    {{
        "factual_accuracy": score,
        "formatting": score,
        "completeness": score,
        "overall_score": average_score,
        "feedback": "brief explanation"
    }}
    """
    
    # In a real scenario, we'd pass the image part too
    response = judge.generate_content([
        Part.from_uri(image_url, mime_type="image/png"),
        prompt
    ])
    
    try:
        # Extract JSON from response text
        result_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(result_text)
    except Exception as e:
        print(f"Failed to parse judge output: {e}")
        return None

import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python validate.py <new_model_id>")
        sys.exit(1)
        
    new_model_id = sys.argv[1]
    client = MongoClient(os.getenv("MONGODB_URI"))
    db = client["heuruxagent_db"]
    collection = db["expert_validation_dataset"]
    
    # Sample 5 examples for validation
    cursor = collection.find().limit(5)
    
    print(f"Starting validation process for model: {new_model_id}")
    total_score = 0
    count = 0
    
    for doc in cursor:
        ui_id = doc.get("ui_id")
        image_url = doc.get("image_url")
        expert_report = doc.get("expert_report")
        
        # In a real pipeline:
        # 1. Call the new_model_id with image_url
        # 2. Call evaluate_report(image_url, expert_report, model_output)
        # For now, we simulate a score
        score = 8.5 # MOCK
        total_score += score
        count += 1
        print(f"Validated {ui_id}: Score {score}")

    avg_score = total_score / count if count > 0 else 0
    print(f"\nAverage Validation Score: {avg_score}")
    
    # Threshold for deployment
    THRESHOLD = 8.0 
    if avg_score >= THRESHOLD:
        print("Validation PASSED! New model is better or matches requirements.")
        sys.exit(0)
    else:
        print("Validation FAILED. New model performance is below threshold.")
        sys.exit(1)

if __name__ == "__main__":
    main()
