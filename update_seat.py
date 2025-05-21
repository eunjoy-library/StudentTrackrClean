import pandas as pd

# Excel 파일 경로
excel_path = 'students.xlsx'

# 학생 데이터 로드
df = pd.read_excel(excel_path)

# 현재 데이터 확인 (처음 10개만)
print("변경 전 학생 데이터:")
print(df.head(10))

# 수정할 학생 정보
student_id = input("수정할 학생의 학번을 입력하세요: ")
new_seat = input("새 좌석번호를 입력하세요: ")

# 학생 찾기 및 좌석번호 수정
if student_id in df['학번'].astype(str).values:
    # 해당 학생의 인덱스 찾기 
    idx = df[df['학번'].astype(str) == student_id].index[0]
    
    # 기존 좌석번호 확인
    old_seat = df.at[idx, '좌석번호']
    print(f"학번 {student_id}의 현재 좌석번호: {old_seat}")
    
    # 새 좌석번호로 수정
    df.at[idx, '좌석번호'] = new_seat
    
    # 변경 사항 저장
    df.to_excel(excel_path, index=False)
    print(f"학번 {student_id}의 좌석번호가 {old_seat}에서 {new_seat}로 변경되었습니다.")
else:
    print(f"학번 {student_id}를 찾을 수 없습니다.")

print("\n수정된 데이터 확인:")
df_updated = pd.read_excel(excel_path)
filtered_df = df_updated[df_updated['학번'].astype(str) == student_id]
if not filtered_df.empty:
    print(filtered_df)
else:
    print("해당 학생 정보를 찾을 수 없습니다.")