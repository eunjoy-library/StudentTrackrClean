#!/usr/bin/env python3
"""
Firebase admin 컬렉션 디버깅 스크립트
실제 저장된 데이터 구조를 확인
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import pytz

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

def init_firebase():
    """Firebase 초기화"""
    if not firebase_admin._apps:
        try:
            # 환경 변수에서 Firebase 인증 정보 로드
            firebase_credentials = os.environ.get('FIREBASE_CREDENTIALS_JSON')
            if firebase_credentials:
                cred_dict = json.loads(firebase_credentials)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                print("Firebase 초기화 성공")
            else:
                print("Firebase 인증 정보 없음")
                return None
        except Exception as e:
            print(f"Firebase 초기화 실패: {e}")
            return None
    
    return firestore.client()

def debug_admin_collection():
    """Admin 컬렉션 디버깅"""
    db = init_firebase()
    if not db:
        return
    
    print("=== Firebase Admin 컬렉션 디버깅 ===")
    
    try:
        # 1. admin 컬렉션의 모든 문서 조회
        admin_collection = db.collection('admin')
        admin_docs = list(admin_collection.get())
        
        print(f"\n1. Admin 컬렉션 총 문서 수: {len(admin_docs)}")
        
        if admin_docs:
            for doc in admin_docs:
                print(f"   - 문서 ID: {doc.id}")
                data = doc.to_dict()
                if data:
                    print(f"     데이터: {data}")
                
                # 하위 students 컬렉션 확인
                students_collection = doc.reference.collection('students')
                students_docs = list(students_collection.get())
                print(f"     하위 students 수: {len(students_docs)}")
                
                if students_docs:
                    for student_doc in students_docs:
                        student_data = student_doc.to_dict()
                        print(f"       - 학생 ID: {student_doc.id}")
                        print(f"         학생 데이터: {student_data}")
        
        # 2. 오늘 날짜 기준으로 특정 교시 확인
        today = datetime.now(KST).strftime('%Y-%m-%d')
        specific_key = f"{today}_5교시"
        
        print(f"\n2. 특정 문서 확인: {specific_key}")
        specific_doc = admin_collection.document(specific_key).get()
        
        if specific_doc.exists:
            print("   문서 존재함")
            data = specific_doc.to_dict()
            print(f"   데이터: {data}")
            
            # 하위 students 확인
            students_ref = specific_doc.reference.collection('students')
            students = list(students_ref.get())
            print(f"   하위 students 수: {len(students)}")
            
            for student in students:
                student_data = student.to_dict()
                print(f"     - 학생: {student_data.get('name')} ({student_data.get('student_id')})")
        else:
            print("   문서 존재하지 않음")
        
        # 3. students 컬렉션도 확인
        print(f"\n3. Students 컬렉션 확인")
        students_collection = db.collection('students')
        students_sample = list(students_collection.limit(5).get())
        print(f"   Students 컬렉션 샘플 문서 수: {len(students_sample)}")
        
        for student_doc in students_sample:
            print(f"   - 학생 ID: {student_doc.id}")
            # 해당 학생의 attendance 하위 컬렉션 확인
            attendance_ref = student_doc.reference.collection('attendance')
            attendance_docs = list(attendance_ref.limit(3).get())
            print(f"     출석 기록 수: {len(attendance_docs)}")
            
            for att_doc in attendance_docs:
                att_data = att_doc.to_dict()
                print(f"       - {att_doc.id}: {att_data}")
        
    except Exception as e:
        print(f"디버깅 중 오류: {e}")

if __name__ == "__main__":
    debug_admin_collection()