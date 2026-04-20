# EventFlow

A production-style **serverless event processing system** built on AWS,
with a live React dashboard.

Events are ingested via REST API, queued asynchronously through SQS, processed
by a batch Lambda consumer, and stored in DynamoDB with atomic counter aggregation.
The React dashboard visualises stats in real time and lets you fire test events
directly from the browser.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENT / APPLICATION                            │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY  (REST)                              │
│   POST /event          GET /stats       GET /events/recent               │
│   (rate-limited: 100 req/s, burst 200)                                   │
└───────┬─────────────────────┬──────────────────────┬────────────────────┘
        │                     │                      │
        ▼                     ▼                      ▼
┌───────────────┐  ┌─────────────────┐  ┌──────────────────────┐
│  PostEvent λ  │  │  GetStats λ     │  │  GetRecent λ         │
│  (validate +  │  │  (read-only     │  │  (GSI query or scan) │
│   enqueue)    │  │   stats)        │  │                      │
└───────┬───────┘  └────────┬────────┘  └──────────┬───────────┘
        │                   │                      │
        │ SendMessage        │ GetItem / Scan        │ Query / Scan
        ▼                   ▼                      ▼
┌───────────────┐  ┌─────────────────────────────────────────────┐
│  SQS Queue    │  │              DynamoDB                        │
│  (standard)   │  │                                              │
│               │  │  ┌──────────────┐   ┌──────────────────┐   │
│  maxReceive=3 │  │  │  EventsTable │   │   StatsTable     │   │
│  ↓ after 3x   │  │  │  PK: event_id│   │  PK: stat_key    │   │
│  ┌──────────┐ │  │  │  GSI: type + │   │  TOTAL           │   │
│  │   DLQ    │ │  │  │  created_at  │   │  TYPE#<name>     │   │
│  └──────────┘ │  │  └──────────────┘   └──────────────────┘   │
└───────┬───────┘  └─────────────────────────────────────────────┘
        │                            ▲
        │ Trigger (batch ≤10)        │ PutItem (conditional)
        ▼                            │ UpdateItem ADD (atomic)
┌───────────────┐                    │
│  SqsProcessor │────────────────────┘
│  λ  (batch)   │
│               │
│  idempotency: │
│  conditional  │
│  write        │
└───────────────┘
```

### Data flow

1. **POST /event** — `PostEventFunction` validates the payload, assigns a UUID
   and ISO-8601 timestamp, then sends it to SQS.  Returns `202 Accepted`
   immediately without touching DynamoDB.

2. **SQS → Processor** — `SqsProcessorFunction` is triggered in batches of up
   to 10 messages.  For each message it:
   - Calls `DynamoDB.put_item` with `ConditionExpression = attribute_not_exists(event_id)`
     to guarantee exactly-once writes (idempotency).
   - Atomically increments the global and per-type counters in `StatsTable`
     using DynamoDB's `ADD` operation.
   - Returns `batchItemFailures` for any message that raised an exception so SQS
     only re-enqueues those messages (partial-batch failure).

3. **GET /stats** — `GetStatsFunction` reads the pre-aggregated counters from
   `StatsTable`.  O(1) regardless of event volume.

4. **GET /events/recent** — `GetRecentFunction` queries the GSI
   `type-created_at-index` when a type filter is provided (efficient range
   query), or does a bounded scan for all-type queries.

---

## API Reference

### POST /event

Enqueue an event for asynchronous processing.

```
POST /event
Content-Type: application/json

{
  "type": "purchase",
  "value": 49.99
}
```

**Response 202**
```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Event accepted for processing",
  "created_at": "2024-01-15T10:30:00.000000+00:00"
}
```

---

### GET /stats

Returns aggregated statistics.

```
GET /stats
```

**Response 200**
```json
{
  "total_events": 1500,
  "total_value": 74250.00,
  "average_value": 49.5,
  "by_type": {
    "purchase": {
      "count": 900,
      "total_value": 62100.0,
      "average_value": 69.0
    },
    "view": {
      "count": 600,
      "total_value": 12150.0,
      "average_value": 20.25
    }
  }
}
```

---

### GET /events/recent

Query recent events with optional filters.

```
GET /events/recent?limit=10&type=purchase&since=2024-01-01T00:00:00Z
```

| Parameter | Type    | Default | Description                             |
|-----------|---------|---------|------------------------------------------|
| `limit`   | integer | 20      | Max results (1–100)                      |
| `type`    | string  | –       | Filter by event type (uses GSI)          |
| `since`   | ISO-8601| –       | Only return events after this timestamp  |

**Response 200**
```json
{
  "count": 2,
  "limit": 10,
  "filters": { "type": "purchase", "since": null },
  "events": [
    {
      "event_id": "...",
      "event_type": "purchase",
      "value": 49.99,
      "created_at": "2024-01-15T10:30:00+00:00",
      "processed_at": "2024-01-15T10:30:01+00:00",
      "status": "processed"
    }
  ]
}
```

---

## Project Structure

```
EventFlow/
├── template.yaml              # AWS SAM template (all infra-as-code)
├── samconfig.toml             # SAM deploy profiles (dev/staging/prod)
├── requirements-dev.txt       # Test dependencies (pytest, moto)
├── src/
│   ├── requirements.txt       # Runtime deps (boto3 is pre-installed on Lambda)
│   ├── handlers/
│   │   ├── post_event.py      # POST /event
│   │   ├── get_stats.py       # GET /stats
│   │   ├── get_recent.py      # GET /events/recent
│   │   └── sqs_processor.py   # SQS batch consumer
│   ├── services/
│   │   ├── event_service.py   # Enqueue + process business logic
│   │   └── stats_service.py   # Stats aggregation logic
│   ├── db/
│   │   └── dynamodb.py        # All DynamoDB I/O (storage layer)
│   └── utils/
│       ├── logger.py          # Structured JSON logger
│       └── response.py        # API response helpers
├── tests/
│   ├── conftest.py            # Fixtures + env setup
│   ├── test_post_event.py
│   ├── test_sqs_processor.py
│   ├── test_stats_service.py
│   └── test_dynamodb.py       # Integration tests using moto
└── frontend/
    ├── package.json           # Vite + React + Recharts
    ├── vite.config.js
    ├── index.html
    ├── deploy.sh              # Build + S3 sync + CloudFront invalidation
    ├── .env.example           # Copy → .env.local with your API URL
    └── src/
        ├── main.jsx
        ├── App.jsx            # Root component + auto-refresh logic
        ├── api/
        │   └── client.js      # Typed fetch wrapper for all 3 endpoints
        ├── components/
        │   ├── StatsCards.jsx # Top-row summary cards
        │   ├── TypeChart.jsx  # Recharts bar chart (count + avg by type)
        │   ├── SendEventForm.jsx  # POST /event form with presets
        │   ├── RecentEvents.jsx   # Filterable events table
        │   └── Toast.jsx          # Toast notification system
        └── styles/
            └── index.css      # Dark theme design tokens + all layout
```

---

## Scalability

| Concern | Design decision |
|---|---|
| **Write throughput** | API Gateway → SQS decouples ingestion from processing. The API can absorb bursts that DynamoDB can't absorb directly. |
| **Processing throughput** | Lambda scales horizontally per SQS queue partition. `ReservedConcurrentExecutions = 10` caps concurrency to protect DynamoDB write capacity. Raise this as you provision more WCUs. |
| **Read scalability** | Stats queries hit pre-aggregated DynamoDB counters (O(1)). No `COUNT` scan on the events table. |
| **Type-filtered queries** | The `type-created_at-index` GSI enables efficient range queries without scanning the full events table. |
| **Cost at scale** | `PAY_PER_REQUEST` billing means no under-utilised provisioned capacity. Switch to provisioned + auto-scaling for predictable high-volume workloads. |
| **Batch processing** | Up to 10 SQS messages per Lambda invocation with a 10-second batching window reduces per-message Lambda overhead by 10×. |

---

## Fault Tolerance

| Failure scenario | Mitigation |
|---|---|
| **Lambda crash mid-batch** | SQS visibility timeout (360 s) hides the batch. On expiry, unacknowledged messages are re-delivered. `batchItemFailures` ensures only failed messages retry. |
| **DynamoDB write throttle** | SQS retries with backoff; DLQ catches messages after 3 failed attempts. CloudWatch alarm fires when DLQ is non-empty. |
| **Duplicate SQS delivery** | `attribute_not_exists(event_id)` conditional write in DynamoDB is the idempotency guard. Even if a message is delivered multiple times, only the first write succeeds. |
| **Partial batch failure** | `ReportBatchItemFailures` + `batchItemFailures` response means the healthy 9/10 messages are acknowledged; only the failed one retries. |
| **Persistent failures** | After `maxReceiveCount = 3` retries, SQS moves the message to the **Dead-Letter Queue** (14-day retention) for manual inspection and replay. |
| **Data loss** | DynamoDB has PITR (Point-In-Time Recovery) enabled on both tables and SSE at rest. |

---

## Deployment

### Prerequisites

```bash
# Install AWS SAM CLI
brew install aws-sam-cli   # macOS
# or: pip install aws-sam-cli

# Configure AWS credentials
aws configure
# or use AWS SSO / environment variables
```

### Build

```bash
sam build
```

### Deploy to dev

```bash
sam deploy
# Guided first-time setup (creates S3 bucket, etc.):
sam deploy --guided
```

### Deploy to staging / prod

```bash
# Staging
sam deploy --config-env staging

# Production
sam deploy --config-env prod
```

### Post-deploy: note the outputs

```
CloudFormation outputs:
  ApiUrl          = https://<id>.execute-api.us-east-1.amazonaws.com/dev
  PostEventUrl    = https://<id>.execute-api.us-east-1.amazonaws.com/dev/event
  GetStatsUrl     = https://<id>.execute-api.us-east-1.amazonaws.com/dev/stats
  GetRecentUrl    = https://<id>.execute-api.us-east-1.amazonaws.com/dev/events/recent
  EventQueueUrl   = https://sqs.us-east-1.amazonaws.com/...
  EventsTableName = eventflow-events-dev
  StatsTableName  = eventflow-stats-dev
```

### Smoke test

```bash
API=https://<your-api-id>.execute-api.us-east-1.amazonaws.com/dev

# Enqueue some events
curl -s -X POST $API/event \
  -H "Content-Type: application/json" \
  -d '{"type": "purchase", "value": 99.99}' | jq

curl -s -X POST $API/event \
  -H "Content-Type: application/json" \
  -d '{"type": "view", "value": 0}' | jq

# Wait ~10-15s for SQS → Lambda to process

# Check stats
curl -s $API/stats | jq

# Query recent events
curl -s "$API/events/recent?limit=5&type=purchase" | jq
```

### Teardown

```bash
# Delete stack (tables are Retain so data is not lost)
sam delete

# To also delete tables:
aws dynamodb delete-table --table-name eventflow-events-dev
aws dynamodb delete-table --table-name eventflow-stats-dev
```

---

## Frontend Dashboard

### Features

- **Stats cards** — total events, average value, total value, unique type count
- **Bar chart** — event counts and average value per type (Recharts)
- **Send Event form** — preset types or custom, fires a real `POST /event`
- **Recent events table** — filterable by type, click any row to expand raw JSON
- **Auto-refresh** — polls `/stats` and `/events/recent` every 5 seconds with a countdown indicator
- **Toast notifications** — success/error feedback on form submit and fetch errors
- **Dark theme** — fully responsive, works on mobile

### Local development

```bash
cd frontend

# Install dependencies
npm install

# Create a local env file
cp .env.example .env.local
# Edit .env.local and set VITE_API_URL to your deployed API Gateway URL

# Start dev server on http://localhost:3000
npm run dev
```

### Deploy to AWS (S3 + CloudFront)

The SAM template provisions the S3 bucket and CloudFront distribution automatically.
After `sam deploy`, run:

```bash
./frontend/deploy.sh dev       # or staging / prod
```

The script:
1. Reads the API URL and bucket name from CloudFormation outputs
2. Writes `frontend/.env.local` with `VITE_API_URL` set
3. Runs `npm run build`
4. Syncs `dist/` to S3 (HTML: no-cache, assets: immutable 1-year cache)
5. Creates a CloudFront invalidation so the new build is live immediately

The dashboard URL is in the CloudFormation output `FrontendUrl`.

---

## Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Configuration

All configuration is via environment variables (injected by SAM / CloudFormation):

| Variable | Description |
|---|---|
| `EVENTS_TABLE` | DynamoDB events table name |
| `STATS_TABLE` | DynamoDB stats table name |
| `EVENT_QUEUE_URL` | SQS queue URL |
| `LOG_LEVEL` | Python log level (default: `INFO`) |

Rate limits and environment-specific parameters are defined in `samconfig.toml`.

---

## IAM Least-Privilege Summary

| Function | Permissions |
|---|---|
| `PostEventFunction` | `sqs:SendMessage` on EventQueue only |
| `GetStatsFunction` | `dynamodb:GetItem`, `dynamodb:Scan` on StatsTable + EventsTable |
| `GetRecentFunction` | `dynamodb:GetItem`, `dynamodb:Query`, `dynamodb:Scan` on EventsTable |
| `SqsProcessorFunction` | `dynamodb:PutItem`, `dynamodb:UpdateItem` on both tables + `sqs:ReceiveMessage`, `sqs:DeleteMessage` on EventQueue |

No function has cross-service permissions it doesn't need.
