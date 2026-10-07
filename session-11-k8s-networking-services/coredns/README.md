# CoreDNS in Kubernetes

**Session 11 - Kubernetes Networking & Services**
**Author:** Vivek Singh Solanki (Roll No: 24bcs10338)

CoreDNS is the component that turns a Service name into an IP inside the cluster. This document covers what it is, how it is wired into Kubernetes, how to read and change its configuration, and how to debug it when name resolution breaks.

---

## What is CoreDNS?

CoreDNS is a **plugin-based DNS server written in Go**. Every feature (serving Kubernetes records, forwarding to upstream resolvers, caching, metrics, logging) is a plugin, and the server is built by chaining plugins together in a config file called the **Corefile**.

Key facts:

- Started in 2016 as a fork of the Caddy web server, rewritten as a DNS server.
- Accepted into the CNCF in 2017 and **graduated** in January 2019 (same tier as Kubernetes, Prometheus and Envoy).
- Became the **default cluster DNS in Kubernetes 1.13** (December 2018), replacing kube-dns. `kubeadm` has deployed CoreDNS by default since 1.11.
- Runs as a normal Deployment in the `kube-system` namespace, exposed by a Service that is still named `kube-dns` for backward compatibility.
- Ships as a single static binary, which makes the container image small and easy to run.

```bash
kubectl get deploy,svc -n kube-system -l k8s-app=kube-dns
# NAME                      READY   UP-TO-DATE   AVAILABLE
# deployment.apps/coredns   2/2     2            2
#
# NAME               TYPE        CLUSTER-IP   PORT(S)
# service/kube-dns   ClusterIP   10.96.0.10   53/UDP,53/TCP,9153/TCP
```

---

## Why Kubernetes uses CoreDNS

Before 1.13 the cluster DNS was **kube-dns**, a Pod made of three containers: `kubedns` (watched the API and served records), `dnsmasq` (caching layer) and `sidecar` (health checks). It worked, but it had drawbacks:

| Concern | kube-dns | CoreDNS |
|---|---|---|
| Process model | 3 containers, 3 code bases (Go + dnsmasq in C) | 1 container, 1 Go binary |
| Configuration | Fragmented: ConfigMap for stub domains, dnsmasq flags, etc. | One readable Corefile |
| Extensibility | Hard; had to modify dnsmasq or kubedns | Add a plugin line to the Corefile |
| Security surface | dnsmasq had several CVEs | Smaller, memory-safe binary |
| Metrics | Limited | Native Prometheus `/metrics` endpoint |
| Behaviour | Fixed | Composable: rewrite, hosts, autopath, stub zones, etc. |
| Negative caching, EDNS, DNSSEC | Partial | Supported |

In short: fewer moving parts, one config file, and the ability to add behaviour with a single line. CoreDNS is also used outside Kubernetes (as a general-purpose authoritative or forwarding DNS server), so the skills transfer.

---

## How Service discovery works

```
kubectl apply -f svc.yaml
        |
        v
  kube-apiserver  (stores Service object in etcd)
        |
        |  watch stream (Services, EndpointSlices, Namespaces)
        v
  CoreDNS pod  --> kubernetes plugin keeps an in-memory index
        |
        |  on query "backend.default.svc.cluster.local"
        v
  Answer built from the index:
     ClusterIP Service  -> A/AAAA record with the ClusterIP
     Headless Service   -> A/AAAA record per ready Pod IP
     Named port         -> SRV record _<port>._<proto>.<svc>.<ns>.svc.cluster.local
     ExternalName       -> CNAME to the external hostname
     Pod (if enabled)   -> <ip-dashed>.<ns>.pod.cluster.local
```

Step by step:

1. A Service is created or updated through the API server.
2. The CoreDNS `kubernetes` plugin maintains a **watch** on Services, EndpointSlices and Namespaces (it needs RBAC for this; the `coredns` ClusterRole grants `list` and `watch`). It does not poll and it does not query etcd directly.
3. When a query arrives for a name under `cluster.local`, the plugin answers from its in-memory cache of API objects. No network round trip is required, which is why cluster lookups are fast.
4. For a regular ClusterIP Service the answer is the **virtual IP**. For a **headless** Service (`clusterIP: None`) the answer is the list of Pod IPs taken from the EndpointSlice, limited to Pods that are Ready (unless `publishNotReadyAddresses: true` is set).
5. The response TTL is 30 seconds by default (`ttl` option in the `kubernetes` block).

Because the plugin only serves names in the zones it is configured for (`cluster.local` and the reverse zones), any other name falls through to the next plugin in the chain, which is `forward`.

---

## How DNS queries are resolved

Full path of a lookup from an application Pod:

```
 Application Pod
 +------------------------------------------------------+
 | app: getaddrinfo("backend")                          |
 | libc reads /etc/resolv.conf:                         |
 |   nameserver 10.96.0.10                              |
 |   search default.svc.cluster.local svc.cluster.local |
 |          cluster.local                               |
 |   options ndots:5                                    |
 | -> sends query backend.default.svc.cluster.local     |
 +---------------------------+--------------------------+
                             | UDP/TCP 53 to 10.96.0.10 (kube-dns ClusterIP)
                             v
                    kube-proxy DNAT to one CoreDNS Pod IP
                             |
                             v
 CoreDNS Pod  (plugin chain, in Corefile order)
 +------------------------------------------------------+
 |  errors -> health -> ready -> kubernetes -> ...      |
 |                                                      |
 |  name ends in cluster.local ?                        |
 |     YES -> kubernetes plugin answers from API cache  |
 |     NO  -> cache plugin checks cache                 |
 |              miss -> forward plugin sends query to   |
 |                      upstream (/etc/resolv.conf of   |
 |                      the node, e.g. 8.8.8.8)         |
 |              hit  -> return cached answer            |
 +---------------------------+--------------------------+
                             |
                             v
                    Answer returned to Pod
```

Two important distinctions:

- **Cluster-internal names** (`*.cluster.local`, plus `in-addr.arpa` / `ip6.arpa` reverse zones) are handled entirely by the `kubernetes` plugin.
- **External names** (`google.com`, `registry-1.docker.io`) are passed to the `forward` plugin, which sends them to the upstream resolvers listed in the CoreDNS Pod's own `/etc/resolv.conf` (inherited from the node, because the CoreDNS Deployment uses `dnsPolicy: Default`).

The `cache` plugin sits in front of `forward` so repeated external lookups do not leave the cluster every time. It also caches negative answers (NXDOMAIN), which matters because `ndots:5` produces several failing lookups for every external name.

---

## CoreDNS configuration

The entire configuration lives in a ConfigMap called `coredns` in `kube-system`. The `Corefile` key is mounted into the Pod at `/etc/coredns/Corefile`.

```bash
kubectl -n kube-system get configmap coredns -o yaml
```

### Default Corefile (kubeadm, Kubernetes 1.30+)

```
.:53 {
    errors
    health {
       lameduck 5s
    }
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
       pods insecure
       fallthrough in-addr.arpa ip6.arpa
       ttl 30
    }
    prometheus :9153
    forward . /etc/resolv.conf {
       max_concurrent 1000
    }
    cache 30 {
       disable success cluster.local
       disable denial cluster.local
    }
    loop
    reload
    loadbalance
}
```

`.:53` is the **server block**: listen on port 53 for the root zone `.`, meaning every query. Everything inside the braces is a plugin, and they are executed in a fixed order defined at compile time (not the order written in the file, although convention is to write them in that order).

### Plugin by plugin

| Plugin | What it does |
|---|---|
| `errors` | Logs any error that occurs during query processing to stdout. Without it, failures are silent. |
| `health` | Exposes `http://:8080/health`. Used by the Pod's **liveness** probe. `lameduck 5s` keeps the process alive for 5 seconds after a shutdown signal so in-flight queries finish. |
| `ready` | Exposes `http://:8181/ready`, returning 200 only once every plugin that reports readiness (mainly `kubernetes`, after its initial API sync) is ready. Used by the **readiness** probe so a cold CoreDNS Pod does not receive traffic before it has loaded Services. |
| `kubernetes` | The core of cluster DNS. Serves the zones `cluster.local`, `in-addr.arpa`, `ip6.arpa` from the API watch. `pods insecure` enables `<ip-dashed>.<ns>.pod.cluster.local` records without verifying the Pod exists (kept for kube-dns compatibility; `pods verified` is stricter). `fallthrough in-addr.arpa ip6.arpa` lets reverse lookups for non-cluster IPs continue to `forward`. `ttl 30` sets the record TTL. |
| `prometheus` | Exposes metrics at `:9153/metrics` (query counts, latency, cache hits, forward errors). This is the third port on the `kube-dns` Service. |
| `forward` | Sends anything not answered by earlier plugins to upstream resolvers. `/etc/resolv.conf` means "use the nameservers of the node". `max_concurrent 1000` caps in-flight upstream queries to protect the upstream and CoreDNS memory. You can replace it with explicit IPs, e.g. `forward . 8.8.8.8 1.1.1.1`. |
| `cache` | Caches responses for up to 30 seconds (success and denial have separate TTL caps). The `disable success cluster.local` and `disable denial cluster.local` lines (added in 1.29+) stop CoreDNS from caching cluster-internal answers, so Service changes are visible immediately instead of after a stale cache entry expires. |
| `loop` | Sends a random probe query through the chain at startup. If it comes back, there is a forwarding loop (for example the node's resolv.conf points back at CoreDNS) and CoreDNS halts with a clear log message rather than spinning the CPU. |
| `reload` | Watches the Corefile for changes and reloads it (default check every 30s with a jitter). This is why editing the ConfigMap takes effect without restarting Pods, after a short delay. |
| `loadbalance` | Randomises the order of A/AAAA records in a response (round-robin). Useful for headless Services so clients do not all pick the first Pod. |

### Editing the configuration

```bash
kubectl -n kube-system edit configmap coredns
```

Save and exit. Because of the `reload` plugin the change is picked up in about 30 to 60 seconds. Watch the logs to confirm:

```bash
kubectl -n kube-system logs -l k8s-app=kube-dns -f
# [INFO] Reloading
# [INFO] plugin/reload: Running configuration SHA512 = ...
# [INFO] Reloading complete
```

If the new Corefile has a syntax error, CoreDNS logs the error and **keeps running the previous configuration**, so a typo does not take down cluster DNS. To force an immediate restart instead of waiting for reload:

```bash
kubectl -n kube-system rollout restart deployment coredns
```

### Adding a custom hosts entry

Useful for pointing an internal hostname at a fixed IP (lab environments, on-prem services without DNS). Insert the `hosts` plugin **before** `kubernetes` or `forward` in the server block:

```
.:53 {
    errors
    health { lameduck 5s }
    ready
    hosts {
       192.168.1.50 gitlab.internal
       192.168.1.51 registry.internal
       fallthrough
    }
    kubernetes cluster.local in-addr.arpa ip6.arpa {
       pods insecure
       fallthrough in-addr.arpa ip6.arpa
       ttl 30
    }
    prometheus :9153
    forward . /etc/resolv.conf { max_concurrent 1000 }
    cache 30
    loop
    reload
    loadbalance
}
```

`fallthrough` is essential: without it, any name not in the hosts list would get NXDOMAIN and never reach the other plugins.

### Adding a rewrite rule

The `rewrite` plugin changes the query before it is answered. A common use is to make a short alias resolve to a real Service:

```
    rewrite name db.example.com mysql.default.svc.cluster.local
```

Or to map an entire external-looking domain onto a namespace:

```
    rewrite name regex (.*)\.internal\.example\.com {1}.default.svc.cluster.local
```

### Forwarding a specific domain to a different resolver (stub domain)

Add a second server block for that zone:

```
corp.example.com:53 {
    errors
    cache 30
    forward . 10.10.0.5 10.10.0.6
}
```

### Adding records without touching the main Corefile

kubeadm clusters support an import hook. Any ConfigMap entry matched by `import custom/*.override` or `import custom/*.server` (when present in the Corefile) lets you drop extra plugin lines or extra server blocks without editing the main block. Check whether your Corefile contains those `import` lines before relying on it; managed clusters (EKS, GKE, AKS) each have their own convention.

---

## How to troubleshoot DNS issues

Work top-down: is CoreDNS running, is it reachable, is the Pod configured to use it, is the name correct?

### 1. Is CoreDNS healthy?

```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=100
kubectl describe pod -n kube-system -l k8s-app=kube-dns | grep -A5 Events
```

Look for `CrashLoopBackOff`, restarts, or `Loop detected` in the logs. Two Ready replicas is the normal state on kubeadm.

### 2. Is the Service and are its endpoints correct?

```bash
kubectl get svc kube-dns -n kube-system
kubectl get endpoints kube-dns -n kube-system
kubectl get endpointslices -n kube-system -l kubernetes.io/service-name=kube-dns
```

The endpoints must list the CoreDNS Pod IPs on ports 53/UDP and 53/TCP. If the list is empty, the Pods are not Ready (check the `ready` plugin and the API sync).

### 3. Can a Pod actually resolve names?

```bash
# Cluster name
kubectl run dns-test --image=busybox:1.36 --rm -it --restart=Never -- \
  nslookup kubernetes.default.svc.cluster.local

# External name (tests the forward plugin)
kubectl run dns-test --image=busybox:1.36 --rm -it --restart=Never -- \
  nslookup kubernetes.io

# Query CoreDNS directly, bypassing the Service VIP
kubectl run dns-test --image=busybox:1.36 --rm -it --restart=Never -- \
  nslookup kubernetes.default.svc.cluster.local <coredns-pod-ip>
```

If querying the Pod IP works but the Service IP does not, the problem is kube-proxy, not CoreDNS.

### 4. Check the Pod's resolver configuration

```bash
kubectl exec -it <pod-name> -- cat /etc/resolv.conf
kubectl get pod <pod-name> -o jsonpath='{.spec.dnsPolicy}{"\n"}'
```

The nameserver must be `10.96.0.10` (or whatever `kube-dns` has). If it shows the node's resolvers instead, the Pod has `dnsPolicy: Default` or is using `hostNetwork: true` without `ClusterFirstWithHostNet`.

### 5. Is a NetworkPolicy blocking port 53?

A default-deny egress policy silently kills DNS. Make sure every policy that restricts egress also allows UDP **and** TCP 53 to `kube-system`:

```yaml
egress:
  - to:
      - namespaceSelector:
          matchLabels:
            kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
      - protocol: UDP
        port: 53
      - protocol: TCP
        port: 53
```

```bash
kubectl get networkpolicy -A
```

### 6. Turn on query logging

Add the `log` plugin to the Corefile (temporarily; it is noisy):

```
.:53 {
    log
    errors
    ...
```

Then watch the logs and reproduce the failing lookup. Every query is printed with its name, type, response code and latency, which usually makes the problem obvious.

```bash
kubectl -n kube-system logs -l k8s-app=kube-dns -f | grep backend
# [INFO] 10.244.3.7:41532 - 12345 "A IN backend.default.svc.cluster.local. udp 51 false 512" NOERROR qr,aa,rd 100 0.000215s
```

### 7. Check metrics

```bash
kubectl -n kube-system port-forward svc/kube-dns 9153:9153
curl -s localhost:9153/metrics | grep -E 'coredns_dns_requests_total|coredns_forward_requests_total|coredns_dns_responses_total'
```

A high `SERVFAIL` count on `coredns_dns_responses_total` or growing `coredns_forward_healthcheck_failures_total` points at the upstream resolver.

### Common errors and what they mean

| Symptom | Meaning | Usual cause |
|---|---|---|
| `nslookup: can't resolve 'backend'` / `server can't find backend: NXDOMAIN` | The DNS server answered, but the name does not exist | Typo, wrong namespace (short name from another namespace), Service not created yet, or querying `pod.cluster.local` without `pods` enabled |
| `NXDOMAIN` for an external name | Upstream says the name does not exist | Search-domain expansion tried first (normal, resolver moves on); if the final bare query also fails, the upstream resolver is wrong or has no internet |
| `SERVFAIL` | CoreDNS could not produce an answer | Upstream unreachable or timing out, `forward` misconfigured, DNSSEC validation failure upstream, or `kubernetes` plugin not yet synced with the API server |
| `;; connection timed out; no servers could be reached` / `i/o timeout` | The query never got a response at all | NetworkPolicy blocking 53, CoreDNS Pods down, kube-proxy not programming the `kube-dns` VIP, CNI problem on that node, or wrong nameserver in resolv.conf |
| `REFUSED` | Server refused to answer that zone | Query sent to a server that is not authoritative and does not forward; usually a stub domain or `forward` block pointing at the wrong IP |
| `Loop (127.0.0.1:53 -> :53) detected` in CoreDNS logs | CoreDNS forwarded a query to itself | Node `/etc/resolv.conf` points at `127.0.0.53` (systemd-resolved). Fix by pointing kubelet `resolvConf` at `/run/systemd/resolve/resolv.conf` or setting explicit upstreams in `forward` |
| Resolution works but is slow (hundreds of ms) | Many failed search-domain lookups before the real one | `ndots:5` with external names; set `ndots:2` in Pod `dnsConfig`, use trailing dots, or enable the `autopath` plugin |
| Works from some nodes only | Node-local problem | kube-proxy or CNI broken on that node; compare `iptables -t nat -L KUBE-SERVICES \| grep 10.96.0.10` across nodes |
| Intermittent failures under load | CoreDNS overloaded | Scale the Deployment, increase CPU limits, or deploy NodeLocal DNSCache |

### Quick checklist

```
[ ] kubectl get pods -n kube-system -l k8s-app=kube-dns           -> 2/2 Running
[ ] kubectl logs -n kube-system -l k8s-app=kube-dns               -> no loop/error lines
[ ] kubectl get svc kube-dns -n kube-system                       -> ClusterIP 10.96.0.10
[ ] kubectl get endpoints kube-dns -n kube-system                 -> Pod IPs on 53/UDP+TCP
[ ] nslookup kubernetes.default.svc.cluster.local from busybox    -> answers
[ ] nslookup kubernetes.io from busybox                           -> answers (forward works)
[ ] cat /etc/resolv.conf in the failing Pod                       -> nameserver 10.96.0.10
[ ] kubectl get networkpolicy -A                                  -> nothing blocks 53
[ ] add `log` plugin, reproduce, read the logs
```

---

## References

- CoreDNS website and documentation: https://coredns.io/
- CoreDNS plugin reference: https://coredns.io/plugins/
- CoreDNS `kubernetes` plugin: https://coredns.io/plugins/kubernetes/
- CoreDNS `forward` plugin: https://coredns.io/plugins/forward/
- CoreDNS `rewrite` plugin: https://coredns.io/plugins/rewrite/
- CoreDNS `hosts` plugin: https://coredns.io/plugins/hosts/
- Kubernetes docs - Using CoreDNS for Service Discovery: https://kubernetes.io/docs/tasks/administer-cluster/coredns/
- Kubernetes docs - Customizing DNS Service: https://kubernetes.io/docs/tasks/administer-cluster/dns-custom-nameservers/
- Kubernetes docs - Debugging DNS Resolution: https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/
- Kubernetes docs - DNS for Services and Pods: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/
- Kubernetes docs - Using NodeLocal DNSCache: https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/
- CNCF - CoreDNS graduation announcement: https://www.cncf.io/announcements/2019/01/24/coredns-graduation/
