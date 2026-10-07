# GitOps

**Student:** Vivek Singh Solanki | **Roll number:** 24bcs10338
**Session:** 20 - Monitoring, Observability and GitOps
**Topic:** GitOps principles, Git as the source of truth, reconciliation, and GitOps on Kubernetes with Argo CD and Flux

## What is GitOps?

GitOps is an operating model for infrastructure and applications in which the **desired state of the system is described declaratively and stored in Git**, and **software agents continuously reconcile the live system to match it**. The term was coined by Weaveworks in 2017 and is now formalised by the CNCF OpenGitOps project.

OpenGitOps v1.0 defines four principles:

| # | Principle | Meaning |
|---|---|---|
| 1 | **Declarative** | The desired state is expressed as data (YAML, HCL, Kustomize, Helm values), not as a sequence of commands. |
| 2 | **Versioned and immutable** | Desired state is stored in a system that keeps full history and does not allow in-place mutation: Git. Every version is addressable (a commit SHA). |
| 3 | **Pulled automatically** | Agents running *inside* the environment pull the desired state from the repository; nobody pushes changes into the cluster by hand or from a CI runner. |
| 4 | **Continuously reconciled** | The agents keep comparing actual state with desired state and correct any difference, not only at deploy time. |

Anything that satisfies these four points is GitOps; a CI job running `kubectl apply` on every push satisfies only the first two.

## Git as the source of truth

"Source of truth" means that **if it is not in Git, it is not supposed to exist in the cluster**, and if the cluster differs from Git, the cluster is wrong.

What this gives in practice:

- **Change through pull requests.** Nobody edits the cluster directly. A change is a PR against the config repo: it gets review, automated checks (YAML lint, `kubeconform`, policy tests), and approval before merge.
- **Audit trail for free.** `git log` shows who changed what, when, and why (commit message + PR discussion). This replaces hand-written change tickets for most changes.
- **Rollback is `git revert`.** Reverting the commit restores the previous desired state; the agent applies it. There is no separate rollback procedure to document or test.
- **Disaster recovery.** Rebuilding a cluster is: create cluster, install the agent, point it at the repo. Everything else re-materialises.
- **Access control moves to Git.** Developers need write access to a repo and branch protection, not `cluster-admin` credentials on their laptops.

The repo is usually separate from the application source code (an "environment" or "deploy" repo) so that config changes and code changes have independent histories and permissions.

## Declarative configuration

Imperative: tell the system *what to do*, step by step. Declarative: tell the system *what the result should be* and let it figure out the steps.

Imperative (not reproducible, not reviewable, lives only in shell history):

```bash
kubectl create deployment web --image=registry.example.com/web:1.4.2
kubectl scale deployment web --replicas=3
kubectl set env deployment/web LOG_LEVEL=info
kubectl expose deployment web --port=80
```

Declarative (committed to Git at `apps/web/deployment.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  namespace: shop
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
        - name: web
          image: registry.example.com/web:1.4.2
          env:
            - name: LOG_LEVEL
              value: info
          ports:
            - containerPort: 80
```

The declarative file can be diffed, reviewed, reverted and applied any number of times with the same result (idempotent). Kustomize overlays or Helm values files are used to describe differences between dev, staging and prod without copying the whole manifest.

## Continuous reconciliation

The GitOps agent runs a control loop very much like a Kubernetes controller:

```
            +------------------------------------------------------+
            |                                                      |
            v                                                      |
   read desired state (Git, commit abc123)                         |
            |                                                      |
            v                                                      |
   read actual state (cluster API)                                 |
            |                                                      |
            v                                                      |
   diff  ---- no difference ----> status: Synced / Healthy --------+  (wait interval, e.g. 3 min,
            |                                                      |   or webhook on push)
            | difference found ("OutOfSync")                       |
            v                                                      |
   apply desired state (if automated sync) ----> status back ------+
```

Important behaviours:

- **Drift detection.** If someone runs `kubectl edit` or a Pod is scaled manually, the agent notices and marks the app `OutOfSync`. In Argo CD this is visible in the UI and via `argocd app diff`.
- **selfHeal.** When enabled, the agent reverts manual changes automatically instead of just reporting them. This is what makes "the cluster is wrong, Git is right" enforceable.
- **prune.** When a resource is deleted from Git, the agent deletes it from the cluster. Without prune, removed manifests leave orphaned objects behind.
- **Health assessment.** Beyond "applied", the agent checks that Deployments have rolled out, Pods are Ready, Ingresses have addresses, and reports `Healthy`, `Progressing` or `Degraded`.
- **Sync waves / hooks.** Ordering (CRDs before CRs, migrations before app) is expressed with annotations rather than scripts.

## GitOps workflow

```
  Developer                 Git (app repo)              CI (GitHub Actions / Jenkins)
  --------                  --------------              ----------------------------
  write code -> PR -> merge  ---------------------->  build, test, docker build
                                                      push image registry/web:1.4.3
                                                      update image tag in CONFIG repo
                                                      (kustomize edit set image ... + commit/PR)
                                                               |
                                                               v
                                                    Git (config / env repo)
                                                    apps/web/kustomization.yaml
                                                    newTag: 1.4.3    <- commit def456
                                                               |
                               pull (poll every 3 min or webhook)
                                                               |
                                                               v
                                            +------------------------------+
                                            | Argo CD / Flux (in cluster)  |
                                            | desired: def456              |
                                            | actual : abc123  -> OutOfSync|
                                            | sync -> kubectl apply (server-side) |
                                            +------------------------------+
                                                               |
                                                               v
                                                    Kubernetes cluster
                                                    Deployment web -> 1.4.3 rolled out
                                                               |
                                                               v
                                       status back: Synced / Healthy (UI, CLI, Slack, commit status)
```

Key point: **CI never touches the cluster.** CI's job ends with a commit to the config repo. The in-cluster agent does the deployment. This is the "pull" model.

## Kubernetes + GitOps

### Argo CD vs Flux

| Aspect | Argo CD | Flux (v2) |
|---|---|---|
| Project | CNCF graduated (Argo project, from Intuit) | CNCF graduated (from Weaveworks) |
| Core CRDs | `Application`, `ApplicationSet`, `AppProject` | `GitRepository`, `Kustomization`, `HelmRelease`, `ImagePolicy` |
| UI | Rich built-in web UI with resource tree and diff view | No built-in UI (Weave GitOps UI or Headlamp plugin optional) |
| CLI | `argocd` | `flux` |
| Multi-cluster | Hub-and-spoke from one Argo CD, cluster credentials stored as Secrets | One Flux per cluster is the norm; multi-cluster via Kustomization of kubeconfigs |
| Helm handling | Renders `helm template` and applies (no Helm release object) | Uses Helm SDK; real Helm releases, supports `helm rollback` |
| Image automation | Argo CD Image Updater (separate component) | Built-in image reflector and automation controllers |
| Multi-tenancy | `AppProject` restricts repos, destinations, resource kinds | Kubernetes RBAC + per-namespace controllers |
| Sync trigger | Poll (default 3 min) + webhooks | Poll (default 1 min for sources) + webhooks (Receiver CRD) |
| Progressive delivery | Argo Rollouts (sibling project) | Flagger (sibling project) |
| Typical fit | Teams wanting a visual control plane and app-centric view | Teams wanting a lightweight, Kubernetes-native toolkit |

Both implement the four OpenGitOps principles; the choice is mostly about UI preference and ecosystem.

### Argo CD Application example

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: shop-web
  namespace: argocd                     # Applications live where Argo CD is installed
  finalizers:
    - resources-finalizer.argocd.argoproj.io   # deleting the Application also deletes its resources
spec:
  project: default
  source:
    repoURL: https://github.com/vivek-solanki/shop-config.git
    targetRevision: main                # branch, tag or commit SHA
    path: apps/web/overlays/prod        # Kustomize overlay (Helm chart or plain YAML also work)
  destination:
    server: https://kubernetes.default.svc   # the cluster Argo CD runs in
    namespace: shop
  syncPolicy:
    automated:
      prune: true                       # delete resources removed from Git
      selfHeal: true                    # revert manual changes in the cluster
      allowEmpty: false                 # refuse to delete everything if the path renders empty
    syncOptions:
      - CreateNamespace=true            # create "shop" if it does not exist
      - ServerSideApply=true
      - PruneLast=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

Installing Argo CD on minikube for practice:

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
kubectl port-forward svc/argocd-server -n argocd 8080:443    # UI at https://localhost:8080 (user: admin)
argocd login localhost:8080 --username admin --insecure
kubectl apply -f shop-web-application.yaml
```

### Push vs pull deployment

| | Push (classic CI/CD) | Pull (GitOps) |
|---|---|---|
| Who applies to the cluster | CI runner (`kubectl apply`, `helm upgrade`) | Agent inside the cluster (Argo CD, Flux) |
| Cluster credentials | Stored in CI secrets, reachable from outside | Never leave the cluster; CI only needs Git access |
| Network direction | Inbound to the cluster API | Outbound from cluster to Git/registry; works behind firewalls |
| Drift handling | None after the pipeline finishes | Continuous detection and (optionally) correction |
| Visibility of actual state | Pipeline log says "applied" | Agent reports Synced/OutOfSync and Healthy/Degraded continuously |
| Rollback | Re-run an older pipeline | `git revert` |
| Failure mode | Pipeline passes but cluster drifts later, nobody notices | Agent flags OutOfSync; cluster converges once Git or cluster fixed |

## Benefits and challenges

Benefits:

- Every change is reviewed, versioned and attributable; compliance evidence comes from Git history.
- Rollback and disaster recovery are routine Git operations.
- Reduced blast radius: no shared `cluster-admin` kubeconfigs on developer machines or CI servers.
- Drift is detected (and with selfHeal, corrected) rather than discovered during an outage.
- The same workflow scales from one app on minikube to hundreds of clusters via ApplicationSets or Flux Kustomizations.

Challenges:

- **Secrets.** Plain Secrets cannot be committed. Needs Sealed Secrets, SOPS (Flux native), External Secrets Operator, or Vault integration.
- **Repo structure.** Mono-repo vs per-team repos, app repo vs config repo, branch-per-environment vs folder-per-environment; getting this wrong is painful to change later.
- **Image tag updates.** Someone (CI, Image Updater, Flux image automation) must write the new tag back to Git, which creates bot commits and possible merge conflicts.
- **Ordering and dependencies.** CRDs, operators, databases and migrations need sync waves, hooks or `dependsOn`.
- **Learning curve and feedback loop.** Developers wait for a merge plus a sync interval instead of seeing `kubectl apply` output; good status reporting (Slack notifications, PR commit statuses) is essential.
- **Imperative escape hatches.** Emergency `kubectl` changes get reverted by selfHeal, which surprises people until they internalise "fix it in Git".

## Useful commands

```bash
# Argo CD
argocd app list                                   # all applications with sync and health status
argocd app get shop-web                           # details, resource tree, conditions
argocd app diff shop-web                          # what differs between Git and the cluster
argocd app sync shop-web                          # trigger a sync now (or --prune, --dry-run)
argocd app history shop-web                       # previous synced revisions
argocd app rollback shop-web 3                    # roll back to history id 3 (disables auto-sync)
argocd app set shop-web --sync-policy automated --self-heal --auto-prune
kubectl get applications -n argocd                # same data through the Kubernetes API
kubectl describe application shop-web -n argocd   # events and sync errors
kubectl get appprojects -n argocd

# Flux
flux check
flux get sources git
flux get kustomizations --watch
flux reconcile kustomization shop-web --with-source
flux suspend kustomization shop-web && flux resume kustomization shop-web
```

## Key takeaways

1. GitOps = declarative desired state in Git + an in-cluster agent that pulls and continuously reconciles.
2. Git is the only approved way to change the cluster; PRs are the change process and `git revert` is the rollback.
3. `automated` sync with `prune` and `selfHeal` turns Git into an enforced source of truth rather than a suggestion.
4. CI builds and tests the image and updates a tag in Git; CD is done by Argo CD or Flux pulling that change.
5. Plan secrets management and repo layout early; they are the two hardest parts in practice.

## References

- OpenGitOps principles (CNCF): https://opengitops.dev/
- Argo CD documentation: https://argo-cd.readthedocs.io/en/stable/
- Argo CD Application spec and sync options: https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
- Argo CD automated sync policy: https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/
- Flux documentation: https://fluxcd.io/flux/
- Flux core concepts: https://fluxcd.io/flux/concepts/
- Kustomize: https://kubectl.docs.kubernetes.io/
- Sealed Secrets: https://github.com/bitnami-labs/sealed-secrets
- External Secrets Operator: https://external-secrets.io/
- Kubernetes declarative object management: https://kubernetes.io/docs/tasks/manage-kubernetes-objects/declarative-config/
