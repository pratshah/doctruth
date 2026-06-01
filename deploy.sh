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

# Load variables dynamically from local .env file (which is safely git-ignored)
if [ -f .env ]; then
    # Parse variables ignoring comments
    GEMINI_API_KEY=$(grep -E "^GEMINI_API_KEY=" .env | cut -d'=' -f2- | tr -d '"'\')
    ARIZE_SPACE_ID=$(grep -E "^ARIZE_SPACE_ID=" .env | cut -d'=' -f2- | tr -d '"'\')
    ARIZE_API_KEY=$(grep -E "^ARIZE_API_KEY=" .env | cut -d'=' -f2- | tr -d '"'\')
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=$(grep -E "^OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=" .env | cut -d'=' -f2- | tr -d '"'\')
else
    echo "❌ Error: .env file not found! Please create it to run deployment."
    exit 1
fi

# Ensure critical variables are loaded
if [ -z "$GEMINI_API_KEY" ] || [ -z "$ARIZE_API_KEY" ] || [ -z "$ARIZE_SPACE_ID" ]; then
    echo "❌ Error: Missing credentials in .env file."
    exit 1
fi

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
