#!/usr/bin/env bash
set -e

# กำหนดพอร์ตบนเครื่อง Host ที่ต้องการเปิดเข้าใช้งาน
LOCAL_PORT="${1:-8082}"
GW_POD_NAME="kata-gw"

echo "[1/4] Looking for Kata Pod IP from deployment/test-kata..."
KATA_IP=$(kubectl get pod -l app.kubernetes.io/name=test-kata -o jsonpath='{.items[0].status.podIP}')

if [ -z "$KATA_IP" ]; then
    echo "Error: Could not find Pod IP. Is deployment/test-kata running?"
    echo "Try checking: kubectl get pods -l app.kubernetes.io/name=test-kata"
    exit 1
fi

echo "Found Kata Pod IP: $KATA_IP"

# ฟังก์ชันทำความสะอาดเมื่อกด Ctrl+C หรือสคริปต์จบการทำงาน
cleanup() {
    echo ""
    echo "[Cleanup] Deleting gateway pod ($GW_POD_NAME)..."
    kubectl delete pod "$GW_POD_NAME" --ignore-not-found=true --wait=false > /dev/null 2>&1
    echo "[Cleanup] Done."
}
trap cleanup EXIT INT TERM

# ตรวจสอบและลบ kata-gw เก่าที่อาจค้างอยู่
if kubectl get pod "$GW_POD_NAME" > /dev/null 2>&1; then
    echo "Removing previous $GW_POD_NAME pod..."
    kubectl delete pod "$GW_POD_NAME" --wait=true > /dev/null 2>&1
fi

echo "[2/4] Creating temporary socat gateway pod ($GW_POD_NAME)..."
kubectl run "$GW_POD_NAME" \
    --image=alpine/socat \
    --restart=Never \
    -- tcp-listen:8080,fork,reuseaddr tcp:"$KATA_IP":8080 > /dev/null

echo "[3/4] Waiting for gateway pod to be ready..."
kubectl wait --for=condition=Ready pod/"$GW_POD_NAME" --timeout=30s > /dev/null

echo "[4/4] Starting port-forward on http://localhost:$LOCAL_PORT -> $KATA_IP:8080"
echo "------------------------------------------------------------"
echo ">> Open browser at: http://localhost:$LOCAL_PORT"
echo ">> Press Ctrl+C to stop and auto-clean the gateway pod"
echo "------------------------------------------------------------"

kubectl port-forward pod/"$GW_POD_NAME" "$LOCAL_PORT":8080
