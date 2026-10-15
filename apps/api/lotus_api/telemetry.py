import logging

from google.adk.telemetry.google_cloud import get_gcp_exporters
from google.adk.telemetry.setup import maybe_set_otel_providers

from .config import Settings

logger = logging.getLogger("uvicorn.error.lotus.telemetry")
_configured = False


def configure_telemetry(settings: Settings) -> None:
    """Configure ADK's authenticated Google Cloud OTLP exporters once."""
    global _configured
    if _configured or not settings.telemetry_enabled:
        return
    try:
        exporters = get_gcp_exporters(
            enable_cloud_tracing=True,
            enable_cloud_metrics=True,
            enable_cloud_logging=False,
        )
        maybe_set_otel_providers([exporters])
        _configured = True
        logger.info("telemetry.configured tracing=true metrics=true content_capture=false")
    except Exception as exc:
        logger.warning("telemetry.disabled reason=%s", type(exc).__name__)
