from flask import Flask, render_template, request, redirect, flash, url_for
from models import db, Attendance
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        student_id = request.form["student_id"]
        name = request.form["name"]
        seat = request.form["seat"]
        period = request.form["period"]
        Attendance.add_attendance(student_id, name, seat, period)
        flash("출석이 완료되었습니다.")
        return redirect("/")
    return render_template("index.html")

@app.route("/list")
def list_attendance():
    records = Attendance.query.order_by(Attendance.date.desc()).all()
    return render_template("list.html", records=records)

if __name__ == "__main__":
    app.run()