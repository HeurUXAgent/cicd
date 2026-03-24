import os
import json
import time
import vertexai
from vertexai.tuning import sft
from google.cloud import storage
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "heuruxagent")
LOCATION = "us-central1"  # Default region for Vertex AI tuning
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", f"{PROJECT_ID}-tuning-data")
DATA_DIR = Path("data")
JSONL_FILE = DATA_DIR / "tuning_data.jsonl"
IMAGES_DIR = DATA_DIR / "images"


def upload_to_gcs(local_path, remote_path):
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)
    if not bucket.exists():
        print(f"Creating bucket {BUCKET_NAME}...")
        bucket.create(location=LOCATION)

    blob = bucket.blob(remote_path)
    print(f"Uploading {local_path} to gs://{BUCKET_NAME}/{remote_path}...")
    blob.upload_from_filename(local_path)
    return f"gs://{BUCKET_NAME}/{remote_path}"


def prepare_gcs_dataset():
    # 1. Upload images and update JSONL with GCS URIs
    examples = []
    with open(JSONL_FILE, 'r') as f:
        for line in f:
            ex = json.loads(line)
            # Update fileUri in fileData
            for part in ex["contents"][0]["parts"]:
                if "fileData" in part:
                    local_image_path = part["fileData"]["fileUri"]
                    image_name = Path(local_image_path).name
                    gcs_uri = upload_to_gcs(local_image_path, f"images/{image_name}")
                    part["fileData"]["fileUri"] = gcs_uri
            examples.append(ex)

    # 2. Save updated JSONL
    gcs_jsonl_path = DATA_DIR / "tuning_data_gcs.jsonl"
    with open(gcs_jsonl_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')

    # 3. Upload JSONL to GCS
    final_gcs_jsonl_uri = upload_to_gcs(str(gcs_jsonl_path), "tuning_data.jsonl")
    return final_gcs_jsonl_uri


def trigger_tuning(dataset_uri):
    # Initialize Vertex AI SDK
    vertexai.init(project=PROJECT_ID, location=LOCATION)

    # Base model for supervised fine-tuning
    # Supported models: gemini-2.5-flash, gemini-2.5-flash-lite, gemini-2.5-pro
    BASE_MODEL = "gemini-2.5-flash"

    print(f"Triggering SFT job for {BASE_MODEL}...")
    sft_job = sft.train(
        source_model=BASE_MODEL,
        train_dataset=dataset_uri,
        tuned_model_display_name="gemini-3-report-v1",
        epochs=3,
        learning_rate_multiplier=1.0,
    )
    return sft_job


def main():
    if not JSONL_FILE.exists():
        print(f"Dataset {JSONL_FILE} not found. Run extract_data.py first.")
        return

    print("Step 1: Preparing GCS dataset...")
    gcs_dataset_uri = prepare_gcs_dataset()
    print(f"Dataset ready at: {gcs_dataset_uri}")

    print("\nStep 2: Triggering fine-tuning job...")
    job = trigger_tuning(gcs_dataset_uri)

    print(f"Tuning job resource: {job.resource_name}")

    # Poll for completion (fine-tuning can take 1-3+ hours)
    print("Waiting for tuning job to complete...")
    while not job.has_ended:
        time.sleep(60)
        job.refresh()
        print(f"  Job state: {job.state.name}")

    # Check if job succeeded
    if job.has_succeeded:
        tuned_model = job.tuned_model_name
        tuned_endpoint = job.tuned_model_endpoint_name
        print(f"Tuning job completed successfully!")
        print(f"Tuned model: {tuned_model}")
        print(f"Tuned model endpoint: {tuned_endpoint}")

        # Output the tuned model endpoint for GitHub Actions
        # LiteLLM format for fine-tuned Vertex AI Gemini: vertex_ai/gemini/<ENDPOINT_ID>
        # tuned_endpoint is like: projects/.../locations/.../endpoints/1234567890
        endpoint_id = tuned_endpoint.split("/")[-1]
        crewai_model_id = f"vertex_ai/gemini/{endpoint_id}"
        print(f"CrewAI model identifier: {crewai_model_id}")

        if os.getenv("GITHUB_OUTPUT"):
            with open(os.getenv("GITHUB_OUTPUT"), "a") as f:
                f.write(f"model_id={crewai_model_id}\n")
    else:
        print(f"Tuning job failed with state: {job.state.name}")
        if hasattr(job, 'error') and job.error:
            print(f"Error: {job.error}")
        exit(1)


if __name__ == "__main__":
    main()

