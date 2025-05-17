from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from datetime import datetime
import pytz

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key")

# 테스트용 하드코딩 데이터
STUDENTS = {
    "10307": ("박지호", "387"),
    "20101": ("강지훈", "331"),
    "30107": ("김리나", "175"),
    "30207": ("김유담", "281"),
    "20240101": ("홍길동", "A1")
}

# 간단한 메모리 기반 데이터 저장소
ATTENDANCE_RECORDS = []

def get_current_period():
    """현재 교시 계산"""
    now = datetime.now(KST)
    current_time = now.time()
    
    # 요일이 토요일(5) 또는 일요일(6)인 경우 시간 외로 처리
    if now.weekday() > 4:  # 토요일(5), 일요일(6)
        return -1
    
    # 간단한 교시 시간 정의
    if current_time.hour < 8:
        return -1  # 시간 외
    elif current_time.hour < 10:
        return 1  # 1교시
    elif current_time.hour < 12:
        return 2  # 2교시
    elif current_time.hour < 12 or (current_time.hour == 12 and current_time.minute < 30):
        return 0  # 4교시 (이용 불가)
    elif current_time.hour < 14:
        return 5  # 5교시
    elif current_time.hour < 16:
        return 6  # 6교시
    else:
        return -1  # 시간 외

@app.route('/')
def index():
    """기본 페이지 리다이렉트"""
    return redirect(url_for('attendance'))

@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    """출석 페이지 및 처리"""
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
    
    # POST 요청 처리 (출석 등록)
    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        
        if not student_id:
            flash('학번을 입력해주세요.', 'danger')
            return redirect(url_for('attendance'))
        
        # 학생 정보 찾기
        student_info = STUDENTS.get(student_id)
        
        if student_info:
            name = student_info[0]
            seat = student_info[1]
        else:
            # 임의의 학생 생성
            name = "홍길동"
            seat = "A1"
        
        # 출석 정보 저장
        attendance_record = {
            'student_id': student_id,
            'name': name,
            'seat': seat,
            'period': period_text,
            'date': now.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        ATTENDANCE_RECORDS.append(attendance_record)
        flash('출석이 성공적으로 등록되었습니다!', 'success')
        return redirect(url_for('attendance'))
    
    # GET 요청 처리
    return render_template('simple_form.html', now=now, period_text=period_text)

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    """관리자 로그인"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == '1234':
            session['admin'] = True
            flash('관리자로 로그인되었습니다.', 'success')
            return redirect(url_for('list_attendance'))
        else:
            flash('비밀번호가 올바르지 않습니다.', 'danger')
    
    if session.get('admin'):
        return redirect(url_for('list_attendance'))
    
    return render_template('admin.html')

@app.route('/list')
def list_attendance():
    """출석 기록 목록"""
    if not session.get('admin'):
        flash('관리자 로그인이 필요합니다.', 'warning')
        return redirect(url_for('admin_login'))
    
    return render_template('list_simple.html', records=ATTENDANCE_RECORDS)

@app.route('/logout')
def logout():
    """로그아웃"""
    session.pop('admin', None)
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('attendance'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)