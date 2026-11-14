#!/usr/bin/env bash
# รันบน Mac: วัด RAM บน worker แบบละ N รอบ (ค่าเริ่มต้น 5) แล้วรวมผลเป็น CSV เดียว
# ต้องมี bench-mem.sh อยู่ที่ ~/ บน worker แล้ว
set -euo pipefail
N=${1:-5}
KC=~/.kube/kata-config
NS=dev-james
SSH="ssh -i $HOME/.ssh/kata-key.pem ubuntu@100.124.98.29"
k() { kubectl --kubeconfig "$KC" -n "$NS" "$@"; }

for rt in runc kata; do
  for i in $(seq 1 "$N"); do
    echo "== $rt รอบ $i/$N"
    if [ "$rt" = kata ]; then
      k run mem-test --image=nginx:alpine --overrides='{"spec":{"runtimeClassName":"kata"}}' >/dev/null
    else
      k run mem-test --image=nginx:alpine >/dev/null
    fi
    k wait --for=condition=Ready pod/mem-test --timeout=120s >/dev/null
    sleep 10                                   # ให้ RAM นิ่งก่อนวัด
    $SSH "./bench-mem.sh $rt" || { k delete pod mem-test --wait=true; exit 1; }
    k delete pod mem-test --wait=true >/dev/null
    until [ "$($SSH 'pgrep -fc [/]opt/kata/bin/qemu-system || true')" = 0 ]; do sleep 2; done
  done
done

# ดึงผลกลับมารวมเป็นไฟล์เดียว
OUT="bench/final/mem-$(date +%Y%m%d-%H%M%S).csv"
TMP=$(mktemp -d)
scp -q -i ~/.ssh/kata-key.pem "ubuntu@100.124.98.29:results/mem-*.csv" "$TMP/"
echo "runtime,round,process,rss_mb" > "$OUT"
for rt in runc kata; do
  i=0
  for f in $(ls "$TMP"/mem-$rt-*.csv | sort); do
    i=$((i+1))
    tail -n +2 "$f" | awk -F, -v r="$i" 'BEGIN{OFS=","}{n=split($2,a,"/");p=a[n];sub(/:$/,"",p);print $1,r,p,$3}' >> "$OUT"
  done
done
rm -rf "$TMP"
echo "✅ บันทึกผลรวมที่ $OUT"
