#!/usr/bin/env python3
"""
bench.py - วัดผลเทียบ runc กับ Kata (งาน B3 ของกลุ่ม)

ใช้ได้ทั้ง Mac, Windows และ Ubuntu ขอแค่มี Python 3 และ kubectl ที่ตั้งไฟล์กุญแจไว้แล้ว

วิธีใช้:
  python3 bench.py start runc 10     วัดเวลาเริ่ม pod แบบ runc 10 รอบ
  python3 bench.py start kata 10     วัดเวลาเริ่ม pod แบบ Kata 10 รอบ
  python3 bench.py cpu runc 5        วัดความเร็ว CPU แบบ runc 5 รอบ
  python3 bench.py cpu kata 5        วัดความเร็ว CPU แบบ Kata 5 รอบ
  (บน Windows ใช้ python แทน python3)

ตัวเลือกเพิ่ม:
  -n ชื่อห้อง    ระบุ namespace เอง (ไม่ต้องใส่ ถ้าใช้ไฟล์กุญแจของตัวเอง)

ผลจะถูกบันทึกเป็นไฟล์ CSV ในโฟลเดอร์ results ข้าง ๆ สคริปต์นี้
ถ้ามีรอบไหนผิดพลาด สคริปต์จะหยุดทันที ลบ pod ที่สร้างไว้ และไม่บันทึกไฟล์ผล
"""

import argparse
import csv
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime

# ---------- ค่าที่ทุกคนใช้เหมือนกัน (ห้ามแก้ตอนวัดจริง เพื่อให้ผลเทียบกันได้) ----------
START_IMAGE = "nginx:alpine"            # image ที่ใช้วัดเวลาเริ่ม
CPU_IMAGE = "busybox:1.36"              # image ที่ใช้วัด CPU (มี dd และ md5sum ในตัว)
CPU_WORK = "dd if=/dev/zero bs=1M count=1024 2>/dev/null | md5sum >/dev/null"  # งาน: md5 ของข้อมูล 1 GB
READY_TIMEOUT = "180s"                  # รอ pod พร้อมได้นานสุดเท่านี้
KATA_OVERRIDE = json.dumps({"spec": {"runtimeClassName": "kata"}})


class BenchError(Exception):
    """ข้อผิดพลาดที่ต้องหยุดการวัด"""


def kubectl(args, ns, check=True):
    """เรียก kubectl แล้วคืนผลลัพธ์ ถ้าล้มเหลวให้หยุดพร้อมบอกสาเหตุ"""
    cmd = ["kubectl"] + (["-n", ns] if ns else []) + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()
        hint = ""
        if "exceeded quota" in msg:
            hint = "\nคำแนะนำ: โควตาห้องเต็ม ให้ลบ pod เก่าก่อน (kubectl get pods แล้ว kubectl delete pod ชื่อ)"
        elif "Unable to connect" in msg or "timeout" in msg.lower():
            hint = "\nคำแนะนำ: เช็กว่า Tailscale เชื่อมต่ออยู่ และเครื่อง EC2 เปิดอยู่"
        elif "Forbidden" in msg:
            hint = "\nคำแนะนำ: กำลังใช้ห้องที่ไม่มีสิทธิ์ ลองไม่ใส่ -n"
        raise BenchError(f"คำสั่ง {' '.join(cmd)} ล้มเหลว:\n{msg}{hint}")
    return r


def preflight(ns):
    """เช็กความพร้อมก่อนเริ่มวัด"""
    if shutil.which("kubectl") is None:
        raise BenchError("ไม่พบ kubectl ในเครื่อง ให้ติดตั้งตามคู่มือในแท็บ จากน้อง คลอด ก่อน")
    kubectl(["get", "pods"], ns)  # เช็กว่าเชื่อมต่อ cluster และเข้าห้องได้


def make_pod(name, runtime, image, ns, command=None):
    """สร้าง pod แบบ runc หรือ kata"""
    args = ["run", name, f"--image={image}", "--restart=Never"]
    if runtime == "kata":
        args.append(f"--overrides={KATA_OVERRIDE}")
    if command:
        args += ["--"] + command
    kubectl(args, ns)


def wait_ready(name, ns):
    kubectl(["wait", "--for=condition=Ready", f"pod/{name}", f"--timeout={READY_TIMEOUT}"], ns)


def delete_pod(name, ns, wait=True):
    """ลบ pod เงียบ ๆ (ถ้าไม่มีอยู่ก็ไม่เป็นไร)"""
    kubectl(["delete", "pod", name, "--ignore-not-found", f"--wait={'true' if wait else 'false'}"], ns, check=False)


def check_runtime(name, runtime, ns):
    """ยืนยันว่า pod ใช้ runtime ที่ตั้งใจจริง กันกรณีตั้งค่าผิดแล้ววัดผิดแบบ"""
    r = kubectl(["get", "pod", name, "-o", "jsonpath={.spec.runtimeClassName}"], ns)
    actual = r.stdout.strip() or "runc"
    if actual != runtime:
        raise BenchError(f"pod {name} ใช้ runtime '{actual}' ไม่ใช่ '{runtime}' ตามที่ตั้งใจ จึงหยุดการวัด")


def bench_start(runtime, rounds, ns):
    """วัดเวลาตั้งแต่สั่งสร้าง pod จนพร้อมใช้งาน รอบ 0 เป็นรอบอุ่นเครื่องและไม่นับ"""
    results = []
    tag = datetime.now().strftime("%H%M%S")
    for i in range(rounds + 1):
        name = f"bench-start-{runtime}-{tag}-{i}"
        try:
            t0 = time.perf_counter()
            make_pod(name, runtime, START_IMAGE, ns)
            wait_ready(name, ns)
            sec = time.perf_counter() - t0
            check_runtime(name, runtime, ns)
        finally:
            delete_pod(name, ns, wait=True)  # ลบทุกรอบ แม้รอบนั้นจะพัง
        if i == 0:
            print(f"  รอบอุ่นเครื่อง: {sec:.3f} วินาที (ไม่นับ)")
        else:
            results.append(sec)
            print(f"  รอบ {i}: {sec:.3f} วินาที")
    return results


def bench_cpu(runtime, rounds, ns):
    """วัดเวลาที่ใช้คำนวณ md5 ของข้อมูล 1 GB ภายใน pod เดียว"""
    results = []
    name = f"bench-cpu-{runtime}-{datetime.now().strftime('%H%M%S')}"
    try:
        make_pod(name, runtime, CPU_IMAGE, ns, command=["sleep", "3600"])
        wait_ready(name, ns)
        check_runtime(name, runtime, ns)
        for i in range(1, rounds + 1):
            t0 = time.perf_counter()
            kubectl(["exec", name, "--", "sh", "-c", CPU_WORK], ns)
            sec = time.perf_counter() - t0
            results.append(sec)
            print(f"  รอบ {i}: {sec:.3f} วินาที")
    finally:
        delete_pod(name, ns, wait=False)
    return results


def save(test, runtime, results, ns):
    """บันทึกผลเป็น CSV พร้อมข้อมูลว่าใครวัด วัดเมื่อไร จากเครื่องอะไร"""
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(folder, f"{test}-{runtime}-{stamp}.csv")
    who = kubectl(["config", "view", "--minify", "-o", "jsonpath={.contexts[0].context.namespace}"], None, check=False).stdout.strip()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["test", "runtime", "round", "seconds", "namespace", "measured_at", "client_os"])
        for i, sec in enumerate(results, 1):
            w.writerow([test, runtime, i, f"{sec:.3f}", ns or who, stamp, platform.system()])
    return path


def main():
    p = argparse.ArgumentParser(description="วัดผลเทียบ runc กับ Kata")
    p.add_argument("test", choices=["start", "cpu"], help="start = เวลาเริ่ม pod, cpu = ความเร็ว CPU")
    p.add_argument("runtime", choices=["runc", "kata"])
    p.add_argument("rounds", type=int, nargs="?", default=None, help="จำนวนรอบ (start ค่าเริ่มต้น 10, cpu ค่าเริ่มต้น 5)")
    p.add_argument("-n", "--namespace", default=None, help="ระบุห้องเอง (ไม่ต้องใส่ถ้าใช้ไฟล์กุญแจของตัวเอง)")
    a = p.parse_args()
    rounds = a.rounds or (10 if a.test == "start" else 5)
    if rounds < 1:
        p.error("จำนวนรอบต้องมากกว่า 0")

    print(f"เริ่มวัด {a.test} แบบ {a.runtime} จำนวน {rounds} รอบ")
    try:
        preflight(a.namespace)
        fn = bench_start if a.test == "start" else bench_cpu
        results = fn(a.runtime, rounds, a.namespace)
    except BenchError as e:
        print(f"\n❌ หยุดการวัด: {e}\nไม่ได้บันทึกผลรอบนี้", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ ยกเลิกโดยผู้ใช้ ไม่ได้บันทึกผลรอบนี้", file=sys.stderr)
        sys.exit(130)

    path = save(a.test, a.runtime, results, a.namespace)
    sd = statistics.stdev(results) if len(results) > 1 else 0.0
    print(f"\n✅ เสร็จแล้ว: เฉลี่ย {statistics.mean(results):.3f} วินาที "
          f"(ต่ำสุด {min(results):.3f}, สูงสุด {max(results):.3f}, SD {sd:.3f})")
    print(f"บันทึกผลที่ {path}")


if __name__ == "__main__":
    main()
