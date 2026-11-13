#!/usr/bin/env bash

echo "Cleaning up all test resources..."

# ลบ Deployments จากไฟล์ yaml
echo "[1/3] Deleting test-kata and test-runc deployments..."
kubectl delete -f test-kata.yaml --ignore-not-found=true
kubectl delete -f test-runc.yaml --ignore-not-found=true

# ลบ pods กรณีรันแบบ kubectl run เดี่ยวๆ
echo "[2/3] Deleting any standalone pods (demo-kata, demo-runc, kata-gw)..."
kubectl delete pod demo-kata demo-runc kata-gw --ignore-not-found=true

echo "[3/3] Done! Current pods in namespace:"
kubectl get pods
