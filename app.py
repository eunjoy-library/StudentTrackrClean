import os
import json
import logging
from datetime import datetime, timedelta, time
from collections import Counter

import pytz
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from dotenv import load_dotenv

# Firebase 관련 라이브러리
import firebase_admin
from firebase_admin import credentials, firestore

# 환경 변수 로드
load_dotenv(override=True)

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

# Firebase 초기화
db = None
try:
    FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if not FIREBASE_CREDENTIALS_JSON:
        raise ValueError("FIREBASE_CREDENTIALS_JSON 환경변수가 없습니다.")
    
    # JSON 문자열을 딕셔너리로 변환
    firebase_config = json.loads(FIREBASE_CREDENTIALS_JSON)
    
    # Firebase 인증 정보 생성
    cred = credentials.Certificate(firebase_config)
    
    # Firebase 앱 초기화 (이미 초기화되었는지 확인)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    
    # Firestore 클라이언트 설정
    db = firestore.client()
    print("Firebase 초기화 성공")
except Exception as e:
    print(f"Firebase 초기화 오류: {e}")

# 로깅 설정    
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Flask 앱 초기화
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key")

# 캐싱을 위한 전역 변수
_student_data_cache = None
_last_student_data_load_time = None

# ================== [UTILITY 함수] ==================
def get_current_period():
    """
    현재 시간 기준으로 교시를 결정하는 함수
    1교시: 7:50 - 9:15
    2교시: 9:15 - 10:40
    3교시: 10:40 - 12:05
    4교시: 12:05 - 12:30
    5교시: 12:30 - 14:25
    6교시: 14:25 - 15:50
    
    Returns:
        int: 1~10 교시, -1 (시간 외), 0 (4교시)
    """
    now = datetime.now(KST)
    current_time = now.time()
    
    # 요일이 토요일(5) 또는 일요일(6)인 경우 시간 외로 처리
    if now.weekday() > 4:  # 토요일(5), 일요일(6)
        return -1
    
    # 교시 시간대 정의
    periods = [
        (time(7, 50), time(9, 15), 1),   # 1교시
        (time(9, 15), time(10, 40), 2),  # 2교시
        (time(10, 40), time(12, 5), 3),  # 3교시
        (time(12, 5), time(12, 30), 0),  # 4교시 (도서실 이용 불가 시간)
        (time(12, 30), time(14, 25), 5), # 5교시
        (time(14, 25), time(15, 50), 6)  # 6교시
    ]
    
    # 현재 시간이 어느 교시에 해당하는지 확인
    for start, end, period in periods:
        if start <= current_time < end:
            return period
    
    # 어느 교시에도 해당하지 않으면 시간 외로 처리
    return -1

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
        # 엑셀 파일에서 학생 정보 읽기
        try:
            df = pd.read_excel('students.xlsx', dtype={'학번': str})
            student_data = {
                str(row['학번']).strip(): (row['이름'], row.get('공강좌석번호', ''))
                for _, row in df.iterrows() if row['학번'] and row['이름']
            }
        except Exception as excel_error:
            logging.error(f"엑셀 파일 읽기 실패: {excel_error}")
            # 임시 학생 데이터 제공 (테스트용)
            student_data = {
                "10307": ("박지호", "387"),
                "20101": ("강지훈", "331"),
                "30107": ("김리나", "175"),
                "30207": ("김유담", "281"),
                "20240101": ("홍길동", "A1"),
                # 추가 데이터...
            }
            
        _student_data_cache = student_data
        _last_student_data_load_time = now
        return student_data
    except Exception as e:
        logging.error(f"학생 데이터 로딩 중 오류: {e}")
        return {}

def save_attendance(student_id, name, seat, period_text):
    """
    Save attendance record to Firebase (with Korean time)
    """
    try:
        if not db:
            flash("Firebase 설정이 완료되지 않았습니다.", "danger")
            return False
        
        # 현재 한국 시간
        now_kst = datetime.now(KST)
        date_only = now_kst.strftime('%Y-%m-%d')
        datetime_str = now_kst.strftime('%Y-%m-%d %H:%M:%S')
        
        # Firebase에 데이터 저장
        attendance_ref = db.collection('attendances').document()
        attendance_ref.set({
            'student_id': student_id,
            'name': name,
            'seat': seat,
            'period': period_text,
            'date': datetime_str,
            'date_only': date_only,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        return True
    except Exception as e:
        logging.error(f"출석 저장 중 오류: {e}")
        return False

def load_attendance():
    """
    Load all attendance records from Firebase
    Returns a list of dictionaries containing attendance records
    """
    try:
        if not db:
            return []
        
        # Firebase에서 모든 출석 데이터 가져오기
        attendance_records = []
        attendance_refs = db.collection('attendances').order_by('timestamp', direction=firestore.Query.DESCENDING).get()
        
        for doc in attendance_refs:
            data = doc.to_dict()
            data['id'] = doc.id  # document ID 추가
            
            # 날짜 문자열 처리 (필요한 경우)
            if 'date' in data and data['date']:
                date_str = data['date']
                if isinstance(date_str, str):
                    # 이미 문자열이면 그대로 사용
                    pass
                else:
                    # Firestore Timestamp 객체인 경우 변환
                    date_str = data['date'].strftime('%Y-%m-%d %H:%M:%S')
                data['date'] = date_str
            
            attendance_records.append(data)
        
        return attendance_records
    except Exception as e:
        logging.error(f"출석 기록 로딩 중 오류: {e}")
        return []

def check_weekly_attendance_limit(student_id):
    """
    학생이 이번 주(일~토)에 1회 이상 출석했는지 확인
    
    Returns:
        (exceeded, count, recent_dates): 
        - exceeded: 주 1회 초과 여부 (True/False) - 1회 이미 있으면 True
        - count: 이번 주 출석 횟수
        - recent_dates: 최근 출석 날짜 목록
    """
    try:
        if not db:
            logging.error("Firebase DB 연결이 설정되지 않았습니다.")
            return False, 0, []
        
        # 현재 날짜 기준으로 이번 주의 월요일 찾기
        now = datetime.now(KST)
        weekday = now.weekday()  # 0=월요일, 1=화요일, ..., 6=일요일
        days_since_monday = weekday
        monday = now - timedelta(days=days_since_monday)
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 이번 주 토요일 끝 시간 (일요일부터 토요일까지)
        sunday = monday - timedelta(days=1)  # 일요일은 월요일 하루 전
        sunday = sunday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        saturday = monday + timedelta(days=5)  # 토요일은 월요일부터 5일 후
        saturday = saturday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Firebase에서 학생의 이번 주 출석 기록 조회
        sunday_str = sunday.strftime('%Y-%m-%d')
        saturday_str = saturday.strftime('%Y-%m-%d')
        
        logging.debug(f"학생 {student_id}의 이번 주({sunday_str} ~ {saturday_str}) 출석 기록 확인 중")
        
        try:
            # 학생 ID로 출석 기록 검색
            records = db.collection('attendances').where('student_id', '==', student_id).get()
            
            # 이번 주 출석 횟수 카운트
            count = 0
            recent_dates = []
            
            for record in records:
                data = record.to_dict()
                date_only = data.get('date_only', '')
                
                if sunday_str <= date_only <= saturday_str:
                    count += 1
                    recent_dates.append(date_only)
                    logging.debug(f"학생 {student_id}의 출석일: {date_only}")
            
            # 중복 날짜 제거 (같은 날 여러 번 출석한 경우)
            unique_dates = sorted(list(set(recent_dates)))
            
            # 주간 출석 제한 (일주일에 1번만 허용)
            # 1회까지 허용하고, 이미 1회 출석한 경우 2번째 출석을 제한
            exceeded = len(unique_dates) >= 1  # 이미 1회 출석했으면 제한
            
            logging.debug(f"학생 {student_id}의 이번 주 출석 횟수: {count}, 초과 여부: {exceeded}")
            return exceeded, count, recent_dates
            
        except Exception as db_error:
            logging.error(f"Firebase 쿼리 실행 중 오류: {db_error}")
            raise
        
    except Exception as e:
        logging.error(f"주간 출석 제한 확인 중 오류: {e}")
        return False, 0, []

# ================== [ROUTES] ==================

@app.route('/check_attendance_status')
def check_attendance_status():
    """학생의 출석 상태를 확인하는 API (주간 출석 제한용)"""
    student_id = request.args.get('student_id')
    if not student_id:
        return jsonify({'error': '학번이 필요합니다.', 'already_attended': False})
    
    try:
        # 주간 출석 상태 확인
        exceeded, count, recent_dates = check_weekly_attendance_limit(student_id)
        
        # 최근 출석일 포맷팅
        last_attendance_date = ""
        if recent_dates:
            last_attendance_date = recent_dates[0]  # 가장 최근 출석일
        
        return jsonify({
            'already_attended': exceeded,
            'attendance_count': count,
            'last_attendance_date': last_attendance_date
        })
    except Exception as e:
        logging.error(f"출석 상태 확인 중 오류: {e}")
        return jsonify({'error': str(e), 'already_attended': False})

@app.route('/')
def index():
    """Redirect to attendance page"""
    return redirect(url_for('attendance'))

@app.route('/favicon.ico')
def favicon():
    """Serve favicon.ico"""
    return send_from_directory(os.path.join(app.root_path, 'attached_assets'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

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
    
    # POST 요청 처리 (출석 폼 제출)
    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        name = request.form.get('name', '').strip()
        seat = request.form.get('seat', '').strip()
        
        if not student_id:
            flash('학번을 입력해주세요.', 'danger')
            return redirect(url_for('attendance'))
        
        # 주간 출석 제한 확인 (1회만 허용)
        exceeded, count, recent_dates = check_weekly_attendance_limit(student_id)
        if exceeded:
            # 주간 1회 초과 출석 제한
            formatted_dates = ', '.join(recent_dates)
            flash(f'주간 출석 제한 (1회/주)을 초과했습니다. 최근 출석일: {formatted_dates}', 'danger')
            return redirect(url_for('attendance'))
        
        # name과 seat이 비어있는 경우 학생 정보 찾기
        if not name or not seat:
            student_data = load_student_data()
            student_info = student_data.get(student_id)
            
            # 학생 정보가 있으면 이름과 좌석 설정
            if student_info:
                name = student_info[0]
                seat = student_info[1]
            else:
                # 테스트용 하드코딩 데이터
                test_data = {
                    "10307": {"name": "박지호", "seat": "387"},
                    "20101": {"name": "강지훈", "seat": "331"},
                    "30107": {"name": "김리나", "seat": "175"},
                    "30207": {"name": "김유담", "seat": "281"},
                    "20240101": {"name": "홍길동", "seat": "A1"}
                }
                
                if student_id in test_data:
                    name = test_data[student_id]["name"]
                    seat = test_data[student_id]["seat"]
                else:
                    flash('해당 학번의 학생 정보를 찾을 수 없습니다.', 'danger')
                    return redirect(url_for('attendance'))
        
        # 출석 정보 저장
        try:
            # 교시 텍스트 설정
            period_text_for_db = period_text
            if period_text == "4교시 (도서실 이용 불가)":
                period_text_for_db = "4교시"
            
            # 출석 정보 저장
            if save_attendance(student_id, name, seat, period_text_for_db):
                flash('출석이 성공적으로 등록되었습니다!', 'success')
            else:
                flash('출석 등록에 실패했습니다.', 'danger')
        except Exception as e:
            flash(f'출석 등록 중 오류가 발생했습니다: {str(e)}', 'danger')
        
        return redirect(url_for('attendance'))
        
    # GET 요청 처리 (출석 폼 표시)
    return render_template('simple_form.html', 
                         now=now, 
                         period_text=period_text)

@app.route('/lookup_name')
def lookup_name():
    """학생 정보 조회 API"""
    student_id = request.args.get('student_id', '').strip()
    if not student_id:
        return jsonify({'error': '학번이 없습니다.'})
    
    # 학생 데이터 로드 (Excel 파일에서)
    student_data = load_student_data()
    student_info = student_data.get(student_id)
    
    if student_info:
        # Excel 파일에서 찾은 정보 반환
        return jsonify({
            'success': True,
            'name': student_info[0],
            'seat': student_info[1]
        })
    else:
        # 테스트용 하드코딩 데이터 (Excel 파일에서 찾지 못한 경우)
        test_data = {
            "10307": {"name": "박지호", "seat": "387"},
            "20101": {"name": "강지훈", "seat": "331"},
            "30107": {"name": "김리나", "seat": "175"},
            "30207": {"name": "김유담", "seat": "281"},
            "20240101": {"name": "홍길동", "seat": "A1"}
        }
        
        if student_id in test_data:
            return jsonify({
                'success': True,
                'name': test_data[student_id]["name"],
                'seat': test_data[student_id]["seat"]
            })
            
        # 어디에서도 찾지 못한 경우
        return jsonify({'error': '학번에 해당하는 학생 정보가 없습니다.'})

@app.route('/list', methods=['GET'])
def list_attendance():
    """List all attendance records"""
    if session.get('admin'):
        current_page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        sort_by = request.args.get('sort_by', 'date')  # 기본 정렬: 날짜
        sort_direction = request.args.get('sort_direction', 'desc')  # 기본 방향: 내림차순
        
        # 모든 출석 기록 로드
        all_records = load_attendance()
        
        # 정렬 처리
        if sort_by and all_records:
            reverse = sort_direction.lower() == 'desc'
            
            def get_sort_key(record):
                value = record.get(sort_by)
                # 날짜는 특별 처리
                if sort_by == 'date':
                    try:
                        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                    except:
                        return datetime.min
                return str(value).lower() if value is not None else ""
                
            all_records = sorted(all_records, key=get_sort_key, reverse=reverse)
        
        # 간단한 페이지네이션
        total_pages = (len(all_records) + limit - 1) // limit if all_records else 1
        current_page = min(max(1, current_page), total_pages)
        start_idx = (current_page - 1) * limit
        end_idx = start_idx + limit
        paged_records = all_records[start_idx:end_idx] if all_records else []
        
        return render_template('list_simple.html', 
                              records=paged_records, 
                              current_page=current_page, 
                              total_pages=total_pages, 
                              limit=limit,
                              sort_by=sort_by,
                              sort_direction=sort_direction)
    else:
        flash('관리자 로그인이 필요합니다.', 'warning')
        return redirect(url_for('admin_login'))

@app.route('/by_period')
def by_period():
    """교시별 출석 현황"""
    if not session.get('admin'):
        flash('관리자 로그인이 필요합니다.', 'warning')
        return redirect(url_for('admin_login'))
    
    # 날짜 선택 (기본값: 오늘)
    today = datetime.now(KST).strftime('%Y-%m-%d')
    selected_date = request.args.get('date', today)
    
    # 정렬 옵션 (기본: 좌석번호 오름차순)
    sort_by = request.args.get('sort_by', 'seat')
    sort_direction = request.args.get('sort_direction', 'asc')
    
    # 모든 기록 로드
    all_records = load_attendance()
    
    # 날짜로 필터링
    day_records = [r for r in all_records if r.get('date_only') == selected_date]
    
    # 교시별로 그룹화
    grouped_records = {}
    for record in day_records:
        period = record.get('period', '기타')
        if period not in grouped_records:
            grouped_records[period] = []
        grouped_records[period].append(record)
    
    # 교시 순서대로 정렬 (1교시, 2교시 등)
    sorted_groups = {}
    period_order = ["1교시", "2교시", "3교시", "4교시", "5교시", "6교시", "7교시", "8교시", "9교시", "10교시", "시간 외", "기타"]
    
    for period in period_order:
        if period in grouped_records:
            # 각 교시 내에서 학생 정렬 적용
            students = grouped_records[period]
            
            # 정렬 기준에 따라 정렬
            if sort_by == 'seat':
                # 좌석번호 정렬 (숫자는 숫자끼리, 문자는 문자끼리)
                def seat_sort_key(student):
                    seat = student.get('seat', '')
                    if seat and seat.isdigit():
                        return (0, int(seat))  # 숫자는 앞에 배치
                    return (1, seat.lower())   # 문자는 뒤에 배치
                
                students = sorted(students, key=seat_sort_key, reverse=(sort_direction == 'desc'))
            elif sort_by == 'name':
                # 이름 정렬
                students = sorted(students, key=lambda s: s.get('name', ''), reverse=(sort_direction == 'desc'))
            elif sort_by == 'student_id':
                # 학번 정렬
                students = sorted(students, key=lambda s: s.get('student_id', ''), reverse=(sort_direction == 'desc'))
            
            sorted_groups[period] = students
    
    # 정의되지 않은 교시가 있다면 마지막에 추가
    for period in grouped_records:
        if period not in sorted_groups:
            sorted_groups[period] = grouped_records[period]
    
    # 날짜 포맷팅 (YYYY-MM-DD -> M월 D일)
    formatted_date = ''
    try:
        date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
        weekday_names = ['월', '화', '수', '목', '금', '토', '일']
        weekday = weekday_names[date_obj.weekday()]
        formatted_date = f"{date_obj.month}월 {date_obj.day}일 ({weekday})"
    except:
        formatted_date = selected_date
    
    return render_template('by_period_new.html', 
                          grouped_records=sorted_groups, 
                          today=today,
                          selected_date=formatted_date,
                          sort_by=sort_by,
                          sort_direction=sort_direction)

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == '1234':  # 임시 비밀번호 (실제 구현에서는 환경변수나 보안 저장소 사용)
            session['admin'] = True
            flash('관리자로 로그인되었습니다.', 'success')
            return redirect(url_for('by_period'))  # 교시별 보기로 바로 이동
        else:
            flash('비밀번호가 올바르지 않습니다.', 'danger')
    
    if session.get('admin'):
        return redirect(url_for('by_period'))  # 교시별 보기로 바로 이동
    
    return render_template('admin.html')

@app.route('/logout')
def logout():
    """Logout from admin"""
    session.pop('admin', None)
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('attendance'))

@app.route('/delete_records', methods=['POST'])
def delete_records():
    """Delete selected attendance records (admin only)"""
    if not session.get('admin'):
        flash('관리자 권한이 필요합니다.', 'danger')
        return redirect(url_for('admin_login'))
    
    record_ids = request.form.getlist('record_ids[]')
    if not record_ids:
        flash('삭제할 기록을 선택해주세요.', 'warning')
        return redirect(url_for('list_attendance'))
    
    try:
        if not db:
            flash("Firebase 설정이 완료되지 않았습니다.", "danger")
            return redirect(url_for('list_attendance'))
        
        for record_id in record_ids:
            db.collection('attendances').document(record_id).delete()
        
        flash(f'{len(record_ids)}개의 기록이 삭제되었습니다.', 'success')
    except Exception as e:
        flash(f'기록 삭제 중 오류가 발생했습니다: {e}', 'danger')
    
    return redirect(url_for('list_attendance'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
