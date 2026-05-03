# Cost Analysis & Scalability Reasoning

## 1. Monthly Cost Breakdown (Current Production)

| Service | Tier / Config | Monthly Estimate | Free Tier Coverage |
|---------|--------------|-----------------|-------------------|
| Cloud Run (web) | 1Gi, 1 vCPU, min=0, max=10 | ~$0-5 | 2M requests/month free; scale-to-zero eliminates idle cost |
| Cloud SQL (PostgreSQL 14) | db-f1-micro, 10GB, ZONAL, daily backup | ~$7-9 | N/A (always-on instance) |
| Cloud Scheduler | 2 jobs (every 8h + daily 2AM) | $0 | 3 free jobs/month |
| Secret Manager | 6 secrets, low-frequency access | ~$0 | 6 active secret versions free |
| Cloud Natural Language API | annotateText (~2,250 calls/month) | ~$2-4 | 5,000 units/month free |
| BigQuery | <1GB storage, <1TB queries/month | $0 | 10GB storage + 1TB queries free |
| Artifact Registry | 3 Docker images, ~500MB total | ~$0.05 | 500MB free storage |
| Firebase Hosting | Static SPA, <10GB bandwidth | $0 | Generous free tier (10GB/month) |
| Firebase Auth | Google sign-in, <100 MAU | $0 | 50K MAU free |
| **Total** | | **~$9-18/month** | |

Cloud SQL is the dominant cost (~80% of total). Everything else fits within free tiers at current scale.

## 2. Cost-Conscious Design Decisions

Every architectural choice was evaluated for cost impact:

### Cloud Run: Scale-to-Zero (`min-instances=0`)
- **Cost impact**: Zero compute charges when idle (no traffic = no cost)
- **Trade-off**: Cold starts of ~2-3 seconds when first request arrives after idle period
- **Why acceptable**: News analysis is not latency-critical. Users can tolerate a brief initial load. For a student project budget, eliminating idle cost is more important than sub-second cold starts.

### Cloud SQL: db-f1-micro, ZONAL
- **Cost impact**: ~$7/month (smallest PostgreSQL tier available)
- **Alternatives rejected**:
  - *HA (REGIONAL)*: Doubles cost (~$14/month) for automatic failover. Not justified for a single-user student project.
  - *Serverless (Neon, Supabase)*: Would reduce cost but adds vendor lock-in beyond GCP. Cloud SQL keeps the stack on one platform.
  - *Firestore*: Free tier is generous, but the data model is inherently relational (articles, sources, entities, bookmarks). Shoehorning into a document DB would compromise the database module assessment.

### PITR Enabled (Point-in-Time Recovery)
- **Cost impact**: ~$0.15/month additional at current data volume (10GB disk on `db-f1-micro`). PITR retains write-ahead-log segments for the backup retention window so recovery can target a specific timestamp, not just the last nightly snapshot.
- **Why acceptable**: At this disk size the additional backup-storage charge is negligible relative to the ~$8/month base instance cost, and the recovery semantics it provides (down to a specific second within the retention window) are worth the rounding error.
- **Configuration:** [infra/main.tf:75-79](../infra/main.tf#L75-L79) — `point_in_time_recovery_enabled = true` under `backup_configuration`.

### BigQuery for Analytics (OLAP Separation)
- **Cost impact**: $0 at current scale (well within free tier)
- **Why not just PostgreSQL views?**: Separation of OLTP (PostgreSQL — handles API requests) and OLAP (BigQuery — handles aggregation queries) prevents analytics queries from degrading API performance as data grows. BigQuery's columnar storage is purpose-built for aggregation.

### Cloud Scheduler over Container Cron
- **Cost impact**: $0 (2 jobs, free tier covers 3)
- **Alternative**: Run cron inside the worker container
- **Why Scheduler wins**: A cron in a container dies when the container scales to zero. Cloud Scheduler is a managed service that survives restarts, provides retry policies, and is visible in GCP Console for observability.

### `annotateText` Combined API Call
- **Cost impact**: 1 API call instead of 3 per article (~66% cost reduction)
- **How**: Cloud NL's `annotateText` endpoint combines sentiment analysis, entity extraction, and content classification in a single request. The API is billed per call, not per feature within a call.
- **Monthly savings**: At 2,250 articles/month, this saves ~4,500 API calls.

### Staging Not Deployed
- **Cost impact**: Saves ~$7-9/month (avoids duplicate Cloud SQL)
- **Architecture readiness**: Terraform tfvars exist for both prod and staging. Activating staging requires one `terraform apply` command — the design supports it, the budget does not justify it.

## 3. Scalability Analysis

The architecture is designed for the current scale of a student project, but each component has a clear scaling path.

### Current Scale
- ~75 articles/day (25 per run x 3 runs)
- ~3 ingestion pipeline runs per day
- <10 active users
- <1GB database size

### Scaling Tiers

| Component | Current Config | Medium Scale (100x) | Large Scale (10,000x) |
|-----------|---------------|--------------------|-----------------------|
| **Cloud Run** | 0-1 instances, 1Gi | Auto-scales to max=10 (already configured) | Increase max-instances, set min=1 to avoid cold starts, further increase memory |
| **Cloud SQL** | db-f1-micro, 50 connections | Upgrade to db-n1-standard-1, add read replicas | Migrate to Cloud Spanner for horizontal scaling, or add PgBouncer for connection pooling |
| **BigQuery** | Append-only streaming | Partitioning + clustering already configured, handles petabytes natively | No changes needed — BigQuery auto-scales storage and compute |
| **Ingestion** | Synchronous worker, Cloud Scheduler | Add Pub/Sub queue for parallel crawl workers | Cloud Dataflow / Pub/Sub fan-out pipeline |
| **NL API** | Direct call per article | Batch API support, implement rate limiting | Self-hosted models (e.g., HuggingFace Transformers) to eliminate per-call costs |
| **Auth** | Firebase Auth, Google sign-in | Firebase scales to 50K MAU free | Identity Platform for enterprise features (MFA, SAML) |
| **Frontend** | Firebase Hosting (static SPA) | Firebase CDN handles traffic spikes globally | No changes needed — static hosting scales inherently |

### Key Insight: Cloud Run Auto-Scaling
Cloud Run is the natural scaling lever for this architecture:
- **Current**: min=0, max=10 instances
- Handles up to **800 concurrent requests** (10 instances x 80 concurrency)
- Scales automatically based on CPU utilization and request queue depth
- No code changes needed — just adjust `max-instances` flag in deploy.yml

## 4. Scaling Bottlenecks & Mitigation

| Bottleneck | Why It Matters | Mitigation Path |
|-----------|---------------|-----------------|
| **Cloud SQL (vertical only)** | PostgreSQL on Cloud SQL only scales vertically (bigger machine). Connection limits cap concurrent API handling. | Add read replicas for read-heavy analytics queries. For true horizontal scaling, migrate to Cloud Spanner or shard by source/region. |
| **Synchronous ingestion** | Articles are crawled sequentially in the worker. At 7,500 articles/day, sequential processing becomes a bottleneck. | Introduce Pub/Sub: publish article URLs to a topic, Cloud Run workers consume and crawl in parallel. |
| **No caching layer** | Every `/articles` request hits PostgreSQL directly. At 1,000+ users, this creates unnecessary DB load for frequently-accessed data. | Add Redis via Memorystore for hot data (article lists, sentiment aggregations). TTL-based cache invalidation on ingestion. |
| **NL API cost at scale** | At 10,000x scale (~750K articles/month), NL API costs ~$5,000/month. | Self-host sentiment models (BERT, DistilBERT) on Cloud Run or Vertex AI. Higher upfront effort, but eliminates per-call costs. |
| **No CDN for API** | API responses are served directly from Cloud Run without caching. | Add Cloud CDN in front of Cloud Run for cacheable endpoints (article lists, analytics aggregations). |

## 5. Cost Projection at Scale

| Scale | Cloud Run | Cloud SQL | NL API | BigQuery | Other | Total |
|-------|-----------|-----------|--------|----------|-------|-------|
| **Current** (~75 articles/day) | ~$0-5 | ~$8 | ~$3 | $0 | ~$0 | **~$11-16** |
| **Medium** (100x: 7,500/day) | ~$20-50 | ~$50 | ~$150 | $0 | ~$10 | **~$230-260** |
| **Large** (10,000x: 750K/day) | ~$200+ | ~$500+ | ~$5,000+ | ~$50 | ~$100 | **~$5,850+** |

### Cost Dominance Shift
At current scale, **Cloud SQL** dominates (~80% of cost).
At large scale, **NL API** becomes dominant (~85% of cost). The optimization path at scale is self-hosting ML models — a common pattern where managed APIs are great for prototyping but custom inference is necessary at production scale.

## 6. Budget Monitoring

GCP provides built-in budget controls:
- **Budget alerts**: Set in GCP Console > Billing > Budgets to alert at $15, $25, $50 thresholds
- **Billing export to BigQuery**: Enables cost analysis using the same analytics infrastructure
- **Per-service breakdown**: Cloud Console shows cost per service, making it easy to identify unexpected spikes

For this project, a $20/month budget alert would catch any unexpected cost increases while allowing normal operation.
