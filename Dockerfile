FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application.
COPY . .

# Pre-generate the bundled synthetic dataset so the image runs offline instantly.
RUN python -m medigraph.data.generator

EXPOSE 8501 8000

# Default: launch the Streamlit clinical workspace.
# Override the command to run the API:  uvicorn medigraph.api.main:app --host 0.0.0.0
CMD ["streamlit", "run", "ui/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
