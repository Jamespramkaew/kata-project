# คู่มือทดสอบ Web Demo (Kata vs runc)

ไปที่โฟลเดอร์ทำงาน:
```bash
cd ~/kata-project/app/k8s/Deploy
```

---

## 1. ฝั่ง runc (Container ปกติ)

### 1.1 สร้าง Pod
```bash
kubectl apply -f test-runc.yaml
```

### 1.2 เปิดดูหน้าเว็บ (Port-forward ตรงได้เลย)
```bash
kubectl port-forward deployment/test-runc 8081:8080
```
* เปิดเบราว์เซอร์: **http://localhost:8081**
* กด `Ctrl + C` เพื่อหยุด

---

## 2. ฝั่ง Kata (VM Container)

> **หมายเหตุ:** Kata ทำ port-forward ตรงๆ ไม่ได้ ต้องใช้ gateway pod (`socat`) เป็นตัวกลาง

### 2.1 สร้าง Pod
```bash
kubectl apply -f test-kata.yaml
```

### 2.2 เปิดดูหน้าเว็บ (ใช้สคริปต์อัตโนมัติ)
```bash
chmod +x port-forward-kata.sh
./port-forward-kata.sh
```
* เปิดเบราว์เซอร์: **http://localhost:8082**
* กด `Ctrl + C` เพื่อหยุด (สคริปต์จะลบ gateway pod ให้อัตโนมัติ)

---

## 3. ตรวจสอบสถานะ Pod ทั้งหมด
```bash
kubectl get pods
```

---

## 4. ลบทุกอย่างเมื่อทดสอบเสร็จ

ใช้สคริปต์ลบทั้งหมดในคำสั่งเดียว:
```bash
chmod +x cleanup.sh
./cleanup.sh
```
