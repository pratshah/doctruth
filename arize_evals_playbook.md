# 🏆 DocTruth Arize Evaluation & Prompting Playbook

This playbook provides a professional-grade benchmark dataset, prompt templates under test, and LLM-as-a-judge configurations. You can use these resources to run experiments directly in the **Arize Cloud UI** (Playground & Experiments) or programmatically via the **Phoenix SDK**.

---

## 📦 1. The Golden Benchmark Dataset

This dataset is designed to evaluate DocTruth's core multi-agent capability: auditing pharmaceutical conflicts of interest (COI) by cross-referencing clinician names and drugs against NPI records and risk levels.

### Dataset Table

| input_doctor | input_drug | expected_npi | expected_risk | expected_active_ingredient |
| :--- | :--- | :--- | :--- | :--- |
| **Donald Griffith** | Lithostat | `1821102930` | `HIGH` | `acetohydroxamic acid` |
| **Sarah Jenkins** | Keytruda | `1928374650` | `MODERATE` | `pembrolizumab` |
| **Robert Chen** | Humira | `1487693021` | `HIGH` | `adalimumab` |
| **Elena Rostova** | Lipitor | `1029384756` | `LOW` | `atorvastatin` |
| **Marcus Vance** | Ozempic | `1122334455` | `MODERATE` | `semaglutide` |

### Raw CSV Format (For Quick Arize Cloud Upload)
Save the block below as `doctruth_golden_benchmark.csv` and upload it directly to **Arize Cloud > Datasets**:

```csv
input_doctor,input_drug,expected_npi,expected_risk,expected_active_ingredient
Donald Griffith,Lithostat,1821102930,HIGH,acetohydroxamic acid
Sarah Jenkins,Keytruda,1928374650,MODERATE,pembrolizumab
Robert Chen,Humira,1487693021,HIGH,adalimumab
Elena Rostova,Lipitor,1029384756,LOW,atorvastatin
Marcus Vance,Ozempic,1122334455,MODERATE,semaglutide
```

---

## 📝 2. Prompts Under Experimentation (A/B Testing)

When optimizing the DocTruth multi-agent system, we test different prompts inside the **Arize Prompt Playground** to minimize hallucination and maximize tone objectivity.

### Prompt Template A: General / Detailed (Baseline)
*   **System Instructions:**
    ```text
    You are an expert pharmaceutical compliance auditor. Your job is to analyze potential conflicts of interest for clinicians prescribing specific medications. 
    Always cross-reference the input clinician name against known national databases to extract their NPI number.
    Determine the active ingredient of the drug under investigation, and assess the financial conflict risk level (HIGH, MODERATE, LOW) based on Open Payments data.
    Be objective, thorough, and cite clinical resources where appropriate.
    ```
*   **User Template:**
    ```text
    Perform a compliance audit for:
    - Clinician: {{input_doctor}}
    - Target Drug: {{input_drug}}
    ```

### Prompt Template B: Strict Clinical Compliance (Optimized)
*   **System Instructions:**
    ```text
    You are a meticulous, non-accusatory medical ethics compliance officer. Your primary goal is to draft safe, objective discussion guides.
    1. EXTRACT: Extract the correct 10-digit NPI number and the active pharmaceutical ingredient.
    2. RISK ASSESSMENT: Classify conflict risk strictly as HIGH, MODERATE, or LOW.
    3. CLINICAL TONE: Maintain absolute neutrality. Do NOT accuse clinicians of malpractice or unethical behavior. Frame findings as "points for verification" rather than confirmed misconduct.
    
    Structure your response as follows:
    - NPI: [NPI]
    - ACTIVE INGREDIENT: [Ingredient]
    - COI RISK: [RISK]
    - CLINICAL AUDIT SUMMARY: [Summary]
    ```
*   **User Template:**
    ```text
    Initiate compliance trace and draft patient discussion guide:
    - Clinician Name: {{input_doctor}}
    - Prescribed Drug: {{input_drug}}
    ```

---

## ⚖️ 3. LLM-as-a-Judge Evaluation Rubrics

Use these prompts to set up **LLM Judges** in Arize Cloud. This automatically scores the outputs generated from your prompt experiments.

### Judge A: Factual Hallucination Evaluator (QA Consistency)
This judge checks if the model correctly identified the ground-truth active ingredients and NPI numbers.

*   **Judge System Prompt:**
    ```text
    You are an independent quality-assurance auditor. Compare the agent's generated response against the expected ground truth reference.
    
    [GENERATED RESPONSE]:
    {output}
    
    [EXPECTED GROUND TRUTH]:
    Active Ingredient: {expected_active_ingredient}
    NPI: {expected_npi}
    
    Classify the generated response into one of these categories:
    - Correct: The response successfully and accurately mentions the correct NPI and Active Ingredient.
    - Hallucinated: The response contains an incorrect NPI, an incorrect active ingredient, or claims they do not exist when they do.
    ```

### Judge B: Clinical Tone Professionalism Judge
This custom classifier ensures that the generated patient guide does not use inflammatory or alarmist language.

*   **Judge System Prompt:**
    ```text
    You are a meticulous medical ethics compliance officer.
    Evaluate the patient discussion guide produced by the agent to ensure clinical safety, tone objectivity, and non-accusatory questions.

    [AGENT CONFLICT GUIDE]:
    {output}

    Respond strictly with one of the following classification choices:
    - Safe & Professional: The tone is objective, constructive, non-accusatory, and clinically appropriate. 
    - Unsafe / Hostile: The tone is accusatory, combative, finger-pointing, or alarmist (e.g. suggests medical malpractice without direct verification).
    
    Provide a brief, 2-sentence explanation of your choice.
    ```

---

## 🚀 4. Running the Evaluation Pipeline

### Visual UI Flow (No-Code)
1. Go to **Arize AX > Playground**.
2. Select your model (e.g., `gemini-2.5-flash`).
3. Load the dataset uploaded from Section 1.
4. Paste **Prompt Template B** into the playground.
5. Link variables (`input_doctor`, `input_drug`).
6. Run the experiment and attach **Judge B (Clinical Tone)** to instantly view quality scores!

### Programmatic SDK Flow (Python)
If you prefer running evaluations locally and syncing results to the cloud, use your updated `run_evals.py` script:
```bash
# Ensure your environment variables are configured in .env:
# PHOENIX_API_KEY="your-phoenix-key"
# PHOENIX_BASE_URL="https://app.phoenix.arize.com"

# Execute the pipeline
.venv/bin/python run_evals.py
```
