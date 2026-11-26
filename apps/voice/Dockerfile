FROM python:3.12-slim
RUN pip install --no-cache-dir uv==0.11.32
WORKDIR /repo
COPY pyproject.toml uv.lock ./
COPY packages/core packages/core
COPY apps/api apps/api
COPY apps/voice apps/voice
RUN uv sync --frozen --no-dev --package ondra-voice
ENV PATH="/repo/.venv/bin:$PATH"
WORKDIR /repo/apps/voice
CMD ["python", "-m", "ondra_voice", "start"]
