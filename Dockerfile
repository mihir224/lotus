FROM node:22-slim AS web-builder

WORKDIR /workspace/apps/web
COPY apps/web/package.json apps/web/package-lock.json apps/web/.npmrc ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build


FROM python:3.12-slim AS python-builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /workspace
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


FROM python:3.12-slim AS runtime

ENV PATH="/workspace/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080
WORKDIR /workspace

COPY --from=python-builder /workspace/.venv .venv
COPY apps/api apps/api
COPY demo_data demo_data
COPY migrations migrations
COPY alembic.ini pyproject.toml ./
COPY --from=web-builder /workspace/apps/web/dist apps/web/dist

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn --app-dir apps/api lotus_api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
