#!/usr/bin/env python3
"""
Direct Firebase test to verify data saving and loading
"""
import os
import json
from datetime import datetime
import pytz

# Import Firebase from app.py
import sys
sys.path.append('.')
from app import db, logging

def test_firebase_direct():
    """Test Firebase operations directly"""
    if not db:
        print("❌ Firebase not initialized")
        return
    
    print("✅ Firebase connected")
    
    # Test data
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    date_str = now.strftime('%Y-%m-%d')
    
    test_data = {
        'student_id': 'TEST123',
        'name': '테스트학생',
        'seat': 'T01',
        'period': '테스트교시',
        'date': now.strftime('%Y-%m-%d %H:%M:%S'),
        'date_only': date_str,
    }
    
    # 1. Save to attendance collection
    try:
        attendance_ref = db.collection('attendance').document('TEST123').collection('records').document(date_str)
        attendance_ref.set(test_data)
        print("✅ attendance 저장 성공")
    except Exception as e:
        print(f"❌ attendance 저장 실패: {e}")
    
    # 2. Save to admin collection
    try:
        admin_ref = db.collection('admin').document(f"{date_str}_테스트교시").collection('students').document('TEST123')
        admin_ref.set(test_data)
        print("✅ admin 저장 성공")
    except Exception as e:
        print(f"❌ admin 저장 실패: {e}")
    
    # 3. Load from attendance collection
    try:
        attendance_docs = db.collection('attendance').get()
        print(f"📂 attendance 컬렉션: {len(attendance_docs)}개 학생")
        
        for doc in attendance_docs:
            records = doc.reference.collection('records').get()
            print(f"  - 학생 {doc.id}: {len(records)}개 기록")
    except Exception as e:
        print(f"❌ attendance 로드 실패: {e}")
    
    # 4. Load from admin collection
    try:
        admin_docs = db.collection('admin').get()
        print(f"📂 admin 컬렉션: {len(admin_docs)}개 날짜+교시")
        
        for doc in admin_docs:
            students = doc.reference.collection('students').get()
            print(f"  - {doc.id}: {len(students)}명 출석")
    except Exception as e:
        print(f"❌ admin 로드 실패: {e}")

if __name__ == "__main__":
    test_firebase_direct()