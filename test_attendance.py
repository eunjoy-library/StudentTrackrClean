#!/usr/bin/env python3
"""
Firebase 출석 데이터 테스트 및 샘플 데이터 추가
"""

import os
import json
import logging
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# 로깅 설정
logging.basicConfig(level=logging.INFO)

def init_firebase():
    """Firebase 초기화"""
    try:
        # 환경 변수에서 Firebase 인증 정보 로드
        firebase_credentials = os.environ.get('FIREBASE_CREDENTIALS')
        if not firebase_credentials:
            print("Firebase 인증 정보가 없습니다.")
            return None
            
        # JSON 문자열을 파싱
        cred_dict = json.loads(firebase_credentials)
        cred = credentials.Certificate(cred_dict)
        
        # Firebase Admin SDK 초기화 (이미 초기화된 경우 건너뛰기)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        print("Firebase 초기화 성공")
        return db
    except Exception as e:
        print(f"Firebase 초기화 실패: {e}")
        return None

def add_sample_data(db):
    """샘플 출석 데이터 추가"""
    if not db:
        return
    
    # 한국 시간대 설정
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    
    # 오늘 날짜 문자열
    date_str = now.strftime('%Y-%m-%d')
    datetime_str = now.strftime('%Y-%m-%d %H:%M:%S')
    
    # 샘플 학생 데이터
    sample_students = [
        {"student_id": "10307", "name": "박지호", "seat": "387", "period": "1교시"},
        {"student_id": "20101", "name": "강지훈", "seat": "331", "period": "2교시"},
        {"student_id": "30107", "name": "김리나", "seat": "175", "period": "3교시"},
        {"student_id": "30207", "name": "김유담", "seat": "281", "period": "1교시"},
        {"student_id": "20240101", "name": "홍길동", "seat": "A1", "period": "시간 외"}
    ]
    
    print(f"샘플 데이터 추가 시작 (날짜: {date_str})")
    
    for student in sample_students:
        try:
            # 출석 데이터 구조
            attendance_data = {
                'student_id': student['student_id'],
                'name': student['name'],
                'seat': student['seat'],
                'period': student['period'],
                'date': datetime_str,
                'date_only': date_str,
                'timestamp': firestore.SERVER_TIMESTAMP
            }
            
            # 1. attendance/{student_id}/records/{date} 구조에 저장
            student_ref = db.collection('attendance').document(student['student_id']).collection('records').document(date_str)
            student_ref.set(attendance_data)
            
            # 2. admin/{date_period}/students/{student_id} 구조에 저장
            date_period_key = f"{date_str}_{student['period']}"
            admin_ref = db.collection('admin').document(date_period_key).collection('students').document(student['student_id'])
            admin_ref.set(attendance_data)
            
            print(f"추가됨: {student['name']} ({student['student_id']}) - {student['period']}")
            
        except Exception as e:
            print(f"데이터 추가 실패 - {student['name']}: {e}")
    
    print("샘플 데이터 추가 완료")

def check_data(db):
    """Firebase 데이터 확인"""
    if not db:
        return
    
    print("\n=== Firebase 데이터 확인 ===")
    
    # attendance 컬렉션 확인
    try:
        attendance_docs = db.collection('attendance').get()
        print(f"attendance 컬렉션: {len(attendance_docs)}개 학생 문서")
        
        for doc in attendance_docs:
            student_id = doc.id
            records = doc.reference.collection('records').get()
            print(f"  - 학생 {student_id}: {len(records)}개 출석 기록")
            
    except Exception as e:
        print(f"attendance 확인 실패: {e}")
    
    # admin 컬렉션 확인
    try:
        admin_docs = db.collection('admin').get()
        print(f"admin 컬렉션: {len(admin_docs)}개 날짜+교시 문서")
        
        for doc in admin_docs:
            date_period = doc.id
            students = doc.reference.collection('students').get()
            print(f"  - {date_period}: {len(students)}명 출석")
            
    except Exception as e:
        print(f"admin 확인 실패: {e}")

if __name__ == "__main__":
    # Firebase 초기화
    db = init_firebase()
    
    if db:
        # 기존 데이터 확인
        check_data(db)
        
        # 샘플 데이터 추가
        add_sample_data(db)
        
        # 추가 후 데이터 확인
        check_data(db)
    else:
        print("Firebase 연결 실패")