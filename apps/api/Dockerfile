FROM python:3.12-slim
RUN pip install --no-cache-dir uv==0.11.32
WORKDIR /repo
COPY pyproject.toml uv.lock ./
COPY packages/core packages/core
COPY apps/api apps/api
RUN uv sync --frozen --no-dev --package ondra-api
ENV PATH="/repo/.venv/bin:$PATH"
WORKDIR /repo/apps/api
# Not root: the code stays root-owned and read-only to the process that serves requests.
RUN useradd --uid 10001 --create-home app
USER app
EXPOSE 8000
# Migrations run as the owner role, then the API serves as the RLS-bound app role.
CMD ["sh", "-c", "alembic upgrade head && python -m ondra_api.seed --if-empty && uvicorn ondra_api.main:app --host 0.0.0.0 --port 8000"]
