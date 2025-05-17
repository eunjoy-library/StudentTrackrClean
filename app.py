from flask import Flask, render_template, request, redirect, flash, url_for, jsonify
from models import db, Attendance
from config import Config
import pandas as pd
import os

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()

# 학생 데이터 캐싱
_student_data_cache = None

def load_student_data():
    """
    Load student data from Excel file with caching
    Returns a dictionary with student_id as key and (name, seat) as value
    """
    global _student_data_cache
    if _student_data_cache is not None:
        return _student_data_cache

    try:
        df = pd.read_excel('students.xlsx', dtype={'학번': str})
        student_data = {
            str(row['학번']).strip(): (row['이름'], row.get('공강좌석번호', ''))
            for _, row in df.iterrows() if pd.notna(row['학번']) and pd.notna(row['이름'])
        }
        _student_data_cache = student_data
        return student_data
    except Exception as e:
        print(f"학생 정보 로드 실패: {e}")
        return {}

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        student_id = request.form["student_id"]
        name = request.form["name"]
        seat = request.form["seat"]
        period = request.form["period"]
        Attendance.add_attendance(student_id, name, seat, period)
        flash("출석이 완료되었습니다.")
        return redirect("/")
    return render_template("index.html")

@app.route("/lookup_name")
def lookup_name():
    """학생 정보 조회 API"""
    student_id = request.args.get('student_id', '').strip()
    if not student_id:
        return jsonify({"error": "학번이 입력되지 않았습니다."}), 400
    
    student_data = load_student_data()
    student = student_data.get(student_id)
    
    if not student:
        return jsonify({"error": "존재하지 않는 학번입니다."}), 404
    
    return jsonify({
        "name": student[0],
        "seat": student[1]
    })

@app.route("/list")
def list_attendance():
    records = Attendance.query.order_by(Attendance.date.desc()).all()
    return render_template("list.html", records=records)

if __name__ == "__main__":
    app.run()