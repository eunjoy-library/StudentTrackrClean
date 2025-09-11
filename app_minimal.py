#!/usr/bin/env python3
"""
Render 배포 테스트용 최소 Flask 앱
"""

from flask import Flask, render_template_string
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'test-secret-key')

@app.route('/')
def home():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>출석 시스템 - 배포 테스트</title>
        <meta charset="UTF-8">
    </head>
    <body>
        <h1>📚 도서관 출석 시스템</h1>
        <p>✅ Flask 앱이 성공적으로 배포되었습니다!</p>
        <p>🔗 환경 변수 상태:</p>
        <ul>
            <li>SESSION_SECRET: {{ 'O' if session_secret else 'X' }}</li>
            <li>ADMIN_ACCESS_ID: {{ 'O' if admin_id else 'X' }}</li>
            <li>FIREBASE_CREDENTIALS_JSON: {{ 'O' if firebase else 'X' }}</li>
        </ul>
        <p><a href="/health">헬스체크</a></p>
    </body>
    </html>
    """
    
    return render_template_string(html,
        session_secret=bool(os.environ.get('SESSION_SECRET')),
        admin_id=bool(os.environ.get('ADMIN_ACCESS_ID')),
        firebase=bool(os.environ.get('FIREBASE_CREDENTIALS_JSON'))
    )

@app.route('/health')
def health():
    return {
        "status": "OK",
        "message": "출석 시스템이 정상 작동 중입니다",
        "python_version": "3.11+",
        "flask_version": "3.1.0"
    }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)