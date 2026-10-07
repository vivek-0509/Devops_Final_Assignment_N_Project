# Kubernetes Object Comparison

**Session 11 - Kubernetes Networking & Services**
**Author:** Vivek Singh Solanki (Roll No: 24bcs10338)

This document compares the Kubernetes workload and networking objects that I kept mixing up while working through the labs: Deployment, ReplicaSet, DaemonSet, StatefulSet and Service. The goal is to be able to answer "which object do I reach for, and why?" without thinking twice.

---

## Part A: Deployment vs ReplicaSet

### Purpose

| Aspect | ReplicaSet | Deployment |
|---|---|---|
| Core job | Guarantee that a given number of identical Pods are running at all times | Provide declarative updates (rollouts, rollbacks, pause/resume) on top of ReplicaSets |
| Owns | Pods | ReplicaSets (which in turn own Pods) |
| Rolling updates | No. Changing the Pod template does **not** replace existing Pods | Yes. A template change triggers a new ReplicaSet and a controlled rollout |
| Rollback | Not supported | `kubectl rollout undo` |
| Revision history | None | Keeps old ReplicaSets (`revisionHistoryLimit`, default 10) |
| Scaling | `kubectl scale rs <name> --replicas=N` | `kubectl scale deploy <name> --replicas=N` (propagates to the active RS) |
| Typical use | Almost never created directly | The standard way to run stateless workloads |
| API group | `apps/v1` | `apps/v1` |

### Pod management

A ReplicaSet uses a **label selector** to find the Pods it owns. Its control loop is simple:

1. Count Pods matching `.spec.selector` that have an `ownerReference` pointing at this ReplicaSet.
2. If the count is lower than `.spec.replicas`, create Pods from `.spec.template`.
3. If the count is higher, delete the extras.

It only cares about *how many* Pods exist, not *which version* of the template they were created from. That is exactly the gap a Deployment fills.

### Scaling

Both objects can be scaled, but the Deployment is the one you should scale. When you run `kubectl scale deployment web --replicas=5`, the Deployment controller updates `.spec.replicas` on the current ReplicaSet. If you scale the ReplicaSet directly, the Deployment controller will notice the drift and reset it on the next reconcile, which is a confusing thing to debug.

Horizontal Pod Autoscalers also target the Deployment, not the ReplicaSet.

### Rolling updates

When the Pod template of a Deployment changes (new image tag, new env var, new resource limits), the Deployment controller:

1. Computes a hash of the new Pod template (`pod-template-hash` label).
2. Creates a **new ReplicaSet** with that hash in its name.
3. Scales the new RS up and the old RS down in steps controlled by `maxSurge` and `maxUnavailable`.
4. Keeps the old RS around at 0 replicas so a rollback is just "scale the old RS back up".

```bash
kubectl set image deployment/web nginx=nginx:1.27
kubectl rollout status deployment/web
kubectl rollout history deployment/web
kubectl rollout undo deployment/web --to-revision=1
```

### Relationship between Deployment and ReplicaSet

```
Deployment (web)
  |
  |-- ReplicaSet web-5d7c9f8b4   (old template hash, replicas: 0)
  |
  +-- ReplicaSet web-7f6b4d9c2   (current template hash, replicas: 3)
        |
        |-- Pod web-7f6b4d9c2-abcde
        |-- Pod web-7f6b4d9c2-fghij
        +-- Pod web-7f6b4d9c2-klmno
```

The ReplicaSet name is `<deployment-name>-<pod-template-hash>` and each Pod name is `<replicaset-name>-<random-suffix>`. You can verify ownership with:

```bash
kubectl get rs -l app=web
kubectl get pod web-7f6b4d9c2-abcde -o jsonpath='{.metadata.ownerReferences[0].name}'
```

### YAML: ReplicaSet (for reference only)

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: web-rs
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - name: nginx
          image: nginx:1.27
          ports:
            - containerPort: 80
```

### YAML: Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - name: nginx
          image: nginx:1.27
          ports:
            - containerPort: 80
```

The two specs are nearly identical. The only real difference is `kind` and the `strategy` block. That is the point: a Deployment is a ReplicaSet plus update management.

> **Rule of thumb:** you normally never create a ReplicaSet directly. Create a Deployment and let it manage ReplicaSets for you. The only time you see ReplicaSets is when inspecting rollouts (`kubectl get rs`) or debugging why a rollout is stuck.

---

## Part B: Deployment vs DaemonSet vs StatefulSet

### Use cases

| Aspect | Deployment | DaemonSet | StatefulSet |
|---|---|---|---|
| Best for | Stateless apps: web servers, APIs, workers | One Pod per node: log agents, monitoring exporters, CNI/CSI plugins | Stateful apps that need stable identity and storage: databases, message brokers, coordination services |
| Pod creation | N interchangeable replicas scheduled anywhere | Exactly one Pod on every (matching) node; new nodes get a Pod automatically | Pods created **in order** (`-0`, `-1`, `-2`), each waits for the previous to be Ready |
| Pod names | Random suffix (`web-7f6b4d9c2-abcde`) | `<name>-<random>` (`fluentd-x8k2p`) | Ordinal, predictable (`mysql-0`, `mysql-1`) |
| Scaling | `replicas` field, any number | Follows node count; `replicas` is not a field | `replicas` field; scaled up/down in ordinal order (highest ordinal removed first) |
| Networking | Pods reached via a normal ClusterIP Service; no per-Pod identity | Usually accessed on the node itself (hostPort / hostNetwork) or via a Service | Stable per-Pod DNS via a **headless Service**: `mysql-0.mysql.default.svc.cluster.local` |
| Storage | Shared volumes or none; PVCs must be created separately | Typically hostPath volumes to read node-level data | `volumeClaimTemplates` create one PVC per Pod; PVC survives Pod restarts and reschedules |
| Rolling update | RollingUpdate / Recreate | RollingUpdate / OnDelete | RollingUpdate (ordered, reverse ordinal) / OnDelete, supports `partition` for canaries |
| Examples | nginx, Node.js API, Spring Boot service | fluentd, Fluent Bit, node-exporter, kube-proxy, Calico node agent | MySQL, PostgreSQL, Kafka, Zookeeper, Elasticsearch, Redis Cluster |

### Pod creation details

- **Deployment**: the scheduler places replicas wherever resources allow. Two replicas can end up on the same node unless you add anti-affinity or topology spread constraints.
- **DaemonSet**: the DaemonSet controller (not the default scheduler logic for replicas) ensures one Pod per node. You can restrict nodes with `nodeSelector` or `affinity`, and tolerations let it run on control-plane or tainted nodes.
- **StatefulSet**: Pods are created sequentially with `podManagementPolicy: OrderedReady` (default). `Parallel` is available if ordering does not matter for your app.

### Networking: stable identity for StatefulSets

A StatefulSet requires a headless Service (`clusterIP: None`) referenced by `.spec.serviceName`. CoreDNS then publishes an A record for every Pod:

```
<pod-name>.<service-name>.<namespace>.svc.cluster.local
mysql-0.mysql.default.svc.cluster.local  -> 10.244.1.15
mysql-1.mysql.default.svc.cluster.local  -> 10.244.2.9
```

Even if `mysql-0` is rescheduled to a different node and gets a new IP, its DNS name stays the same. This is what lets a replica point at `mysql-0` as the primary, or lets Kafka brokers advertise a stable address to each other.

### Storage: volumeClaimTemplates

With a Deployment, every replica mounting the same PVC would share one disk (and most storage classes only support `ReadWriteOnce` anyway). A StatefulSet instead stamps out one PVC per Pod from a template:

```
PVC data-mysql-0  <-> Pod mysql-0
PVC data-mysql-1  <-> Pod mysql-1
```

Deleting the StatefulSet does **not** delete the PVCs by default (`persistentVolumeClaimRetentionPolicy` controls this since 1.27 / stable in 1.32). This is deliberate: you do not want a `kubectl delete` to wipe a database.

### YAML: DaemonSet (node-exporter style)

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: node-exporter
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      hostNetwork: true
      hostPID: true
      tolerations:
        - key: node-role.kubernetes.io/control-plane
          operator: Exists
          effect: NoSchedule
      containers:
        - name: node-exporter
          image: prom/node-exporter:v1.8.2
          ports:
            - containerPort: 9100
              name: metrics
          volumeMounts:
            - name: proc
              mountPath: /host/proc
              readOnly: true
      volumes:
        - name: proc
          hostPath:
            path: /proc
```

### YAML: StatefulSet with headless Service (MySQL style)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mysql
spec:
  clusterIP: None          # headless: DNS returns Pod IPs, not a VIP
  selector:
    app: mysql
  ports:
    - port: 3306
      name: mysql
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
spec:
  serviceName: mysql       # must match the headless Service above
  replicas: 3
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
        - name: mysql
          image: mysql:8.4
          ports:
            - containerPort: 3306
              name: mysql
          volumeMounts:
            - name: data
              mountPath: /var/lib/mysql
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
```

### Quick decision guide

- Does every node need exactly one copy? -> **DaemonSet**
- Does each replica need its own disk and a fixed name? -> **StatefulSet**
- Everything else (which is most things) -> **Deployment**

---

## Part C: ReplicaSet vs Service

These two objects are often confused because both use a label selector, but they solve completely different problems.

### Responsibilities

| | ReplicaSet | Service |
|---|---|---|
| Layer | Workload (compute) | Networking |
| Responsibility | Keep N Pods running that match the selector | Give a group of Pods one stable virtual IP, a DNS name, and load balance traffic across them |
| Creates Pods? | Yes | No, never |
| Uses selector for | Deciding which Pods it owns (and will recreate) | Deciding which Pod IPs go into the Endpoints / EndpointSlice |
| Has an IP? | No | Yes (ClusterIP), unless headless |
| API group | `apps/v1` | `v1` (core) |

### Why a Service is required

Pod IPs are **ephemeral**. Every time a Pod is recreated (crash, rollout, node drain, scale event) it gets a brand-new IP from the CNI plugin. If the frontend hard-coded `10.244.1.15` for the backend, it would break on the very next rollout.

A Service gives the backend a fixed `ClusterIP` (for example `10.96.45.12`) and a DNS name (`backend.default.svc.cluster.local`) that never change for the lifetime of the Service, regardless of how many times the Pods behind it are replaced.

A ReplicaSet alone cannot solve this because it does not know or care about networking. A Service alone cannot solve it either because it does not create Pods. You need both.

### How traffic reaches Pods

```
  Client Pod
     |
     |  DNS: backend.default.svc.cluster.local -> 10.96.45.12 (ClusterIP)
     v
  Service "backend"  (ClusterIP 10.96.45.12:80, selector app=backend)
     |
     |  Endpoint controller / EndpointSlice controller
     |  watches Pods with label app=backend that are Ready
     v
  EndpointSlice "backend-xxxxx"
     [10.244.1.15:8080, 10.244.2.9:8080, 10.244.3.4:8080]
     |
     |  kube-proxy on every node watches Services + EndpointSlices
     |  and programs iptables (or IPVS / nftables) DNAT rules
     v
  iptables rule:  dst 10.96.45.12:80  --> pick one of
                     10.244.1.15:8080 | 10.244.2.9:8080 | 10.244.3.4:8080
     |
     v
  Backend Pod (10.244.2.9:8080)   <- managed by ReplicaSet backend-7f6b4d9c2
```

Step by step:

1. The client resolves the Service name through CoreDNS and gets the ClusterIP.
2. The packet leaves the client Pod with `dst = ClusterIP`. The ClusterIP is purely virtual; no interface in the cluster actually has that address.
3. On the node, kube-proxy's iptables/IPVS rules intercept the packet and DNAT it to one of the Pod IPs listed in the EndpointSlice (round-robin for IPVS, random probability chains for iptables).
4. The packet is routed by the CNI to the chosen Pod.
5. Only Pods that pass their readiness probe are included in the EndpointSlice, so a crashing Pod stops receiving traffic even before the ReplicaSet replaces it.

Note: in Kubernetes 1.30+ the `nftables` proxy mode is available (beta in 1.31, GA in 1.33) as a faster alternative to iptables, but the concept is identical.

### Minimal YAML for a Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
spec:
  type: ClusterIP
  selector:
    app: backend
  ports:
    - name: http
      port: 80          # port exposed on the ClusterIP
      targetPort: 8080  # port on the Pod
      protocol: TCP
```

### Useful kubectl commands

```bash
# What does the Service resolve to, and what backs it?
kubectl get svc backend
kubectl describe svc backend          # shows Selector, IP, Port, Endpoints

# Legacy Endpoints object (still populated for compatibility)
kubectl get endpoints backend
kubectl get endpoints backend -o yaml

# EndpointSlices are the modern source of truth (default since 1.21)
kubectl get endpointslices -l kubernetes.io/service-name=backend
kubectl describe endpointslice <name>

# Check that the ReplicaSet and Service selectors actually agree
kubectl get rs -l app=backend -o wide
kubectl get pods -l app=backend -o wide --show-labels

# Inspect kube-proxy rules on a node (iptables mode)
sudo iptables -t nat -L KUBE-SERVICES -n | grep backend
sudo iptables -t nat -L KUBE-SVC-<hash> -n
# IPVS mode
sudo ipvsadm -Ln

# Test from inside the cluster
kubectl run curl --rm -it --image=curlimages/curl:8.10.1 -- \
  curl -s http://backend.default.svc.cluster.local/
```

If `kubectl describe svc backend` shows `Endpoints: <none>`, the usual causes are:

- The Service selector does not match the Pod labels (check with `--show-labels`).
- The Pods are not Ready (readiness probe failing).
- The Pods are in a different namespace than the Service.

---

## Summary

| Object | One-line definition |
|---|---|
| ReplicaSet | Keeps N identical Pods alive. Do not create by hand. |
| Deployment | ReplicaSet + rolling updates + rollback. Default for stateless apps. |
| DaemonSet | One Pod per node. Agents and exporters. |
| StatefulSet | Ordered Pods with stable names, stable DNS and their own PVCs. Databases and brokers. |
| Service | Stable IP + DNS + load balancing in front of a set of Pods. |

## References

- Kubernetes docs - Deployments: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- Kubernetes docs - ReplicaSet: https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/
- Kubernetes docs - DaemonSet: https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/
- Kubernetes docs - StatefulSets: https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/
- Kubernetes docs - Service: https://kubernetes.io/docs/concepts/services-networking/service/
- Kubernetes docs - EndpointSlices: https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/
- Kubernetes docs - Virtual IPs and Service Proxies: https://kubernetes.io/docs/reference/networking/virtual-ips/
