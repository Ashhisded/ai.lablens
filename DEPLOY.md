# Deployment Guide: LabLens on Google Cloud Run

This guide details how to deploy LabLens to Google Cloud Run as a secure, cost-controlled, autoscaling containerized service.

---

## Prerequisites

1. [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and authenticated.
2. An active Google Cloud Project with billing enabled.
3. A Google Gemini API key obtained from [Google AI Studio](https://ai.google.dev).

---

## 1. Project Configuration

Set your project variables (replace placeholders with your real values):

```bash
export PROJECT_ID="YOUR_GCP_PROJECT_ID"
export REGION="us-central1"
export SERVICE_NAME="lablens"

# Configure gcloud defaults
gcloud config set project ${PROJECT_ID}
gcloud config set run/region ${REGION}
```

---

## 2. Enable Required APIs

Enable the Cloud Run, Artifact Registry, Cloud Build, and Secret Manager APIs:

```bash
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com
```

---

## 3. Store Gemini API Key in Secret Manager

Securely create a secret for your Gemini API key:

```bash
# Create the secret container
gcloud secrets create gemini-api-key --replication-policy="automatic"

# Add the secret version (replace your-real-key-here)
echo -n "your-real-key-here" | gcloud secrets versions add gemini-api-key --data-file=-
```

Grant Cloud Run's default service account permission to read the secret:

```bash
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")

gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

---

## 4. Deploy to Google Cloud Run

Deploy directly from source using Google Cloud Build and Cloud Run:

```bash
gcloud run deploy ${SERVICE_NAME} \
    --source . \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
    --set-env-vars="APP_ENV=production,GEMINI_MODEL=gemini-3.5-flash,RATE_LIMIT_RPM=20" \
    --cpu=1 \
    --memory=512Mi \
    --concurrency=80 \
    --timeout=30 \
    --min-instances=0 \
    --max-instances=3
```

### Resource & Cost Control Notes:
- `--min-instances=0`: Scales to zero when idle (no baseline hosting cost).
- `--max-instances=3`: Hard ceiling to prevent runaway costs during traffic spikes.
- `--memory=512Mi` / `--cpu=1`: Minimal resource allocation tailored to LabLens's lightweight ASGI architecture.
- `--allow-unauthenticated`: Public access for users to assess their lab reports.

---

## 5. Verify the Deployment

Retrieve the deployed service URL:

```bash
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format="value(status.url)")
echo "LabLens deployed at: ${SERVICE_URL}"
```

### Health Check Verification
```bash
curl -i "${SERVICE_URL}/health"
```
Expected output:
```http
HTTP/1.1 200 OK
content-type: application/json
content-security-policy: default-src 'self'; ...
x-content-type-options: nosniff
x-frame-options: DENY

{"status":"ok"}
```

### Analysis API Verification
```bash
curl -i -X POST "${SERVICE_URL}/api/analyze" \
    -H "Content-Type: application/json" \
    -d '{
      "sex": "male",
      "values": {
        "hemoglobin": 11.0,
        "fasting_glucose": 115.0
      }
    }'
```

---

## 6. Local Container Testing (Optional)

You can build and test the container locally before deploying to Cloud Run:

```bash
# Build local container
docker build -t lablens:local .

# Run container (port 8080)
docker run --rm -p 8080:8080 \
    -e GEMINI_API_KEY="your-gemini-api-key" \
    -e APP_ENV="development" \
    lablens:local

# Check health endpoint
curl http://localhost:8080/health
```
