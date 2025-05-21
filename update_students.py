"""
학생 정보를 일괄 업데이트하는 간단한 스크립트
- 새 학생 추가 및 기존 학생 정보 수정 지원
- 기본 students.xlsx 파일에 직접 쓰기
"""

import os
import pandas as pd
from openpyxl import load_workbook

def update_student_data(student_id, seat=None, name=None):
    """
    학생 정보를 업데이트하거나 없는 경우 새로 추가
    
    Args:
        student_id (str): 학번
        seat (str, optional): 새 좌석번호
        name (str, optional): 새 이름
    
    Returns:
        bool: 성공 여부
    """
    excel_path = 'students.xlsx'
    
    # 파일 존재 여부 확인
    if not os.path.exists(excel_path):
        print(f"오류: {excel_path} 파일이 존재하지 않습니다.")
        return False
    
    try:
        # pandas로 데이터 로드
        df = pd.read_excel(excel_path)
        
        # 학번 열 이름 파악
        id_col = None
        seat_col = None
        name_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if '학번' in col_lower or 'id' in col_lower:
                id_col = col
            elif '좌석' in col_lower or 'seat' in col_lower:
                seat_col = col
            elif '이름' in col_lower or 'name' in col_lower:
                name_col = col
        
        if not id_col or not seat_col:
            print(f"오류: 학번 또는 좌석번호 열을 찾을 수 없습니다.")
            return False
        
        # 문자열로 변환하여 비교 (데이터 타입 불일치 방지)
        df[id_col] = df[id_col].astype(str)
        
        # 학번으로 학생 검색
        student_exists = student_id in df[id_col].values
        
        if student_exists:
            # 기존 학생 정보 업데이트
            idx = df[df[id_col] == student_id].index[0]
            
            if seat and seat_col:
                df.at[idx, seat_col] = seat
            
            if name and name_col:
                df.at[idx, name_col] = name
                
            print(f"학생 정보 업데이트 완료: {student_id}")
        else:
            # 새 학생 추가
            new_student = {id_col: student_id}
            
            if seat and seat_col:
                new_student[seat_col] = seat
                
            if name and name_col:
                new_student[name_col] = name
                
            df = pd.concat([df, pd.DataFrame([new_student])], ignore_index=True)
            print(f"새 학생 추가 완료: {student_id}")
        
        # 엑셀 파일로 저장
        df.to_excel(excel_path, index=False)
        return True
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return False

if __name__ == "__main__":
    # 사용 예시
    update_student_data("10701", "600", "한가람")