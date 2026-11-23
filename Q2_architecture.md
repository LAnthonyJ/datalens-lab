# DataLens AI deployment architecture

This course design targets **100,000 concurrent connections**. The inference budget below allows roughly 100 completed requests per second, with excess requests queued. All capacities and costs are planning estimates.

## 1. Architecture overview

```mermaid
graph TB
    subgraph "Ingress"
        DNS[DNS / CDN]
        LB[Load balancer: Nginx/Kong]
    end

    subgraph "Application"
        API[API Gateway]
        WS[WebSocket service]
        AUTH[OAuth/JWT authentication]
    end

    subgraph "Core services"
        QUERY[Query parser]
        SQLGEN[SQL generator]
        ANALYZE[Analytics engine]
        REPORT[Reporting]
    end

    subgraph "LLM inference"
        vLLM[vLLM cluster]
        MODEL[Qwen3.5-0.8B Fine-tuned]
        RATE[Rate limiter]
    end

    subgraph "Data processing"
        ETL[ETL preprocessing]
        EMBED[Vector embeddings]
        SEARCH[RAG retrieval]
    end

    subgraph "Storage"
        PG[(PostgreSQL metadata)]
        CH[(ClickHouse analytics)]
        REDIS[(Redis cache cluster)]
        OSS[(Object storage for logs and files)]
    end

    subgraph "Messaging and streaming"
        KAFKA[Kafka message queue]
        FLINK[Flink stream processing]
    end

    subgraph "Observability"
        PROM[Prometheus metrics]
        GRAF[Grafana dashboards]
        ELK[ELK log analytics]
        ALERT[Alertmanager notifications]
    end

    DNS --> LB
    LB --> API
    API --> AUTH
    API --> QUERY
    QUERY --> SQLGEN --> vLLM
    QUERY --> ANALYZE
    ANALYZE --> REPORT
    vLLM --> MODEL
    vLLM --> RATE
    RATE --> REDIS
    API --> SEARCH --> EMBED
    ETL --> CH
    SQLGEN --> PG
    ANALYZE --> PG
    ANALYZE --> CH
    QUERY --> KAFKA
    KAFKA --> FLINK --> CH
    API -.-> REDIS
    REPORT -.-> OSS
    ALL -.-> PROM --> GRAF
    ALL -.-> ELK
    PROM --> ALERT
```

## 2. Service design

### Inference

Run the fine-tuned Qwen3.5-0.8B model with vLLM v0.6+ using PagedAttention and continuous batching. The design assumes about 2 GB of model memory per instance, eight NVIDIA A10 or L20 GPUs per node with 24–48 GB per GPU, optional 4-bit AWQ, and at least ten replicas managed by Kubernetes HPA.

At 5,000 output tokens per GPU-second and 500 tokens per request, each GPU serves about 10 requests per second. Ten replicas serve about 100 requests per second. The proposal assumes a 10–20× throughput improvement with batching, prefix KV-cache sharing across turns, priority for paying customers through a Redis sorted set, and a 5–30 minute cache for common queries such as monthly sales.

```mermaid
graph LR
    REQ[Inference request] --> QUEUE[Redis priority queue]
    QUEUE --> SCHED[vLLM scheduler]
    SCHED --> GPU0[GPU 0: Replica 1]
    SCHED --> GPU1[GPU 1: Replica 2]
    SCHED --> GPU2[GPU N: Replica N]
    GPU0 --> CACHE[Redis result cache]
```

### Load balancing and API gateway

Alibaba Cloud DNS or Cloudflare directs global traffic. A CDN serves static files. Nginx or HAProxy distributes TCP connections at layer 4. Kong or APISIX handles authentication, routing, rate limits, logging and plugins. Consul or Kubernetes Services provide discovery and health checks.

The Nginx estimate uses four workers with 65,535 worker connections each. Stateless gateways scale horizontally. Kubernetes can adjust pod counts based on CPU, memory and QPS.

```mermaid
graph TB
    USER[User request] --> DNS[Global DNS]
    DNS --> CDN[Static assets on CDN]
    DNS --> LB[Nginx L4 load balancer]
    LB --> GW1[Kong API Gateway-1]
    LB --> GW2[Kong API Gateway-2]
    GW1 --> SVC[Consul service registry]
    SVC --> NODE1[Service nodes]
```

### Data processing

Connectors discover schemas and sample enterprise databases. PostgreSQL holds metadata. Milvus stores embeddings for retrieval. The context builder combines schema and retrieved examples for inference. In a private deployment, processing stays inside the corporate network. The design includes rule-based PII masking and an audit trail of SQL executions.

```mermaid
graph TB
    DB[Enterprise database] --> CONN[Database connector]
    CONN --> ETL[ETL Pipeline]
    ETL --> SCHEMA[Schema discovery]
    ETL --> SAMPLE[Data sampling]
    SCHEMA --> META[PostgreSQL metadata]
    SAMPLE --> VEC[Vector embeddings]
    VEC --> MILVUS[(Milvus vector database)]
    MILVUS --> RAG[RAG retrieval]
    META --> CTX[Context assembly]
    RAG --> CTX
    CTX --> LLM[LLM inference]
```

### Storage

| Service | Purpose | Proposed capacity |
| --- | --- | --- |
| PostgreSQL 14+ | Users, tenants, subscriptions and configuration | Primary and replica, 500 GB SSD |
| ClickHouse | Query logs, aggregates and user behavior | Cluster, 2 TB SSD |
| Redis 7 Cluster | Sessions, rate counters and cached results | Three primaries and three replicas, 64 GB |
| Milvus | Schema vector index | Single node, 128 GB |
| MinIO or S3 | Reports, archived logs and model backups | Expandable object storage |

### Background jobs

Kafka buffers sudden traffic increases and separates incoming requests from slow queries, report generation and log collection. Workers notify Redis when jobs finish. WebSocket connections deliver progress and results to clients.

```mermaid
graph LR
    USER[User request] --> API
    API --> KAFKA[Kafka Topic: queries]
    KAFKA --> WORKER1[SQL generation worker]
    KAFKA --> WORKER2[Report worker]
    KAFKA --> WORKER3[Log collection worker]
    WORKER1 --> REDIS[Result notification]
    WORKER2 --> REDIS
    REDIS --> WS[WebSocket delivery]
```

### Tenant isolation and billing

Each tenant receives a database schema and a Redis namespace. Tenants share the GPU pool. Usage metering counts tokens and API calls.

```mermaid
graph TB
    subgraph "Tenant isolation"
        T1[Tenant A: retail]
        T2[Tenant B: finance]
        T3[Tenant C: manufacturing]
    end

    subgraph "Shared services"
        LLM[Shared inference cluster]
        INFRA[Shared infrastructure]
    end

    subgraph "Isolated resources"
        DB1[(Database A)]
        DB2[(Database B)]
        DB3[(Database C)]
        CACHE1[(Cache namespace A)]
        CACHE2[(Cache namespace B)]
        CACHE3[(Cache namespace C)]
    end

    T1 --> DB1
    T2 --> DB2
    T3 --> DB3
    T1 --> LLM
    T2 --> LLM
    T3 --> LLM
```

### Monitoring and operations

```mermaid
graph TB
    subgraph "Log collection"
        APP[Application logs] --> FLUENT[Fluentd Agent]
        SYS[System logs] --> FLUENT
        K8S[Kubernetes logs] --> FLUENT
        FLUENT --> ES[(Elasticsearch)]
    end

    subgraph "Metrics"
        NODE[Node metrics] --> PROM[Prometheus]
        POD[Pod metrics] --> PROM
        LLM_M[LLM latency and throughput] --> PROM
    end

    subgraph "Visualization and alerts"
        ES --> KIBANA[Kibana log search]
        PROM --> GRAF[Grafana dashboards]
        PROM --> ALERT[AlertManager]
        ALERT --> WECHAT[WeCom notification]
        ALERT --> MAIL[Email notification]
    end
```

| Metric | Proposed action |
| --- | --- |
| P50/P99 inference latency | Alert when P99 exceeds 5 seconds |
| Token throughput | Alert below 50% of baseline |
| API QPS | Scale above 70% of capacity |
| HTTP 5xx rate | Alert above 1% |
| Database connections and slow queries | Alert above 80% connection utilization |
| GPU utilization | Alert below 30% or above 95% |
| Memory or disk usage | Alert above 85% |
| Daily active users | Alert on a 30% decline |

## 3. Capacity planning

| Layer | Per node | Cluster in the proposal | Theoretical capacity listed in the design |
| --- | --- | --- | --- |
| Nginx L4 | 100K connections | Two nodes, active/standby | 200K combined node capacity |
| Kong | 10K QPS | Five nodes | 50K QPS |
| Redis | 100K operations/s | Six nodes | 600K operations/s |
| Kafka | 100K messages/s | Three brokers | 300K messages/s |
| vLLM | 10 requests/s per GPU | Ten GPUs | 100 requests/s plus buffering |

Requests pass through Nginx and Kong to autoscaled backend services and a Kafka buffer. When demand exceeds inference capacity, scale on queue depth, show waiting times to lower-priority users, and use a circuit breaker to return a status message if a downstream service fails.

## 4. Deployment and recovery

The proposed production cluster separates GPU, CPU and storage pools. GitLab builds and tests images, then Helm deploys rolling updates. The design places the primary cluster in Beijing, the recovery cluster in Shanghai, and full backups in object storage.

```mermaid
graph TB
    subgraph "Production Kubernetes cluster"
        subgraph "GPU Node Pool"
            GPU1[GPU Node × 4]
            GPU2[vLLM Deployments × 10]
        end
        subgraph "CPU Node Pool"
            CPU1[CPU Node × 6]
            CPU2[API / Worker / Gateway]
        end
        subgraph "Storage Node Pool"
            STORE1[Storage Node × 3]
            STORE2[PG / Redis / Kafka]
        end
    end

    subgraph "CI/CD Pipeline"
        GIT[GitLab] --> BUILD[Build Image]
        BUILD --> TEST[Auto Test]
        TEST --> DEPLOY[Helm Deploy]
        DEPLOY --> K8S[K8s Rolling Update]
    end

    subgraph "Disaster recovery and backups"
        MAIN[Primary cluster in Beijing]
        DR[Recovery cluster in Shanghai]
        MAIN -.->|Data replication| DR
        BACKUP[Scheduled full backups to object storage]
    end
```

## 5. Monthly cloud budget

| Resource | Configuration | Estimated monthly cost |
| --- | --- | ---: |
| GPU nodes | Four nodes, eight A10 GPUs each | RMB 32,000 |
| CPU nodes | Six nodes, 32 cores and 64 GB each | RMB 12,000 |
| Storage nodes | Three nodes, 2 TB SSD each | RMB 6,000 |
| Object storage | 10 TB | RMB 2,000 |
| Network | 100 Mbps BGP | RMB 3,000 |
| Kubernetes, monitoring and backups | Other costs | RMB 5,000 |
| Total | | RMB 60,000 |

The proposal estimates monthly infrastructure costs of RMB 12,000 per 1,000 monthly active users.

The original document was drafted with Claude (Anthropic). Its prompts requested an architecture for 100,000 concurrent connections, Mermaid diagrams, capacity and cost estimates, and a design for tenant isolation and billing.
