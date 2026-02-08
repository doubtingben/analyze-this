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
from opentelemetry.trace import Status, StatusCode, SpanKind, Link
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

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

    # Add Honeycomb header if key is present
    honeycomb_key = os.getenv("HONEYCOMB_API_KEY")
    if honeycomb_key and "x-honeycomb-team" not in headers:
        headers["x-honeycomb-team"] = honeycomb_key

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


# --- Distributed Tracing Context Propagation ---

_propagator = TraceContextTextMapPropagator()


def inject_trace_context(carrier: Optional[dict] = None) -> dict:
    """
    Inject current trace context into a carrier dict for propagation.

    Use this when enqueueing a job to pass trace context to the worker.

    Usage:
        payload = {"source": "note"}
        payload = inject_trace_context(payload)
        await db.enqueue_worker_job(item_id, user_email, "follow_up", payload)

    Returns the carrier dict with trace context injected.
    """
    if carrier is None:
        carrier = {}

    # Only inject if tracing is enabled and we have a current span
    span = trace.get_current_span()
    if span and span.is_recording():
        _propagator.inject(carrier)

    return carrier


def extract_trace_context(carrier: dict) -> Optional[trace.Context]:
    """
    Extract trace context from a carrier dict.

    Use this when processing a job to continue the trace from the API.

    Usage:
        ctx = extract_trace_context(job.get('payload', {}))
        with create_span_with_context("process_job", ctx):
            # Processing code here

    Returns the extracted context, or None if no context found.
    """
    if not carrier:
        return None

    return _propagator.extract(carrier)


@contextmanager
def create_span_with_context(
    name: str,
    parent_context: Optional[trace.Context] = None,
    attributes: Optional[dict] = None,
    kind: SpanKind = SpanKind.INTERNAL
):
    """
    Create a span with an optional parent context from a different process.

    Use this in workers to continue a trace started in the API.

    Usage:
        ctx = extract_trace_context(job_payload)
        with create_span_with_context("worker_process_job", ctx) as span:
            # Processing code
    """
    if _tracer is None:
        yield NoOpSpan()
        return

    with _tracer.start_as_current_span(
        name,
        context=parent_context,
        kind=kind
    ) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


@contextmanager
def create_linked_span(
    name: str,
    link_context: Optional[trace.Context] = None,
    attributes: Optional[dict] = None,
    kind: SpanKind = SpanKind.CONSUMER
):
    """
    Create a new root span with a link to the original trace.

    Use this for async processing where you want a separate trace
    but still want to reference the originating request.

    This is useful for workers that process jobs asynchronously,
    creating a new trace while maintaining a link to the enqueuing trace.
    """
    if _tracer is None:
        yield NoOpSpan()
        return

    links = []
    if link_context:
        # Extract the span context from the parent context
        span_context = trace.get_current_span(link_context).get_span_context()
        if span_context.is_valid:
            links.append(Link(span_context))

    with _tracer.start_as_current_span(
        name,
        kind=kind,
        links=links
    ) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        # Add link info as attribute for easier querying
        if links and links[0].context.is_valid:
            span.set_attribute("linked.trace_id", format(links[0].context.trace_id, '032x'))
            span.set_attribute("linked.span_id", format(links[0].context.span_id, '016x'))
        yield span
