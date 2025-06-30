#!/usr/bin/env python3
"""
학번 20202의 현재 주 출석 데이터를 Firebase에 추가하는 스크립트
중복출석 테스트를 위한 용도
"""

import os
import json
import logging
from datetime import datetime, timedelta
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

def init_firebase():
    """Firebase 초기화"""
    try:
        if not firebase_admin._apps:
            # 환경변수에서 Firebase 인증 정보 가져오기
            firebase_key = os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY')
            if firebase_key:
                firebase_config = json.loads(firebase_key)
                cred = credentials.Certificate(firebase_config)
                firebase_admin.initialize_app(cred)
                print("Firebase 초기화 성공")
            else:
                print("Firebase 인증 정보가 없습니다.")
                return None
        
        return firestore.client()
    except Exception as e:
        print(f"Firebase 초기화 실패: {e}")
        return None

def add_test_attendance():
    """학번 20202의 현재 주 출석 데이터 추가"""
    db = init_firebase()
    if not db:
        return
    
    try:
        # 현재 한국 시간
        now = datetime.now(KST)
        date_str = now.strftime('%Y-%m-%d')
        datetime_str = now.strftime('%Y-%m-%d %H:%M:%S')
        
        # 출석 데이터
        attendance_data = {
            'student_id': '20202',
            'name': '곽환준',
            'seat': '346',
            'period': '1교시',
            'date': datetime_str,
            'date_only': date_str,
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        
        # 1. attendance/{student_id}/records/{date} 구조에 저장
        student_ref = db.collection('attendance').document('20202').collection('records').document(date_str)
        student_ref.set(attendance_data)
        print(f"학번 20202 출석 데이터 추가 완료: {date_str}")
        
        # 2. admin/{date_period}/students/{student_id} 구조에 저장
        date_period_key = f"{date_str}_1교시"
        admin_ref = db.collection('admin').document(date_period_key).collection('students').document('20202')
        admin_ref.set(attendance_data)
        print(f"관리자 컬렉션에도 데이터 추가 완료: {date_period_key}")
        
        # 3. CSV도 업데이트
        with open('attendance.csv', 'w', encoding='utf-8') as f:
            f.write('출석일,교시,학번,이름,공강좌석번호\n')
            f.write(f'{datetime_str},1교시,20202,곽환준,346\n')
        print("CSV 파일도 업데이트 완료")
        
    except Exception as e:
        print(f"출석 데이터 추가 실패: {e}")

if __name__ == '__main__':
    add_test_attendance()