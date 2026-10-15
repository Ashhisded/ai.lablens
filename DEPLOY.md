# Deployment Guide: LabLens

This guide outlines deployment options for LabLens, with **Vercel** as the primary serverless target (zero billing required) and **Google Cloud Run** as an alternative containerized target.

---

## 1. Vercel Deployment (Primary – Free Tier)

Deploying to Vercel requires no Docker daemon, no credit card or billing account, and takes under 3 minutes via the Vercel Web Dashboard.

### Step 1: Push Code to GitHub
Ensure your latest changes are committed and pushed to your public GitHub repository:
```bash
git push origin main
```

### Step 2: Import Project in Vercel Dashboard
1. Log in to your [Vercel Dashboard](https://vercel.com).
2. Click **"Add New..."** &rarr; **"Project"**.
3. Under **Import Git Repository**, find `lablens` (or your repository name) and click **"Import"**.

### Step 3: Configure Project & Environment Variables
Before clicking Deploy, configure your project settings:
1. **Framework Preset:** Vercel automatically detects FastAPI / Python. If prompted, confirm Root Directory is `./`.
2. Expand the **Environment Variables** panel. Add the following variables:
   - `GEMINI_API_KEY`: Your Google Gemini API key from [Google AI Studio](https://aistudio.google.com).
   - `GEMINI_MODEL`: `gemini-3.5-flash` (or leave unset to use default).
   - `APP_ENV`: `production` (disables `/docs` and `/redoc` for security).
   - `RATE_LIMIT_RPM`: `20` (in-memory rate limit per instance).

> **Important:** Always add `GEMINI_API_KEY` *before* the initial deployment so that the serverless build has access to runtime configuration upon cold start. If no key is set, LabLens will automatically use its built-in static fallback explanations.

### Step 4: Deploy & Verify
1. Click **"Deploy"**.
2. Once the build finishes, Vercel will provide your live deployment URL (e.g. `https://lablens.vercel.app`).
3. Verify the deployment:
   - **Health check:** Open `https://your-domain.vercel.app/health` &rarr; returns `{"status":"ok"}`.
   - **Home page:** Open `https://your-domain.vercel.app/` &rarr; landing page loads with styles and navigation.
   - **Analyzer:** Click **"Check my lab values"** (`/analyze`). Click **"Fill sample values"** and submit &rarr; verify results and explanations render.
   - **API:** Send a test POST request to `https://your-domain.vercel.app/api/analyze`.

### Step 5: Viewing Runtime Logs
In your Vercel Dashboard:
1. Navigate to your project &rarr; **Deployments**.
2. Select your current production deployment and click **Logs**.
3. Runtime logs display anonymous request IDs, HTTP status codes, and latency. In compliance with strict health data safety guidelines, user-submitted lab values and credentials are never logged.

---

## 2. Alternative: Google Cloud Run (Containerized)

If you have a Google Cloud account with billing enabled, you can deploy LabLens as a managed container on Google Cloud Run.

### Prerequisites
1. [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and authenticated.
2. An active Google Cloud Project with billing enabled.
3. Secret Manager API enabled.

### Deployment Commands
```bash
export PROJECT_ID="YOUR_GCP_PROJECT_ID"
export REGION="us-central1"
export SERVICE_NAME="lablens"

# Configure gcloud
gcloud config set project ${PROJECT_ID}
gcloud config set run/region ${REGION}

# Enable APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

# Store Gemini API Key in Secret Manager
gcloud secrets create gemini-api-key --replication-policy="automatic"
echo -n "YOUR_GEMINI_KEY" | gcloud secrets versions add gemini-api-key --data-file=-

# Deploy to Cloud Run
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
- `--min-instances=0`: Scales to zero when idle (no baseline server cost).
- `--max-instances=3`: Hard ceiling preventing runaway costs during traffic spikes.
- `--memory=512Mi` / `--cpu=1`: Minimal resource allocation tailored to LabLens's lightweight ASGI architecture.
