# Troubleshooting scenarios used in Task 5

| # | File | Symptom | Root cause |
|---|---|---|---|
| 1 | `broken-secret-newline.yaml` + `mysql.yaml` + `db-client.yaml` | MySQL Pod goes to `Error`/`CrashLoopBackOff` (`mysql: [ERROR] unknown option '--"'`) and the client gets `ERROR 2003: Can't connect to MySQL server` | Secret value was encoded with `echo "..." \| base64` which adds a trailing `\n` (see `../troubleshooting/secret-base64-gotcha.md`) |
| 2 | `broken-ingress.yaml` | `curl http://yatri.local/api/` returns **503 Service Temporarily Unavailable** | Ingress backend points to a Service name that does not exist (`yatri-backend-svc` instead of `yatri-backend-service`) |
