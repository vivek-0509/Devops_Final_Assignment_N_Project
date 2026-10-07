# FQDN and Kubernetes Service DNS

**Session 11 - Kubernetes Networking & Services**
**Author:** Vivek Singh Solanki (Roll No: 24bcs10338)

This document covers what a Fully Qualified Domain Name is, how Kubernetes builds DNS names for Services and Pods, and why a short name like `backend` works in one namespace but not in another.

---

## What is an FQDN?

A **Fully Qualified Domain Name (FQDN)** is the complete, unambiguous name of a host in the DNS hierarchy. It spells out every label from the host all the way up to the root of the DNS tree.

```
www.example.com.
 |    |      |  |
 |    |      |  +-- root (the trailing dot)
 |    |      +----- top-level domain (TLD)
 |    +------------ domain
 +----------------- hostname
```

- **Hostname**: the leftmost label (`www`).
- **Domain**: everything to the right (`example.com`).
- **Trailing dot**: technically an FQDN ends with a `.` which represents the DNS root zone. `www.example.com.` is the true FQDN; `www.example.com` is what we type day to day and resolvers treat it the same once they decide it is "fully qualified enough".

The opposite of an FQDN is a **relative** or **short** name such as `www` or `backend`. A relative name only works if the resolver appends a search domain to it. That distinction is the whole story of Kubernetes DNS.

| Term | Example | Resolvable on its own? |
|---|---|---|
| FQDN (absolute) | `backend.default.svc.cluster.local.` | Yes, always |
| FQDN without trailing dot | `backend.default.svc.cluster.local` | Yes (resolver treats as absolute because of ndots) |
| Partially qualified | `backend.default` | Only with search domains |
| Short name | `backend` | Only with search domains |

---

## Kubernetes Service DNS

Every Kubernetes cluster runs a DNS server (CoreDNS by default) as a Deployment in `kube-system`, exposed through the `kube-dns` Service, usually at ClusterIP `10.96.0.10`. The kubelet configures every Pod to use that IP as its nameserver.

When you create a Service, CoreDNS automatically publishes a DNS record for it. No extra configuration is needed. This is what makes service discovery in Kubernetes "just work": a Pod can reach another Service by name instead of by IP.

```bash
kubectl get svc -n kube-system kube-dns
# NAME       TYPE        CLUSTER-IP   PORT(S)                  AGE
# kube-dns   ClusterIP   10.96.0.10   53/UDP,53/TCP,9153/TCP   12d
```

The cluster domain is `cluster.local` by default. It is set by the `clusterDomain` field in the kubelet config and the `kubernetes` block of the CoreDNS Corefile. Almost nobody changes it.

---

## Kubernetes DNS naming convention

### Services (normal ClusterIP)

```
<service-name>.<namespace>.svc.<cluster-domain>
backend.default.svc.cluster.local      -> A record -> ClusterIP (e.g. 10.96.45.12)
```

### Services (headless, `clusterIP: None`)

Same name pattern, but the A record returns **all Pod IPs** instead of a single virtual IP:

```
mysql.default.svc.cluster.local        -> 10.244.1.15, 10.244.2.9, 10.244.3.4
```

### Individual Pods behind a headless Service (StatefulSet)

```
<pod-name>.<service-name>.<namespace>.svc.<cluster-domain>
mysql-0.mysql.default.svc.cluster.local  -> 10.244.1.15
```

This works because the StatefulSet sets `hostname` and `subdomain` on each Pod. It is the mechanism that gives StatefulSet Pods a stable network identity.

### Pods by IP

```
<pod-ip-with-dashes>.<namespace>.pod.<cluster-domain>
10-244-1-15.default.pod.cluster.local    -> 10.244.1.15
```

Rarely used directly, but you will see these names in reverse lookups and some service meshes.

### SRV records (named ports)

For every named port on a Service, CoreDNS also publishes an SRV record so a client can discover the port number as well as the address:

```
_<port-name>._<protocol>.<service-name>.<namespace>.svc.<cluster-domain>
_http._tcp.backend.default.svc.cluster.local  -> 0 100 80 backend.default.svc.cluster.local.
```

The answer contains priority, weight, port and the target name. For headless Services the SRV record points at each individual Pod.

### Summary of the hierarchy

```
cluster.local
  |
  +-- svc.cluster.local
  |     +-- default.svc.cluster.local
  |     |     +-- backend.default.svc.cluster.local         (Service)
  |     |     +-- mysql.default.svc.cluster.local           (headless Service)
  |     |     |     +-- mysql-0.mysql.default.svc.cluster.local  (StatefulSet Pod)
  |     |     +-- _http._tcp.backend.default.svc.cluster.local   (SRV)
  |     +-- kube-system.svc.cluster.local
  |           +-- kube-dns.kube-system.svc.cluster.local
  |
  +-- pod.cluster.local
        +-- default.pod.cluster.local
              +-- 10-244-1-15.default.pod.cluster.local       (Pod by IP)
```

---

## Namespace-based DNS

Namespaces are baked into the DNS name, which is how two teams can both have a Service called `api` without clashing.

| From a Pod in namespace | Target | What to type | Works? |
|---|---|---|---|
| `default` | `backend` in `default` | `backend` | Yes |
| `default` | `backend` in `default` | `backend.default` | Yes |
| `default` | `backend` in `default` | `backend.default.svc.cluster.local` | Yes |
| `payments` | `backend` in `default` | `backend` | **No** (resolves to `backend.payments.svc.cluster.local`, NXDOMAIN) |
| `payments` | `backend` in `default` | `backend.default` | Yes |
| `payments` | `backend` in `default` | `backend.default.svc.cluster.local` | Yes |

Rule: **a short name only works within the same namespace**. For cross-namespace calls, use at least `<service>.<namespace>`. In config files and Helm values I prefer the full FQDN so the behaviour does not change if the chart is deployed somewhere else.

### How `/etc/resolv.conf` makes short names work

The kubelet writes this into every Pod (with `dnsPolicy: ClusterFirst`, the default):

```
nameserver 10.96.0.10
search default.svc.cluster.local svc.cluster.local cluster.local
options ndots:5
```

Three things matter here:

1. **nameserver**: every query goes to the `kube-dns` ClusterIP, which is CoreDNS.
2. **search**: if a name is not considered absolute, the resolver appends each search domain in turn and tries again. The first entry is always the Pod's own namespace, which is why `backend` resolves to `backend.default.svc.cluster.local` from `default` but to `backend.payments.svc.cluster.local` from `payments`.
3. **ndots:5**: a name with fewer than 5 dots is treated as relative and goes through the search list *first*. A name with 5 or more dots (or a trailing dot) is tried as absolute first.

Resolution of `backend` from a Pod in `default`:

```
1. backend.default.svc.cluster.local   -> hit, return 10.96.45.12
```

Resolution of `backend.default` from a Pod in `payments`:

```
1. backend.default.payments.svc.cluster.local  -> NXDOMAIN
2. backend.default.svc.cluster.local           -> hit, return 10.96.45.12
```

Resolution of an external name like `api.github.com` (2 dots, fewer than 5):

```
1. api.github.com.default.svc.cluster.local  -> NXDOMAIN
2. api.github.com.svc.cluster.local          -> NXDOMAIN
3. api.github.com.cluster.local              -> NXDOMAIN
4. api.github.com                            -> forwarded upstream, hit
```

That last example is why `ndots:5` is sometimes criticised: external lookups generate several wasted queries. CoreDNS caches the NXDOMAIN answers (negative caching) so the cost is small, and you can set `ndots:1` per Pod through `dnsConfig` if a workload makes a lot of external calls. Using the trailing dot (`api.github.com.`) also skips the search list entirely.

---

## Pod-to-Service communication walkthrough

Scenario: a `frontend` Pod in namespace `default` calls `http://backend/api/orders`.

```
 frontend Pod (10.244.3.7)                  CoreDNS (kube-system)         backend Pods
 ==========================                 =====================         ============

 1. app calls http://backend/api/orders
 2. libc resolver reads /etc/resolv.conf
    "backend" has 0 dots < ndots:5
    -> try backend.default.svc.cluster.local
                      |
                      |  UDP 53 to 10.96.0.10
                      v
 3.                                          kubernetes plugin looks up
                                             Service backend in ns default
                                             A 10.96.45.12  (TTL 30)
                      |
                      v
 4. resolver returns 10.96.45.12
 5. TCP SYN to 10.96.45.12:80
    kube-proxy iptables/IPVS rule on node:
    DNAT 10.96.45.12:80 -> 10.244.1.15:8080
                                                                      |
                                                                      v
 6.                                                            backend-7f6b-abcde
                                                               (10.244.1.15:8080)
 7. response flows back, conntrack reverses the DNAT
```

Key observations:

- DNS resolves to the **ClusterIP**, never to a Pod IP (unless the Service is headless).
- The ClusterIP is virtual. Nothing listens on it; kube-proxy rules rewrite the destination on the fly.
- The frontend never learns which backend Pod answered. That is the point: Pods can come and go and the name stays valid.

---

## Examples of Kubernetes FQDNs

| FQDN | Type | Resolves to |
|---|---|---|
| `kubernetes.default.svc.cluster.local` | ClusterIP Service | API server ClusterIP (`10.96.0.1`) |
| `kube-dns.kube-system.svc.cluster.local` | ClusterIP Service | CoreDNS ClusterIP (`10.96.0.10`) |
| `backend.default.svc.cluster.local` | ClusterIP Service | `10.96.45.12` |
| `backend.payments.svc.cluster.local` | ClusterIP Service in another namespace | `10.96.72.3` |
| `mysql.default.svc.cluster.local` | Headless Service | All Pod IPs: `10.244.1.15`, `10.244.2.9`, `10.244.3.4` |
| `mysql-0.mysql.default.svc.cluster.local` | StatefulSet Pod via headless Service | `10.244.1.15` |
| `kafka-2.kafka.streaming.svc.cluster.local` | StatefulSet Pod in `streaming` namespace | `10.244.5.21` |
| `10-244-1-15.default.pod.cluster.local` | Pod by IP | `10.244.1.15` |
| `_http._tcp.backend.default.svc.cluster.local` | SRV record | `0 100 80 backend.default.svc.cluster.local.` |
| `_mysql._tcp.mysql.default.svc.cluster.local` | SRV record (headless) | One entry per Pod, port 3306 |
| `my-db.default.svc.cluster.local` | ExternalName Service | CNAME to `db.example.com` |

---

## Test commands

### One-off DNS lookup from a temporary Pod

```bash
kubectl run dns-test --image=busybox:1.36 --rm -it --restart=Never -- \
  nslookup backend.default.svc.cluster.local
```

Expected output:

```
Server:    10.96.0.10
Address:   10.96.0.10:53

Name:      backend.default.svc.cluster.local
Address:   10.96.45.12
```

### Short name vs cross-namespace

```bash
# From default namespace: works
kubectl run dns-test --image=busybox:1.36 --rm -it --restart=Never -- nslookup backend

# From payments namespace: short name fails, qualified name works
kubectl run dns-test -n payments --image=busybox:1.36 --rm -it --restart=Never -- nslookup backend
kubectl run dns-test -n payments --image=busybox:1.36 --rm -it --restart=Never -- nslookup backend.default
```

### Inspect resolv.conf inside a running Pod

```bash
kubectl exec -it <pod-name> -- cat /etc/resolv.conf
# nameserver 10.96.0.10
# search default.svc.cluster.local svc.cluster.local cluster.local
# options ndots:5
```

### Headless Service and StatefulSet Pod records

```bash
kubectl run dns-test --image=busybox:1.36 --rm -it --restart=Never -- nslookup mysql
kubectl run dns-test --image=busybox:1.36 --rm -it --restart=Never -- nslookup mysql-0.mysql
```

### SRV lookup (busybox nslookup does not support SRV, use dig from a richer image)

```bash
kubectl run dns-test --image=nicolaka/netshoot --rm -it --restart=Never -- \
  dig SRV _http._tcp.backend.default.svc.cluster.local +short
```

### Check the Pod's DNS policy

```bash
kubectl get pod <pod-name> -o jsonpath='{.spec.dnsPolicy}{"\n"}'
# ClusterFirst            (default)
# ClusterFirstWithHostNet (needed when hostNetwork: true)
# Default                 (inherits node resolv.conf, cluster names will NOT resolve)
# None                    (fully custom via dnsConfig)
```

---

## Key takeaways

- An FQDN is the full path from host to root. In Kubernetes that path is `<svc>.<ns>.svc.cluster.local`.
- Short names work only because of the `search` list in `/etc/resolv.conf`, and the first search domain is the Pod's own namespace.
- Cross-namespace calls need `<svc>.<ns>` at minimum.
- Headless Services and StatefulSets add per-Pod records, which is how databases get stable addresses.
- When DNS "does not work", the first thing to check is `cat /etc/resolv.conf` inside the Pod.

## References

- Kubernetes docs - DNS for Services and Pods: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/
- Kubernetes docs - Service: https://kubernetes.io/docs/concepts/services-networking/service/
- Kubernetes docs - Headless Services: https://kubernetes.io/docs/concepts/services-networking/service/#headless-services
- Kubernetes docs - StatefulSet stable network ID: https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#stable-network-id
- Kubernetes docs - Customizing DNS Service: https://kubernetes.io/docs/tasks/administer-cluster/dns-custom-nameservers/
- Kubernetes docs - Debugging DNS Resolution: https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/
- RFC 1034 - Domain Names, Concepts and Facilities: https://www.rfc-editor.org/rfc/rfc1034
