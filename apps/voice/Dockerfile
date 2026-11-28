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
# Not root: the code stays root-owned and read-only; the model files below go into this user's own cache.
RUN useradd --uid 10001 --create-home app
USER app
# Bake the turn-detector and other local models into the image, so a new Machine doesn't download them on its first call.
RUN python -m ondra_voice download-files
CMD ["python", "-m", "ondra_voice", "start"]
