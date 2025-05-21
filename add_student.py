"""
새 학생 정보를 직접 추가하는 간단한 스크립트
- 엑셀 파일에 새 행을 직접 추가하는 방식
"""

import sys
import pandas as pd
from openpyxl import load_workbook

def add_new_student(student_id, name, seat):
    """학생 정보를 Excel 파일에 직접 추가"""
    try:
        # 파일 열기
        excel_path = 'students.xlsx'
        
        # 기존 파일 로드
        df = pd.read_excel(excel_path)
        
        # 칼럼 이름 확인
        column_names = df.columns.tolist()
        print(f"엑셀 파일 칼럼: {column_names}")
        
        # 학번, 이름, 좌석번호 열 찾기
        id_column = None
        name_column = None
        seat_column = None
        
        for col in column_names:
            if '학번' in str(col) or 'id' in str(col).lower():
                id_column = col
            elif '이름' in str(col) or 'name' in str(col).lower():
                name_column = col
            elif '좌석' in str(col) or 'seat' in str(col).lower():
                seat_column = col
        
        print(f"학번 열: {id_column}")
        print(f"이름 열: {name_column}")
        print(f"좌석번호 열: {seat_column}")
        
        if not id_column or not seat_column:
            print("오류: 필수 열을 찾을 수 없습니다")
            return False
        
        # 중복 학번 확인
        if student_id in df[id_column].astype(str).values:
            print(f"학번 {student_id}는 이미 존재합니다.")
            # 기존 데이터 업데이트
            idx = df[df[id_column].astype(str) == student_id].index[0]
            if seat_column:
                df.at[idx, seat_column] = seat
            if name_column and name:
                df.at[idx, name_column] = name
            print(f"학생 정보를 업데이트했습니다. 학번: {student_id}")
        else:
            # 새 학생 추가
            new_row = {id_column: student_id}
            if seat_column:
                new_row[seat_column] = seat
            if name_column and name:
                new_row[name_column] = name
                
            # 데이터프레임에 행 추가
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            print(f"새 학생을 추가했습니다. 학번: {student_id}")
        
        # 변경사항 저장
        df.to_excel(excel_path, index=False)
        print(f"파일에 변경사항이 저장되었습니다: {excel_path}")
        return True
    
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("사용법: python add_student.py <학번> <이름> <좌석번호>")
        sys.exit(1)
    
    student_id = sys.argv[1]
    name = sys.argv[2]
    seat = sys.argv[3]
    
    add_new_student(student_id, name, seat)