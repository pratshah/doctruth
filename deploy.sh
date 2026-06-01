#!/bin/bash
# DocTruth Cloud Run Deployment Script

echo "--------------------------------------------------------"
echo "🚀 Deploying DocTruth Multi-Agent Platform to Cloud Run"
echo "--------------------------------------------------------"

# Ensure gcloud CLI is authenticated and set up
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: Google Cloud SDK (gcloud) is not installed."
    echo "Please install it from https://cloud.google.com/sdk/docs/install and try again."
    exit 1
fi

# Retrieve project values from .env
GEMINI_API_KEY="AIzaSyBqR6EXjUqtBdGfdoiiA57kK9ID0JYbQbU"
ARIZE_SPACE_ID="U3BhY2U6NDU3Mjc6N2xsQw=="
ARIZE_API_KEY="ak-277b98c1-e815-4c63-8b78-9637c15b1cca-rN5pWDpQusP60SCktg07kLeIbLUVwaSU"
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="https://otlp.arize.com/v1/traces"

echo "📡 Registering Google Cloud Run service 'doctruth'..."
gcloud run deploy doctruth \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY},ARIZE_SPACE_ID=${ARIZE_SPACE_ID},ARIZE_API_KEY=${ARIZE_API_KEY},OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT},ENABLE_LOCAL_PHOENIX=false"

echo "--------------------------------------------------------"
echo "🎉 Deployment initiated successfully!"
echo "--------------------------------------------------------"
