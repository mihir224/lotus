import logging
from time import perf_counter

from opentelemetry import trace
from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("uvicorn.error.lotus.database")
tracer = trace.get_tracer("lotus.database")


def record_retrieval(operation: str, result_count: int) -> None:
    """Record bounded retrieval metadata without query or result content."""

    with tracer.start_as_current_span(f"lotus.db.retrieval.{operation}") as span:
        span.set_attribute("db.system.name", "postgresql")
        span.set_attribute("lotus.store.backend", "postgres")
        span.set_attribute("lotus.db.result_count", result_count)
    logger.info(
        "db.retrieval operation=%s store=postgres result_count=%d",
        operation,
        result_count,
    )


def instrument_database(engine: Engine) -> None:
    """Emit database timings without SQL text, bind values, or application content."""

    @event.listens_for(engine, "checkout")
    def checkout(_dbapi_connection, connection_record, _connection_proxy):
        connection_record.info["lotus_checked_out_at"] = perf_counter()
        logger.info("db.pool.checkout store=postgres")

    @event.listens_for(engine, "checkin")
    def checkin(_dbapi_connection, connection_record):
        checked_out_at = connection_record.info.pop("lotus_checked_out_at", None)
        held_ms = (perf_counter() - checked_out_at) * 1000 if checked_out_at else 0.0
        logger.info("db.pool.checkin store=postgres held_ms=%.1f", held_ms)

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(_conn, _cursor, statement, _parameters, context, _executemany):
        operation = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else "UNKNOWN"
        context._lotus_started = perf_counter()
        context._lotus_operation = operation
        context._lotus_span = tracer.start_span(f"lotus.db.{operation.casefold()}")
        context._lotus_span.set_attribute("db.system.name", "postgresql")
        context._lotus_span.set_attribute("db.operation.name", operation)

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(_conn, cursor, _statement, _parameters, context, _executemany):
        started = getattr(context, "_lotus_started", perf_counter())
        operation = getattr(context, "_lotus_operation", "UNKNOWN")
        duration_ms = (perf_counter() - started) * 1000
        row_count = cursor.rowcount if cursor.rowcount >= 0 else None
        span = getattr(context, "_lotus_span", None)
        if span is not None:
            span.set_attribute("lotus.db.duration_ms", duration_ms)
            if row_count is not None:
                span.set_attribute("lotus.db.row_count", row_count)
            span.end()
        logger.info(
            "db.complete operation=%s duration_ms=%.1f row_count=%s",
            operation,
            duration_ms,
            row_count if row_count is not None else "unknown",
        )

    @event.listens_for(engine, "handle_error")
    def handle_error(exception_context):
        context = exception_context.execution_context
        span = getattr(context, "_lotus_span", None) if context is not None else None
        if span is not None:
            span.record_exception(exception_context.original_exception)
            span.set_attribute("error.type", type(exception_context.original_exception).__name__)
            span.end()
        logger.warning(
            "db.failed error=%s",
            type(exception_context.original_exception).__name__,
        )
