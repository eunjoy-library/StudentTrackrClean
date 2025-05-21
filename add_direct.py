"""
새 학생을 직접 추가하는 간단한 API 엔드포인트
"""
from flask import Flask, request, jsonify
import csv
import os

app = Flask(__name__)

@app.route('/api/add_student', methods=['POST'])
def add_student():
    """새 학생을 추가하는 API"""
    data = request.json
    
    if not data or 'student_id' not in data or 'seat' not in data or 'name' not in data:
        return jsonify({"error": "필수 정보가 누락되었습니다. (학번, 이름, 좌석번호)"}), 400
    
    student_id = data['student_id']
    name = data['name']
    seat = data['seat']
    
    try:
        # 기존 학생 데이터 로드
        students = []
        student_ids = set()
        
        # CSV 형태로 저장
        csv_path = "new_students.csv"
        
        # 기존 파일이 있으면 로드
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)  # 헤더 읽기
                for row in reader:
                    if len(row) >= 3:
                        students.append(row)
                        student_ids.add(row[0])
        else:
            # 새 파일 생성 시 헤더 설정
            header = ["학번", "이름", "좌석번호"]
        
        # 중복 체크
        if student_id in student_ids:
            return jsonify({"warning": "이미 존재하는 학번입니다. 정보가 업데이트되지 않았습니다."}), 200
        
        # 학생 추가
        students.append([student_id, name, seat])
        
        # CSV 파일로 저장
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(students)
        
        return jsonify({
            "success": True, 
            "message": f"학생이 추가되었습니다: 학번 {student_id}, 이름 {name}, 좌석번호 {seat}"
        })
    
    except Exception as e:
        return jsonify({"error": f"학생 추가 중 오류 발생: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)