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
    """Redirect to attendance page"""
    return redirect(url_for('attendance'))

# 출석 관련 함수들
def check_attendance(student_id, admin_override=False):
    """
    Check if the student has already attended this week or has an active warning
    Returns tuple:
      (already_attended, last_attendance_date, is_warned, warning_info)
      
    이미 출석했거나 경고를 받은 학생은 출석을 제한함
    
    admin_override: 관리자 수동 추가 시 체크를 건너뛰는 옵션
    """
    # 학생 경고 여부 확인 - 임시 비활성화
    is_warned = False
    warning_info = None
    
    # 이번 주 출석 여부 확인
    try:
        # 오늘 날짜로 해당 주의 월요일 계산 (한국 시간 기준)
        now = datetime.now(KST)
        today = now.date()
        days_since_monday = today.weekday()  # 0=월요일, 1=화요일, ..., 6=일요일
        monday = today - timedelta(days=days_since_monday)
        
        # 방학 중에는 한 달에 한 번 출석 가능하도록 수정 가능
        # month_start = today.replace(day=1)
        
        # 모든 출석 기록 로드
        attendances = load_attendance()
        
        # 이번 주에 이미 출석했는지 확인 (월~일 기준 주간 체크)
        this_week_attendance = None
        
        for attendance in attendances:
            # 학번 체크
            if attendance.get('student_id') != student_id:
                continue
                
            # 날짜 파싱
            attendance_date = attendance.get('date')
            if isinstance(attendance_date, str):
                try:
                    if 'T' in attendance_date:
                        attendance_date = datetime.fromisoformat(attendance_date).date()
                    else:
                        attendance_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()
                except ValueError:
                    continue
            elif hasattr(attendance_date, 'timestamp'):
                # Firebase Timestamp 객체인 경우
                attendance_date = datetime.fromtimestamp(attendance_date.timestamp()).date()
            else:
                # 알 수 없는 타입이면 스킵
                continue
                
            # 이번 주 출석인지 체크 (월요일 이후 출석)
            if attendance_date >= monday:
                this_week_attendance = attendance
                break
                
        if this_week_attendance and not admin_override:
            return (True, this_week_attendance.get('date'), is_warned, warning_info)
            
        return (False, None, is_warned, warning_info)
    except Exception as e:
        logging.error(f"출석 체크 중 오류 발생: {e}")
        # 오류 발생시 출석 허용 (오류 때문에 학생이 피해받지 않도록)
        return (False, None, False, None)

def get_current_period_attendance_count():
    """
    현재 교시의 출석 인원 수를 반환하는 함수
    - 현재 교시에 출석한 사람들의 수를 계산
    - 최대 인원 초과 여부 확인에 사용됨
    """
    try:
        now = datetime.now(KST)
        today = now.date().strftime('%Y-%m-%d')
        current_period = get_current_period()
        
        # 시간대 외인 경우 0 반환
        if current_period < 1:  # -1, 0인 경우
            return 0
            
        period_text = f"{current_period}교시"
        count = 0
        
        # 오늘 날짜의 모든 출석 중에서 현재 교시 출석만 카운트
        all_attendances = load_attendance()
        for attendance in all_attendances:
            # 출석일 문자열 추출 (날짜만)
            date_str = attendance.get('date_only', '')
            
            # 오늘 날짜와 현재 교시 일치 여부 확인
            if date_str == today and attendance.get('period') == period_text:
                count += 1
                
        return count
    except Exception as e:
        logging.error(f"현재 교시 출석 인원 계산 중 오류: {e}")
        return 0  # 오류 발생 시 0 반환

@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
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
        
        # 학생 데이터 로드
        student_data = load_student_data()
        student_info = student_data.get(student_id)
        
        # 학번 검증
        if not student_info:
            flash("❌ 학번이 올바르지 않습니다. 다시 확인해주세요.", "danger")
            return redirect(url_for('attendance'))
            
        name = student_info[0]
        seat = student_info[1]
        
        # 출석 가능 여부 확인 (이미 출석했거나 경고를 받은 경우)
        already_attended, last_attendance_date, is_warned, warning_info = check_attendance(student_id)
        
        # 현재 교시의 출석 인원 수 확인 (최대 35명)
        MAX_CAPACITY = 35
        current_count = get_current_period_attendance_count()
        
        if current_period == 0:
            flash("⚠️ 지금은 도서실 이용 시간이 아닙니다.", "danger")
            return redirect(url_for('attendance'))
        elif current_count >= MAX_CAPACITY:
            flash(f"⚠️ 도서실 수용인원이 초과되었습니다({MAX_CAPACITY}명). 4층 공강실로 올라가주세요!", "danger")
            return redirect(url_for('attendance'))
        elif already_attended:
            flash("⚠️ 이번 주에 이미 출석하셨습니다. 4층 공강실로 올라가주세요!", "warning")
            return redirect(url_for('attendance'))
        elif is_warned:
            flash("⚠️ 경고를 받은 학생입니다. 관리자에게 문의하세요.", "danger")
            return redirect(url_for('attendance'))
        else:
            # 출석 저장 (현재 교시 정보 사용)
            if save_attendance(student_id, name, seat, period_text):
                flash(f"✅ 출석이 완료되었습니다. 공강좌석번호: {seat}", "success")
            else:
                flash("❌ 출석 저장에 실패했습니다.", "danger")
            
            return redirect(url_for('attendance'))
    
    # 현재 교시의 출석 인원 수 (최대 인원 제한을 위해)
    current_count = get_current_period_attendance_count()
    MAX_CAPACITY = 35
    
    return render_template(
        'attendance.html',
        current_date=now.strftime("%Y년 %m월 %d일"),
        current_time=now.strftime("%H:%M"),
        weekday_korean=weekday_korean,
        current_period=current_period,
        period_text=period_text,
        current_count=current_count,
        max_capacity=MAX_CAPACITY
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
        
        # 원본 기록에 날짜 정보 추가 (새로운 필드는 한글 대신 영어로)
        record_copy = record.copy()
        record_copy['date_md'] = date_md
        record_copy['original_date'] = original_date  # 정렬용 원본 날짜 저장
        
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
        
        # 템플릿에서 .name, .student_id 등으로 접근할 수 있도록 필드명 수정
        student_record = {
            'name': record_copy.get('name', ''),
            'student_id': record_copy.get('student_id', ''),
            'seat': record_copy.get('seat', ''),
            'date_only': record_copy.get('date_only', ''),
            'period': record_copy.get('period', ''),
            'original_date': record_copy.get('original_date', datetime(1900, 1, 1))
        }
        period_groups[new_period_key]['학생_목록'].append(student_record)
    
    # 최근 날짜가 먼저 나오도록 정렬하고, 같은 날짜 내에서는 교시 번호가 큰 순서대로 정렬
    sorted_periods = sorted(
        period_groups.keys(), 
        key=lambda p: (
            # 날짜 추출 (기본 형식: "n월n일 m교시")
            # 각 교시에 속한 가장 최근 날짜를 기준으로 정렬 (내림차순)
            -1 * max([r['original_date'].timestamp() for r in period_groups[p]['학생_목록']]) if period_groups[p]['학생_목록'] else 0,
            # 같은 날짜면 교시 번호 내림차순 (큰 교시 먼저)
            -period_groups[p]['교시_번호']
        )
    )
    
    # 각 교시 내에서 학생을 날짜 최신순, 이름으로 정렬
    for period in period_groups:
        period_groups[period]['학생_목록'] = sorted(
            period_groups[period]['학생_목록'], 
            key=lambda r: (-r['original_date'].timestamp(), r.get('name', ''))
        )
    
    # 현재 날짜 포맷팅 (템플릿에서 사용)
    now = datetime.now(KST)
    current_date = now.strftime('%Y-%m-%d')
    
    return render_template(
        'by_period.html', 
        period_groups=period_groups, 
        sorted_periods=sorted_periods,
        current_date=current_date
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