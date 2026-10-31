# Container image for the web app. NOT BUILT OR RUN in the environment this project was developed in (no Docker
# was available there); treat it as a starting point and verify it on your machine.
#
#   docker build -t rag-workbench .
#   docker run --rm -p 8501:8501 -e RAGWB_APP_PASSWORD=choose-a-password -v ragwb-data:/app/data rag-workbench
#
# The app is reachable from outside the container, so a password is required. There is no TLS: put the container
# behind a TLS-terminating proxy before exposing it beyond a trusted network. Pass OPENAI_API_KEY (or another
# provider's key plus OPENAI_BASE_URL) at run time with -e; never bake a key into the image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEEPEVAL_TELEMETRY_OPT_OUT=1
WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY examples ./examples
COPY .streamlit ./.streamlit
COPY start.py streamlit_app.py ./
COPY scripts ./scripts
RUN uv sync --frozen --no-dev

VOLUME ["/app/data"]
EXPOSE 8501
# Refuses to start without a password, because the app listens on every interface inside the container. The example
# runs are not pre-created here; use the New evaluation page, or run `docker exec <id> uv run --no-sync python
# scripts/seed_demo_runs.py` once.
CMD ["sh", "-c", "test -n \"$RAGWB_APP_PASSWORD\" || test -s /app/data/users.json || { echo 'Set RAGWB_APP_PASSWORD, or create accounts first (ragwb user add) in the data volume.' >&2; exit 1; }; exec uv run --no-sync streamlit run streamlit_app.py --server.address 0.0.0.0 --server.headless true"]
