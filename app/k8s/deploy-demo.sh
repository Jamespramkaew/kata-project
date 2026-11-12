#!/usr/bin/env bash
set -euo pipefail

namespace="dev-mawn"

usage() {
  printf 'Usage: %s <image>\n' "$0" >&2
  printf 'Example: %s ghcr.io/owner/demo:v1\n' "$0" >&2
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

image="$1"
if [[ ! "$image" =~ ^[A-Za-z0-9._/:@+-]+$ ]]; then
  printf 'Invalid image reference: %s\n' "$image" >&2
  usage
  exit 2
fi

if ! command -v kubectl >/dev/null 2>&1; then
  printf 'kubectl is required but was not found in PATH.\n' >&2
  exit 1
fi

context="$(kubectl config current-context)"
printf 'Using Kubernetes context: %s\n' "$context"

if ! kubectl get namespace "$namespace" >/dev/null; then
  printf 'Cannot access namespace %s; check Tailscale and your kubeconfig.\n' "$namespace" >&2
  exit 1
fi

permission="$(kubectl auth can-i create deployments --namespace="$namespace")"
if [[ "$permission" != "yes" ]]; then
  printf 'The current identity cannot create deployments in namespace %s.\n' "$namespace" >&2
  exit 1
fi

apply_deployment() {
  local name="$1"
  local system_name="$2"
  local runtime_class="$3"
  local runtime_class_field=""

  if [[ -n "$runtime_class" ]]; then
    runtime_class_field="      runtimeClassName: ${runtime_class}"
  fi

  kubectl apply --namespace="$namespace" -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${name}
  labels:
    app.kubernetes.io/name: ${name}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: ${name}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ${name}
    spec:
${runtime_class_field}
      containers:
        - name: app
          image: "${image}"
          ports:
            - name: http
              containerPort: 8080
          env:
            - name: SYSTEM_NAME
              value: "${system_name}"
EOF
}

apply_deployment "demo-runc" "runc" ""
apply_deployment "demo-kata" "kata" "kata"

kubectl rollout status "deployment/demo-runc" \
  --namespace="$namespace" --timeout=180s
kubectl rollout status "deployment/demo-kata" \
  --namespace="$namespace" --timeout=180s

printf '\nBoth deployments are ready.\n'
printf 'Forward ports in separate terminals:\n'
printf '  kubectl port-forward --namespace=%s deployment/demo-runc 8081:8080\n' "$namespace"
printf '  kubectl port-forward --namespace=%s deployment/demo-kata 8082:8080\n' "$namespace"
printf 'Then open http://localhost:8081 and http://localhost:8082.\n'
