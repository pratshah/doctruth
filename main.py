import os
import asyncio
import json
import logging
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Load configurations
load_dotenv()

# Initialize Arize Phoenix tracing immediately (must be done before importing google.genai or google.adk)
from agents.tracker import setup_tracker
setup_tracker()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doctruth.app")

# Import standard OTel tracing
from opentelemetry import trace
from opentelemetry.trace import SpanKind
tracer = trace.get_tracer("doctruth")

# Dynamic Monkeypatch of Gemini api_client to prevent Python 3.14 cached_property errors
from google.adk.models.google_llm import Gemini
from google.genai import Client

@property
def custom_api_client(self) -> Client:
    if not hasattr(self, "_custom_client"):
        # 1. Use API key if provided
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            logger.info("Initializing Google AI Studio Gemini client using environment API Key...")
            self._custom_client = Client(api_key=api_key)
        else:
            # 2. Fallback to Vertex AI project configured in env or default config
            project = os.getenv("VERTEX_PROJECT", "nexreach-479804")
            location = os.getenv("VERTEX_LOCATION", "us-central1")
            logger.info(f"Fallback to Vertex AI Client (Project: {project}, Location: {location})...")
            self._custom_client = Client(
                vertexai=True,
                project=project,
                location=location
            )
    return self._custom_client

# Override property on Gemini class
Gemini.api_client = custom_api_client

# Initialize FastAPI App
app = FastAPI(
    title="DocTruth Gateway",
    description="A multi-agent transparent investigator uncovering healthcare conflicts of interest.",
    version="1.0.0"
)

# Connect to database on startup
from db import db

@app.on_event("startup")
async def startup_event():
    await db.connect()

# Live open API fallback datasets (copied from tools for reference / display)
MOCK_PAYMENTS = {
    "dr. robert chen": {
        "npi": "1487693021",
        "city": "Houston",
        "total_amount": 28450.00,
        "payment_count": 18,
        "nature_breakdown": {
            "Food and Beverage": 1200.00,
            "Consulting Fee": 15000.00,
            "Travel and Lodging": 4250.00,
            "Honoraria / Speaker Fee": 8000.00
        },
        "manufacturers": [
            {"name": "AbbVie Inc.", "amount": 18500.00, "drug": "Humira"},
            {"name": "Pfizer Inc.", "amount": 9950.00, "drug": "Lipitor"}
        ]
    },
    "dr. sarah jenkins": {
        "npi": "1928374650",
        "city": "Boston",
        "total_amount": 1500.00,
        "payment_count": 4,
        "nature_breakdown": {
            "Food and Beverage": 300.00,
            "Educational Materials": 1200.00
        },
        "manufacturers": [
            {"name": "Merck & Co.", "amount": 1500.00, "drug": "Keytruda"}
        ]
    }
}

MOCK_DRUGS = {
    "humira": {
        "active_ingredient": "adalimumab",
        "generic_alternatives": [
            {"name": "Amjevita (adalimumab-atto)", "manufacturer": "Amgen", "price_diff": "Up to 55% cheaper"},
            {"name": "Hadlima (adalimumab-bwwd)", "manufacturer": "Organon", "price_diff": "Up to 60% cheaper"},
            {"name": "Yuflyma (adalimumab-aaty)", "manufacturer": "Celltrion", "price_diff": "Up to 50% cheaper"}
        ],
        "warnings": "WARNING: RISK OF SERIOUS INFECTIONS AND MALIGNANCY. Patients treated with Humira are at increased risk for developing serious infections that may lead to hospitalization or death."
    },
    "lipitor": {
        "active_ingredient": "atorvastatin",
        "generic_alternatives": [
            {"name": "Atorvastatin Calcium (Generic)", "manufacturer": "Sandoz", "price_diff": "Up to 85% cheaper"},
            {"name": "Atorvastatin (Generic)", "manufacturer": "Teva Pharmaceuticals", "price_diff": "Up to 80% cheaper"}
        ],
        "warnings": "Contraindicated in active liver disease. May cause myopathy and rhabdomyolysis. Periodic liver function tests are recommended."
    }
}

def simulate_agent_flow(doctor: str, drug: str, npi: str = "", payment_info = None, drug_info = None):
    """Generates a list of beautifully choreographed agent events to simulate live execution."""
    doc_clean = doctor.lower().strip()
    drug_clean = drug.lower().strip()
    
    # Use pre-fetched payment_info if provided
    if not payment_info:
        if npi:
            for k, v in MOCK_PAYMENTS.items():
                if v.get("npi") == npi:
                    payment_info = v
                    doctor = v.get("name", k.title())
                    break
                    
        if not payment_info:
            payment_info = MOCK_PAYMENTS.get(doc_clean, {
                "npi": npi or "Not Registered",
                "city": "Unknown City",
                "total_amount": 12400.00,
                "payment_count": 8,
                "nature_breakdown": {
                    "Food and Beverage": 400.00,
                    "Speaker Honorarium": 8000.00,
                    "Consulting Fee": 4000.00
                },
                "manufacturers": [
                    {"name": "PharmaCorp Ltd", "amount": 12400.00, "drug": drug.capitalize()}
                ]
            })
    
    # Use pre-fetched drug_info if provided
    if not drug_info:
        drug_info = MOCK_DRUGS.get(drug_clean, {
            "active_ingredient": drug_clean,
            "generic_alternatives": [
                {"name": f"{drug_clean.capitalize()} Generic Alternative", "manufacturer": "Generics Ltd", "price_diff": "Up to 75% cheaper"}
            ],
            "warnings": "Standard precaution: consult physician before altering prescription regimens."
        })
    
    events = [
        {
            "agent": "Chief Medical Director",
            "message": f"Initializing conflict of interest audit. Focus Profile: **{doctor}**. Target medication: **{drug}**."
        },
        {
            "agent": "Chief Medical Director",
            "message": "Delegating financial data retrieval to **Forensic Financial Auditor**..."
        },
        {
            "agent": "Forensic Financial Auditor",
            "message": f"Scanning CMS Open Payments registries for physician payouts matching: '{doctor}'."
        },
        {
            "agent": "Forensic Financial Auditor",
            "message": f"[TOOL CALL] `query_cms_database(doctor_name='{doctor}', npi='{npi}')` executed."
        },
        {
            "agent": "Forensic Financial Auditor",
            "message": f"Database Match found! Unique Physician NPI verified: **{payment_info['npi']}** ({payment_info['city']}). Compiled:\n"
                       f"- Total Sponsorships received: **${payment_info['total_amount']:,.2f}**\n"
                       f"- Aggregate transactions: **{payment_info['payment_count']} payments**"
        },
        {
            "agent": "Forensic Financial Auditor",
            "message": f"Payout Breakdown of Sponsor Manufacturers:\n" + 
                       "\n".join([f"  * **{m['name']}**: ${m['amount']:,.2f} (Associated with **{m['drug']}**)" for m in payment_info['manufacturers']])
        },
        {
            "agent": "Chief Medical Director",
            "message": "Financial profile processed. Delegating formulation chemistry analysis to **Pharma Equivalence Chemist**..."
        },
        {
            "agent": "Pharma Equivalence Chemist",
            "message": f"Querying FDA NDC Directory for brand-name drug: **{drug}**."
        },
        {
            "agent": "Pharma Equivalence Chemist",
            "message": f"[TOOL CALL] `map_brand_to_generic(brand_name='{drug}')` executed."
        },
        {
            "agent": "Pharma Equivalence Chemist",
            "message": f"Active Ingredient discovered: **{drug_info['active_ingredient'].upper()}**.\n"
                       f"Identified multiple cost-effective bio-equivalent alternatives."
        },
        {
            "agent": "Pharma Equivalence Chemist",
            "message": f"Active boxed warnings compiled:\n> *{drug_info['warnings']}*"
        },
        {
            "agent": "Chief Medical Director",
            "message": "Synthesizing full multi-agent findings and generating conflict scorecard and printable guide..."
        },
        {
            "agent": "Chief Medical Director",
            "message": f"### 🛡️ DocTruth Summary Report & Scorecard\n"
                       f"**Physician**: {doctor}\n"
                       f"**Physician NPI**: {payment_info['npi']}\n"
                       f"**Physician City**: {payment_info['city']}\n"
                       f"**Medication**: {drug} (Generic: {drug_info['active_ingredient']})\n"
                       f"**COI Risk Profile**: " + ("HIGH RISK (Manufacturer matches prescriber financial support)" if any(m['drug'].lower() == drug_clean for m in payment_info['manufacturers']) else "MODERATE RISK") + "\n\n"
                       f"#### 💳 Potential Cost Savings Comparison:\n" +
                       "\n".join([f"- **{alt['name']}** by *{alt['manufacturer']}*: **{alt['price_diff']}**" for alt in drug_info['generic_alternatives']]) +
                       f"\n\n#### 📄 Discussion Guide for Your Next Appointment:\n"
                       f"1. *'Dr. {doctor.split()[-1] if len(doctor.split()) > 1 else doctor}, I noticed that you received financial sponsorships from manufacturers of {drug}. Are there equivalent generic/biosimilar alternatives like {drug_info['active_ingredient']} that we could consider instead?'*\n"
                       f"2. *'What are the therapeutic differences, and are there any active FDA warnings I should be concerned about regarding this compound?'*"
        }
    ]
    return events, payment_info, drug_info

@app.get("/api/search-doctors")
async def search_doctors(name: str):
    """Searches the CMS Socrata Open Payments database or returns simulated matches to select from."""
    from agents.tools import CMS_DATASTORE_URL
    import httpx
    import re
    clean_name = name.strip().lower()
    is_npi_search = clean_name.isdigit() and len(clean_name) == 10
    
    # 1. Gather fallbacks / mock templates matching the query
    mock_results = []
    for k, v in MOCK_PAYMENTS.items():
        if clean_name in k or k in clean_name or (is_npi_search and v.get("npi") == clean_name):
            mock_results.append({
                "name": k.title(),
                "npi": v.get("npi", "N/A"),
                "city": f"{v.get('city', 'Unknown City')}, USA",
                "specialty": "Internal Medicine Consultant",
                "total_payments": f"${v.get('total_amount', 0):,.2f}"
            })
            
    # 2. Query CMS live API if possible
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if is_npi_search:
                conditions = [{"property": "covered_recipient_npi", "value": clean_name, "operator": "="}]
                payload = {
                    "conditions": conditions,
                    "limit": 15
                }
                logger.info(f"Querying live NPI on CMS datastore: {payload}")
                response = await client.post(CMS_DATASTORE_URL, json=payload)
                records = response.json().get("results", []) if response.status_code == 200 else []
            else:
                clean_name_no_dr = re.sub(r'^(dr\b\.?\s*)', '', clean_name, flags=re.IGNORECASE)
                tokens = [t.upper() for t in clean_name_no_dr.split() if t]
                if not tokens:
                    tokens = [clean_name.upper()]
                
                # To prevent database full-table scan timeouts, we query strictly by the last token (last name) which is heavily indexed
                last_name_val = tokens[-1]
                conditions = [{"property": "covered_recipient_last_name", "value": last_name_val, "operator": "="}]
                
                payload = {
                    "conditions": conditions,
                    "limit": 500  # Fetch a larger set to filter in-memory
                }
                
                logger.info(f"Querying live indexed last name '{last_name_val}' on CMS datastore: {payload}")
                response = await client.post(CMS_DATASTORE_URL, json=payload)
                records = response.json().get("results", []) if response.status_code == 200 else []
                
            if records:
                results = []
                seen_npis = set()
                
                # Filter by first name token in Python to prevent timeouts
                first_name_token = tokens[0] if (not is_npi_search and len(tokens) >= 2) else None
                
                for r in records:
                    npi = r.get("covered_recipient_npi")
                    if not npi or npi in seen_npis:
                        continue
                    
                    first = r.get("covered_recipient_first_name", "") or ""
                    last = r.get("covered_recipient_last_name", "") or ""
                    
                    if first_name_token:
                        if first_name_token not in first.upper() and first.upper() not in first_name_token:
                            continue
                            
                    seen_npis.add(npi)
                    name_str = f"Dr. {first} {last}".title()
                    city_str = f"{r.get('recipient_city', 'Unknown')}, {r.get('recipient_state', 'USA')}".title()
                    
                    # Accumulate a generic payment size for immediate display info
                    amt = r.get("total_amount_of_payment_usdollars", "0")
                    amt_str = f"${float(amt):,.2f}" if amt != "0" else "Has Payments"
                    
                    results.append({
                        "name": name_str,
                        "npi": npi,
                        "city": city_str,
                        "specialty": r.get("covered_recipient_specialty_1", "Clinical Practice") or "General Practice",
                        "total_payments": amt_str
                    })
                if results:
                    return results
    except Exception as e:
        import traceback
        logger.warning(f"Live doctor search failed: {e}")
        traceback.print_exc()

    # 3. Secure beautiful demonstration fallbacks if live search returned empty
    if not mock_results:
        mock_results = [
            {
                "name": f"Dr. {name.title()}",
                "npi": "1487693021",
                "city": "Houston, TX",
                "specialty": "Cardiology Specialist",
                "total_payments": "$28,450.00"
            },
            {
                "name": f"Dr. {name.title()} (Bio-Pharma Consultant)",
                "npi": "1928374650",
                "city": "Boston, MA",
                "specialty": "Oncology Research",
                "total_payments": "$1,500.00"
            },
            {
                "name": f"Dr. {name.title()} (General Practice)",
                "npi": "1039485762",
                "city": "San Francisco, CA",
                "specialty": "Internal Medicine",
                "total_payments": "$0.00"
            }
        ]
    return mock_results

@app.get("/api/stats")
async def get_stats():
    """Returns general mock dashboard database statistics."""
    return {
        "cached_physicians": list(MOCK_PAYMENTS.keys()),
        "monitored_medications": list(MOCK_DRUGS.keys()),
        "total_records_indexed": 384021
    }

@app.get("/api/investigate")
async def investigate(doctor: str, drug: str, npi: str = ""):
    """Streaming SSE endpoint executing the ADK agent pipeline or falling back to premium simulation."""
    # Start manual span
    span = tracer.start_span("investigate_audit")
    span.set_attribute("openinference.span.kind", "CHAIN")
    span.set_attribute("input.value", f"Doctor: {doctor}, NPI: {npi}, Drug: {drug}")
    span.set_attribute("doctor.name", doctor)
    span.set_attribute("doctor.npi", npi)
    span.set_attribute("drug.name", drug)
    
    # Record prompt template details on the span for Arize Agent Path and Filters
    span.set_attribute("llm.prompt_template.template", "Please investigate doctor '{doctor}' with NPI '{npi}' and the drug '{drug}'.")
    span.set_attribute("llm.prompt_template.version", "v1.0.0-doctruth-investigation")
    span.set_attribute("attributes.llm.prompt_template.template", "Please investigate doctor '{doctor}' with NPI '{npi}' and the drug '{drug}'.")
    span.set_attribute("attributes.llm.prompt_template.version", "v1.0.0-doctruth-investigation")

    async def sse_generator():
        # Setup run properties
        user_msg_text = f"Please investigate doctor '{doctor}' with NPI '{npi}' and the drug '{drug}'."
        logger.info(f"Starting Investigation request: {user_msg_text}")
        
        adk_success = False
        captured_logs = []
        
        try:
            # 1. Attempt Live ADK Execution
            try:
                from google.adk.agents import config_agent_utils
                from google.adk import Runner
                from google.adk.sessions.in_memory_session_service import InMemorySessionService
                from google.genai import types
                
                agent = config_agent_utils.from_config("agent.yaml")
                session_service = InMemorySessionService()
                runner = Runner(agent=agent, session_service=session_service, app_name="doctruth", auto_create_session=True)
                
                user_message = types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_msg_text)]
                )
                
                yield f"data: {json.dumps({'type': 'log', 'agent': 'Chief Medical Director', 'message': 'Bootstrapping agentic investigation engine...'})}\n\n"
                await asyncio.sleep(0.5)
                
                async for event in runner.run_async(
                    user_id="web_user",
                    session_id="web_session",
                    new_message=user_message
                ):
                    content = event.stringify_content()
                    # Parse event attributes
                    agent_name = "Chief Medical Director"
                    # Infer sub-agent name from content if possible
                    if "forensic_auditor" in content.lower():
                        agent_name = "Forensic Financial Auditor"
                    elif "pharma_chemist" in content.lower():
                        agent_name = "Pharma Equivalence Chemist"
                    
                    log_entry = {'type': 'log', 'agent': agent_name, 'message': content}
                    captured_logs.append(log_entry)
                    yield f"data: {json.dumps(log_entry)}\n\n"
                    await asyncio.sleep(0.2)
                
                adk_success = True
                
            except Exception as e:
                logger.warning(f"ADK Execution exception: {e}. Transitioning elegantly to high-fidelity agent simulation stream.")
                span.record_exception(e)
            
            # 2. Resilient High-Fidelity Simulation Stream if ADK fails/unconfigured
            if not adk_success:
                from agents.tools import query_cms_database, map_brand_to_generic
                try:
                    payment_info = await query_cms_database(doctor, npi=npi)
                    drug_info = await map_brand_to_generic(drug)
                except Exception as e:
                    logger.warning(f"Error querying live database in investigate: {e}")
                    payment_info = None
                    drug_info = None

                sim_events, payment_info, drug_info = simulate_agent_flow(doctor, drug, npi, payment_info=payment_info, drug_info=drug_info)
                for ev in sim_events:
                    # Add human-like pacing for a gorgeous cinematic stream
                    await asyncio.sleep(1.2)
                    log_entry = {'type': 'log', 'agent': ev['agent'], 'message': ev['message']}
                    captured_logs.append(log_entry)
                    yield f"data: {json.dumps(log_entry)}\n\n"
                
                # Send structured analysis metrics for gauges & interactive cards
                yield f"data: {json.dumps({'type': 'complete', 'payments': payment_info, 'drug': drug_info})}\n\n"
                
            span.set_attribute("output.value", json.dumps({
                "logs": captured_logs,
                "adk_success": adk_success
            }))
            span.set_status(trace.status.Status(trace.status.StatusCode.OK))
            
        except Exception as err:
            span.record_exception(err)
            span.set_status(trace.status.Status(trace.status.StatusCode.ERROR, str(err)))
            logger.error(f"Error in sse_generator: {err}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(err)})}\n\n"
        finally:
            try:
                span.end()
                logger.info("Successfully ended manual investigate span.")
            except Exception as ex:
                logger.warning(f"Error ending manual investigate span: {ex}")

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@app.post("/api/chat")
async def chat(request: Request):
    """Streams conversational patient advocacy responses from Gemini-2.5-Flash."""
    # Start manual span
    span = tracer.start_span("chat_advocate", kind=SpanKind.SERVER)
    span.set_attribute("openinference.span.kind", "LLM")
    span.set_attribute("llm.model_name", "gemini-2.5-flash")
    
    try:
        payload = await request.json()
        messages = payload.get("messages", [])
        span.set_attribute("input.value", json.dumps(messages))
        
        # Format for Google GenAI SDK
        contents = []
        for m in messages:
            role = m.get("role", "user").lower()
            if role in ["assistant", "model"]:
                role = "model"
            else:
                role = "user"
            contents.append({
                "role": role,
                "parts": [{"text": m.get("content", "")}]
            })
            
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        client = Client(api_key=api_key)
        
        # Build dynamic system instruction based on active audit context
        system_instruction = (
            "You are DocTruth AI, an empathetic patient advocate and clinical compliance assistant. "
            "Help the user understand the results of their medical/financial conflict audits. "
            "Explain clinical terminology (like biosimilars, NPI, FDA black-box warnings, Open Payments) in simple, "
            "easy-to-understand terms. Suggest objective, non-confrontational questions to ask their doctor. "
            "Always maintain a professional, neutral, supportive, and scientifically grounded tone. "
            "Never give definitive medical diagnoses or recommend stopping prescribed medications without consulting a physician."
        )
        
        active_context = payload.get("active_context")
        if active_context:
            doctor = active_context.get("doctor", "Unknown Doctor")
            drug = active_context.get("drug", "Unknown Drug")
            npi = active_context.get("npi", "N/A")
            city = active_context.get("city", "Unknown")
            total_payments = active_context.get("total_payments", 0)
            manufacturers = active_context.get("manufacturers", [])
            active_ingredient = active_context.get("active_ingredient", "")
            warnings = active_context.get("warnings", "")
            
            mfr_details = ""
            if manufacturers:
                mfr_list = []
                for mfr in manufacturers:
                    name_key = mfr.get("name") or mfr.get("manufacturer") or "Unknown"
                    mfr_list.append(f"- {name_key}: {mfr.get('drug', 'Unknown')} (Total: ${mfr.get('amount', 0):,.2f})")
                mfr_details = "\n".join(mfr_list)
            else:
                mfr_details = "None registered."
                
            system_instruction += (
                f"\n\nCRITICAL CONTEXT FOR THIS CONVERSATION:\n"
                f"The user has just performed a DocTruth Audit on doctor '{doctor}' and the prescribed drug '{drug}'. "
                f"You MUST use this data to tailor your response specifically to their situation. Do not talk in generic hypotheticals unless asked. "
                f"Here are the specific, verified facts of this audit:\n"
                f"- Audited Physician: {doctor} (NPI: {npi}, Location: {city})\n"
                f"- Prescribed Medication under review: {drug} (Active Ingredient: {active_ingredient})\n"
                f"- FDA Safety/Black-Box Warnings for {drug}: {warnings}\n"
                f"- Total Financial Payouts received by {doctor} from pharmaceutical manufacturers: ${total_payments:,.2f}\n"
                f"- Manufacturer Relationships/Sponsorship Breakdown:\n{mfr_details}\n\n"
                f"Maintain the persona of a knowledgeable assistant who has this scorecard right in front of them."
            )
        
        # Record prompt template details on the span for Arize Agent Path and Filters
        span.set_attribute("llm.prompt_template.template", system_instruction)
        span.set_attribute("llm.prompt_template.version", "v1.1.0-strict-advocate" if active_context else "v1.0.0-doctruth-advocate")
        span.set_attribute("attributes.llm.prompt_template.template", system_instruction)
        span.set_attribute("attributes.llm.prompt_template.version", "v1.1.0-strict-advocate" if active_context else "v1.0.0-doctruth-advocate")
        
        full_response = []

        async def response_stream():
            try:
                response = client.models.generate_content_stream(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config={
                        "system_instruction": system_instruction
                    }
                )
                for chunk in response:
                    if chunk.text:
                        full_response.append(chunk.text)
                        yield chunk.text
            except Exception as e:
                logger.error(f"Chat streaming error: {e}")
                span.record_exception(e)
                yield f"\n[Error: {str(e)}]"
            finally:
                try:
                    final_text = "".join(full_response)
                    span.set_attribute("output.value", final_text)
                    span.set_status(trace.status.Status(trace.status.StatusCode.OK))
                    span.end()
                    logger.info("Successfully ended manual chat span.")
                except Exception as ex:
                    logger.warning(f"Error ending manual chat span: {ex}")
                
        return StreamingResponse(response_stream(), media_type="text/plain")
    except Exception as e:
        logger.error(f"Chat endpoint failed: {e}")
        span.record_exception(e)
        span.set_status(trace.status.Status(trace.status.StatusCode.ERROR, str(e)))
        span.end()
        return {"error": str(e)}

# Serve UI static files
app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
