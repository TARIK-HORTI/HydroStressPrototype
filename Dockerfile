# Image de production de HydroStress (Cloud Run, VPS, ou tout hôte Docker).
#   docker build -t hydrostress .
#   docker run -p 8080:8080 -e EE_SERVICE_ACCOUNT_JSON="$(cat key.json)" hydrostress
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    HYDROSTRESS_STAGE=beta

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home appuser && mkdir -p data && chown -R appuser /app
USER appuser

EXPOSE 8080
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false"]
