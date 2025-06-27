#!/usr/bin/env python3
"""
Firebase 연결 및 데이터 확인 디버그 스크립트
"""

import os
import json
import logging
from datetime import datetime
import pytz

# 로깅 설정
logging.basicConfig(level=logging.INFO)

def test_firebase():
    """Firebase 연결 및 데이터 테스트"""
    try:
        # Firebase 초기화 (app.py와 동일한 방식)
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        # 환경 변수에서 Firebase 인증 정보 로드
        firebase_credentials = os.environ.get('FIREBASE_CREDENTIALS')
        if not firebase_credentials:
            print("❌ Firebase 인증 정보가 없습니다.")
            return False
            
        # JSON 문자열을 파싱
        cred_dict = json.loads(firebase_credentials)
        cred = credentials.Certificate(cred_dict)
        
        # Firebase Admin SDK 초기화 (이미 초기화된 경우 건너뛰기)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        print("✅ Firebase 초기화 성공")
        
        # 1. 모든 컬렉션 확인
        print("\n📂 컬렉션 목록:")
        collections = db.collections()
        for collection in collections:
            docs = collection.get()
            print(f"  - {collection.id}: {len(docs)}개 문서")
            
            # 각 문서의 하위 컬렉션도 확인
            for doc in docs[:3]:  # 처음 3개만
                subcollections = doc.reference.collections()
                for subcol in subcollections:
                    subdocs = subcol.get()
                    print(f"    └─ {doc.id}/{subcol.id}: {len(subdocs)}개 문서")
        
        # 2. attendance 컬렉션 상세 확인
        print("\n🎯 attendance 컬렉션 상세:")
        attendance_docs = db.collection('attendance').get()
        print(f"attendance 컬렉션: {len(attendance_docs)}개 학생 문서")
        
        for doc in attendance_docs:
            records = doc.reference.collection('records').get()
            print(f"  - 학생 {doc.id}: {len(records)}개 출석 기록")
            for record in records[:2]:  # 처음 2개만
                data = record.to_dict()
                print(f"    └─ {record.id}: {data.get('name')} - {data.get('period')}")
        
        # 3. admin 컬렉션 상세 확인
        print("\n🔧 admin 컬렉션 상세:")
        admin_docs = db.collection('admin').get()
        print(f"admin 컬렉션: {len(admin_docs)}개 날짜+교시 문서")
        
        for doc in admin_docs:
            students = doc.reference.collection('students').get()
            print(f"  - {doc.id}: {len(students)}명 출석")
            for student in students[:2]:  # 처음 2개만
                data = student.to_dict()
                print(f"    └─ {student.id}: {data.get('name')} - {data.get('seat')}")
        
        # 4. 테스트 데이터 추가
        print("\n➕ 테스트 데이터 추가:")
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        date_str = now.strftime('%Y-%m-%d')
        datetime_str = now.strftime('%Y-%m-%d %H:%M:%S')
        
        test_data = {
            'student_id': 'TEST001',
            'name': '테스트학생',
            'seat': 'T01',
            'period': '테스트교시',
            'date': datetime_str,
            'date_only': date_str,
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        
        # attendance 구조에 저장
        attendance_ref = db.collection('attendance').document('TEST001').collection('records').document(date_str)
        attendance_ref.set(test_data)
        print("✅ attendance/TEST001/records 저장 완료")
        
        # admin 구조에 저장
        admin_ref = db.collection('admin').document(f"{date_str}_테스트교시").collection('students').document('TEST001')
        admin_ref.set(test_data)
        print("✅ admin 구조 저장 완료")
        
        # 5. 저장된 데이터 확인
        print("\n🔍 저장된 데이터 확인:")
        saved_attendance = attendance_ref.get()
        if saved_attendance.exists:
            print("✅ attendance 구조에서 데이터 확인됨")
        else:
            print("❌ attendance 구조에서 데이터 없음")
            
        saved_admin = admin_ref.get()
        if saved_admin.exists:
            print("✅ admin 구조에서 데이터 확인됨")
        else:
            print("❌ admin 구조에서 데이터 없음")
        
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

if __name__ == "__main__":
    test_firebase()