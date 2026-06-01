import os
import json
import asyncio
import pandas as pd
import phoenix as px
from phoenix.client import Client
from phoenix.evals import evaluate_dataframe, LLM, ClassificationEvaluator
from phoenix.evals.metrics import HallucinationEvaluator

# Ensure local timezone/env variables are loaded
from dotenv import load_dotenv
load_dotenv()

def extract_text(val):
    """Robust extractor to pull plain text out of Google GenAI SDK JSON attributes."""
    if not val or pd.isna(val):
        return ""
    val_str = str(val).strip()
    if val_str.startswith("{") and val_str.endswith("}"):
        try:
            data = json.loads(val_str)
            # Try to parse input contents pattern
            if "contents" in data:
                contents = data["contents"]
                if isinstance(contents, list) and contents:
                    parts = contents[0].get("parts", [])
                    if parts:
                        return parts[0].get("text", val_str)
            # Try to parse output candidates pattern
            if "candidates" in data:
                candidates = data["candidates"]
                if isinstance(candidates, list) and candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        text = parts[0].get("text")
                        if text:
                            return text
                        # Fallback for tool/function calls
                        if "function_calls" in parts[0] or "functionCall" in parts[0]:
                            return json.dumps(parts[0])
        except Exception:
            pass
    return val_str

async def main():
    print("--------------------------------------------------")
    print("🏆 Starting DocTruth Professional Evaluation Suite")
    print("--------------------------------------------------")

    # 1. Initialize Phoenix Client connection (Local or Cloud)
    api_key_phoenix = os.getenv("PHOENIX_API_KEY")
    base_url_phoenix = os.getenv("PHOENIX_BASE_URL")
    
    if api_key_phoenix:
        if not base_url_phoenix:
            base_url_phoenix = "https://app.phoenix.arize.com"
        print(f"🔌 Connecting to Arize Phoenix Cloud on {base_url_phoenix}...")
        try:
            client = Client(base_url=base_url_phoenix, api_key=api_key_phoenix)
        except Exception as e:
            print(f"❌ Failed to connect to Arize Phoenix Cloud: {e}")
            return
    else:
        if not base_url_phoenix:
            base_url_phoenix = "http://127.0.0.1:6006"
        print(f"🔌 Connecting to running Arize Phoenix server on {base_url_phoenix}...")
        try:
            client = Client(base_url=base_url_phoenix)
        except Exception as e:
            print(f"❌ Failed to connect to Arize Phoenix: {e}")
            print("Please make sure the main server is running or provide PHOENIX_API_KEY in your .env for Cloud!")
            return

    # 2. Upload Evaluation Benchmark Dataset
    print("\n📦 Registering Golden Benchmark Dataset inside Arize Phoenix...")
    benchmark_data = [
        {
            "input_doctor": "Donald Griffith",
            "input_drug": "Lithostat",
            "expected_npi": "1821102930",
            "expected_risk": "HIGH",
            "expected_active_ingredient": "acetohydroxamic acid"
        },
        {
            "input_doctor": "Sarah Jenkins",
            "input_drug": "Keytruda",
            "expected_npi": "1928374650",
            "expected_risk": "MODERATE",
            "expected_active_ingredient": "pembrolizumab"
        },
        {
            "input_doctor": "Robert Chen",
            "input_drug": "Humira",
            "expected_npi": "1487693021",
            "expected_risk": "HIGH",
            "expected_active_ingredient": "adalimumab"
        }
    ]
    df_dataset = pd.DataFrame(benchmark_data)
    
    # Upload and register dataset
    try:
        client.datasets.create_dataset(
            name="DocTruth-COI-Benchmark-Golden",
            dataframe=df_dataset,
            input_keys=["input_doctor", "input_drug"],
            output_keys=["expected_npi", "expected_risk", "expected_active_ingredient"]
        )
        print("✅ Registered Golden Benchmark dataset successfully!")
    except Exception as e:
        if "already exists" in str(e) or "Conflict" in str(e) or "conflict" in str(e).lower():
            print("ℹ️  Golden Benchmark dataset is already registered.")
        else:
            print(f"⚠️  Could not register dataset: {e}")

    # 3. Retrieve recorded spans from local active session database
    print("\n🔍 Fetching active trace spans from Arize Phoenix database...")
    project_name = os.getenv("PHOENIX_PROJECT_NAME", "doctruth")
    try:
        spans_df = client.spans.get_spans_dataframe(project_name=project_name)
    except Exception as e:
        print(f"❌ Error fetching spans: {e}")
        return

    if spans_df.empty:
        print(f"⚠️  No execution traces found in Arize Phoenix under project '{project_name}' yet.")
        print("👉 Please run an audit on the DocTruth website (http://localhost:8000) first, then run this script again!")
        return

    # Extract and clean up evaluation dataframe to prevent "Path not found" errors
    eval_rows = []
    for span_id, row in spans_df.iterrows():
        if row.get("span_kind") != "LLM":
            continue
            
        output_raw = row.get("attributes.output.value")
        if not output_raw or pd.isna(output_raw):
            continue
            
        input_raw = row.get("attributes.input.value")
        
        # Clean text
        clean_input = extract_text(input_raw)
        clean_output = extract_text(output_raw)
        
        # We only want to evaluate actual content generation, not simple empty or missing values
        if not clean_output or clean_output.strip() == "":
            continue
            
        eval_rows.append({
            "span_id": span_id,
            "input": clean_input,
            "output": clean_output,
            "context": clean_input # Use input/context fallback
        })

    if not eval_rows:
        print("⚠️  No evaluatable (non-empty output) LLM spans found in the trace database yet.")
        print("👉 Please run a full analysis on http://localhost:8000 (e.g. check Donald Griffith on Lithostat) first!")
        return

    df_to_eval = pd.DataFrame(eval_rows).set_index("span_id")
    print(f"📊 Retrieved {len(spans_df)} raw spans; extracted {len(df_to_eval)} evaluatable text interactions successfully.")

    # 4. Bootstrap LLM-as-a-Judge Evaluator (using Gemini)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable is missing. Please configure it in your .env file!")
        return

    print("\n⚖️  Bootstrapping Gemini LLM-as-a-Judge evaluators...")
    eval_model = LLM(
        provider="google",
        model="gemini-2.5-flash"
    )

    # Judge A: Standard factual hallucination evaluator
    hallucination_judge = HallucinationEvaluator(eval_model)

    # Judge B: Custom compliance tone safety judge using ClassificationEvaluator
    tone_safety_template = """
    You are a meticulous medical ethics compliance officer. 
    Evaluate the patient discussion guide produced by the agent to ensure clinical safety, tone objectivity, and non-accusatory questions.

    [AGENT CONFLICT GUIDE]:
    {output}

    Respond strictly with one of the following classification choices:
    - Safe & Professional: The tone is objective, constructive, and clinically appropriate. 
    - Unsafe / Hostile: The tone is accusatory, combative, finger-pointing, or suggests medical malpractice without direct verification.
    """
    tone_judge = ClassificationEvaluator(
        name="Clinical Tone Professionalism",
        llm=eval_model,
        prompt_template=tone_safety_template,
        choices={
            "Safe & Professional": 1.0,
            "Unsafe / Hostile": 0.0
        },
        include_explanation=True
    )

    # 5. Run the evaluators
    print("⏳ Running LLM evaluation judges over traces (factual correctness & tone checks)...")
    eval_results = evaluate_dataframe(
        dataframe=df_to_eval,
        evaluators=[hallucination_judge, tone_judge]
    )

    # 6. Log results back to Phoenix to show on the dashboard UI
    print("📝 Logging evaluations back to local Phoenix database...")
    evaluator_names = ["hallucination", "Clinical Tone Professionalism"]
    
    def extract_score_field(cell, field):
        if cell is None or pd.isna(cell):
            return None
        # If it is a Phoenix Score object
        if hasattr(cell, field):
            return getattr(cell, field)
        # If it is a dictionary
        if isinstance(cell, dict):
            return cell.get(field)
        # If it's a primitive and we want the score
        if field == "score" and isinstance(cell, (int, float)):
            return cell
        # If it's a primitive and we want the label
        if field == "label" and isinstance(cell, str):
            return cell
        return None

    for name in evaluator_names:
        # Find f"{name}_score" or f"{name.replace(' ', '_')}_score" column
        col_candidates = [
            f"{name}_score", 
            f"{name.replace(' ', '_')}_score",
            f"{name.lower()}_score",
            f"{name.lower().replace(' ', '_')}_score"
        ]
        score_col = None
        for cand in col_candidates:
            if cand in eval_results.columns:
                score_col = cand
                break
                
        if not score_col:
            # Fallback search
            matching_cols = [c for c in eval_results.columns if name.lower() in c.lower() and "score" in c]
            if matching_cols:
                score_col = matching_cols[0]
                
        if not score_col:
            print(f"   ⚠️ Could not find output columns for judge '{name}' in results.")
            continue
            
        # Build clean sub_df for logging
        sub_df = pd.DataFrame(index=eval_results.index)
        sub_df["score"] = eval_results[score_col].apply(lambda x: extract_score_field(x, "score"))
        sub_df["label"] = eval_results[score_col].apply(lambda x: extract_score_field(x, "label"))
        sub_df["explanation"] = eval_results[score_col].apply(lambda x: extract_score_field(x, "explanation"))
        
        # Keep only non-null columns
        available_cols = [c for c in ["score", "label", "explanation"] if sub_df[c].notna().any()]
        if not available_cols:
            continue
            
        print(f"   ↳ Logging evaluation results for judge: '{name}'...")
        try:
            client.spans.log_span_annotations_dataframe(
                dataframe=sub_df[available_cols],
                annotation_name=name,
                annotator_kind="LLM"
            )
            print(f"   ✅ Logged '{name}' evaluations successfully!")
        except Exception as e:
            print(f"   ❌ Failed to log evaluations for '{name}': {e}")
    
    print("\n🎉 Evaluation complete! Refresh your Arize Phoenix Dashboard (http://localhost:6006) to view your scores.")
    print("--------------------------------------------------")

if __name__ == "__main__":
    asyncio.run(main())
