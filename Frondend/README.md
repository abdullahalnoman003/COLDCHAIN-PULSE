# ColdChain Pulse Dispatcher Dashboard

Responsive React dashboard for MedSwift Logistics. It uses the existing FastAPI service for authentication, shipment summaries, paginated shipment data, alert management, and telemetry.

## Run locally

```bash
npm install
Copy-Item .env.example .env
npm run dev
```

Set `VITE_API_BASE_URL` in `.env` to the backend origin (default: `http://localhost:8000`). The backend must allow the frontend origin through `CORS_ORIGINS`.

## Production build

```bash
npm run build
npm run preview
```

Dispatcher, admin, and auditor accounts can access the dashboard. The shipment table requests 10 records per page from the API; the delayed count uses paginated in-transit records and each shipment's ETA. Search and alternate sorting apply to the currently displayed API page because the existing shipment-list endpoint does not expose search or sort parameters.
