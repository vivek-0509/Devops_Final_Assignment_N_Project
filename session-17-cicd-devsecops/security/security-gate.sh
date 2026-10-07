#!/bin/bash
# Security gate: evaluates the results of the security jobs and blocks the pipeline on any failure.
# Usage: security-gate.sh <sast_result> <sca_result> <secret_result> <image_result>
set -e
printf "%-22s %s\n" "CHECK" "RESULT"
printf "%-22s %s\n" "SAST (bandit)"   "$1"
printf "%-22s %s\n" "SCA (pip-audit)" "$2"
printf "%-22s %s\n" "Secret scan"     "$3"
printf "%-22s %s\n" "Image scan"      "$4"
for r in "$@"; do
  if [ "$r" != "success" ]; then
    echo "SECURITY GATE: BLOCKED - at least one security check did not pass."
    exit 1
  fi
done
echo "SECURITY GATE: PASSED - image may be pushed and deployed."
