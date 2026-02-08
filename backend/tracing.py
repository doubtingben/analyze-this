"""
OpenTelemetry tracing configuration for AnalyzeThis.

Setup for Honeycomb:
1. Create a Honeycomb account at https://www.honeycomb.io
2. Get your API key from: Settings > API Keys > Create API Key
3. Set environment variables:
   - OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io
   - OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=YOUR_API_KEY
   - OTEL_SERVICE_NAME=analyzethis-api (optional, defaults to this)

Alternatively, you can use any OTLP-compatible backend by setting OTEL_EXPORTER_OTLP_ENDPOINT.
"""
import os
import logging
from contextlib import contextmanager
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)

# Global tracer instance
_tracer: Optional[trace.Tracer] = None

# Environment configuration
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() in ("1", "true", "yes")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "analyzethis-api")
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
OTEL_EXPORTER_OTLP_HEADERS = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")


def init_tracing() -> Optional[trace.Tracer]:
    """
    Initialize OpenTelemetry tracing with OTLP exporter.

    Returns the tracer instance, or None if tracing is disabled.
    """
    global _tracer

    if not OTEL_ENABLED:
        logger.info("OpenTelemetry tracing is disabled (OTEL_ENABLED=false)")
        return None

    if not OTEL_EXPORTER_OTLP_ENDPOINT:
        logger.warning(
            "OpenTelemetry tracing disabled: OTEL_EXPORTER_OTLP_ENDPOINT not set. "
            "For Honeycomb, set OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io"
        )
        return None

    # Create resource with service name
    resource = Resource.create({
        SERVICE_NAME: OTEL_SERVICE_NAME
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Parse headers for OTLP exporter
    headers = {}
    if OTEL_EXPORTER_OTLP_HEADERS:
        for header in OTEL_EXPORTER_OTLP_HEADERS.split(","):
            if "=" in header:
                key, value = header.split("=", 1)
                headers[key.strip()] = value.strip()

    # Create OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=f"{OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces",
        headers=headers
    )

    # Add batch processor for efficient span export
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Get tracer instance
    _tracer = trace.get_tracer(__name__)

    logger.info(f"OpenTelemetry tracing initialized: service={OTEL_SERVICE_NAME}, endpoint={OTEL_EXPORTER_OTLP_ENDPOINT}")

    return _tracer


def get_tracer() -> Optional[trace.Tracer]:
    """Get the global tracer instance."""
    return _tracer


def shutdown_tracing():
    """Shutdown tracing and flush any pending spans."""
    provider = trace.get_tracer_provider()
    if hasattr(provider, 'shutdown'):
        provider.shutdown()
        logger.info("OpenTelemetry tracing shutdown complete")


@contextmanager
def create_span(name: str, attributes: Optional[dict] = None):
    """
    Create a new span with the given name and optional attributes.

    Usage:
        with create_span("operation_name", {"key": "value"}) as span:
            # Your code here
            span.set_attribute("result", "success")

    If tracing is disabled, yields a no-op context.
    """
    if _tracer is None:
        yield NoOpSpan()
        return

    with _tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


class NoOpSpan:
    """No-op span for when tracing is disabled."""

    def set_attribute(self, key: str, value) -> None:
        pass

    def set_status(self, status) -> None:
        pass

    def record_exception(self, exception) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        pass


def add_span_attributes(attributes: dict) -> None:
    """Add attributes to the current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def record_exception(exception: Exception) -> None:
    """Record an exception on the current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR, str(exception)))


def add_span_event(name: str, attributes: Optional[dict] = None) -> None:
    """Add an event to the current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes=attributes or {})
