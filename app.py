# ================== [IMPORTS] ==================
# 표준 라이브러리
import os
import csv
import json
import logging
from datetime import datetime, timedelta
from collections import Counter

# 외부 라이브러리
import pandas as pd
import pytz
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, jsonify, after_this_request, send_from_directory
from dotenv import load_dotenv

# Firebase 관련 라이브러리
import firebase_admin
from firebase_admin import credentials, firestore

# ================== [환경 변수 로드] ==================
# .env 파일에서 환경 변수 명시적으로 읽어오기
load_dotenv(override=True)  # 기존 환경 변수 덮어쓰기

# ====== Firebase 초기화 ======
db = None
try:
    FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if not FIREBASE_CREDENTIALS_JSON:
        raise ValueError("FIREBASE_CREDENTIALS_JSON 환경변수가 없습니다.")

    cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
    cred = credentials.Certificate(cred_dict)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    logging.info("Firebase 초기화 성공")
except Exception as e:
    logging.error(f"Firebase 초기화 실패: {e}")

# ================== [Flask 객체 생성] ==================
app = Flask(__name__)

# ================== [앱 설정] ==================
from config import Config
app.config.from_object(Config)
app.secret_key = app.config.get('SECRET_KEY', 'your_fallback_secret_here')

# ================== [시간대 설정] ==================
KST = pytz.timezone('Asia/Seoul')

# ================== [학생 데이터 캐싱] ==================
_student_data_cache = None
_last_student_data_load_time = None

def load_student_data():
    """
    Load student data from Excel file with caching
    Returns a dictionary with student_id as key and (name, seat) as value
    """
    global _student_data_cache, _last_student_data_load_time
    now = datetime.now()
    
    # 캐시 사용 - 30분 유효
    if _student_data_cache and _last_student_data_load_time and (now - _last_student_data_load_time).seconds < 1800:
        return _student_data_cache

    try:
        df = pd.read_excel('students.xlsx', dtype={'학번': str})
        student_data = {
            str(row['학번']).strip(): (row['이름'], row.get('공강좌석번호', ''))
            for _, row in df.iterrows() if pd.notna(row['학번']) and pd.notna(row['이름'])
        }
        _student_data_cache = student_data
        _last_student_data_load_time = now
        return student_data
    except Exception as e:
        logging.error(f"학생 정보 로드 실패: {e}")
        return {}

# ================== [Firebase 출석 기록 함수] ==================
def save_attendance(student_id, name, seat, period_text):
    """
    Save attendance record to Firebase (with Korean time)
    """
    try:
        now = datetime.now(KST)
        db.collection("attendances").add({
            "student_id": student_id,
            "name": name,
            "seat": seat,
            "period": period_text,
            "date": now,
            "display_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "time_only": now.strftime("%H:%M"),
            "date_only": now.strftime("%Y-%m-%d"),
        })
        return True
    except Exception as e:
        logging.error(f"출석 저장 실패: {e}")
        return False

def load_attendance():
    """
    Load all attendance records from Firebase
    Returns a list of dictionaries containing attendance records
    """
    try:
        attendances = []
        results = db.collection("attendances").order_by(
            "date", direction=firestore.Query.DESCENDING
        ).limit(500).get()
        
        for doc in results:
            data = doc.to_dict()
            data['id'] = doc.id
            
            # Firebase Timestamp를 datetime으로 변환
            if 'date' in data and hasattr(data['date'], 'timestamp'):
                date_val = data['date'].timestamp()
                data['date'] = datetime.fromtimestamp(date_val)
                
            attendances.append(data)
        
        return attendances
    except Exception as e:
        logging.error(f"출석 기록 로드 실패: {e}")
        return []

# ================== [라우트 정의] ==================
@app.route('/', methods=['GET', 'POST'])
def index():
    """Main attendance page and form submission handler"""
    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        name = request.form.get('name', '').strip()
        seat = request.form.get('seat', '').strip()
        period = request.form.get('period', '').strip()
        
        if not student_id or not name:
            flash("학번과 이름을 입력해주세요.", "danger")
            return redirect(url_for('index'))
            
        # 출석 저장
        if save_attendance(student_id, name, seat, period):
            flash("출석이 완료되었습니다.", "success")
        else:
            flash("출석 저장에 실패했습니다.", "danger")
            
        return redirect(url_for('index'))
        
    return render_template('index.html')

@app.route('/lookup_name')
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

@app.route('/list')
def list_attendance():
    """List all attendance records"""
    records = load_attendance()
    return render_template('list.html', records=records)

if __name__ == '__main__':
    app.run(debug=True)