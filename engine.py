import os
import json
import glob
from groq import Groq
from config import LOG_DIR, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

SUMMARY_DIR = LOG_DIR / "summaries"

# Initialize client
api_key = os.getenv("API_KEY")
client = Groq(api_key=api_key) if api_key else None

def get_latest_summary():
    """Finds and reads the latest summary file in the summaries directory."""
    if not SUMMARY_DIR.exists():
        return None
        
    summary_files = glob.glob(str(SUMMARY_DIR / "*.json"))
    if not summary_files:
        return None
        
    latest_file = max(summary_files, key=os.path.getctime)
    try:
        with open(latest_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[engine] Error reading summary: {e}")
        return None

def generate_recommendation():
    """Generates actionable recommendations based on the latest anomaly summary."""
    if not client:
        return {"error": "API_KEY not found in environment variables."}
        
    summary_data = get_latest_summary()
    if not summary_data:
        return {"error": "No anomaly summary found. Please wait for the next summary generation."}
        
    if summary_data.get("overview", {}).get("total_anomalies", 0) == 0:
        return {"message": "No anomalies detected in the last period. System is healthy."}

    # Extract relevant parts for the LLM to keep context focused
    overview = summary_data.get("overview", {})
    top_anomalies = summary_data.get("top_anomalies_API", [])
    
    prompt_context = f"Overview:\n{json.dumps(overview, indent=2)}\n\nTop Anomalies:\n{json.dumps(top_anomalies, indent=2)}"

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Kamu adalah sistem monitoring API profesional. "
                        "Tugasmu adalah menganalisis ringkasan anomali yang diberikan dan memberikan rekomendasi teknis yang singkat, jelas, dan actionable. "
                        "Jawab hanya dengan 3 langkah remediasi dalam format bernomor. "
                        "Tidak perlu basa-basi atau penjelasan panjang."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Anomali terdeteksi pada API monitoring dengan detail berikut:\n\n{prompt_context}\n\n"
                        f"Berikan 3 langkah remediasi teknis yang harus segera dilakukan."
                    )
                }
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS
        )

        raw = response.choices[0].message.content
        steps = [step.strip() for step in raw.split('\n') if step.strip()]
        
        return {
            "period": summary_data.get("summary_period"),
            "recommendation": steps
        }
        
    except Exception as e:
        return {"error": f"LLM Generation failed: {str(e)}"}
