# DevOps Final Assignment - Vivek Singh Solanki (Roll No: 24bcs10338)

Hands-on homework for all 21 sessions of the DevOps course. Every session folder contains its own `README.md` with the commands I ran, their real output, terminal screenshots and the files (scripts, Dockerfiles, Kubernetes manifests, Helm charts, Terraform, workflows) produced for that session.

**Environment used:** macOS (Apple Silicon) + Ubuntu 24.04 VM (Colima) for Docker, minikube v1.39 (Kubernetes v1.37) with ingress / metrics-server / MetalLB addons, Helm 4, Terraform 1.14 against my AWS account (us-east-1), GitHub Actions (workflows in `.github/workflows/`, also executed locally with `act`).

## Submission links (one README per session)

| Session | Topic | README |
|---|---|---|
| 1 & 2 | Linux Fundamentals | [session-01-02-linux/README.md](session-01-02-linux/README.md) |
| 3 | Shell Scripting | [session-03-shell-scripting/README.md](session-03-shell-scripting/README.md) |
| 4 | Networking | [session-04-networking/README.md](session-04-networking/README.md) |
| 5 | Git and GitHub | [session-05-git-github/README.md](session-05-git-github/README.md) |
| 6 | Docker Fundamentals (Hello World apps) | [session-06-docker-fundamentals/README.md](session-06-docker-fundamentals/README.md) |
| 7 | Docker Images (multi-stage build) | [session-07-docker-images/README.md](session-07-docker-images/README.md) |
| 8 | Docker Networking & Volumes | [session-08-docker-networking/README.md](session-08-docker-networking/README.md) |
| 9 | Kubernetes Fundamentals | [session-09-kubernetes-fundamentals/README.md](session-09-kubernetes-fundamentals/README.md) |
| 10 | Kubernetes Pods, ReplicaSets & Deployments | [session-10-k8s-pods-replicasets-deployments/README.md](session-10-k8s-pods-replicasets-deployments/README.md) |
| 11 | Kubernetes Networking & Services | [session-11-k8s-networking-services/README.md](session-11-k8s-networking-services/README.md) |
| 12 | Kubernetes Ingress, ConfigMaps & Secrets | [session-12-k8s-ingress-configmaps-secrets/README.md](session-12-k8s-ingress-configmaps-secrets/README.md) |
| 13 | Kubernetes Storage, HPA & Probes | [session-13-k8s-storage-hpa-probes/README.md](session-13-k8s-storage-hpa-probes/README.md) |
| 14 | Kubernetes Troubleshooting | [session-14-k8s-troubleshooting/README.md](session-14-k8s-troubleshooting/README.md) |
| 15 | Helm | [session-15-helm/README.md](session-15-helm/README.md) |
| 16 | CI/CD & GitHub Actions | [session-16-cicd-github-actions/README.md](session-16-cicd-github-actions/README.md) |
| 17 | Complete CI/CD & DevSecOps | [session-17-cicd-devsecops/README.md](session-17-cicd-devsecops/README.md) |
| 18 | Terraform & Infrastructure as Code | [session-18-terraform-iac/README.md](session-18-terraform-iac/README.md) |
| 19 | Cloud & Terraform in Action | [session-19-cloud-terraform/README.md](session-19-cloud-terraform/README.md) |
| 20 | Monitoring, Observability & GitOps | [session-20-monitoring-observability-gitops/README.md](session-20-monitoring-observability-gitops/README.md) |
| 21 | Final DevOps Project & Troubleshooting | [session-21-final-devops-project/final-devops-project/README.md](session-21-final-devops-project/final-devops-project/README.md) |

## Repository layout

```text
.
├── demo/                       presentation video link and slide deck (PPTX + PDF) for the final project
├── .github/workflows/          GitHub Actions pipelines (session16-ci-cd.yml, session17-devsecops.yml, session21-final-pipeline.yml)
├── session-01-02-linux/        links, adduser/useradd, journalctl, cheat-sheet practice
├── session-03-shell-scripting/ system_info.sh + run output
├── session-04-networking/      networking commands with explanations
├── session-05-git-github/      git commit -a vs -m, cherry-pick
├── session-06-docker-fundamentals/   nodejs-app, python-app, java-app, Apache-app, React-app, nginx-app
├── session-07-docker-images/   multi-stage build on port 8080 + 3 app types
├── session-08-docker-networking/     3 networks / 3 containers, host network, bind mount, overlay research
├── session-09-kubernetes-fundamentals/   minikube, architecture notes, Kubernetes Basics tutorial
├── session-10-k8s-pods-replicasets-deployments/  rolling / blue-green / canary / recreate + pod lifecycle
├── session-11-k8s-networking-services/   5 Service types, comparison docs, fqdn/, coredns/
├── session-12-k8s-ingress-configmaps-secrets/   ConfigMap, Secret, Ingress demo, troubleshooting
├── session-13-k8s-storage-hpa-probes/    volumes doc, HPA + load generator, mini project, probes
├── session-14-k8s-troubleshooting/       kubectl commands, 9 broken scenarios fixed, mini project
├── session-15-helm/            helm commands, rollback workflow, notes-chart mini project
├── session-16-cicd-github-actions/   calculator API + CI/CD workflow
├── session-17-cicd-devsecops/  Flask app + SAST/SCA/secret/image scans + security gate + deploy
├── session-18-terraform-iac/   terraform-s3-demo + aws-services research (IAM, EC2, S3, VPC, DynamoDB/RDS)
├── session-19-cloud-terraform/ VPC + subnet + SG + EC2 + S3 end-to-end with Terraform
├── session-20-monitoring-observability-gitops/  Prometheus/Grafana stack, alerts, Argo CD GitOps demo
└── session-21-final-devops-project/final-devops-project/   TaskBoard Lite capstone (app, docker, kubernetes, helm, terraform, workflows, security, monitoring, gitops, troubleshooting)
```

## Final project demo

The `demo/` folder holds the presentation video link and the slide deck (`DevOps_Final_Project_Presentation.pptx` and `.pdf`) required by the final-project submission, see [demo/README.md](demo/README.md).

## How the evidence was produced
- Every command in the READMEs was executed on my machine; the `screenshots/` folders contain terminal captures of those runs plus browser screenshots of the running applications, Prometheus, Grafana and Argo CD.
- Cloud resources (S3 buckets, VPC, EC2) were created with `terraform apply` in my AWS account and removed again with `terraform destroy` right after the verification steps.
- The GitHub Actions workflows live in `.github/workflows/` and are triggered by pushes that touch the matching session folder; they were also executed locally with `act` (see the Session 16/17/21 READMEs).
