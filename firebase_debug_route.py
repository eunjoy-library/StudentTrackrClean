#!/usr/bin/env python3
"""
Firebase debug route to check data directly
"""

from datetime import datetime
import pytz
from firebase_admin import firestore

def debug_firebase_data(db):
    """Debug Firebase data structure"""
    if not db:
        return "Firebase not connected"
    
    results = []
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    date_str = now.strftime('%Y-%m-%d')
    
    # 1. Test write operation
    try:
        test_data = {
            'student_id': 'DEBUG001',
            'name': '디버그테스트',
            'seat': 'D01',
            'period': '디버그교시',
            'date': now.strftime('%Y-%m-%d %H:%M:%S'),
            'date_only': date_str,
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        
        # Write to admin collection
        admin_ref = db.collection('admin').document(f"{date_str}_디버그교시").collection('students').document('DEBUG001')
        admin_ref.set(test_data)
        results.append("✅ admin 컬렉션 저장 성공")
        
        # Write to attendance collection
        attendance_ref = db.collection('attendance').document('DEBUG001').collection('records').document(date_str)
        attendance_ref.set(test_data)
        results.append("✅ attendance 컬렉션 저장 성공")
        
    except Exception as e:
        results.append(f"❌ 저장 실패: {e}")
    
    # 2. Test read operations
    try:
        # Read from admin
        admin_docs = list(db.collection('admin').stream())
        results.append(f"📂 admin 컬렉션: {len(admin_docs)}개 문서")
        
        for doc in admin_docs[:3]:
            students = list(doc.reference.collection('students').stream())
            results.append(f"  - {doc.id}: {len(students)}명")
            
        # Read from attendance
        attendance_docs = list(db.collection('attendance').stream())
        results.append(f"📂 attendance 컬렉션: {len(attendance_docs)}개 학생")
        
        for doc in attendance_docs[:3]:
            records = list(doc.reference.collection('records').stream())
            results.append(f"  - 학생 {doc.id}: {len(records)}개 기록")
            
    except Exception as e:
        results.append(f"❌ 읽기 실패: {e}")
    
    # 3. All collections
    try:
        all_collections = list(db.collections())
        results.append(f"📚 전체 컬렉션: {[c.id for c in all_collections]}")
    except Exception as e:
        results.append(f"❌ 컬렉션 목록 실패: {e}")
    
    return "\n".join(results)