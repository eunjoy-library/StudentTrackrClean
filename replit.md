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

- June 27, 2025: 
  - Fixed admin login credentials mismatch - updated ADMIN_ACCESS_ID from 20250107 to 20255008
  - Resolved CSV header compatibility issue for Korean language headers in attendance records
  - Fixed attendance record display in admin panel by correcting CSV parsing
  - Restored twice-weekly student popup notification feature with special messaging
  - Implemented dual CSV+Firebase saving for immediate reflection in admin dashboard
- June 26, 2025: Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.