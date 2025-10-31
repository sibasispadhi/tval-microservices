FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent.py .
COPY policy.rego .
RUN mkdir -p /app/manifests /app/logs
# Manifests and logs are bind-mounted at runtime by docker-compose. Create
# the directories here so the image build does not fail if the host dirs are
# absent during build.
CMD ["python", "/app/agent.py"]
