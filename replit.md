# Library Attendance System

## Overview

This is a Flask-based library attendance system designed for student check-ins during class periods. The system allows students to check in by entering their student ID, tracks attendance by time periods, and provides administrative features for managing student data and viewing attendance statistics.

## System Architecture

### Backend Architecture
- **Framework**: Flask (Python web framework)
- **Database**: PostgreSQL (via Render cloud service)
- **Cloud Storage**: Firebase Firestore for real-time data operations
- **Authentication**: Session-based admin authentication
- **File Processing**: pandas and openpyxl for Excel data manipulation

### Frontend Architecture
- **Template Engine**: Jinja2 (Flask's default)
- **CSS Framework**: Bootstrap 5 with dark theme
- **Icons**: Font Awesome
- **JavaScript**: Vanilla JS with Web Audio API for sound effects
- **Responsive Design**: Mobile-first approach with tablet optimization

## Key Components

### Core Flask Application (`app.py`)
- Main application entry point with route definitions
- Handles student check-in process with duplicate prevention
- Manages time period calculations (1st-6th periods, after-hours)
- Implements session-based admin authentication
- Provides REST API endpoints for AJAX operations

### Student Data Management
- Excel-based student roster (`students.xlsx`)
- In-memory caching with 30-minute refresh intervals
- Support for adding, editing, and deleting student records
- Bulk seat number updates via CSV upload

### Attendance Tracking
- CSV-based attendance logging (`attendance.csv`)
- Period-based organization (1교시-6교시, 시간 외)
- Real-time attendance validation (one check-in per week rule)
- Firebase integration for real-time updates

### Administrative Features
- Protected admin routes with password authentication
- Student statistics and attendance reports
- Warning system for student behavior management
- Bulk operations for student data management

## Data Flow

1. **Student Check-in Process**:
   - Student enters ID on main form
   - System validates student existence and attendance eligibility
   - Current time period is calculated
   - Attendance record is created in CSV and Firebase
   - Audio feedback is provided for success/failure

2. **Data Storage**:
   - Student roster: Excel file (`students.xlsx`)
   - Attendance records: CSV file (`attendance.csv`)
   - Real-time sync: Firebase Firestore
   - Admin sessions: Flask session storage

3. **Admin Operations**:
   - Authentication via session management
   - CRUD operations on student data
   - Attendance report generation
   - Bulk data import/export capabilities

## External Dependencies

### Cloud Services
- **Render PostgreSQL**: Primary database hosting
- **Firebase**: Real-time data synchronization and cloud storage
- **Replit**: Application hosting and development environment

### Python Libraries
- Flask ecosystem (Flask, Flask-SQLAlchemy, Flask-WTF)
- Data processing (pandas, openpyxl, numpy)
- Firebase SDK (firebase-admin)
- Database connectivity (psycopg2-binary)
- Web server (gunicorn)

### Frontend Libraries
- Bootstrap 5 (via CDN)
- Font Awesome icons (via CDN)
- Google Fonts (Noto Sans KR)

## Deployment Strategy

### Production Configuration
- **Web Server**: Gunicorn WSGI server
- **Port Configuration**: 5000 (mapped to external port 80)
- **Environment**: Production mode with environment variables
- **Process Management**: Replit's autoscale deployment target

### Environment Variables
- Database connection strings (PostgreSQL)
- Firebase service account credentials (JSON format)
- Admin authentication credentials
- Flask secret keys for session management

### Deployment Files
- `.replit`: Replit configuration with deployment settings
- `Procfile`: Process definition for production deployment
- `requirements.txt`: Python dependency specifications
- `pyproject.toml`: Modern Python project configuration

## Changelog

- August 25, 2025:
  - **NEW FEATURE**: 3학년 학생 중복 출석 허용 기능 추가
    - 학번이 3으로 시작하는 3학년 학생들은 일주일에 여러 번 출석 가능
    - 3학년 학생 중복 출석시 특별 격려 메시지 표시 ("📚 3학년 중복 출석 가능 📚 입시 준비 화이팅!")
    - 백엔드와 프론트엔드 모두에서 3학년 학생 특별 처리 로직 구현
  - **ENHANCEMENT**: 관리자 자동 로그인 기능 추가
    - /admin 접속시 비밀번호 입력 없이 바로 관리자 페이지로 이동
    - 수동 로그인은 /admin_manual_login에서 여전히 사용 가능
  - **BUG FIX**: 새 학생 추가 후 즉시 출석 불가 문제 해결
    - Excel 파일 구조 자동 감지 (헤더 유무 판단)
    - 학생 추가 후 캐시 강제 새로고침으로 즉시 인식
    - Firebase 자동 백업으로 데이터 영구 보존
- June 27, 2025: 
  - Fixed admin login credentials mismatch - updated ADMIN_ACCESS_ID from 20250107 to 20255008
  - Resolved CSV header compatibility issue for Korean language headers in attendance records
  - Fixed attendance record display in admin panel by correcting CSV parsing
  - Restored twice-weekly student popup notification feature with special messaging
  - Implemented dual CSV+Firebase saving for immediate reflection in admin dashboard
  - **MAJOR FIX**: Resolved delete functionality in admin panel by correcting CSV column name mapping ('날짜' → '출석일')
  - Delete function now properly removes records from both CSV and Firebase with accurate matching
- June 26, 2025: Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.