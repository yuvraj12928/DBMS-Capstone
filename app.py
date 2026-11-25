from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from datetime import date

app = Flask(__name__)
app.secret_key = "payroll_attendance_project_key"


# ---------------- DATABASE CONNECTION ----------------

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Kunal.dahiyaa@2468",
        database="payroll_attendance_db"
    )


# ---------------- DASHBOARD ----------------

@app.route("/")
def dashboard():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM Employee")
    total_employees = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM Attendance
        WHERE attendance_date = CURDATE()
        AND attendance_status = 'Present'
    """)
    present_today = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM `Leave`
        WHERE leave_status = 'Pending'
    """)
    pending_leaves = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COALESCE(SUM(net_salary), 0) AS total
        FROM Payroll
        WHERE payroll_month = DATE_FORMAT(CURDATE(), '%Y-%m-01')
    """)
    monthly_payroll = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT employee_id, full_name, department,
               designation, employment_status
        FROM Employee
        ORDER BY employee_id
    """)
    employees = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "index.html",
        total_employees=total_employees,
        present_today=present_today,
        pending_leaves=pending_leaves,
        monthly_payroll=monthly_payroll,
        employees=employees
    )


# ---------------- EMPLOYEES ----------------

@app.route("/employees")
def employees_page():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM Employee
        ORDER BY employee_id
    """)
    employees = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("employees.html", employees=employees)


@app.route("/employees/add", methods=["POST"])
def add_employee():
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO Employee
            (full_name, email, phone, joining_date,
             department, designation, employment_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            request.form["full_name"],
            request.form["email"],
            request.form.get("phone", ""),
            request.form["joining_date"],
            request.form["department"],
            request.form["designation"],
            "Active"
        ))

        db.commit()
        flash("Employee added successfully!", "success")

    except mysql.connector.Error as e:
        db.rollback()
        flash(f"Error adding employee: {e}", "error")

    finally:
        cursor.close()
        db.close()

    return redirect(url_for("employees_page"))


# ---------------- ATTENDANCE ----------------

@app.route("/attendance")
def attendance_page():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT A.*, E.full_name, E.department
        FROM Attendance A
        JOIN Employee E ON A.employee_id = E.employee_id
        ORDER BY A.attendance_date DESC, A.employee_id
    """)
    attendance = cursor.fetchall()

    cursor.execute("""
        SELECT employee_id, full_name
        FROM Employee
        WHERE employment_status = 'Active'
        ORDER BY full_name
    """)
    employees = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "attendance.html",
        attendance=attendance,
        employees=employees
    )


@app.route("/attendance/add", methods=["POST"])
def add_attendance():
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO Attendance
            (employee_id, attendance_date, check_in, check_out,
             attendance_status, late_minutes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            request.form["employee_id"],
            request.form["attendance_date"],
            request.form.get("check_in") or None,
            request.form.get("check_out") or None,
            request.form["attendance_status"],
            request.form.get("late_minutes", 0)
        ))

        db.commit()
        flash("Attendance added successfully!", "success")

    except mysql.connector.Error as e:
        db.rollback()
        flash(f"Attendance error: {e}", "error")

    finally:
        cursor.close()
        db.close()

    return redirect(url_for("attendance_page"))


# ---------------- LEAVES ----------------

@app.route("/leaves")
def leaves_page():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT L.*, E.full_name, E.department
        FROM `Leave` L
        JOIN Employee E ON L.employee_id = E.employee_id
        ORDER BY L.leave_id DESC
    """)
    leaves = cursor.fetchall()

    cursor.execute("""
        SELECT employee_id, full_name
        FROM Employee
        ORDER BY full_name
    """)
    employees = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "leaves.html",
        leaves=leaves,
        employees=employees
    )


@app.route("/leaves/add", methods=["POST"])
def add_leave():
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO `Leave`
            (employee_id, start_date, end_date,
             leave_type, leave_status, reason)
            VALUES (%s, %s, %s, %s, 'Pending', %s)
        """, (
            request.form["employee_id"],
            request.form["start_date"],
            request.form["end_date"],
            request.form["leave_type"],
            request.form.get("reason", "")
        ))

        db.commit()
        flash("Leave request submitted!", "success")

    except mysql.connector.Error as e:
        db.rollback()
        flash(f"Leave error: {e}", "error")

    finally:
        cursor.close()
        db.close()

    return redirect(url_for("leaves_page"))


@app.route("/leaves/update/<int:leave_id>", methods=["POST"])
def update_leave(leave_id):
    status = request.form["leave_status"]

    if status not in ["Approved", "Rejected"]:
        flash("Invalid leave status.", "error")
        return redirect(url_for("leaves_page"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        if status == "Approved":
            cursor.execute("""
                SELECT employee_id, start_date, end_date
                FROM `Leave`
                WHERE leave_id = %s
            """, (leave_id,))
            selected_leave = cursor.fetchone()

            if selected_leave:
                cursor.execute("""
                    SELECT leave_id
                    FROM `Leave`
                    WHERE employee_id = %s
                    AND leave_status = 'Approved'
                    AND start_date <= %s
                    AND end_date >= %s
                    AND leave_id != %s
                """, (
                    selected_leave["employee_id"],
                    selected_leave["end_date"],
                    selected_leave["start_date"],
                    leave_id
                ))

                overlap = cursor.fetchone()

                if overlap:
                    flash("This leave overlaps with an approved leave.", "error")
                    return redirect(url_for("leaves_page"))

        cursor.execute("""
            UPDATE `Leave`
            SET leave_status = %s
            WHERE leave_id = %s
            AND leave_status = 'Pending'
        """, (status, leave_id))

        db.commit()
        flash(f"Leave {status.lower()} successfully!", "success")

    except mysql.connector.Error as e:
        db.rollback()
        flash(f"Error updating leave: {e}", "error")

    finally:
        cursor.close()
        db.close()

    return redirect(url_for("leaves_page"))


# ---------------- PAYROLL ----------------

@app.route("/payroll")
def payroll_page():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT P.*, E.full_name, E.department, E.designation
        FROM Payroll P
        JOIN Employee E ON P.employee_id = E.employee_id
        ORDER BY P.payroll_month DESC, E.employee_id
    """)
    payroll = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("payroll.html", payroll=payroll)


# ---------------- REPORTS ----------------

@app.route("/reports")
def reports_page():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Monthly attendance report
    cursor.execute("""
        SELECT
            E.employee_id,
            E.full_name,
            YEAR(A.attendance_date) AS attendance_year,
            MONTH(A.attendance_date) AS attendance_month,
            COUNT(*) AS total_records,
            SUM(A.attendance_status = 'Present') AS present_days,
            SUM(A.attendance_status = 'Absent') AS absent_days,
            SUM(A.attendance_status = 'Half Day') AS half_days,
            SUM(A.late_minutes) AS total_late_minutes
        FROM Employee E
        JOIN Attendance A ON E.employee_id = A.employee_id
        GROUP BY
            E.employee_id,
            E.full_name,
            YEAR(A.attendance_date),
            MONTH(A.attendance_date)
        ORDER BY attendance_year DESC, attendance_month DESC,
                 E.employee_id
    """)
    attendance_report = cursor.fetchall()

    # Late attendance report
    cursor.execute("""
        SELECT E.full_name, E.department,
               A.attendance_date, A.check_in, A.late_minutes
        FROM Attendance A
        JOIN Employee E ON A.employee_id = E.employee_id
        WHERE A.late_minutes > 0
        ORDER BY A.attendance_date DESC
    """)
    late_report = cursor.fetchall()

    # Salary report
    cursor.execute("""
        SELECT E.employee_id, E.full_name,
               P.payroll_month, P.gross_salary,
               P.deductions, P.tax, P.net_salary,
               P.payment_status
        FROM Payroll P
        JOIN Employee E ON P.employee_id = E.employee_id
        ORDER BY P.payroll_month DESC, E.employee_id
    """)
    salary_report = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "reports.html",
        attendance_report=attendance_report,
        late_report=late_report,
        salary_report=salary_report
    )


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    app.run(debug=True)
