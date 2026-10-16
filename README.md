# Trinetra — Insurance Automation Platform

> A prototype for vehicle insurance claim triage, fraud risk screening, decision tracking, and reviewer support.

## 🎬 Demo

[![Watch Demo](https://img.shields.io/badge/Watch-Demo-blue?logo=googledrive&style=for-the-badge)](https://drive.google.com/file/d/1kxVvMh3pEdsU7B3ISRmeHn2RcwrOPcNd/view?usp=drive_link)

---

## 🚀 Features

- **Claim intake and triage** — Submit vehicle claims and route them using a model risk score.
- **Review support** — Browse decisions, an investigator queue, and template explanations.
- **Decision history** — Store claim inputs, decisions, model/policy versions, and scoring warnings.
- **Monitoring** — View decision counts and block rates; these are not confirmed fraud outcomes.

The current implementation does not manage policy lifecycles or execute payouts.

---

## Architecture

Next.js / React / TypeScript UI → FastAPI automation API → XGBoost model service.
PostgreSQL stores claims and decisions. Separate FastAPI services provide monitoring
and template explanations. Docker uses PostgreSQL with the pgvector extension;
policy retrieval and OpenAI helpers are experimental and are not wired into the active explanation endpoints.

## Decision behavior and limitations

- Scores below the saved model threshold are eligible for automatic approval;
  scores at or above it go to review. Automatic blocking is disabled by default.
  An optional `BLOCK_CUTOFF` environment variable enables a separate blocking policy
  and must exceed the model threshold. No blocking cutoff has been validated here.
- Failed predictions use an explicitly marked fallback scorer. These results always
  go to human review, with warnings saved in the decision history.
- The intake is a partial match to the training schema. Age, previous claims, police
  report, channel, and policy age are mapped; missing vehicle attributes use defaults.
  Claim amount is not used to invent vehicle value or deductible. This model needs
  representative data and validation before operational use.
- Scores are not calibrated fraud probabilities. Decision confidence is unavailable;
  the legacy database column stores zero for schema compatibility and the API returns null.
- Explanations describe recorded scores, thresholds, and claim facts. They do not
  measure model feature contributions. Portfolio statistics do not determine decisions.
- KPI summaries default to the last 24 hours (`window_hours=1..720`). Block rate is
  the fraction of decisions blocked, not confirmed fraud prevalence.
- Future training selects the operating threshold on validation data. The bundled
  model and metrics were not retrained; their original threshold used the test split,
  so those metrics are not an independent evaluation of that threshold.

## Checks

Install service dependencies and `httpx` in a Python environment, then run:

```bash
python -m unittest discover -s tests -v
cd ui
npm run lint
npx tsc --noEmit
npm run build
```

## ⚙️ Installation

### Recommended setup

Prerequisite: Docker Desktop or another Docker Compose installation.

```bash
git clone https://github.com/march-M-R/trinetra.git
cd trinetra
docker compose -f trinethra/infra/docker-compose.yml up --build
```

Open http://localhost:3000. Interactive API documentation is available at:

- Explanation service: http://localhost:8001/docs
- Model service: http://localhost:8002/docs
- Automation API: http://localhost:8003/docs
- Monitoring service: http://localhost:8004/docs

### Frontend-only development

```bash
cd ui
npm ci
npm run dev
```

Point it at locally running services if needed:

```env
NEXT_PUBLIC_AUTOMATION_API_BASE=http://localhost:8003
NEXT_PUBLIC_EXPLAIN_API_BASE=http://localhost:8001
```

---

## 👩‍💻 Author

**Mahathi Rachavelpula**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-%230077B5.svg?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/mahathi9/)
[![GitHub](https://img.shields.io/badge/GitHub-%23121011.svg?style=for-the-badge&logo=github&logoColor=white)](https://github.com/march-M-R)

---

> ⭐ If you found this project useful, consider giving it a star!

## Production deployment

The existing frontend is hosted on Vercel at https://trinethra.vercel.app.
Use `ui` as the Vercel project root. Frontend API calls use same-origin
`/api/automation` routes; configure `AUTOMATION_API_BASE` on the server to point
to the automation service. The older `NEXT_PUBLIC_AUTOMATION_API_BASE` variable
is also accepted by the server for compatibility.

Template explanations and analyst responses are served by the frontend's
`/api/explain` routes, so the public website does not require a separate explanation
service. These are deterministic templates, not LLM feature attributions.

The automation service requires a working PostgreSQL database (`DATABASE_URL`,
or `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) and `MODEL_URL`.
Initialize new databases with `trinethra/infra/sql/001_init.sql` before serving
claims. Its `/health` endpoint returns HTTP 503 if the database or decision table
is unavailable. A frontend-only deployment does not restore an unavailable database.
