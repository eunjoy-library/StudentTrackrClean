import os
import json
import logging
import time
from datetime import datetime, timedelta
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
    
    # 교시 시간대 정의 (datetime 모듈에서 직접 time 사용)
    from datetime import time
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

def load_student_data(force_reload=False):
    """
    Load student data from Excel file with caching
    Returns a dictionary with student_id as key and (name, seat) as value
    
    Args:
        force_reload: 강제로 새로 로딩할지 여부 (기본값: False)
    """
    global _student_data_cache, _last_student_data_load_time
    now = datetime.now()
    
    # 새로고침 필요 없고, 캐시가 있는 경우 (시간 체크 제거)
    if not force_reload and _student_data_cache:
        logging.debug("학생 데이터 캐시 사용")
        return _student_data_cache

    logging.debug("학생 데이터 새로 로딩")
    try:
        # 엑셀 파일에서 학생 정보 읽기
        try:
            df = pd.read_excel('students.xlsx', dtype={'학번': str})
            # 컬럼명 확인 (좌석번호 또는 공강좌석번호)
            seat_column = '공강좌석번호' if '공강좌석번호' in df.columns else '좌석번호'
            
            student_data = {}
            for _, row in df.iterrows():
                # 학번이 있는 경우만 처리
                if pd.notna(row['학번']) and pd.notna(row['이름']):
                    student_id = str(row['학번']).strip()
                    name = str(row['이름']).strip()
                    # 좌석번호 가져오기 (없으면 빈 문자열)
                    seat = str(row.get(seat_column, '')) if pd.notna(row.get(seat_column, '')) else ''
                    student_data[student_id] = (name, seat)
            
            logging.debug(f"로드된 학생 수: {len(student_data)}")
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

def save_attendance(student_id, name, seat, period_text, admin_override=False):
    """
    출석 기록을 데이터베이스에 저장 (한국 시간 기준)
    - DB에서 직접 중복 출석 여부 확인
    - 안전한 트랜잭션 방식으로 처리
    - admin_override: 관리자 권한으로 중복 출석 허용 여부 (True이면 중복 체크 건너뜀)
    """
    # 전역 변수에 이미 출석 처리 여부 저장
    attendance_status = False
    
    try:
        # Firebase 연결 확인
        if not db:
            flash("Firebase 설정이 완료되지 않았습니다.", "danger")
            return False
        
        # 관리자 모드이고 중복 확인 무시 설정인 경우, 중복 체크 건너뜀
        if not admin_override:
            # 현재 주 범위 계산 (일~토)
            now = datetime.now(KST)
            
            # 이번 주 일요일(주 시작) 계산
            days_to_sunday = now.weekday() + 1  # 월=0, 일=6이므로 역으로 계산
            if days_to_sunday == 7:  # 일요일인 경우
                days_to_sunday = 0
                
            sunday = now - timedelta(days=days_to_sunday)
            sunday = sunday.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 토요일(주 마지막) 계산
            days_to_saturday = (5 - now.weekday()) % 7  # 토요일까지 남은 일수
            saturday = now + timedelta(days=days_to_saturday)
            saturday = saturday.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            sunday_str = sunday.strftime('%Y-%m-%d')
            saturday_str = saturday.strftime('%Y-%m-%d')
                
            # 이번 주 출석 기록을 직접 확인 (캐시 없이)
            attendance_query = db.collection('attendances').where('student_id', '==', student_id)
            attendance_docs = attendance_query.get()
                
            # 학생이 이번 주에 이미 출석했는지 직접 확인
            already_attended = False
            attendance_date = ""
                
            for doc in attendance_docs:
                doc_data = doc.to_dict()
                doc_date = doc_data.get('date_only', '')
                    
                # 이번 주 날짜 범위 내에 있는 출석인지 확인
                if sunday_str <= doc_date <= saturday_str:
                    already_attended = True
                    attendance_date = doc_date
                    logging.warning(f"학생 {student_id}는 이미 이번 주에 출석했습니다. 날짜: {doc_date}")
                    break
                    
            # 이미 출석한 경우 처리 중단
            if already_attended:
                flash(f'이미 이번 주에 출석 기록이 있습니다. (출석일: {attendance_date})', 'warning')
                return False
            
        # 현재 시간으로 출석 기록 생성
        now_kst = datetime.now(KST)
        date_str = now_kst.strftime('%Y-%m-%d')
        datetime_str = now_kst.strftime('%Y-%m-%d %H:%M:%S')
            
        # 새 문서 추가
        new_attendance = {
            'student_id': student_id,
            'name': name,
            'seat': seat,
            'period': period_text,
            'date': datetime_str,
            'date_only': date_str,
            'timestamp': firestore.SERVER_TIMESTAMP
        }
            
        # 출석 데이터 저장
        db.collection('attendances').add(new_attendance)
        
        # 성공 로그 기록
        logging.info(f"학생 {student_id}({name})의 출석이 성공적으로 등록되었습니다. 좌석: {seat}, 날짜: {date_str}")
        
        # 모든 캐시 즉시 초기화
        global attendance_status_cache
        attendance_status_cache.clear()
        
        return True
        
    except Exception as e:
        logging.error(f"출석 저장 중 오류 발생: {e}")
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

# 출석 상태 캐싱을 위한 딕셔너리와 캐시 만료 시간 (초)
attendance_status_cache = {}
CACHE_EXPIRY = 5  # 5초로 대폭 감소 (중복 출석 방지 강화)
student_data_cache = {}  # 학생 정보 캐시
STUDENT_CACHE_EXPIRY = 600  # 학생 정보는 10분 동안 캐시 (성능 향상)

# 중복 출석 방지를 위한 잠금 메커니즘 (동시 요청 처리용)
attendance_locks = {}

# 이번 주 날짜 범위 정보 캐싱 (매번 계산하지 않도록)
current_week_info = {
    'last_updated': 0,
    'sunday_str': '',
    'saturday_str': ''
}
WEEK_INFO_EXPIRY = 3600  # 주 정보는 1시간마다 갱신

def get_current_week_range():
    """현재 주의 시작(일요일)과 끝(토요일) 계산 - 캐싱 적용"""
    global current_week_info
    
    now = time.time()
    if now - current_week_info['last_updated'] < WEEK_INFO_EXPIRY and current_week_info['sunday_str']:
        return current_week_info['sunday_str'], current_week_info['saturday_str']
    
    # 현재 날짜 기준으로 이번 주의 월요일 찾기
    now_date = datetime.now(KST)
    weekday = now_date.weekday()  # 0=월요일, 1=화요일, ..., 6=일요일
    days_since_monday = weekday
    monday = now_date - timedelta(days=days_since_monday)
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 이번 주 토요일 끝 시간 (일요일부터 토요일까지)
    sunday = monday - timedelta(days=1)  # 일요일은 월요일 하루 전
    sunday = sunday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    saturday = monday + timedelta(days=5)  # 토요일은 월요일부터 5일 후
    saturday = saturday.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # 텍스트 형식으로 변환
    sunday_str = sunday.strftime('%Y-%m-%d')
    saturday_str = saturday.strftime('%Y-%m-%d')
    
    # 결과 캐싱
    current_week_info = {
        'last_updated': now,
        'sunday_str': sunday_str,
        'saturday_str': saturday_str
    }
    
    return sunday_str, saturday_str

def check_weekly_attendance_limit(student_id):
    """
    학생이 이번 주(일~토)에 1회 이상 출석했는지 확인
    캐싱 기능 추가: 같은 학생 ID에 대해 반복 쿼리 최소화
    메모리 캐싱으로 Firebase 쿼리 최소화
    
    Returns:
        (exceeded, count, recent_dates): 
        - exceeded: 주 1회 초과 여부 (True/False) - 1회 이미 있으면 True
        - count: 이번 주 출석 횟수
        - recent_dates: 최근 출석 날짜 목록
    """
    global attendance_status_cache
    
    # 캐시에 있고 만료되지 않았으면 캐시된 결과 반환
    cache_key = f"weekly_limit_{student_id}"
    if cache_key in attendance_status_cache:
        cache_entry = attendance_status_cache[cache_key]
        if time.time() - cache_entry['timestamp'] < CACHE_EXPIRY:
            logging.debug(f"학생 {student_id}의 출석 상태 캐시 사용")
            return cache_entry['exceeded'], cache_entry['count'], cache_entry['recent_dates']
    
    try:
        if not db:
            logging.error("Firebase DB 연결이 설정되지 않았습니다.")
            return False, 0, []
        
        # 현재 주 범위 얻기 (캐싱됨)
        sunday_str, saturday_str = get_current_week_range()
        logging.debug(f"학생 {student_id}의 이번 주({sunday_str} ~ {saturday_str}) 출석 기록 확인 중")
        
        try:
            # 일반 쿼리 실행 (인덱스 없이도 작동) - 학생 ID로 제한
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
            
            # 결과 정리 및 캐싱
            recent_dates = sorted(recent_dates, reverse=True)  # 최신 날짜 먼저
            unique_dates = sorted(list(set(recent_dates)))
            
            # 주간 출석 제한 (일주일에 1번만 허용)
            exceeded = len(unique_dates) >= 1  # 이미 1회 출석했으면 제한
            
            # 결과 캐싱 (자주 조회하는 학생은 캐시에서 빠르게 반환)
            attendance_status_cache[cache_key] = {
                'exceeded': exceeded,
                'count': count,
                'recent_dates': recent_dates,
                'timestamp': time.time()
            }
            
            logging.debug(f"학생 {student_id}의 이번 주 출석 횟수: {count}, 초과 여부: {exceeded}")
            return exceeded, count, recent_dates
            
        except Exception as db_error:
            logging.error(f"Firebase 쿼리 실행 중 오류: {db_error}")
            raise
        
    except Exception as e:
        logging.error(f"주간 출석 제한 확인 중 오류: {e}")
        return False, 0, []

# ================== [ROUTES] ==================

@app.route('/api/check_attendance', methods=['GET', 'POST'])
def api_check_attendance():
    """
    학생 ID로 해당 주에 출석 기록이 있는지 직접 확인하는 API
    - 정확한 기록 확인을 위해 캐시 없이 DB에서 직접 조회
    - 중복 출석 방지를 위한 실시간 검증
    - 경고받은 학생 출석 제한 기능 추가
    """
    student_id = request.args.get('student_id')
    
    # POST 파라미터에서도 확인
    if not student_id and request.method == 'POST':
        student_id = request.form.get('student_id')
    
    # 타임스탬프 확인 (캐시 방지)
    timestamp = request.args.get('t')
    
    if not student_id:
        return jsonify({'error': '학번이 필요합니다.', 'has_attendance': False})
    
    # 경고받은 학생인지 확인 (추가)
    try:
        # 'warnings' 컬렉션에서 해당 학생 ID에 대한 활성화된 경고 확인
        if db:
            warnings_query = db.collection('warnings').where('student_id', '==', student_id).where('active', '==', True)
            warning_docs = warnings_query.get()
            
            # 활성화된 경고가 있는지 확인
            for doc in warning_docs:
                warning_data = doc.to_dict()
                # 경고 상태인 경우 출석 제한
                return jsonify({
                    'warning': True,
                    'has_attendance': False,
                    'message': '경고 상태로 인해 출석이 제한되었습니다. 관리자에게 문의하세요.',
                    'warning_reason': warning_data.get('reason', '경고 상태')
                })
    except Exception as e:
        logging.error(f"경고 확인 오류: {e}")
        # 경고 확인 실패 시에도 계속 진행하여 출석은 확인
    
    try:
        # 현재 주의 범위 계산 (일요일부터 토요일까지)
        now = datetime.now(KST)
        
        # 이번 주 일요일(주 시작) 계산
        days_to_sunday = now.weekday() + 1  # 월=0, 일=6이므로 역으로 계산
        if days_to_sunday == 7:  # 일요일인 경우
            days_to_sunday = 0
            
        sunday = now - timedelta(days=days_to_sunday)
        sunday = sunday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 토요일(주 마지막) 계산
        days_to_saturday = (5 - now.weekday()) % 7  # 토요일까지 남은 일수
        saturday = now + timedelta(days=days_to_saturday)
        saturday = saturday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        sunday_str = sunday.strftime('%Y-%m-%d')
        saturday_str = saturday.strftime('%Y-%m-%d')
        
        # Firebase 직접 쿼리
        if not db:
            logging.error("Firebase DB 연결이 설정되지 않았습니다.")
            return jsonify({'error': 'Firebase 연결 오류', 'has_attendance': False})
            
        try:
            # 학생 ID로 필터링하여 쿼리 실행 (인덱스 오류 없는 단순 쿼리)
            records = db.collection('attendances').where('student_id', '==', student_id).get()
            
            # 이번 주에 해당하는 기록만 필터링 (직접 확인)
            has_attendance = False
            attendance_date = ""
            recent_dates = []
            
            for record in records:
                data = record.to_dict()
                date_only = data.get('date_only', '')
                
                # 이번 주 날짜 범위에 있는지 확인 
                if sunday_str <= date_only <= saturday_str:
                    has_attendance = True
                    attendance_date = date_only
                    recent_dates.append(date_only)
            
            # 결과 정리 (캐시 사용 안함)
            recent_dates = sorted(recent_dates, reverse=True)  # 최신 날짜 먼저
            
            # 한국어 요일 추가
            formatted_date = ""
            if attendance_date:
                try:
                    # yyyy-mm-dd 형식의 날짜 문자열에서 datetime 객체로 변환
                    date_obj = datetime.strptime(attendance_date, '%Y-%m-%d')
                    # 한국어 요일
                    weekdays = ['월', '화', '수', '목', '금', '토', '일']
                    weekday_kr = weekdays[date_obj.weekday()]
                    # 날짜 형식: 5월 18일 (토)
                    formatted_date = f"{date_obj.month}월 {date_obj.day}일 ({weekday_kr})"
                except Exception as e:
                    logging.error(f"날짜 변환 중 오류: {e}")
                    formatted_date = attendance_date
            
            logging.info(f"학생 {student_id}의 이번 주 출석 상태: {has_attendance}, 출석일: {recent_dates}")
            
            return jsonify({
                'has_attendance': has_attendance,
                'attendance_date': attendance_date,
                'formatted_date': formatted_date,
                'cached': False,
                'timestamp': str(datetime.now(KST))
            })
            
        except Exception as db_error:
            logging.error(f"Firebase 쿼리 실행 중 오류: {db_error}")
            raise
        
    except Exception as e:
        logging.error(f"출석 확인 API 오류: {e}")
        return jsonify({'error': str(e), 'has_attendance': False})

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
        
        # 관리자 접근용 학번 체크 (서버 측에서도 검증)
        if student_id == '20255008':
            # 관리자 페이지로 리다이렉트
            return redirect(url_for('admin_login'))
        
        if not student_id:
            flash('학번을 입력해주세요.', 'danger')
            return redirect(url_for('attendance'))
        
        # 주간 출석 제한 확인 (1회만 허용)
        # 출석 API로 직접 확인 (자바스크립트에서 이미 확인했지만 더블체크)
        try:
            # 직접 함수 호출로 변경 (API 호출 방식 문제 수정)
            exceeded, count, recent_dates = check_weekly_attendance_limit(student_id)
            
            if exceeded:
                # 이미 출석한 학생 (주 1회 초과)
                attendance_date = recent_dates[0] if recent_dates else ""
                flash(f'이번 주에 이미 출석했습니다. 출석일: {attendance_date}', 'danger')
                return redirect(url_for('attendance'))
        except Exception as e:
            # 확인 중 오류 발생 시 기존 방식으로 확인
            logging.error(f"출석 확인 중 오류: {e}")
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
        
        # 마지막으로 한번 더 중복 출석 확인
        # 다른 탭이나 브라우저에서 동시에 요청이 들어올 경우 대비
        try:
            # 다시 한번 더 확인
            exceeded, count, recent_dates = check_weekly_attendance_limit(student_id)
            
            if exceeded:
                # 이미 출석한 학생
                attendance_date = recent_dates[0] if recent_dates else ""
                flash(f'이번 주에 이미 출석했습니다. 출석일: {attendance_date}', 'danger')
                return redirect(url_for('attendance'))
                
            # 출석 정보 저장
            # 교시 텍스트 설정
            period_text_for_db = period_text
            if period_text == "4교시 (도서실 이용 불가)":
                period_text_for_db = "4교시"
            
            # 출석 정보 저장
            if save_attendance(student_id, name, seat, period_text_for_db):
                # 캐시 갱신을 위해 캐시 키 삭제 (강제 새로고침)
                cache_key = f"weekly_limit_{student_id}" 
                if cache_key in attendance_status_cache:
                    del attendance_status_cache[cache_key]
                    
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
        search_query = request.args.get('search', '').strip()
        search_field = request.args.get('search_field', 'all')
        
        # 모든 출석 기록 로드
        all_records = load_attendance()
        total_count = len(all_records)
        
        # 검색 기능 적용
        if search_query:
            filtered_records = []
            search_query = search_query.lower()
            
            for record in all_records:
                # 검색 필드에 따른 필터링
                if search_field == 'all':
                    # 모든 필드에서 검색
                    if (
                        search_query in str(record.get('student_id', '')).lower() or
                        search_query in str(record.get('name', '')).lower() or
                        search_query in str(record.get('seat', '')).lower() or
                        search_query in str(record.get('period', '')).lower() or
                        search_query in str(record.get('date', '')).lower()
                    ):
                        filtered_records.append(record)
                else:
                    # 특정 필드에서만 검색
                    field_value = str(record.get(search_field, '')).lower()
                    if search_query in field_value:
                        filtered_records.append(record)
            
            all_records = filtered_records
            total_count = len(all_records)
        
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
                              total_count=total_count,
                              limit=limit,
                              sort_by=sort_by,
                              sort_direction=sort_direction,
                              search_query=search_query,
                              search_field=search_field)
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
    
    # 교시 순서대로 정렬 (최근 교시가 상단에 오도록 역순 정렬)
    sorted_groups = {}
    period_order = ["10교시", "9교시", "8교시", "7교시", "6교시", "5교시", "4교시", "3교시", "2교시", "1교시", "시간 외", "기타"]
    
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
    
    return render_template('by_period.html', 
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
        if password == '9929':  # 비밀번호 변경 (9929)
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

@app.route('/admin_add_attendance', methods=['GET', 'POST'])
def admin_add_attendance():
    """관리자용 추가 출석 페이지"""
    if not session.get('admin'):
        flash('관리자 로그인이 필요합니다.', 'warning')
        return redirect(url_for('admin_login'))
    
    student_info = None
    attended = False
    last_attendance_date = None
    override = False
    
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        override_check = request.form.get('override_check') == 'on'
        
        # 학생 데이터 로드
        student_data = load_student_data()
        if student_id in student_data:
            name, seat = student_data[student_id]
            
            # 출석 체크를 위한 확인 로직
            # 이미 출석했는지 확인 (결과를 무시하고 attended 플래그만 추출)
            # 관리자 권한으로 추가 시 출석 제한을 무시하기 위해 admin_override=True 전달
            all_records = load_attendance()
            student_records = [r for r in all_records if r.get('student_id') == student_id]
            
            # 이번 주 출석 여부 확인
            sunday_str, saturday_str = get_current_week_range()
            sunday = datetime.strptime(sunday_str, '%Y-%m-%d')
            saturday = datetime.strptime(saturday_str, '%Y-%m-%d')
            
            # 이번주 출석 기록 필터링
            week_records = []
            for record in student_records:
                try:
                    record_date = datetime.strptime(record.get('date'), '%Y-%m-%d %H:%M:%S')
                    if sunday <= record_date <= saturday:
                        week_records.append(record)
                except:
                    pass
            
            attended = len(week_records) > 0
            if attended and week_records:
                # 가장 최근 출석일 찾기
                last_record = max(week_records, key=lambda r: datetime.strptime(r.get('date'), '%Y-%m-%d %H:%M:%S'))
                last_attendance_date = last_record.get('date').split(' ')[0]
                
            # 경고 여부 체크 (실제 구현은 여기에 추가)
            is_warned = False
            warning_info = None
            
            student_info = {
                'id': student_id,
                'name': name,
                'seat': seat,
                'is_warned': is_warned,
                'warning_info': warning_info
            }
            
            override = override_check
            
    return render_template('admin_add_attendance.html',
                          student_info=student_info,
                          attended=attended,
                          last_attendance_date=last_attendance_date,
                          override=override)

@app.route('/admin_add_attendance/confirm', methods=['POST'])
def admin_add_attendance_confirm():
    """관리자용 추가 출석 확인 처리"""
    if not session.get('admin'):
        flash('관리자 로그인이 필요합니다.', 'warning')
        return redirect(url_for('admin_login'))
    
    # 폼 데이터 가져오기
    student_id = request.form.get('student_id')
    name = request.form.get('name')
    seat = request.form.get('seat')
    override = request.form.get('override') == '1'
    
    if not student_id or not name or not seat:
        flash('필수 정보가 누락되었습니다.', 'danger')
        return redirect(url_for('admin_add_attendance'))
    
    try:
        # 관리자 권한으로 출석 추가
        current_period = get_current_period()
        period_text = "시간 외"
        
        if current_period == 0:
            period_text = "4교시"
        elif current_period > 0:
            period_text = f"{current_period}교시"
        
        # 중복 출석 체크 플래그 설정 (override = True면 중복 체크 무시)
        admin_override = override
        
        # 출석 기록 저장 (admin_override 파라미터 전달)
        save_attendance(student_id, name, seat, period_text, admin_override=admin_override)
        
        flash(f"✅ 관리자 권한으로 추가 출석이 완료되었습니다. 학번: {student_id}, 이름: {name}", "success")
        return redirect(url_for('by_period'))
        
    except Exception as e:
        flash(f'오류가 발생했습니다: {str(e)}', 'danger')
        return redirect(url_for('admin_add_attendance'))



@app.route('/admin/warnings')
def admin_warnings():
    """경고 학생 관리 페이지 (관리자만 접근 가능)"""
    if not session.get('admin'):
        flash('관리자 로그인이 필요합니다.', 'warning')
        return redirect(url_for('admin_login'))
    
    try:
        # 모든 경고 기록 가져오기
        warnings_ref = db.collection('warnings').order_by('warning_date', direction=firestore.Query.DESCENDING)
        warnings_docs = warnings_ref.get()
        
        warnings = []
        for doc in warnings_docs:
            warning_data = doc.to_dict()
            warning_data['id'] = doc.id
            
            # 날짜 변환
            if 'warning_date' in warning_data and warning_data['warning_date']:
                warning_data['warning_date'] = warning_data['warning_date'].replace(tzinfo=pytz.UTC).astimezone(KST)
            if 'expiry_date' in warning_data and warning_data['expiry_date']:
                warning_data['expiry_date'] = warning_data['expiry_date'].replace(tzinfo=pytz.UTC).astimezone(KST)
            
            # 경고가 만료되었는지 확인
            now = datetime.now(KST)
            warning_data['active'] = warning_data.get('active', False)
            if warning_data.get('expiry_date') and warning_data['expiry_date'] < now:
                warning_data['active'] = False
            
            warnings.append(warning_data)
        
        return render_template('admin_warnings.html', warnings=warnings)
    except Exception as e:
        flash(f'경고 정보를 불러오는 중 오류가 발생했습니다: {e}', 'danger')
        return redirect(url_for('list_attendance'))

@app.route('/admin/warnings/add', methods=['POST'])
def add_warning():
    """학생 경고 추가 처리"""
    if not session.get('admin'):
        flash('관리자 로그인이 필요합니다.', 'warning')
        return redirect(url_for('admin_login'))
    
    try:
        student_id = request.form.get('student_id')
        reason = request.form.get('reason', '도서실 이용 규정 위반')
        
        # 학생 정보 확인
        student_data = load_student_data().get(student_id)
        student_name = student_data[0] if student_data else None
        
        # 경고 기간 계산
        duration = request.form.get('duration')
        if duration == 'custom':
            days = int(request.form.get('customDuration', 7))
        else:
            days = int(duration)
        
        warning_date = datetime.now(KST)
        expiry_date = warning_date + timedelta(days=days)
        
        # Firestore에 경고 추가
        warning_data = {
            'student_id': student_id,
            'name': student_name,
            'reason': reason,
            'warning_date': warning_date,
            'expiry_date': expiry_date,
            'active': True,
            'created_at': firestore.SERVER_TIMESTAMP
        }
        
        db.collection('warnings').add(warning_data)
        
        flash(f'학생(학번: {student_id})에게 {days}일 동안의 경고가 추가되었습니다.', 'success')
    except Exception as e:
        flash(f'경고 추가 중 오류가 발생했습니다: {e}', 'danger')
    
    return redirect(url_for('admin_warnings'))

@app.route('/admin/warnings/remove/<warning_id>')
def remove_warning(warning_id):
    """학생 경고 해제 처리"""
    if not session.get('admin'):
        flash('관리자 로그인이 필요합니다.', 'warning')
        return redirect(url_for('admin_login'))
    
    try:
        # 경고 정보 가져오기
        warning_ref = db.collection('warnings').document(warning_id)
        warning_doc = warning_ref.get()
        
        if not warning_doc.exists:
            flash('해당 경고를 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin_warnings'))
        
        warning_data = warning_doc.to_dict()
        student_id = warning_data.get('student_id')
        
        # 경고 비활성화 (삭제하지 않고 비활성화만 함)
        warning_ref.update({
            'active': False,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        flash(f'학생(학번: {student_id})의 경고가 해제되었습니다.', 'success')
    except Exception as e:
        flash(f'경고 해제 중 오류가 발생했습니다: {e}', 'danger')
    
    return redirect(url_for('admin_warnings'))

@app.route('/admin/warnings/delete/<warning_id>')
def delete_warning(warning_id):
    """학생 경고 완전 삭제 처리"""
    if not session.get('admin'):
        flash('관리자 로그인이 필요합니다.', 'warning')
        return redirect(url_for('admin_login'))
    
    try:
        # 경고 정보 가져오기
        warning_ref = db.collection('warnings').document(warning_id)
        warning_doc = warning_ref.get()
        
        if not warning_doc.exists:
            flash('해당 경고를 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin_warnings'))
        
        warning_data = warning_doc.to_dict()
        student_id = warning_data.get('student_id')
        
        # 경고 완전 삭제
        warning_ref.delete()
        
        flash(f'학생(학번: {student_id})의 경고가 완전히 삭제되었습니다.', 'success')
    except Exception as e:
        flash(f'경고 삭제 중 오류가 발생했습니다: {e}', 'danger')
    
    return redirect(url_for('admin_warnings'))

@app.route('/admin/warnings/delete-all')
def delete_all_warnings():
    """모든 경고 삭제 처리"""
    if not session.get('admin'):
        flash('관리자 로그인이 필요합니다.', 'warning')
        return redirect(url_for('admin_login'))
    
    try:
        # 모든 경고 가져오기
        warnings_ref = db.collection('warnings').get()
        
        # 배치 삭제 (한 번에 최대 500개)
        batch_size = 0
        batch = db.batch()
        
        for doc in warnings_ref:
            batch.delete(doc.reference)
            batch_size += 1
            
            # 배치 크기가 500에 도달하면 커밋
            if batch_size >= 500:
                batch.commit()
                batch = db.batch()
                batch_size = 0
        
        # 남은 배치 커밋
        if batch_size > 0:
            batch.commit()
        
        flash('모든 경고가 성공적으로 삭제되었습니다.', 'success')
    except Exception as e:
        flash(f'경고 삭제 중 오류가 발생했습니다: {e}', 'danger')
    
    return redirect(url_for('admin_warnings'))

@app.route('/edit_seat')
def edit_seat():
    """학생 좌석번호 수정 페이지 (관리자 전용)"""
    if not session.get('admin'):
        flash('관리자 권한이 필요합니다.', 'danger')
        return redirect(url_for('admin_login'))
    return send_from_directory('static', 'edit_seat.html')

@app.route('/bulk_edit_seats')
def bulk_edit_seats():
    """학생 좌석번호 일괄 수정 페이지 (관리자 전용)"""
    if not session.get('admin'):
        flash('관리자 권한이 필요합니다.', 'danger')
        return redirect(url_for('admin_login'))
    return render_template('bulk_edit_seats.html')

@app.route('/update_seat', methods=['POST'])
def update_seat():
    """학생 좌석번호 업데이트 API (관리자 전용)"""
    if not session.get('admin'):
        return jsonify({"error": "관리자 권한이 필요합니다."}), 403
    
    student_id = request.json.get('student_id')
    new_seat = request.json.get('new_seat')
    
    if not student_id or not new_seat:
        return jsonify({"error": "학번과 새 좌석번호를 모두 입력해주세요."}), 400
    
    try:
        # Excel 파일 수정
        import pandas as pd
        from openpyxl import load_workbook
        
        excel_path = 'students.xlsx'
        
        # pandas 미리보기로 열 이름 확인
        df_preview = pd.read_excel(excel_path, nrows=1)
        column_names = df_preview.columns.tolist()
        
        # 학번과 좌석번호 열 확인
        id_column = [col for col in column_names if '학번' in col or 'ID' in col.upper()][0]
        seat_column = [col for col in column_names if '좌석' in col or 'SEAT' in col.upper()][0]
        
        # openpyxl로 직접 셀 수정
        wb = load_workbook(excel_path)
        ws = wb.active
        
        # 학번 열 및 좌석번호 열의 인덱스 찾기
        col_indices = {}
        for idx, col in enumerate(ws[1]):
            if col.value == id_column:
                col_indices['id'] = idx + 1  # 1-based index
            elif col.value == seat_column:
                col_indices['seat'] = idx + 1  # 1-based index
        
        # 학번으로 학생 찾아 좌석번호 수정
        student_found = False
        for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):  # 2행부터 시작 (헤더 제외)
            cell_id = row[col_indices['id'] - 1].value  # 0-based index
            if str(cell_id) == student_id:
                student_found = True
                old_seat = row[col_indices['seat'] - 1].value
                # 새 좌석번호로 업데이트
                ws.cell(row=row_idx, column=col_indices['seat']).value = new_seat
                break
        
        if not student_found:
            return jsonify({"error": f"학번 {student_id}를 찾을 수 없습니다."}), 404
        
        # 변경 사항 저장
        wb.save(excel_path)
        
        # 학생 데이터 캐시 초기화 (새로고침)
        global _student_data_cache, _student_data_timestamp
        _student_data_cache = None
        _student_data_timestamp = None
        
        return jsonify({
            "success": True, 
            "message": f"학번 {student_id}의 좌석번호가 {old_seat}에서 {new_seat}로 업데이트되었습니다."
        }), 200
    except Exception as e:
        return jsonify({"error": f"좌석번호 업데이트 중 오류가 발생했습니다: {str(e)}"}), 500

@app.route('/add_student_form', methods=['GET'])
def add_student_form():
    """학생 추가 폼 페이지"""
    if not session.get('admin'):
        flash('관리자 권한이 필요합니다.', 'danger')
        return redirect(url_for('admin_login'))
    
    return render_template('add_student.html')

@app.route('/api/add_direct_student', methods=['POST'])
def add_direct_student():
    """새 학생을 직접 추가하는 API"""
    if not session.get('admin'):
        return jsonify({"error": "관리자 권한이 필요합니다."}), 403
    
    data = request.json
    if not data or 'student_id' not in data or 'name' not in data or 'seat' not in data:
        return jsonify({"error": "필수 정보가 누락되었습니다. (학번, 이름, 좌석번호)"}), 400
    
    student_id = data['student_id']
    name = data['name']
    seat = data['seat']
    
    try:
        # 학생 추가 모듈 사용
        from add_student import add_new_student
        success, message = add_new_student(student_id, name, seat)
        
        if success:
            # 데이터를 강제로 새로 로딩하여 캐시 갱신
            global _student_data_cache
            _student_data_cache = None
            load_student_data(force_reload=True)
            
            return jsonify({
                "success": True,
                "message": message
            })
        else:
            return jsonify({
                "warning": message
            }), 200
            
    except Exception as e:
        return jsonify({"error": f"학생 추가 중 오류 발생: {str(e)}"}), 500

@app.route('/api/students', methods=['GET'])
def api_get_students():
    """학생 정보 조회 API (학번 목록으로 학생 정보 반환)"""
    if not session.get('admin'):
        return jsonify({"error": "관리자 권한이 필요합니다."}), 403
    
    # 쿼리 파라미터에서 학번 목록 가져오기
    student_ids = request.args.get('ids', '')
    if not student_ids:
        return jsonify([])
    
    student_id_list = student_ids.split(',')
    
    try:
        # 학생 데이터 로드
        students_data = load_student_data()
        
        # 새 학생 텍스트 파일이 있으면 추가 로드
        new_students = {}
        if os.path.exists('new_students.txt'):
            with open('new_students.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 3:
                        new_students[parts[0]] = (parts[1], parts[2])
        
        # 새로운 학생 데이터도 추가하기 위해 현재 요청 목록에서 학번을 모두 처리
        result = []
        for student_id in student_id_list:
            if student_id in students_data:
                name, seat = students_data[student_id]
                result.append({
                    "student_id": student_id,
                    "name": name or "이름 없음",  # 이름이 없는 경우 대체 텍스트
                    "seat": seat or "-"           # 좌석번호가 없는 경우 대체 텍스트
                })
            elif student_id in new_students:
                name, seat = new_students[student_id]
                result.append({
                    "student_id": student_id,
                    "name": name or "이름 없음",
                    "seat": seat or "-"
                })
            else:
                # 데이터베이스에 없는 새 학생인 경우
                result.append({
                    "student_id": student_id,
                    "name": "새 학생",
                    "seat": "-"
                })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"학생 정보 조회 중 오류가 발생했습니다: {str(e)}"}), 500

@app.route('/api/bulk_update_seats', methods=['POST'])
def api_bulk_update_seats():
    """학생 좌석번호 및 이름 일괄 업데이트 API (관리자 전용)"""
    if not session.get('admin'):
        return jsonify({"error": "관리자 권한이 필요합니다."}), 403
    
    data = request.json
    if not data or 'changes' not in data or not data['changes']:
        return jsonify({"error": "유효한 데이터가 없습니다."}), 400
    
    try:
        # Excel 파일 업데이트
        import pandas as pd
        from openpyxl import load_workbook
        
        excel_path = 'students.xlsx'
        
        # pandas로 열 이름 확인
        df_preview = pd.read_excel(excel_path, nrows=1)
        column_names = df_preview.columns.tolist()
        
        # 학번과 좌석번호 열 확인
        id_column = [col for col in column_names if '학번' in col or 'ID' in col.upper()][0]
        seat_column = [col for col in column_names if '좌석' in col or 'SEAT' in col.upper()][0]
        
        # openpyxl로 직접 셀 수정
        wb = load_workbook(excel_path)
        ws = wb.active
        
        # 학번 열 및 좌석번호 열의 인덱스 찾기
        col_indices = {}
        for idx, col in enumerate(ws[1]):
            if col.value == id_column:
                col_indices['id'] = idx + 1  # 1-based index
            elif col.value == seat_column:
                col_indices['seat'] = idx + 1  # 1-based index
        
        # 변경 사항 추적
        changes_count = 0
        not_found_count = 0
        
        # 학번별 새 좌석번호와 이름 매핑 생성
        changes_map = {}
        for item in data['changes']:
            student_id = item['student_id']
            changes_map[student_id] = {
                'new_seat': item['new_seat']
            }
            # 새 이름이 있는 경우만 추가
            if 'new_name' in item and item['new_name']:
                changes_map[student_id]['new_name'] = item['new_name']
        
        # 엑셀 파일 수정
        seat_changes_count = 0
        name_changes_count = 0
        
        for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):  # 2행부터 시작 (헤더 제외)
            cell_id = row[col_indices['id'] - 1].value  # 0-based index
            if str(cell_id) in changes_map:
                change_item = changes_map[str(cell_id)]
                
                # 좌석번호 업데이트
                ws.cell(row=row_idx, column=col_indices['seat']).value = change_item['new_seat']
                seat_changes_count += 1
                
                # 이름 업데이트 (이름 칼럼이 존재하고 새 이름이 제공된 경우)
                if 'name' in col_indices and 'new_name' in change_item:
                    ws.cell(row=row_idx, column=col_indices['name']).value = change_item['new_name']
                    name_changes_count += 1
                
                changes_count = seat_changes_count + name_changes_count
                
                # 처리한 항목 제거
                del changes_map[str(cell_id)]
        
        # 데이터베이스에 없는 새 학생 추가
        new_students_count = 0
        
        if changes_map and 'name' in col_indices:  # 이름 열이 있는 경우만 새 학생 추가 가능
            # 마지막 행 다음에 새 학생 추가
            last_row = ws.max_row + 1
            
            for student_id, change_item in list(changes_map.items()):
                if 'new_name' in change_item:  # 이름이 제공된 경우에만 새 학생으로 추가
                    # 새 학생 정보 추가
                    ws.cell(row=last_row, column=col_indices['id']).value = student_id
                    ws.cell(row=last_row, column=col_indices['seat']).value = change_item['new_seat']
                    ws.cell(row=last_row, column=col_indices['name']).value = change_item['new_name']
                    
                    new_students_count += 1
                    last_row += 1
                    
                    # 처리한 항목 제거
                    del changes_map[student_id]
        
        # 미처리된 학번 수 계산
        not_found_count = len(changes_map)
        
        # 변경 사항 저장
        wb.save(excel_path)
        
        # 학생 데이터 캐시 초기화
        global _student_data_cache, _student_data_timestamp
        _student_data_cache = None
        _student_data_timestamp = None
        
        return jsonify({
            "success": True,
            "message": f"성공적으로 업데이트되었습니다: 좌석번호 {seat_changes_count}개, 이름 {name_changes_count}개 변경됨, 새 학생 {new_students_count}명 추가됨. {not_found_count}개의 학번은 처리할 수 없습니다."
        })
    except Exception as e:
        return jsonify({"error": f"학생 정보 일괄 업데이트 중 오류가 발생했습니다: {str(e)}"}), 500

@app.route('/delete_records', methods=['POST'])
def delete_records():
    """Delete selected attendance records (admin only)"""
    if not session.get('admin'):
        flash('관리자 권한이 필요합니다.', 'danger')
        return redirect(url_for('admin_login'))
    
    # 이전 페이지 확인 (교시별 보기 또는 출석 목록)
    referrer = request.referrer
    redirect_to_period_view = False
    
    # referrer URL에서 경로 추출 (by_period인지 확인)
    if referrer:
        from urllib.parse import urlparse
        parsed_uri = urlparse(referrer)
        path = parsed_uri.path
        if path.endswith('/by_period'):
            redirect_to_period_view = True
            # 쿼리 파라미터도 기억 (날짜 등)
            query = parsed_uri.query
    
    record_ids = request.form.getlist('record_ids[]')
    if not record_ids:
        flash('삭제할 기록을 선택해주세요.', 'warning')
        if redirect_to_period_view:
            return redirect(url_for('by_period'))
        return redirect(url_for('list_attendance'))
    
    try:
        if not db:
            flash("Firebase 설정이 완료되지 않았습니다.", "danger")
            if redirect_to_period_view:
                return redirect(url_for('by_period'))
            return redirect(url_for('list_attendance'))
        
        for record_id in record_ids:
            db.collection('attendances').document(record_id).delete()
        
        flash(f'{len(record_ids)}개의 기록이 삭제되었습니다.', 'success')
    except Exception as e:
        flash(f'기록 삭제 중 오류가 발생했습니다: {e}', 'danger')
    
    # 이전 페이지가 교시별 보기였으면 그쪽으로 리다이렉트
    if redirect_to_period_view:
        # 원래 URL에 있던 쿼리 파라미터(예: 날짜) 유지
        if 'query' in locals() and query:
            return redirect(url_for('by_period') + '?' + query)
        return redirect(url_for('by_period'))
    
    return redirect(url_for('list_attendance'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
