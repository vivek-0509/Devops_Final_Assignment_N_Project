# Ingress vs Ingress Controller

**Student:** Vivek Singh Solanki | **Roll number:** 24bcs10338
**Session:** 12 - Kubernetes Ingress, ConfigMaps and Secrets
**Topic:** Difference between the Ingress resource and the Ingress Controller, and why both are needed

When I first created an Ingress object on minikube, nothing happened: `kubectl get ingress` showed an empty ADDRESS column and curl timed out. The reason is that an Ingress is only a set of rules; something has to read those rules and actually forward traffic. That "something" is the Ingress Controller. This document separates the two concepts.

## What is Ingress?

`Ingress` is a Kubernetes **API object** (`networking.k8s.io/v1`). It describes how external HTTP/HTTPS traffic should reach Services inside the cluster:

- **Host-based routing** - `api.example.com` goes to one Service, `shop.example.com` to another.
- **Path-based routing** - `/api` goes to the backend Service, `/` to the frontend.
- **TLS termination** - reference a Secret containing a certificate and key so HTTPS ends at the edge.
- **Default backend** - where to send requests that match no rule.

An Ingress is purely declarative. Creating one stores a document in etcd and nothing else. By itself it opens no ports, allocates no IP and proxies no traffic. Kubernetes core has no built-in component that implements Ingress rules.

Compared with the alternatives:

| Approach | Layer | Exposes | Cost / limitation |
|---|---|---|---|
| `Service` type `NodePort` | L4 | One port per Service on every node | High ports (30000-32767), no hostnames or paths |
| `Service` type `LoadBalancer` | L4 | One cloud load balancer per Service | One LB (and bill) per Service |
| `Ingress` | L7 (HTTP) | Many Services behind a single entry point | Needs an Ingress Controller |
| Gateway API | L4/L7 | Role-oriented successor to Ingress | Newer; needs a Gateway controller |

## What is an Ingress Controller?

An Ingress Controller is **running software**, usually deployed as a Deployment or DaemonSet in the cluster, that:

1. Watches the API server for `Ingress`, `Service`, `Endpoints`/`EndpointSlice` and `Secret` objects.
2. Translates the rules into its own configuration (for NGINX: an `nginx.conf`; for the AWS controller: ALB listeners and target groups).
3. Runs the actual reverse proxy / load balancer that accepts client connections and forwards them to Pods.
4. Writes the external IP or hostname back into the Ingress `status.loadBalancer`, which is what the ADDRESS column shows.

Common controllers:

| Controller | Proxy technology | Notes |
|---|---|---|
| NGINX Ingress Controller (`ingress-nginx`) | NGINX | Kubernetes community project; the one minikube's addon installs |
| NGINX Inc. Ingress Controller | NGINX / NGINX Plus | Commercial variant from F5, different annotations |
| Traefik | Traefik | Default in k3s; dynamic config, dashboard, also supports its own CRDs |
| HAProxy Ingress | HAProxy | High-performance TCP/HTTP proxy |
| AWS Load Balancer Controller | AWS ALB | Creates a real ALB per Ingress (or shared via `group.name`); Pods become targets directly |
| Contour | Envoy | CNCF project; also provides `HTTPProxy` CRD |
| Istio / Kong / GKE Ingress | Envoy / Kong / Google LB | Service-mesh or cloud-specific implementations |

The controller is not part of a default `kubeadm`, kind or minikube cluster. It has to be installed, which is why `minikube addons enable ingress` exists.

## Difference between them

| Aspect | Ingress | Ingress Controller |
|---|---|---|
| What it is | Kubernetes API object (YAML in etcd) | Running Pods (reverse proxy + control loop) |
| Kind | `kind: Ingress` | `kind: Deployment` / `DaemonSet` plus a `Service` and RBAC |
| Who creates it | Application developer, per app or namespace | Cluster administrator, once per cluster (or one per class) |
| What it does | Declares routing rules: hosts, paths, TLS, backend Services | Reads those rules and forwards real traffic to Pods |
| Namespaced? | Yes | Usually lives in its own namespace (`ingress-nginx`, `traefik`, `kube-system`) |
| Has an IP? | No; the ADDRESS comes from the controller | Yes, via its `LoadBalancer`/`NodePort` Service or host network |
| Examples | `my-app-ingress`, `shop-ingress` | ingress-nginx, Traefik, HAProxy, AWS LB Controller, Contour |
| Removing it | Routes for that app stop working | Every Ingress in the cluster stops working |

## Why both are required

An analogy that helped me: an Ingress is a **recipe**, the Ingress Controller is the **chef**. A recipe sitting in a drawer never produces a meal; a chef without a recipe does not know what to cook. The recipe (Ingress) can be written by anyone on the team, while the chef (controller) is hired once and executes every recipe handed over.

Concretely:

- Without a controller: `kubectl get ingress` shows the object but the ADDRESS column stays empty forever, nothing listens on port 80/443, and traffic never flows. There is no error, because an unimplemented Ingress is not considered invalid.
- Without an Ingress: the controller runs, its default backend answers `404 Not Found` for everything, but it has no rules telling it where to send `/api` or `shop.example.com`.

This split is deliberate. Kubernetes defines the interface (the Ingress spec) and lets the ecosystem supply implementations, so the same manifest can run on minikube with NGINX and on EKS with an ALB.

### ingressClassName

A cluster can run more than one controller (for example an internal NGINX and a public ALB). The `IngressClass` object names a controller, and each Ingress picks one with `spec.ingressClassName`. A controller only acts on Ingresses whose class points at it.

```bash
kubectl get ingressclass
# NAME    CONTROLLER             PARAMETERS   AGE
# nginx   k8s.io/ingress-nginx   <none>       5m
```

If an Ingress has no `ingressClassName`, only the IngressClass annotated `ingressclass.kubernetes.io/is-default-class: "true"` will pick it up. If there is no default class, the Ingress is silently ignored, which is another cause of a missing ADDRESS. The old annotation `kubernetes.io/ingress.class` is deprecated in favour of the field.

## Traffic flow

```
            Internet / laptop
                   |
                   |  http://demo.local/api/users
                   v
   +------------------------------------------+
   | Ingress Controller Service               |  type LoadBalancer (cloud) or NodePort /
   | (ingress-nginx-controller, port 80/443)  |  hostPort (minikube, k3s)
   +------------------------------------------+
                   |
                   v
   +------------------------------------------+
   | Ingress Controller Pod(s)                |  watches Ingress objects, builds nginx.conf
   |   nginx: server_name demo.local          |
   |     location /api  -> upstream backend   |
   |     location /     -> upstream frontend  |
   +------------------------------------------+
            |                       |
            v                       v
   +----------------+      +----------------+
   | Service        |      | Service        |   ClusterIP; the controller actually
   | backend-svc:80 |      | frontend-svc:80|   reads the EndpointSlices and
   +----------------+      +----------------+   proxies straight to Pod IPs
            |                       |
      +-----+-----+           +-----+-----+
      v           v           v           v
   [backend]  [backend]   [frontend]  [frontend]   Pods
```

## Example: complete Ingress

Two path rules plus a host-based rule, all on one object. `pathType: Prefix` matches `/api`, `/api/`, `/api/users`; `Exact` would match only `/api`.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: demo-ingress
  namespace: default
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2   # strip /api prefix before proxying (optional)
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - demo.local
      secretName: demo-local-tls          # kubernetes.io/tls Secret with tls.crt and tls.key
  rules:
    - host: demo.local
      http:
        paths:
          - path: /api(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: backend-svc
                port:
                  number: 80
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend-svc
                port:
                  number: 80
    - host: admin.demo.local               # second host -> different Service
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: admin-svc
                port:
                  number: 8080
```

A simpler variant without rewriting, where the backend already serves under `/api`:

```yaml
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: backend-svc
                port:
                  number: 80
```

## Enabling and verifying on minikube

```bash
# 1. install the controller (ingress-nginx) into namespace ingress-nginx
minikube addons enable ingress
kubectl get pods -n ingress-nginx
# NAME                                        READY   STATUS      RESTARTS   AGE
# ingress-nginx-admission-create-xxxxx        0/1     Completed   0          60s
# ingress-nginx-admission-patch-xxxxx         0/1     Completed   0          60s
# ingress-nginx-controller-xxxxxxxxxx-xxxxx   1/1     Running     0          60s

# 2. deploy sample apps and the Ingress
kubectl create deployment frontend --image=nginxdemos/hello:plain-text --port=80
kubectl create deployment backend  --image=hashicorp/http-echo --port=5678 -- /http-echo -text="backend"
kubectl expose deployment frontend --name=frontend-svc --port=80
kubectl expose deployment backend  --name=backend-svc  --port=80 --target-port=5678
kubectl apply -f demo-ingress.yaml

# 3. verify the Ingress picked up an address
kubectl get ingress
# NAME           CLASS   HOSTS        ADDRESS        PORTS   AGE
# demo-ingress   nginx   demo.local   192.168.49.2   80      30s
kubectl describe ingress demo-ingress        # shows each rule and the backend endpoints

# 4. send traffic with a Host header (no DNS needed)
curl -H "Host: demo.local" http://$(minikube ip)/
curl -H "Host: demo.local" http://$(minikube ip)/api
# or add "$(minikube ip) demo.local" to /etc/hosts and use the hostname directly
```

On macOS with the Docker driver, `minikube ip` is not reachable from the host directly. Run `minikube tunnel` in a second terminal and curl `http://127.0.0.1/` with the same Host header.

## Typical troubleshooting

| Symptom | Usual cause | Check |
|---|---|---|
| `kubectl get ingress` shows no ADDRESS | No controller installed, or `ingressClassName` does not match any IngressClass | `kubectl get pods -n ingress-nginx`, `kubectl get ingressclass` |
| `404 Not Found` with `nginx` server header | The controller received the request but no rule matched: wrong Host header, wrong path, or `pathType: Exact` | `curl -v -H "Host: demo.local" ...`, `kubectl describe ingress` |
| `503 Service Temporarily Unavailable` | Rule matched but the Service has no endpoints: Pods not Ready, selector mismatch, wrong port name/number | `kubectl get endpoints backend-svc`, `kubectl get pods -l app=backend` |
| `502 Bad Gateway` | Pod is listening on a different port than the Service `targetPort`, or app crashed | `kubectl logs -n ingress-nginx deploy/ingress-nginx-controller` |
| Connection refused / timeout | Firewall, wrong node IP, or on macOS Docker driver without `minikube tunnel` | `minikube service list`, `minikube tunnel` |
| TLS handshake error / default fake cert | `secretName` wrong, Secret in a different namespace than the Ingress, or not type `kubernetes.io/tls` | `kubectl get secret demo-local-tls -o yaml` |
| Admission webhook error on `kubectl apply` | Invalid annotation or path regex rejected by the ingress-nginx validating webhook | Read the error text; fix the annotation |

Useful log command:

```bash
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --tail=50 -f
```

## Key takeaways

1. Ingress = desired routing state (an object). Ingress Controller = the proxy that makes it real (Pods).
2. Kubernetes ships the Ingress API but no controller; install one (NGINX, Traefik, ALB, Contour...).
3. `ingressClassName` tells the cluster which controller should act on an Ingress.
4. Empty ADDRESS means no controller or no matching class; 404 means no rule matched; 503 means no healthy endpoints behind the Service.
5. The same Ingress YAML can move between minikube and a cloud cluster; only the controller changes.

## References

- Ingress concept: https://kubernetes.io/docs/concepts/services-networking/ingress/
- Ingress Controllers: https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/
- IngressClass and default class: https://kubernetes.io/docs/concepts/services-networking/ingress/#ingress-class
- ingress-nginx documentation: https://kubernetes.github.io/ingress-nginx/
- ingress-nginx troubleshooting guide: https://kubernetes.github.io/ingress-nginx/troubleshooting/
- minikube ingress tutorial: https://kubernetes.io/docs/tasks/access-application-cluster/ingress-minikube/
- AWS Load Balancer Controller: https://kubernetes-sigs.github.io/aws-load-balancer-controller/
- Gateway API (successor to Ingress): https://gateway-api.sigs.k8s.io/
