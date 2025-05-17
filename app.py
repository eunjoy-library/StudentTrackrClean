# ================== [IMPORTS] ==================
# 표준 라이브러리
import os
import csv
import json
import logging
from datetime import datetime, timedelta, time
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

# ================== [교시 계산] ==================
def get_current_period():
    """
    Determine the current class period based on current time (Korean time)
    Returns period number (1-10), -1 for time outside scheduled periods, or 0 for 4th period
    
    -1 = 시간 외 (모든 시간대에 출석 허용)
    0  = 4교시 (출석 불가)
    1~10 = 해당 교시
    """
    now = datetime.now(KST)
    weekday = now.weekday()  # 0=월요일, 1=화요일, ..., 6=일요일
    current_time = now.time()
    
    # 주말은 시간 외로 처리
    if weekday >= 5:  # 토요일(5) 또는 일요일(6)
        return -1
    
    # 시간대별 교시 정의
    time_table = [
        (time(7, 50), time(9, 15), 1),    # 1교시: 07:50-09:15
        (time(9, 15), time(10, 40), 2),   # 2교시: 09:15-10:40
        (time(10, 40), time(12, 5), 3),   # 3교시: 10:40-12:05
        (time(12, 5), time(12, 30), 0),   # 4교시: 12:05-12:30 (출석 불가)
        (time(12, 30), time(14, 25), 5),  # 5교시: 12:30-14:25
        (time(14, 25), time(15, 50), 6),  # 6교시: 14:25-15:50
        (time(15, 50), time(17, 15), 7),  # 7교시: 15:50-17:15
        (time(17, 15), time(18, 40), 8),  # 8교시: 17:15-18:40
        (time(18, 40), time(20, 5), 9),   # 9교시: 18:40-20:05
        (time(20, 5), time(21, 30), 10),  # 10교시: 20:05-21:30
    ]
    
    # 현재 시간에 맞는 교시 찾기
    for start_time, end_time, period in time_table:
        if start_time <= current_time < end_time:
            return period
    
    # 시간표에 없는 시간은 시간 외로 처리
    return -1

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
    # 현재 시간과 교시 정보 계산
    now = datetime.now(KST)
    current_period = get_current_period()
    weekday_korean = ['월', '화', '수', '목', '금', '토', '일'][now.weekday()]
    
    # 교시 텍스트 생성
    if current_period == -1:
        period_text = "시간 외"
    elif current_period == 0:
        period_text = "4교시 (도서실 이용 불가)"
    else:
        period_text = f"{current_period}교시"
    
    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        name = request.form.get('name', '').strip()
        seat = request.form.get('seat', '').strip()
        
        if not student_id or not name:
            flash("학번과 이름을 입력해주세요.", "danger")
            return redirect(url_for('index'))
            
        # 출석 저장 (현재 교시 정보 사용)
        if save_attendance(student_id, name, seat, period_text):
            flash("출석이 완료되었습니다.", "success")
        else:
            flash("출석 저장에 실패했습니다.", "danger")
            
        return redirect(url_for('index'))
    
    # 현재 교시의 출석 인원 수 (최대 인원 제한을 위해)    
    return render_template(
        'index.html',
        current_date=now.strftime("%Y년 %m월 %d일"),
        current_time=now.strftime("%H:%M"),
        weekday_korean=weekday_korean,
        current_period=current_period,
        period_text=period_text
    )

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

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    # 이미 로그인 되어 있으면 교시별 출석현황 페이지로 바로 리다이렉트
    if session.get('admin'):
        return redirect('/by_period')
        
    if request.method == 'POST':
        password = request.form.get('password')
        if password == "1234":  # 관리자 비밀번호
            session['admin'] = True
            return redirect('/by_period')
        else:
            flash('❌ 비밀번호가 틀렸습니다.', "danger")
    return render_template('admin_login.html')

@app.route('/by_period')
def by_period():
    """교시별 출석 현황 보기 (admin only)"""
    if not session.get('admin'):
        flash("관리자 로그인이 필요합니다.", "danger")
        return redirect('/admin')
        
    records = load_attendance()
    
    # 교시별로만 학생 데이터 그룹화
    period_groups = {}
    
    for record in records:
        period = record.get('period', '시간 외')
        date = record.get('date_only', '날짜 없음')
        
        # 날짜 형식 변환 (YYYY-MM-DD -> n월n일) - 시, 분, 초 제거
        if date != '날짜 없음':
            try:
                # 날짜 객체로 변환
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                # 월, 일만 표시 (n월n일 형식)
                date_md = f"{date_obj.month}월{date_obj.day}일"
                # 원래 날짜도 저장 (정렬용)
                original_date = date_obj
                # 메모 검색을 위한 원본 날짜 문자열
                original_date_str = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                date_md = date
                original_date = datetime(1900, 1, 1)  # 날짜 변환 실패시 고정 날짜로
                original_date_str = date
        else:
            date_md = date
            original_date = datetime(1900, 1, 1)  # 날짜 없음은 고정 날짜로
            original_date_str = date
        
        # 원본 기록에 날짜 정보 추가
        record_copy = record.copy()
        record_copy['날짜_md'] = date_md
        record_copy['원본_날짜'] = original_date  # 정렬용 원본 날짜 저장
        
        # 날짜와 교시를 조합하여 키 생성 (예: "5월7일 6교시")
        period_num = int(period[0]) if period and period[0].isdigit() else 999
        
        # 교시만 키로 사용하는 것이 아니라, 날짜+교시로 새로운 키 생성
        new_period_key = f"{date_md} {period}"
        
        if new_period_key not in period_groups:
            period_groups[new_period_key] = {
                '학생_목록': [],
                '교시_번호': period_num,
                '날짜': original_date_str,
                '교시': period
            }
        
        period_groups[new_period_key]['학생_목록'].append(record_copy)
    
    # 최근 날짜가 먼저 나오도록 정렬하고, 같은 날짜 내에서는 교시 번호가 큰 순서대로 정렬
    sorted_periods = sorted(
        period_groups.keys(), 
        key=lambda p: (
            # 날짜 추출 (기본 형식: "n월n일 m교시")
            # 각 교시에 속한 가장 최근 날짜를 기준으로 정렬 (내림차순)
            -1 * max([r['원본_날짜'].timestamp() for r in period_groups[p]['학생_목록']]) if period_groups[p]['학생_목록'] else 0,
            # 같은 날짜면 교시 번호 내림차순 (큰 교시 먼저)
            -period_groups[p]['교시_번호']
        )
    )
    
    # 각 교시 내에서 학생을 날짜 최신순, 이름으로 정렬
    for period in period_groups:
        period_groups[period]['학생_목록'] = sorted(
            period_groups[period]['학생_목록'], 
            key=lambda r: (-r['원본_날짜'].timestamp(), r.get('name', ''))
        )
    
    return render_template(
        'by_period.html', 
        period_groups=period_groups, 
        sorted_periods=sorted_periods
    )

@app.route('/stats')
def stats():
    """Show attendance statistics (admin only)"""
    if not session.get('admin'):
        flash("관리자 로그인이 필요합니다.", "danger")
        return redirect('/admin')
    records = load_attendance()
    counts = Counter(r['name'] for r in records)
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return render_template('stats.html', attendance_counts=sorted_counts)

@app.route('/logout')
def logout():
    """Logout from admin"""
    session.pop('admin', None)
    flash('로그아웃 되었습니다.', 'info')
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)