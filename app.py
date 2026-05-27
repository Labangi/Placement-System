from datetime import datetime, timedelta, date
from flask import Flask, render_template, request, redirect, session , url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

import os
from werkzeug.utils import secure_filename


# Initialize Flask application
app = Flask(__name__)

# Secret key for session management 
app.secret_key = "Labangi"

# Database configuration - using SQLite for simplicity
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///placement.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_FOLDER = "static/uploads/cvs"
ALLOWED_EXTENSIONS = {"pdf","doc","docx"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize SQLAlchemy database instance
db = SQLAlchemy(app)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin / student / company

    #  Admin control field
    status = db.Column(db.String(20),default="Active")  # active / inactive / blacklisted


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    full_name = db.Column(db.String(150))
    course = db.Column(db.String(100))
    branch = db.Column(db.String(100))
    graduation_year = db.Column(db.Integer)
    cgpa = db.Column(db.Float)
    contact=db.Column(db.String(255))
    skills=db.Column(db.String(255))
    project=db.Column(db.String(255))
    cv_file = db.Column(db.String(255))

    user = db.relationship("User", backref="student_profile")



class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    name = db.Column(db.String(150), nullable=False)
    hr_contact = db.Column(db.String(15))
    website = db.Column(db.String(255))
    approval_status = db.Column(db.String(20),default="pending") 
    user = db.relationship("User", backref="company_profile")


class PlacementDrive(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(db.Integer, db.ForeignKey("company.id"))
    job_title = db.Column(db.String(150))
    job_description = db.Column(db.Text)
    eligibility = db.Column(db.String(255))
    salary = db.Column(db.String(50))
    location = db.Column(db.String(100))
    deadline = db.Column(db.Date)
    status = db.Column(db.String(20), default="pending")  # pending/approved/closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    company = db.relationship("Company", backref="drives")


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.Integer, db.ForeignKey("student.id"))
    drive_id = db.Column(db.Integer, db.ForeignKey("placement_drive.id"))

    application_date = db.Column(db.DateTime, default=datetime.utcnow)

    status = db.Column(
        db.String(20),
        default="applied"
    )  # applied/shortlisted/selected/rejected

    student = db.relationship("Student", backref="applications")
    drive = db.relationship("PlacementDrive", backref="applications")

    #  prevents duplicate applications
    __table_args__ = (
        db.UniqueConstraint("student_id", "drive_id", name="unique_application"),
    )


#Home Page
@app.route('/',methods=['POST','GET'])
def home():
    return render_template('home.html')


#Registration page

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password_raw = request.form.get("password", "")
        role = request.form.get("role", "")

        if not all([username, password_raw, role]):
            flash("All fields are required.", "warning")
            return redirect(url_for("register"))

        if len(password_raw) < 6:
            flash("Password must be at least 6 characters.", "warning")
            return redirect(url_for("register"))


        user=User.query.filter_by(username=username).first()
        if user:
            if user.status=="Blacklisted":
                flash("User has been blacklisted!",'danger')
                return redirect(url_for("home"))

            flash("Username already exists.", "danger")
            return redirect(url_for("register"))

     

        try:
            #  STUDENT
            if role == "Student":
                user = User(
                    username=username,
                    password=generate_password_hash(password_raw),
                    role=role,
                    status="Active"
                )
                db.session.add(user)
                db.session.commit()

                flash("Student registered successfully!", "success")
                return redirect(url_for("login"))

            #  COMPANY
            elif role == "Company":
                user = User(
                    username=username,
                    password=generate_password_hash(password_raw),
                    role=role,
                    status="Inactive"
                )
                db.session.add(user)
                db.session.commit()

                flash("Company registered! Wait for admin approval.", "info")
                return redirect(url_for("home"))

          

        except Exception as e:
            db.session.rollback()
            print(e)
            flash("Registration failed.", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")



#Login module
@app.route('/login',methods=['POST','GET'])
def login():
    
    if request.method == "POST":
        # Get form data
        username = request.form.get("username", "").strip()
        password_raw = request.form.get("password", "")
        role = request.form.get("role", "")

        # Validate all fields are present
        if not all([username, password_raw, role]):
            flash("All fields are required.", "warning")
            return redirect(url_for("login"))

        # Query database for user with matching username and role
        user = User.query.filter_by(username=username, role=role).first()

        if user:

            if user.status=='Active':

                # Check if user exists and password matches
                if user and check_password_hash(user.password, password_raw):
                    # Create session - store user information
                    session["user_id"] = user.id
                    session["username"] = user.username
                    session["role"] = user.role

                    flash(f"Welcome back, {user.username}!", "success")

                    # Redirect to appropriate dashboard based on role
                    return redirect(url_for("dashboard_functions", role=user.role))
                else:
                    flash("Invalid credentials or role. Please try again.", "danger")
                    return redirect(url_for("login"))

            elif user.status=='Blacklisted':

                flash('Sorry!Your account has been blacklisted!','danger')
                return redirect(url_for('home'))

            else:
                flash('Sorry!Your account is inactive!','danger')
                return redirect(url_for('home'))
        
        else:
            flash('No user exists!','warning')
            return redirect(url_for('register'))

    # GET request - show login form
    return render_template("login.html")

#logout
@app.route("/logout")
def logout():
   
    username = session.get("username", "User")
    session.clear()  # Remove all session data
    flash(f"Goodbye, {username}! You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard_<role>")
def dashboard_functions(role):

    # Verify user's role matches requested dashboard
    if session.get("role") != role:
        flash("Access denied!", "danger")
        return redirect(url_for("login"))

    # Get user from database
    user = db.session.get(User, session["user_id"])
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for("login"))

    #  Company
    if role == "Company":

        user_id = session["user_id"]
        company = Company.query.filter_by(user_id=user.id).first()

      

        if not company:
            flash("Sorry!Cant log u in!", "warning")
            return redirect(url_for("login"))

        drives = PlacementDrive.query.filter_by(company_id=company.id).all()

        drive_data = []
        for drive in drives:
            applicant_count = Application.query.filter_by(
                drive_id=drive.id
            ).count()

            drive_data.append({
                "drive": drive,
                "applicant_count": applicant_count
            })

        return render_template(
            "dashboard_company.html",
            company=company,
            drive_data=drive_data
        )

    # STUDENT
    elif role == "Student":

        student = Student.query.filter_by(user_id=user.id).first()

        applications = Application.query.join(Student).filter(
            Student.user_id == user.id
        ).all()

        search = request.args.get("search")

        query = PlacementDrive.query.join(Company).join(User).filter(
            PlacementDrive.status == "approved",
            Company.approval_status == "approved",
            User.status == "Active"
        )

        if search:
            query = query.filter(
                (Company.name.ilike(f"%{search}%")) |
                (PlacementDrive.job_title.ilike(f"%{search}%"))
            )

        drives = query.all()

        return render_template(
            "dashboard_student.html",
            student=student,
            drives=drives,
            applications=applications
        )

    #  Admin
 
    elif role == "Admin":

        # Get search values from frontend
        student_search = request.args.get("student_search")
        company_search = request.args.get("company_search")

        # Pending company approvals
        inactive_users = User.query.filter_by(role="Company", status="Inactive").all()

        # Dashboard statistics
        total_students = User.query.filter_by(role="Student", status="Active").count()
        total_companies = User.query.filter_by(role="Company", status="Active").count()
        total_applications = Application.query.count()
        total_drives = PlacementDrive.query.count()

        # Drives
        pending_drives = PlacementDrive.query.filter_by(status="pending").all()
        all_drives = PlacementDrive.query.all()

        # Applications
        applications = Application.query.all()

        #  USER MANAGEMENT LIST

        if student_search:
            users = User.query.filter(
                (User.role == "Student") &
                ((User.username == student_search) | (User.id == student_search))
            ).all()

        elif company_search:
            users = User.query.filter(
                (User.role == "Company") &
                (User.username == company_search)
            ).all()

        else:
            users = User.query.filter(User.role != "Admin").all()

        return render_template(
            "dashboard_admin.html",
            total_students=total_students,
            total_companies=total_companies,
            total_applications=total_applications,
            total_drives=total_drives,
            pending_drives=pending_drives,
            all_drives=all_drives,
            applications=applications,
            inactive_users=inactive_users,
            users=users
        )

#Company Routes
#Create or edit company
@app.route("/create_company",methods=["GET","POST"])
def create_company():
    if session.get("role") != "Company":
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    company = Company.query.filter_by(user_id=user.id).first()

   
    if request.method == "POST":
        try:
            # Get form data
            name = request.form.get("name", "").strip()
            hr_contact = request.form.get("hr_contact", "").strip()
            website= request.form.get("website", "").strip()
            

            # Validate required field
            if not name:
                flash(" Name is required.", "warning")
                return redirect(url_for("create_company"))

           
            if company is None:
                # Create new student profile
                company = Company(
                    user_id=user.id,
                    name=name,
                    hr_contact=hr_contact,
                    website=website,
                    
                
                )
                db.session.add(company)
                msg = "Company profile created successfully!"
                print(f" company profile created: {name}")

            else:
               
                company.name = name
                company.hr_contact = hr_contact
                company.website = website
                   
                msg = "Company profile updated successfully!"
                print(f" Company profile updated: {company.name}")

            db.session.commit()
            flash(msg, "success")
            return redirect(url_for("dashboard_functions", role="Company"))

        except Exception as e:
            db.session.rollback()
            print(f"Error saving company profile: {str(e)}")
            flash(f"Error saving profile: {str(e)}", "danger")
            return redirect(url_for("create_company"))

            # GET request - show profile form
    return render_template("company_profile.html", user=user, company=company)

# Create Drive

@app.route("/create_drive", methods=["POST"])
def create_drive():

    if session.get("role") != "Company":
        return redirect(url_for("login"))

    user_id = session["user_id"]
    company = Company.query.filter_by(user_id=user_id).first()

    if not company:
        flash("Company profile not found.", "danger")
        return redirect(url_for("login"))

    if company.approval_status != "approved":
        flash("Your company is not approved yet.", "danger")
        return redirect(url_for("dashboard_functions", role="Company"))

    job_title = request.form.get("job_title")
    job_description = request.form.get("job_description")
    eligibility = request.form.get("eligibility")
    salary = request.form.get("salary")
    location = request.form.get("location")
    deadline_str  = request.form.get("deadline")
    deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()

    new_drive = PlacementDrive(
        company_id=company.id,
        job_title=job_title,
        job_description=job_description,
        eligibility=eligibility,
        salary=salary,
        location=location,
        deadline=deadline,
        status="pending"
    )

    db.session.add(new_drive)
    db.session.commit()

    flash("Placement drive created successfully!", "success")
    return redirect(url_for("dashboard_functions", role="Company"))


#  CLOSE DRIVE

@app.route("/close_drive/<int:drive_id>")
def close_drive(drive_id):

    if session.get("role") != "Company":
        return redirect(url_for("login"))

    user_id = session["user_id"]
    company = Company.query.filter_by(user_id=user_id).first()

    drive = PlacementDrive.query.get_or_404(drive_id)

    if drive.company_id != company.id:
        flash("Unauthorized action!", "danger")
        return redirect(url_for("dashboard_functions", role="Company"))

    drive.status = "closed"
    db.session.commit()

    flash("Drive closed successfully.", "success")
    return redirect(url_for("dashboard_functions", role="Company"))


# DELETE DRIVE 

@app.route("/delete_drive/<int:drive_id>")
def delete_drive(drive_id):

    if session.get("role") != "Company":
        return redirect(url_for("login"))

    user_id = session["user_id"]
    company = Company.query.filter_by(user_id=user_id).first()

    drive = PlacementDrive.query.get_or_404(drive_id)

    if drive.company_id != company.id:
        flash("Unauthorized action!", "danger")
        return redirect(url_for("dashboard_functions", role="Company"))

    db.session.delete(drive)
    db.session.commit()

    flash("Drive deleted successfully.", "success")
    return redirect(url_for("dashboard_functions", role="Company"))

#  EDIT DRIVE

@app.route("/edit_drive/<int:drive_id>", methods=["GET", "POST"])
def edit_drive(drive_id):

    if session.get("role") != "Company":
        return redirect(url_for("login"))

    drive = PlacementDrive.query.get_or_404(drive_id)

    user_id = session["user_id"]
    company = Company.query.filter_by(user_id=user_id).first()

    # Security check
    if drive.company_id != company.id:
        flash("Unauthorized action!", "danger")
        return redirect(url_for("dashboard_functions", role="Company"))

    if request.method == "POST":

        drive.job_title = request.form.get("job_title")
        drive.job_description = request.form.get("job_description")
        drive.eligibility = request.form.get("eligibility")
        drive.salary = request.form.get("salary")
        drive.location = request.form.get("location")

        deadline_str = request.form.get("deadline")
        drive.deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()

        db.session.commit()

        flash("Placement drive updated successfully!", "success")

        return redirect(url_for("dashboard_functions", role="Company"))

    return render_template("edit_drive.html", drive=drive)


@app.route("/view_applications/<int:drive_id>")
def view_applications(drive_id):

    if session.get("role") != "Company":
        return redirect(url_for("login"))

    user_id = session["user_id"]
    company = Company.query.filter_by(user_id=user_id).first()

    drive = PlacementDrive.query.get_or_404(drive_id)

    # Security check
    if drive.company_id != company.id:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard_functions", role="Company"))

    applications = Application.query.filter_by(drive_id=drive.id).all()

    return render_template(
        "company_applications.html",
        drive=drive,
        applications=applications
    )

#  UPDATE APPLICATION STATUS 

@app.route("/update_application/<int:app_id>/<status>")
def update_application(app_id, status):

    if session.get("role") != "Company":
        return redirect(url_for("login"))

    application = Application.query.get_or_404(app_id)

  
    if status not in ["shortlisted", "selected", "rejected"]:
        flash("Invalid status.", "danger")
        return redirect(url_for("dashboard_functions", role="Company"))

    application.status = status
    db.session.commit()

    flash("Application status updated.", "success")

    return redirect(
        url_for("view_applications", drive_id=application.drive_id)
    )

# Admin Dashboard
@app.route("/approve/<int:user_id>", methods=["POST"])
def approve(user_id):

    if session.get("role") != "Admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    user = db.session.get(User, user_id)

    if not user:
        flash("User not found!", "danger")
        return redirect(url_for("dashboard_functions", role="Admin"))

    try:
        # Activate user account
        user.status = "Active"

        if user.role == "Company":

            company = Company.query.filter_by(user_id=user.id).first()

            # If company profile does not exist create one
            if not company:
                company = Company(
                    user_id=user.id,
                    name=user.username,
                    approval_status="approved"
                )
                db.session.add(company)

            # If it exists just update approval
            else:
                company.approval_status = "approved"

        db.session.commit()

        flash(f"{user.username} approved successfully!", "success")

    except Exception as e:
        db.session.rollback()
        print(e)
        flash("Approval failed!", "danger")

    return redirect(url_for("dashboard_functions", role="Admin"))


@app.route("/reject/<int:user_id>", methods=["POST"])
def reject(user_id):

    if session.get("role") != "Admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    user = db.session.get(User, user_id)

    if not user:
        flash("User not found!", "danger")
        return redirect(url_for("dashboard_functions", role="Admin"))

    try:
        student = Student.query.filter_by(user_id=user.id).first()
        if student:
            db.session.delete(student)

        company = Company.query.filter_by(user_id=user.id).first()
        if company:
            db.session.delete(company)

        db.session.delete(user)
        db.session.commit()

        flash(f"{user.username} rejected and deleted!", "warning")

    except Exception as e:
        db.session.rollback()
        print(e)
        flash("Deletion failed!", "danger")

    return redirect(url_for("dashboard_functions", role="Admin"))


#ADMIN APPROVE DRIVE 

@app.route("/approve_drive/<int:drive_id>")
def approve_drive(drive_id):

    if session.get("role") != "Admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    drive = PlacementDrive.query.get_or_404(drive_id)

    drive.status = "approved"

    db.session.commit()

    flash("Placement drive approved successfully!", "success")

    return redirect(url_for("dashboard_functions", role="Admin"))


# Admin Reject Drive

@app.route("/reject_drive/<int:drive_id>")
def reject_drive(drive_id):

    if session.get("role") != "Admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    drive = PlacementDrive.query.get_or_404(drive_id)

    drive.status = "closed"

    db.session.commit()

    flash("Placement drive rejected.", "warning")

    return redirect(url_for("dashboard_functions", role="Admin"))

@app.route("/activate_user/<int:user_id>", methods=["POST"])
def activate_user(user_id):

    if session.get("role") != "Admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    user = User.query.get_or_404(user_id)

    # activate user
    user.status = "Active"

    # if user is a company update approval_status
    if user.role == "Company":

        company = Company.query.filter_by(user_id=user.id).first()

        if company:
            company.approval_status = "approved"

    db.session.commit()

    flash("User activated successfully!", "success")

    return redirect(url_for("dashboard_functions", role="Admin"))

@app.route("/deactivate_user/<int:user_id>", methods=["POST"])
def deactivate_user(user_id):

    if session.get("role") != "Admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    user = User.query.get_or_404(user_id)

    user.status = "Inactive"

    if user.role == "Company":

        company = Company.query.filter_by(user_id=user.id).first()

        if company:
            company.approval_status = "deactivated"


    db.session.commit()

    flash("User deactivated successfully!", "warning")

    return redirect(url_for("dashboard_functions", role="Admin"))

@app.route("/blacklist_user/<int:user_id>", methods=["POST"])
def blacklist_user(user_id):

    if session.get("role") != "Admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    user = User.query.get_or_404(user_id)

    user.status = "Blacklisted"

    if user.role == "Company":

        company = Company.query.filter_by(user_id=user.id).first()

        if company:
            company.approval_status = "blacklisted"


    db.session.commit()

    flash("User blacklisted successfully!", "danger")

    return redirect(url_for("dashboard_functions", role="Admin"))

#Admin view applications
@app.route("/admin_view_applications/<int:drive_id>")
def admin_view_applications(drive_id):

    if session.get("role") != "Admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    drive = PlacementDrive.query.get_or_404(drive_id)

    applications = Application.query.filter_by(drive_id=drive.id).all()

    return render_template(
        "admin_applications.html",
        drive=drive,
        applications=applications
    )
#Student Routes
@app.route('/create_student',methods=['GET','POST'])
def create_student():

    if session.get("role") != "Student":
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    student = Student.query.filter_by(user_id=user.id).first()

    if request.method == "POST":
        try:
            # Get form data
            full_name = request.form.get("full_name", "").strip()
            course = request.form.get("course", "").strip()
            branch = request.form.get("branch", "").strip()
            graduation_year = request.form.get("graduation_year", "").strip()
            cgpa = request.form.get("cgpa", "").strip()
            contact = request.form.get("contact", "").strip()
            skills = request.form.get("skills", "").strip()
            project = request.form.get("project", "").strip()

            # -------- CV Upload --------
            cv = request.files.get("cv")
            filename = None

            if cv and allowed_file(cv.filename):

                filename = secure_filename(cv.filename)

                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

                cv.save(filepath)
           

            # Create new student profile
            if student is None:

                student = Student(
                    user_id=user.id,
                    full_name=full_name,
                    course=course,
                    branch=branch,
                    graduation_year=graduation_year,
                    cgpa=cgpa,
                    contact=contact,
                    skills=skills,
                    project=project,
                    cv_file=filename
                )

                db.session.add(student)
                msg = "Student profile created successfully!"

            # Update existing profile
            else:

                student.full_name = full_name
                student.course = course
                student.branch = branch
                student.graduation_year = graduation_year
                student.cgpa = cgpa
                student.contact = contact
                student.skills = skills
                student.project = project

                if filename:
                    student.cv_file = filename

                msg = "Student profile updated successfully!"

            db.session.commit()

            flash(msg, "success")

            return redirect(url_for("dashboard_functions", role="Student"))

        except Exception as e:

            db.session.rollback()
            print(f"Error saving student profile: {str(e)}")

            flash("Error saving profile", "danger")

            return redirect(url_for("create_student"))

    return render_template("student_profile.html", user=user, student=student)

@app.route("/apply_drive/<int:drive_id>")
def apply_drive(drive_id):

    if session.get("role") != "Student":
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    student = Student.query.filter_by(user_id=user.id).first()

    if not student:
        flash("Please complete your student profile first.", "warning")
        return redirect(url_for("create_student"))

    drive = PlacementDrive.query.get_or_404(drive_id)

    # Prevent duplicate applications
    existing = Application.query.filter_by(
        student_id=student.id,
        drive_id=drive.id
    ).first()

    if existing:
        flash("You already applied for this drive.", "warning")
        return redirect(url_for("dashboard_functions", role="Student"))

    application = Application(
        student_id=student.id,
        drive_id=drive.id
    )

    db.session.add(application)
    db.session.commit()

    flash("Application submitted successfully!", "success")

    return redirect(url_for("dashboard_functions", role="Student"))


# Application Initialisation

with app.app_context():

    db.create_all()
    print("Database tables created")

    admin = User.query.filter_by(username="admin").first()

    if not admin:

        admin = User(
            username="admin",
            password=generate_password_hash("admin123"),
            role="Admin",
            status="Active"
        )

        db.session.add(admin)
        db.session.commit()

        print("Admin user created")

    else:
        print("Admin already exists")


if __name__ == "__main__":
    app.run(debug=False)