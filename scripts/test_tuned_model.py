"""
Quick test script to verify the fine-tuned Vertex AI model works with CrewAI/LiteLLM.

Usage (run on the DigitalOcean server):
    PYTHONPATH=. python scripts/test_tuned_model.py

Make sure these env vars are set (in .env or exported):
    VERTEXAI_PROJECT=heuruxagent
    VERTEXAI_LOCATION=us-central1
    GEMINI_FEEDBACK_MODEL=vertex_ai/gemini/<ENDPOINT_ID>
"""

import os
import litellm
from dotenv import load_dotenv

load_dotenv()

# The endpoint ID from the tuning job
ENDPOINT_ID = "2041925583931179008"

# Different model ID formats to test
formats_to_test = [
    f"vertex_ai/gemini/{ENDPOINT_ID}",
    f"vertex_ai/{ENDPOINT_ID}",
    f"vertex_ai/endpoints/{ENDPOINT_ID}",
]

# Set required env vars
os.environ.setdefault("VERTEXAI_PROJECT", "heuruxagent")
os.environ.setdefault("VERTEXAI_LOCATION", "us-central1")

print(f"Project: {os.environ.get('VERTEXAI_PROJECT')}")
print(f"Location: {os.environ.get('VERTEXAI_LOCATION')}")
print(f"GOOGLE_APPLICATION_CREDENTIALS: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'not set')}")
print()

for model_id in formats_to_test:
    print(f"--- Testing: {model_id} ---")
    try:
        response = litellm.completion(
            model=model_id,
            messages=[{"role": "user", "content": "Say hello in one sentence."}],
            max_tokens=50,
        )
        print(f"✅ SUCCESS! Response: {response.choices[0].message.content}")
        print(f"   Model used: {response.model}")
        print(f"\n🎉 Working format: {model_id}")
        print(f"   Set this in your .env as: GEMINI_FEEDBACK_MODEL={model_id}")
        break
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}\n")
else:
    print("\n⚠️  None of the formats worked.")
    print("Check that:")
    print("  1. GOOGLE_APPLICATION_CREDENTIALS points to your service account JSON")
    print("  2. The service account has Vertex AI User role")
    print("  3. The endpoint ID is correct")
    print(f"\n  Current GEMINI_FEEDBACK_MODEL: {os.environ.get('GEMINI_FEEDBACK_MODEL', 'not set')}")
