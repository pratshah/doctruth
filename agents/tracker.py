import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

logger = logging.getLogger("doctruth.tracker")

def setup_tracker():
    """Initializes professional-grade Tracing & Observability (Local Phoenix or Arize Cloud)."""
    try:
        # Check if tracing is globally enabled
        enable_tracing = os.getenv("ENABLE_TRACING", "true").lower() in ("true", "1", "yes")
        if not enable_tracing:
            logger.info("Observability tracing is disabled via environment configuration.")
            return

        space_id = os.getenv("ARIZE_SPACE_ID")
        api_key = os.getenv("ARIZE_API_KEY")

        # -------------------------------------------------------------
        # CONFIGURATION A: Production Arize Cloud Connection (OTel)
        # -------------------------------------------------------------
        if space_id and api_key:
            logger.info("Initializing production-grade Arize Cloud OTel connection...")
            
            # Configure standard OTLP Exporter with Arize headers
            headers = {
                "authorization": f"Bearer {api_key}",
                "api_key": api_key,
                "arize-api-key": api_key,
                "space_id": space_id,
                "space-id": space_id,
                "arize-space-id": space_id,
                "arize-interface": "python",
                "user-agent": "arize-python",
            }
            # Use https endpoint for GRPC/OTLP or HTTP
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "https://otlp.arize.com/v1/traces")
            
            from opentelemetry.sdk.resources import Resource
            project_name = os.getenv("PHOENIX_PROJECT_NAME", "doctruth")
            resource = Resource(attributes={
                "model_id": project_name,
                "arize.project.name": project_name,
                "openinference.project.name": project_name,
            })
            
            exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
            tracer_provider = TracerProvider(resource=resource)
            tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
            
            # Register globally
            trace.set_tracer_provider(tracer_provider)
            
            # Instrument Gemini SDK
            GoogleGenAIInstrumentor().instrument(tracer_provider=tracer_provider)
            logger.info("🚀 Telemetry stream connected successfully to Arize AI Cloud!")

        # -------------------------------------------------------------
        # CONFIGURATION B: Local Phoenix Debug Mode
        # -------------------------------------------------------------
        else:
            logger.info("No cloud credentials found. Falling back to local Arize Phoenix collector...")
            import phoenix as px
            from phoenix.otel import register
            
            enable_local = os.getenv("ENABLE_LOCAL_PHOENIX", "true").lower() in ("true", "1", "yes")
            if enable_local:
                logger.info("Launching local Arize Phoenix UI Server...")
                px.launch_app(host="127.0.0.1", port=6006)
                
            project_name = os.getenv("PHOENIX_PROJECT_NAME", "doctruth")
            tracer_provider = register(
                project_name=project_name,
                endpoint="http://127.0.0.1:6006/v1/traces",
                auto_instrument=True
            )
            GoogleGenAIInstrumentor().instrument(tracer_provider=tracer_provider)
            logger.info("🚀 Local Arize Phoenix collector started on port 6006.")

    except Exception as e:
        logger.warning(f"Failed to initialize tracking: {e}")
        import traceback
        traceback.print_exc()
