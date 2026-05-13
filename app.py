import os
from flask import Flask, render_template, request, redirect, flash, send_file, url_for
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import io
from dotenv import load_dotenv
from urllib.parse import quote_plus

# โหลดค่าจาก .env
load_dotenv()

app = Flask(__name__)
app.secret_key = "yam_reporter_secret_key"

# การตั้งค่าฐานข้อมูล
user = os.getenv("POSTGRES_USER")
password = os.getenv("POSTGRES_PASSWORD")
safe_password = quote_plus(password)
host = os.getenv("POSTGRES_HOST")
port = os.getenv("POSTGRES_PORT")
db_name = os.getenv("POSTGRES_DB")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"postgresql://{user}:{safe_password}@{host}:{port}/{db_name}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class CheckpointRecord(db.Model):
    __tablename__ = "checkpoint_logs"
    id = db.Column(db.Integer, primary_key=True)
    check_date = db.Column(db.String(50))
    check_time = db.Column(db.String(50))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


with app.app_context():
    db.create_all()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename.lower().endswith((".xlsx", ".xls")):
            try:
                try:
                    file.seek(0)
                    df_all = pd.read_excel(file, header=None)
                except:
                    file.seek(0)
                    tables = pd.read_html(file)
                    df_all = tables[0]

                header_row = 0
                for i, row in df_all.iterrows():
                    if "วันที่" in row.values:
                        header_row = i
                        break

                df = df_all.iloc[header_row + 1 :].copy()
                df.columns = [str(c).strip() for c in df_all.iloc[header_row].values]

                new_count = 0
                for _, row in df.iterrows():
                    detail_val = row.get("รายละเอียด")
                    if pd.notnull(detail_val):
                        detail_str = str(detail_val).strip()
                        if detail_str.isdigit():
                            d_val = str(row.get("วันที่", ""))
                            t_val = str(row.get("เวลา", ""))

                            exists = CheckpointRecord.query.filter_by(
                                check_date=d_val,
                                check_time=t_val,
                                description=detail_str,
                            ).first()

                            if not exists:
                                log_entry = CheckpointRecord(
                                    check_date=d_val,
                                    check_time=t_val,
                                    description=detail_str,
                                )
                                db.session.add(log_entry)
                                new_count += 1

                db.session.commit()
                flash(f"นำเข้าสำเร็จ {new_count} รายการ", "success")
                return redirect(url_for("index"))  # Redirect เพื่อให้แสดงข้อมูลล่าสุด

            except Exception as e:
                db.session.rollback()
                flash(f"Error: {str(e)}", "danger")

    # ดึงข้อมูล 50 รายการล่าสุดมาแสดงในหน้าแรกเสมอ (แก้ปัญหา Index หาย)
    recent_logs = (
        CheckpointRecord.query.order_by(CheckpointRecord.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template("index.html", logs=recent_logs)


@app.route("/report")
def report():
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    where_clause = ""
    params = {}

    # คำนวณวันที่ ค.ศ. (CE) เพื่อใช้กรองและจัดกลุ่ม
    date_expr = "(TO_DATE(check_date, 'DD/MM/YYYY') - INTERVAL '543 years')::date"

    if start_date and end_date:
        where_clause = (
            f"WHERE {date_expr} BETWEEN CAST(:start AS DATE) AND CAST(:end AS DATE)"
        )
        params = {"start": start_date, "end": end_date}
    elif start_date:
        where_clause = f"WHERE {date_expr} >= CAST(:start AS DATE)"
        params = {"start": start_date}
    elif end_date:
        where_clause = f"WHERE {date_expr} <= CAST(:end AS DATE)"
        params = {"end": end_date}

    query = f"""
        SELECT 
            check_date,
            {date_expr} AS ce_date,
            -- ดึงเลขชั่วโมงออกมาตรงๆ ไม่มีการปัดเศษ
            EXTRACT(HOUR FROM CAST(check_time AS TIME)) AS hour_group,
            MAX(CASE WHEN description = '1' THEN check_time END) AS p1,
            MAX(CASE WHEN description = '2' THEN check_time END) AS p2,
            MAX(CASE WHEN description = '3' THEN check_time END) AS p3,
            MAX(CASE WHEN description = '4' THEN check_time END) AS p4,
            MAX(CASE WHEN description = '5' THEN check_time END) AS p5,
            MAX(CASE WHEN description = '6' THEN check_time END) AS p6,
            MAX(CASE WHEN description = '7' THEN check_time END) AS p7
        FROM checkpoint_logs
        {where_clause}
        GROUP BY check_date, {date_expr}, hour_group
        ORDER BY {date_expr} DESC, hour_group ASC
    """

    result = db.session.execute(db.text(query), params)
    return render_template(
        "report.html", reports=result, start_date=start_date, end_date=end_date
    )


@app.route("/export")
def export_excel():
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    where_clause = ""
    params = {}
    # check_date เก็บวันที่แบบ พ.ศ. (เช่น 6/8/2568) ต้องลบ 543 ปี เพื่อเปรียบเทียบกับ ค.ศ. จาก input type=date
    date_expr = "(TO_DATE(check_date, 'DD/MM/YYYY') - INTERVAL '543 years')::date"
    if start_date and end_date:
        where_clause = (
            f"WHERE {date_expr} BETWEEN CAST(:start AS DATE) AND CAST(:end AS DATE)"
        )
        params = {"start": start_date, "end": end_date}
    elif start_date:
        where_clause = f"WHERE {date_expr} >= CAST(:start AS DATE)"
        params = {"start": start_date}
    elif end_date:
        where_clause = f"WHERE {date_expr} <= CAST(:end AS DATE)"
        params = {"end": end_date}

    query = f"""
        SELECT 
            check_date AS "วันที่ตรวจ",
            {date_expr} AS "วันที่(ค.ศ.)",
            EXTRACT(HOUR FROM (CAST(check_time AS TIME) + interval '30 minutes')) AS "ชั่วโมง",
            MAX(CASE WHEN description = '1' THEN check_time END) AS "จุด 1",
            MAX(CASE WHEN description = '2' THEN check_time END) AS "จุด 2",
            MAX(CASE WHEN description = '3' THEN check_time END) AS "จุด 3",
            MAX(CASE WHEN description = '4' THEN check_time END) AS "จุด 4",
            MAX(CASE WHEN description = '5' THEN check_time END) AS "จุด 5",
            MAX(CASE WHEN description = '6' THEN check_time END) AS "จุด 6",
            MAX(CASE WHEN description = '7' THEN check_time END) AS "จุด 7"
            
        FROM checkpoint_logs
        {where_clause}
        GROUP BY 1, 2, 3
        ORDER BY {date_expr} DESC, 3 ASC
    """

    df = pd.read_sql(db.text(query), db.engine, params=params)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Checkpoint_Report")

    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="checkpoint_report.xlsx",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
