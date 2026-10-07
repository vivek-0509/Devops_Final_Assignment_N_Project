# Observability: Metrics, Logs, Traces

**Student:** Vivek Singh Solanki | **Roll number:** 24bcs10338
**Session:** 20 - Monitoring, Observability and GitOps
**Topic:** The three pillars of observability, why they matter, and how they apply to Kubernetes

## Observability vs monitoring

**Monitoring** is watching a set of known signals and alerting when they cross a threshold: "CPU above 90%", "disk 95% full", "HTTP 5xx rate above 1%". It answers questions we thought of in advance.

**Observability** is a property of a system: how well its internal state can be inferred from the data it emits (metrics, logs, traces). An observable system lets me ask questions I did not anticipate ("why are checkout requests from one region slow only on Tuesdays?") and answer them from the telemetry alone, without shipping new code.

| | Monitoring | Observability |
|---|---|---|
| Question type | Known-unknowns: "is X above Y?" | Unknown-unknowns: "why is this happening?" |
| Data | Mostly metrics and uptime checks | Metrics + logs + traces, correlated |
| Output | Dashboards, alerts | Exploration, root-cause analysis |
| Relationship | A subset of observability | Includes monitoring |

Monitoring tells me *that* something is wrong; observability helps me find out *why*.

## The three pillars

### 1. Metrics

**What:** numeric measurements sampled over time (a time series), stored as `name{labels} value @timestamp`. They are cheap to store, easy to aggregate and ideal for dashboards and alerting.

Metric types (Prometheus naming):

| Type | Meaning | Example |
|---|---|---|
| Counter | Only goes up (reset on restart) | `http_requests_total{method="GET",code="200"}` |
| Gauge | Goes up and down | `container_memory_working_set_bytes`, `node_cpu_seconds_total` rate |
| Histogram | Buckets of observations, lets you compute percentiles | `http_request_duration_seconds_bucket{le="0.5"}` |
| Summary | Client-side quantiles | `rpc_duration_seconds{quantile="0.95"}` |

Typical examples: CPU and memory per Pod, request rate, error rate, latency p50/p95/p99, queue depth, DB connections in use. The "RED" method (Rate, Errors, Duration) for services and "USE" (Utilisation, Saturation, Errors) for resources are good starting checklists.

**Tools:** Prometheus (pull-based scraping + PromQL), Grafana (dashboards), Amazon CloudWatch, Datadog, New Relic, VictoriaMetrics, Thanos / Mimir for long-term storage.

### 2. Logs

**What:** timestamped, discrete events emitted by an application or system: "user 42 logged in", "connection to db timed out after 5s". Logs carry the detail that metrics aggregate away.

Structured JSON logging makes them searchable and lets the pipeline index fields instead of regex-parsing text:

```json
{"ts":"2026-10-07T09:14:22Z","level":"error","service":"checkout","trace_id":"4bf92f3577b34da6a3ce929d0e0e4736",
 "msg":"payment gateway timeout","order_id":"A-1029","duration_ms":5003}
```

Good practice: log to stdout/stderr (containers), include `level`, `service`, `trace_id`, and avoid logging secrets or PII.

**Tools:** Grafana Loki (label-indexed, cheap), ELK stack (Elasticsearch + Logstash + Kibana), EFK (Elasticsearch + Fluentd + Kibana), Fluent Bit (lightweight collector, usually a DaemonSet), Amazon CloudWatch Logs, Splunk, OpenSearch.

### 3. Traces

**What:** the path of a single request as it crosses service boundaries. A **trace** is a tree of **spans**; each span records one operation (an HTTP call, a DB query) with start time, duration, attributes and the parent span. All spans share one **trace id**, which is propagated in HTTP headers (`traceparent` in the W3C Trace Context standard).

```
trace 4bf92f35...  total 820 ms
|-- api-gateway  POST /checkout            820 ms
    |-- checkout-svc  createOrder          790 ms
        |-- inventory-svc  GET /stock       40 ms
        |-- payment-svc    POST /charge    720 ms   <-- the slow one
            |-- external gateway HTTP     700 ms
        |-- postgres  INSERT orders        12 ms
```

Traces answer "which hop made this request slow?" in a way that per-service metrics cannot.

**Tools:** Jaeger, Grafana Tempo, Zipkin, AWS X-Ray, Datadog APM; **OpenTelemetry (OTel)** is the vendor-neutral SDK/collector standard for producing and shipping all three signals.

## Why observability is required

- **Microservices.** One user request may touch 10-50 services; a failure in any of them appears as a vague error at the edge. Correlated telemetry is the only practical way to follow the request.
- **Unknown-unknowns.** Static dashboards cover the failures we expected. Production regularly produces ones we did not, and we need to explore rather than guess.
- **MTTR (Mean Time To Recovery).** Faster diagnosis directly lowers downtime. Observability shortens the "where is the problem?" phase, which is usually the longest part of an incident.
- **Reliability targets.** Observability provides the data for SLIs, SLOs and SLAs:

| Term | Meaning | Example |
|---|---|---|
| SLI (indicator) | A measured value of service health | % of requests served under 300 ms, availability % |
| SLO (objective) | Internal target for an SLI | 99.9% of requests under 300 ms over 30 days |
| SLA (agreement) | Contractual promise with consequences | 99.5% monthly availability or customer gets credit |

An **error budget** (100% minus SLO) tells the team how much unreliability they can spend on releases; burning it too fast triggers a slowdown.

## Common tools

| Pillar | Open source | Managed / commercial | Collector / agent |
|---|---|---|---|
| Metrics | Prometheus, Grafana, VictoriaMetrics, Thanos, Mimir | CloudWatch, Datadog, New Relic, Grafana Cloud | node-exporter, kube-state-metrics, OTel Collector |
| Logs | Loki, Elasticsearch/OpenSearch, Kibana | CloudWatch Logs, Splunk, Datadog Logs | Fluent Bit, Fluentd, Promtail/Alloy, Vector |
| Traces | Jaeger, Tempo, Zipkin | AWS X-Ray, Datadog APM, Honeycomb | OpenTelemetry SDK + Collector |
| Alerting | Alertmanager, Grafana Alerting | PagerDuty, Opsgenie, CloudWatch Alarms | - |

## Kubernetes observability

| Component | What it provides |
|---|---|
| **metrics-server** | Short-lived CPU/memory for Pods and Nodes; powers `kubectl top` and the Horizontal Pod Autoscaler. Not for long-term storage. |
| **kube-state-metrics** | Metrics about Kubernetes objects: Deployment replicas desired vs available, Pod phase, restarts, PVC status |
| **node-exporter** | Host-level metrics from each node: CPU, memory, disk, network, filesystem |
| **cAdvisor** | Per-container resource usage; built into the kubelet and scraped at `/metrics/cadvisor` |
| **Prometheus Operator / kube-prometheus-stack** | Helm chart that installs Prometheus, Alertmanager, Grafana, the exporters above, and CRDs so scrape targets and alerts are managed as Kubernetes objects |
| **ServiceMonitor / PodMonitor** | CRDs telling the operator which Services/Pods to scrape and on which port/path |
| **PrometheusRule** | CRD holding recording and alerting rules |
| **Alertmanager** | Groups, deduplicates, silences and routes alerts to Slack, email, PagerDuty |
| **Liveness / readiness / startup probes** | Feed Pod health into `kube_pod_container_status_ready` and restart counts, which Prometheus alerts on |

Installation on minikube for practice:

```bash
minikube addons enable metrics-server
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kps prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
kubectl port-forward -n monitoring svc/kps-grafana 3000:80          # admin / prom-operator
kubectl port-forward -n monitoring svc/kps-kube-prometheus-stack-prometheus 9090:9090
```

Everyday commands:

```bash
kubectl top nodes
kubectl top pods -A --sort-by=memory
kubectl logs deploy/checkout -f --since=10m
kubectl logs checkout-7d9f6-abcde -c app --previous        # logs of the crashed container
kubectl get events -A --sort-by=.lastTimestamp
kubectl describe pod checkout-7d9f6-abcde                   # probe failures show under Events
kubectl get servicemonitors,prometheusrules -n monitoring
```

Example ServiceMonitor so Prometheus scrapes an app exposing `/metrics`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: checkout
  namespace: monitoring
  labels:
    release: kps                 # must match the operator's serviceMonitorSelector
spec:
  namespaceSelector:
    matchNames: ["shop"]
  selector:
    matchLabels:
      app: checkout
  endpoints:
    - port: http                 # named port on the Service
      path: /metrics
      interval: 30s
```

### Example PromQL queries

```promql
# CPU usage in cores, per pod, averaged over 5 minutes (namespace "shop")
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="shop", container!=""}[5m]))

# CPU as a percentage of the pod's CPU limit
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="shop", container!=""}[5m]))
  / sum by (pod) (kube_pod_container_resource_limits{namespace="shop", resource="cpu"}) * 100

# Memory working set in MiB, per pod
sum by (pod) (container_memory_working_set_bytes{namespace="shop", container!=""}) / 1024 / 1024

# Memory as a percentage of the limit
sum by (pod) (container_memory_working_set_bytes{namespace="shop", container!=""})
  / sum by (pod) (kube_pod_container_resource_limits{namespace="shop", resource="memory"}) * 100

# Request rate and 5xx error ratio for a service
sum(rate(http_requests_total{job="checkout"}[5m]))
sum(rate(http_requests_total{job="checkout", code=~"5.."}[5m])) / sum(rate(http_requests_total{job="checkout"}[5m]))

# p95 latency from a histogram
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{job="checkout"}[5m])))

# Pods restarting (crash loops) in the last hour
increase(kube_pod_container_status_restarts_total[1h]) > 3
```

### Example alert rule (high CPU)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: pod-resource-alerts
  namespace: monitoring
  labels:
    release: kps
spec:
  groups:
    - name: pod-resources
      rules:
        - alert: PodHighCPU
          expr: |
            sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{container!=""}[5m]))
              / sum by (namespace, pod) (kube_pod_container_resource_limits{resource="cpu"}) > 0.85
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} CPU above 85% of limit"
            description: "CPU usage has been above 85% of the limit for 10 minutes (current: {{ $value | humanizePercentage }})."
        - alert: PodCrashLooping
          expr: increase(kube_pod_container_status_restarts_total[15m]) > 3
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} is crash looping"
```

Alertmanager then routes `severity: critical` to the on-call channel and `warning` to a Slack room.

## Correlating the three pillars

The real value appears when the signals link to each other. A typical incident flow:

```
  1. METRIC fires an alert
     PodHighCPU / p95 latency > 1s on checkout-svc   (Prometheus -> Alertmanager -> Slack)
                 |
                 v  "what was happening at 09:14?"  (same time window, same pod label)
  2. LOGS for that pod and window
     {"level":"error","msg":"payment gateway timeout","trace_id":"4bf92f35..."}   (Loki / Kibana)
                 |
                 v  "follow this one request"  (click the trace_id)
  3. TRACE 4bf92f35...
     api-gateway 820ms -> checkout-svc 790ms -> payment-svc 720ms -> external gateway 700ms
                 |
                 v
  Root cause: the third-party payment gateway is slow; checkout retries pile up and burn CPU.
  Fix: add a timeout + circuit breaker, raise an alert on payment-svc external latency.
```

Grafana supports this flow natively: a metric panel links to Loki with the same labels, and Loki's `trace_id` field links to Tempo. OpenTelemetry makes it possible by stamping the same `trace_id` into logs, spans and exemplars on metrics.

## Key takeaways

1. Monitoring answers known questions; observability lets me answer new ones from the data the system already emits.
2. Metrics are for trends and alerts, logs for detail, traces for the path across services.
3. Structured logs with a `trace_id` are what make correlation possible.
4. On Kubernetes the standard stack is metrics-server (for `kubectl top` and HPA) plus kube-prometheus-stack (Prometheus, Alertmanager, Grafana, exporters) and a log collector such as Fluent Bit or Loki.
5. Alerts should be based on symptoms users feel (latency, errors, saturation), tied to SLOs, and point to a runbook.

## References

- Prometheus documentation: https://prometheus.io/docs/introduction/overview/
- PromQL basics: https://prometheus.io/docs/prometheus/latest/querying/basics/
- Alerting rules: https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- kube-prometheus-stack chart: https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack
- Prometheus Operator CRDs (ServiceMonitor, PrometheusRule): https://prometheus-operator.dev/docs/
- Kubernetes metrics pipeline: https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/
- Kubernetes logging architecture: https://kubernetes.io/docs/concepts/cluster-administration/logging/
- OpenTelemetry: https://opentelemetry.io/docs/
- Grafana Loki: https://grafana.com/docs/loki/latest/
- Grafana Tempo: https://grafana.com/docs/tempo/latest/
- Jaeger: https://www.jaegertracing.io/docs/
- Google SRE Book, "Monitoring Distributed Systems": https://sre.google/sre-book/monitoring-distributed-systems/
