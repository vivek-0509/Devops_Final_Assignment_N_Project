# Presentation narration script

**Student:** Vivek Singh Solanki | **Roll number:** 24bcs10338

One paragraph per slide of `DevOps_Final_Project_Presentation.pptx`. This is the text spoken in the presentation video.

## Slide 1 - Title
Hello, my name is Vivek Singh Solanki, roll number 24 B C S 1 0 3 3 8. This is my final DevOps project, TaskBoard Lite. It is a small task management application, but the point of the project is everything around it: the pipeline, the security gates, the Kubernetes deployment, the infrastructure, the monitoring and the GitOps workflow. Everything you will see was executed for real, and the full documentation is in my GitHub repository.

## Slide 2 - Agenda
Here is the order of the presentation. First the goal and the architecture. Then the application and its Docker image. Then the CI/CD pipeline with the DevSecOps checks. After that the infrastructure on AWS and the Kubernetes deployment with Helm. Then monitoring and GitOps, and finally the troubleshooting challenge and the lessons I learned.

## Slide 3 - Goal
The goal was to take one application from my laptop to a monitored cluster using the complete DevOps toolchain from the course. TaskBoard Lite is written in Python with Flask and stores tasks in SQLite. It was kept deliberately simple so that the focus stays on the delivery process: code, Git and GitHub, a CI pipeline, build and test, security scanning, a Docker image, a container registry, Kubernetes with Helm, monitoring and GitOps. The cloud infrastructure for it is provisioned with Terraform on AWS.

## Slide 4 - Architecture
This is the architecture. A developer pushes to GitHub. GitHub Actions runs the tests, the static analysis, the dependency audit, the secret scan, builds the Docker image, scans it with Trivy and then evaluates a security gate. Only if the gate passes is the image pushed to the GitHub Container Registry and deployed with Helm. In the cluster, the application runs behind an nginx ingress and a service, with two to five pods controlled by a horizontal pod autoscaler, configuration from a ConfigMap and a Secret, and a persistent volume for the data. Prometheus scrapes the metrics endpoint and Grafana shows the dashboard. Argo CD watches the manifests in Git and keeps the cluster in sync. Terraform creates the AWS network, the EC2 instance and the S3 bucket.

## Slide 5 - Technology stack
The stack: Python 3.12 and Flask for the application with seventeen pytest tests at 92 percent coverage. Docker with a multi-stage build on an Alpine base, running as a non-root user. GitHub Actions with nine jobs, plus the act tool to run the same workflow locally. For security, Bandit, pip-audit, gitleaks, Trivy and CodeQL. Kubernetes 1.37 on minikube with Helm. Terraform 1.14 with the AWS provider. Prometheus and Grafana for monitoring, and Argo CD for GitOps.

## Slide 6 - Application and container image
The numbers on this slide are from the real runs: seventeen tests passing, zero high or critical vulnerabilities in the final image, and the container runs as user ten thousand and one. The API exposes health and readiness endpoints for Kubernetes probes, a metrics endpoint for Prometheus, and the task endpoints. Configuration comes from environment variables, and the database password is injected from a secret and never printed. The Dockerfile has two stages. The first Debian based image failed the Trivy gate with forty-four high vulnerabilities, so I switched the runtime to Alpine, and the scan came back clean.

## Slide 7 - CI/CD pipeline
The pipeline has nine jobs in GitHub Actions: unit tests, static analysis, dependency audit, secret scan, Docker build, image scan, the security gate, the push to the registry and the deployment. Each job runs on its own runner and the needs keyword chains them, so a failure stops everything after it. The image is tagged with the Git commit SHA and passed between jobs as an artifact. The push and the deployment only run on the main branch. The screenshot shows the workflow executed locally with act, with all seven CI jobs green.

## Slide 8 - DevSecOps
These gates actually blocked the pipeline during the project, which is the whole point. Bandit reported a bind-to-all-interfaces finding, which I reviewed and suppressed with a justification because a container must listen on all interfaces. Pip-audit found a real vulnerability in Flask 3.1.1, so I upgraded to 3.1.3. Gitleaks keeps the repository clean, and I verified it by planting a fake AWS key and a fake GitHub token in a test, which it caught. Trivy rejected the Debian image and accepted the Alpine image. The security gate job checks all four results and the push and deploy jobs depend on it.

## Slide 9 - Terraform on AWS
Infrastructure is code. Terraform creates a VPC, a public subnet, an internet gateway, a route table, a security group that opens ports 80 and 22, an EC2 instance with a user data script that installs Docker, and a private S3 bucket. That is twelve resources. I ran the full workflow, init, format, validate, plan, apply and destroy, against my own AWS account, and verified the instance and the VPC with the AWS CLI before destroying everything again. The AMI is looked up from an SSM parameter, so nothing is hard coded.

## Slide 10 - Kubernetes with Helm
On Kubernetes, the Helm chart creates a deployment with two replicas and startup, readiness and liveness probes, a service behind the nginx ingress at taskboard dot local, a ConfigMap and a Secret for configuration, a one gigabyte persistent volume for the SQLite file, and a horizontal pod autoscaler between two and five replicas. I verified the application through the ingress, confirmed that the configuration and the secret were injected, deleted a pod and saw the data survive on the volume, and ran a load test that scaled the deployment from two to four pods.

## Slide 11 - Monitoring and observability
For monitoring, the application exposes Prometheus metrics such as the total requests per endpoint and the number of open tasks. Prometheus scrapes them, and the Grafana dashboard you see here is provisioned from the repository: target status, open tasks, the error ratio and the request rate. Logs come from kubectl and docker compose, and alert rules cover the application being down and a high error rate. In the monitoring session I also made an alert fire and resolve to prove the rules work.

## Slide 12 - GitOps with Argo CD
GitOps means Git is the only source of truth. A change is proposed in a pull request, merged to main, and Argo CD detects the new commit and syncs the namespace. If someone changes the cluster by hand, for example by scaling the deployment down with kubectl, self-heal reverts it to what is committed. The Argo CD application manifest in the repository enables automated sync, pruning, self-heal and namespace creation, and the screenshot shows the drift being repaired.

## Slide 13 - Troubleshooting challenge
Four failures were introduced on purpose. A wrong image tag caused ImagePullBackOff. A service selector that did not match the pod labels left the service with no endpoints. A wrong secret key caused a CreateContainerConfigError. And a readiness probe on the wrong path kept the pods from ever becoming ready, so the ingress returned 503. Every one of them was solved with the same loop: identify with kubectl get, investigate with describe, logs and endpoints, find the root cause, fix it, and verify. The before and after output is in the README.

## Slide 14 - The whole course
This project sits on top of the whole course. The repository contains twenty-one completed sessions, eighty-three commits, sixty-two README files and over two hundred screenshots of real command output, covering Linux, shell scripting, networking, Git, Docker, Kubernetes, Helm, GitHub Actions, DevSecOps, Terraform, AWS, monitoring and GitOps.

## Slide 15 - Lessons learned
A few things I learned. A security gate is only useful if it really blocks, and mine did. Hardening has side effects: a read-only root filesystem broke gunicorn until I added a writable temp directory. State shapes the deployment strategy, because a read-write-once volume needs a single writer. Testing the pipeline locally with act saves a lot of failed runs. Terraform experiments are free when every apply ends with a destroy. And with Argo CD, drift becomes a non-event, because the cluster always converges back to Git.

## Slide 16 - Demo and repository
Thank you for watching. The repository is github dot com slash vivek dash 0509 slash Devops Final Assignment N Project. The project README contains the setup, the architecture, the pipeline, the Terraform code, the Kubernetes and Helm files, the monitoring configuration and every screenshot. I am happy to answer questions.
