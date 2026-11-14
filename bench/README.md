# bench — วัดผล runc เทียบกับ Kata (หัวข้อ B3)

เราวัด 3 อย่างเพื่อดูว่า Kata ต้อง "จ่าย" อะไรบ้างแลกกับความปลอดภัยที่เพิ่มขึ้น

| วัดอะไร | สคริปต์ | ใครรัน | รันที่ไหน |
|---|---|---|---|
| เวลาเริ่ม pod | `bench.py start` | pooad | เครื่องตัวเอง (Windows/Mac/Linux) |
| ความเร็ว CPU | `bench.py cpu` | pooad | เครื่องตัวเอง |
| RAM ที่ใช้จริง | `bench-mem.sh` | james | worker (ต้องใช้ SSH) |

## ระบบทำงานอย่างไร

```mermaid
flowchart LR
    subgraph you["เครื่องของเรา"]
        B["bench.py<br/>(start / cpu)"]
    end
    subgraph master["kata-master"]
        API["K3s API"]
    end
    subgraph worker["kata-worker-1"]
        R["pod แบบ runc<br/>รันบนเคอร์เนลของ worker"]
        subgraph VM["VM ของ Kata"]
            K["pod แบบ kata<br/>มีเคอร์เนลของตัวเอง"]
        end
        M["bench-mem.sh<br/>(วัด RAM)"]
    end
    B -- "kubectl ผ่าน Tailscale" --> API
    API -- "สั่งสร้าง pod" --> R
    API -- "สั่งสร้าง pod" --> K
    M -. "อ่าน RAM ของ process" .-> R
    M -. "อ่าน RAM ของ process" .-> K
    B -- "บันทึก" --> CSV[("results/*.csv")]
```

`bench.py` สั่งสร้าง pod ผ่าน kubectl แล้วจับเวลา ส่วน RAM ต้องดูจากในเครื่อง worker โดยตรง จึงใช้ `bench-mem.sh` ที่รันบน worker

## ใช้ pod ตั้งแต่สร้างจนลบ (ทุกคน)

ให้เปลี่ยน `dev-pooad` เป็น namespace ของตัวเอง และ `test` เป็นชื่อ pod ที่ต้องการ

```bash
# 1) สร้าง pod
kubectl run test -n dev-pooad --image=nginx:alpine                    # แบบ runc
kubectl run test -n dev-pooad --image=nginx:alpine \
  --overrides='{"spec":{"runtimeClassName":"kata"}}'                  # แบบ kata

# 2) รอจนพร้อม แล้วเช็กสถานะ
kubectl wait -n dev-pooad --for=condition=Ready pod/test
kubectl get pods -n dev-pooad

# 3) ใช้งาน
kubectl exec -it test -n dev-pooad -- sh           # เข้าไปใน pod (พิมพ์ exit เพื่อออก)
kubectl exec test -n dev-pooad -- free -m          # ดู RAM ในมุมของ pod
kubectl logs test -n dev-pooad                     # ดู log
kubectl describe quota -n dev-pooad                # ดูว่าใช้โควตาไปเท่าไร

# 4) ลบเมื่อใช้เสร็จ (สำคัญ)
kubectl delete pod test -n dev-pooad
```

**ทำไมต้องลบ:** แต่ละ namespace มีโควตา 1Gi และสร้างได้สูงสุด 5 pod โดย pod แบบ Kata 1 ตัวจอง 288Mi (ตัวแอป 128Mi + VM 160Mi) และเมื่อนับ CPU (50m + overhead 100m = 150m ต่อตัว จากโควตา 400m) จะเปิด Kata ได้แค่ 2 ตัวต่อห้อง อีกทั้ง pod ที่เปิดค้างไว้ยังกิน RAM ของ worker และทำให้ผลวัดของคนอื่นเพี้ยนได้

**ข้อยกเว้น:** `bench.py` สร้างและลบ pod ให้เองอัตโนมัติ จึงไม่ต้องลบเอง

**ถ้าลืมลบหรือสร้างไม่ขึ้น** (`exceeded quota`) ให้ดูว่ามี pod อะไรค้างอยู่ด้วย `kubectl get pods -n dev-pooad` แล้วลบตัวที่ไม่ใช้ทิ้ง

## ใช้งาน `bench.py` (pooad)

สิ่งที่ต้องมีคือ Python 3 และ kubeconfig ของตัวเอง (บน Windows ติดตั้ง Python ด้วย `winget install -e --id Python.Python.3.12`)

```bash
python3 bench.py start runc      # Windows พิมพ์ python แทน python3
python3 bench.py start kata
python3 bench.py cpu runc
python3 bench.py cpu kata
```

ค่าตั้งต้นคือ start 10 รอบ และ cpu 5 รอบ ถ้าต้องการกำหนดเอง ให้ใส่ `-n` ตามด้วย namespace และใส่จำนวนรอบต่อท้าย เช่น `python3 bench.py start kata 20 -n dev-pooad`

สคริปต์จะแสดงค่า mean/min/max/SD และบันทึกผลลง `results/<test>-<runtime>-<เวลา>.csv` ถ้ารันพังหรือกด Ctrl+C จะไม่บันทึกผล

## ใช้งาน `bench-mem.sh` (james)

```bash
# 1) Mac: สร้าง pod 1 ตัว (ถ้าวัด kata ให้เพิ่ม --overrides)
kubectl run mem-test -n dev-james --image=nginx:alpine \
  --overrides='{"spec":{"runtimeClassName":"kata"}}'
kubectl wait -n dev-james --for=condition=Ready pod/mem-test

# 2) worker: ssh เข้าไป รอจนขึ้น prompt แล้วรัน
./bench-mem.sh kata        # หรือ runc

# 3) Mac: ลบ pod
kubectl delete pod mem-test -n dev-james
```

ระหว่างวัด บน worker ต้องมี pod แบบที่วัด**รันอยู่ตัวเดียว** ถ้าหา process ไม่เจอ สคริปต์จะหยุดโดยไม่บันทึกผล

## ผลทดลองเบื้องต้น (ทดลอง 2 รอบ ผลจริงอยู่ในโฟลเดอร์ `final/`)

| | runc | kata | สรุป |
|---|---|---|---|
| เวลาเริ่ม pod | ~2.2 s | ~3.6 s | kata ช้ากว่า ~1.4 s เพราะต้องบูต VM |
| CPU (md5 1 GB) | ~6.3 s | ~6.0 s | ใกล้เคียงกัน ยังสรุปไม่ได้ |
| RAM | 11.9 MB | 279.1 MB | kata ใช้มากกว่า ~23 เท่า |

## กติกา
- ห้าม commit kubeconfig, `.pem` หรือ token ขึ้น GitHub
- ระหว่างวัด อย่ารันงานหนักอื่นบน cluster
- ถ้าเจอ error `localhost:8080` แปลว่ารัน kubectl ผิดเครื่อง ให้รันบนเครื่องตัวเองหรือ master