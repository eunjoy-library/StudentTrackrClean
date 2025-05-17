from flask_sqlalchemy import SQLAlchemy
from datetime import date

db = SQLAlchemy()

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), index=True)
    name = db.Column(db.String(100))
    seat = db.Column(db.String(20))
    period = db.Column(db.String(20))
    date = db.Column(db.Date, default=date.today)

    @staticmethod
    def add_attendance(student_id, name, seat, period_text):
        today = date.today()
        existing = Attendance.query.filter_by(
            student_id=student_id,
            period=period_text,
            date=today
        ).first()
        if existing:
            return  # 이미 출석한 경우 저장하지 않음
        new_record = Attendance(
            student_id=student_id,
            name=name,
            seat=seat,
            period=period_text,
            date=today
        )
        db.session.add(new_record)
        db.session.commit()