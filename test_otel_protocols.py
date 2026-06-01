import os
import logging
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_export")

space_id = os.getenv("ARIZE_SPACE_ID")
api_key = os.getenv("ARIZE_API_KEY")

print("Space ID:", space_id)
print("API Key:", api_key)

headers = {
    "space_id": space_id,
    "api_key": api_key,
}

# Try HTTP exporter
try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.resources import Resource
    
    print("Testing HTTP Exporter...")
    resource = Resource(attributes={
        "model_id": "doctruth",
        "arize.project.name": "doctruth",
    })
    exporter = HTTPExporter(endpoint="https://otlp.arize.com/v1/traces", headers=headers)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    
    tracer = provider.get_tracer("test_http")
    with tracer.start_as_current_span("test_span_http") as span:
        span.set_attribute("test_attr", "value_http")
        print("HTTP Span created and ended.")
    print("HTTP Export check done.")
except Exception as e:
    print("HTTP Exporter test failed:", e)

# Try gRPC exporter
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.resources import Resource
    
    print("Testing gRPC Exporter...")
    resource = Resource(attributes={
        "model_id": "doctruth",
        "arize.project.name": "doctruth",
    })
    # For gRPC, endpoint should be otlp.arize.com
    exporter = GRPCExporter(endpoint="otlp.arize.com:443", headers=headers)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    
    tracer = provider.get_tracer("test_grpc")
    with tracer.start_as_current_span("test_span_grpc") as span:
        span.set_attribute("test_attr", "value_grpc")
        print("gRPC Span created and ended.")
    print("gRPC Export check done.")
except Exception as e:
    print("gRPC Exporter test failed:", e)
