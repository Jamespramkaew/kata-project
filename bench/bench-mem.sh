#!/usr/bin/env bash
# รันบน worker เท่านั้น: วัด RAM (RSS) ที่ pod ใช้จริงบนเครื่อง
# วิธีใช้: ./bench-mem.sh <runc|kata>
# ก่อนรัน: ต้องมี pod ของแบบนั้นรันอยู่ตัวเดียวบน worker
set -euo pipefail
RT=${1:?ใส่ runc หรือ kata}
if [ "$RT" = kata ]; then
  PROCS="/opt/kata/bin/qemu-system /opt/kata/runtime-rs/bin/containerd-shim /opt/kata/libexec/virtiofsd"
else
  PROCS="nginx:"
fi
mkdir -p results
OUT="results/mem-$RT-$(date +%Y%m%d-%H%M%S).csv"
echo "runtime,process,rss_mb" > "$OUT"
TOTAL=0
for p in $PROCS; do
  KB=$(ps -o rss= -p "$(pgrep -d, -f -- "$p" || echo 0)" | awk '{s+=$1} END{print s+0}')
  MB=$(awk -v k="$KB" 'BEGIN{printf "%.1f",k/1024}')
  echo "$RT,$p,$MB" >> "$OUT"
  echo "$p: $MB MB"
  TOTAL=$((TOTAL+KB))
done
SUM=$(awk -v k="$TOTAL" 'BEGIN{printf "%.1f",k/1024}')
echo "$RT,total,$SUM" >> "$OUT"
echo "รวม: $SUM MB"
echo "บันทึกผลที่ $OUT"
