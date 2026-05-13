my-excel-app/
├── app.py              # โค้ดหลักของ Flask
├── templates/
│   └── index.html      # หน้าจอแสดงผล
├── uploads/            # โฟลเดอร์พักไฟล์ชั่วคราว
├── Dockerfile          # สำหรับสร้าง Container
├── docker-compose.yml  # สำหรับรันระบบ
└── requirements.txt    # รายการ Library ที่ต้องใช้


<!-- สร้าง db ใน postgresql -->
docker exec -it postgres-db psql -U admincomp -d postgres -c "CREATE DATABASE yamdb;"

docker compose up -d
<!-- -------------------------------------------------- -->
1. ตรวจสอบสถานะการทำงาน
ลองเช็คดูว่า Container รันอยู่อย่างเสถียรหรือไม่ (ไม่ติด Error loop เรื่องการต่อ Database):
docker ps | grep excel-import-service
หรือดู Log เพื่อความแน่ใจว่าเชื่อมต่อ yamdb สำเร็จ:
docker logs -f excel-import-service
ถ้าเห็นข้อความ * Debug mode: on และ * Running on [http://0.0.0.0:5000](http://0.0.0.0:5000) แสดงว่าพร้อมใช้งานแล้ว



docker compose restart