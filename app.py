import os
import logging
from datetime import timedelta

from flask import Flask, request, jsonify, session, send_file
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from dotenv import load_dotenv
from dotenv import load_dotenv
 
load_dotenv()


# ── Local modules ─────────────────────────────
import database as db # type: ignore
from ai_engine   import analyze_resume
from file_parser import extract_text, allowed_file
from pdf_generator import generate_pdf_report

# ── Logging ───────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Flask app ─────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)
app.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("MAX_CONTENT_LENGTH_MB", 5)
) * 1024 * 1024

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── CORS (allow React frontend on localhost:3000 / 5173) ──
CORS(app, supports_credentials=True, origins=[
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "https://compassai-mu.vercel.app",
])

# ── Initialise DB tables on startup ───────────
with app.app_context():
    try:
        db.init_db()
    except Exception as e:
        logger.error("Could not initialise database: %s", e)


# ─────────────────────────────────────────────
# Decorator
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"status": "error", "message": "Unauthorized — please log in"}), 401
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────

@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Smart Career Guidance API is running 🚀"})


# ─────────────────────────────────────────────
# Auth routes
# ─────────────────────────────────────────────

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "JSON body required"}), 400

    username = data.get("username", "").strip()
    email    = data.get("email",    "").strip().lower()
    password = data.get("password", "")
    confirm  = data.get("confirm_password", "")

    # ── Validation ────────────────────────────
    if not all([username, email, password]):
        return jsonify({"status": "error", "message": "username, email and password are required"}), 400

    if password != confirm:
        return jsonify({"status": "error", "message": "Passwords do not match"}), 400

    if len(password) < 6:
        return jsonify({"status": "error", "message": "Password must be at least 6 characters"}), 400

    if db.email_exists(email):
        return jsonify({"status": "error", "message": "Email already registered"}), 409

    hashed = generate_password_hash(password)
    user_id = db.create_user(username, email, hashed)

    session.permanent = True
    session["user_id"]  = user_id
    session["username"] = username

    return jsonify({
        "status":  "success",
        "message": "Account created successfully",
        "user": {"id": user_id, "username": username, "email": email}
    }), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "JSON body required"}), 400

    email    = data.get("email",    "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password are required"}), 400

    user = db.get_user_by_email(email)

    if user and check_password_hash(user["password_hash"], password):
        session.permanent  = True
        session["user_id"]  = user["id"]
        session["username"] = user["username"]

        return jsonify({
            "status":  "success",
            "message": "Login successful",
            "user": {
                "id":       user["id"],
                "username": user["username"],
                "email":    user["email"],
            }
        })

    return jsonify({"status": "error", "message": "Invalid email or password"}), 401


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return jsonify({"status": "success", "message": "Logged out successfully"})


@app.route("/me", methods=["GET"])
@login_required
def me():
    """Return current session user — used by the frontend to check auth state."""
    return jsonify({
        "status":  "success",
        "user_id":  session["user_id"],
        "username": session["username"],
    })


# ─────────────────────────────────────────────
# Resume analysis
# ─────────────────────────────────────────────

@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    # ── Check file ────────────────────────────
    if "resume" not in request.files:
        return jsonify({
            "status": "error",
            "message": "No file uploaded — field name must be 'resume'",
            "received_fields": list(request.files.keys()),
            "received_form":   list(request.form.keys()),
        }), 400

    file = request.files["resume"]

    if file.filename == "":
        return jsonify({"status": "error", "message": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"status": "error", "message": "Unsupported file type. Use PDF, DOCX, or TXT"}), 415

    # ── Save file ─────────────────────────────
    filename  = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, f"{session['user_id']}_{filename}")
    file.save(save_path)
    logger.info("Saved upload: %s", save_path)

    # ── Extract text ──────────────────────────
    try:
        resume_text = extract_text(save_path)
    except (ValueError, ImportError) as e:
        try:
            os.remove(save_path)
        except OSError:
            pass
        return jsonify({"status": "error", "message": str(e)}), 422

    # ── AI analysis ───────────────────────────
    try:
        result = analyze_resume(resume_text)
    except Exception as e:
        logger.error("AI analysis error: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": f"AI analysis failed: {str(e)}"}), 500

    # ── Persist to DB ─────────────────────────
    try:
        analysis_id = db.save_analysis(
            user_id    = session["user_id"],
            filename   = filename,
            career     = result["career"],
            skills     = result["skills"],
            roadmap    = result["roadmap"],
            courses    = result["courses"],
            raw_output = result.get("raw", ""),
        )
    except Exception as e:
        logger.error("DB save error: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500

    # ── Clean up temp file ────────────────────
    try:
        os.remove(save_path)
    except OSError:
        pass

    return jsonify({
        "status":      "success",
        "analysis_id": analysis_id,
        "career":      result["career"],
        "skills":      result["skills"],
        "roadmap":     result["roadmap"],
        "courses":     result["courses"],
    })

# ─────────────────────────────────────────────
# History
# ─────────────────────────────────────────────

@app.route("/history", methods=["GET"])
@login_required
def history():
    """Return all past analyses for the logged-in user."""
    records = db.get_user_history(session["user_id"])
    return jsonify({"status": "success", "history": records})


@app.route("/history/<int:analysis_id>", methods=["GET"])
@login_required
def history_detail(analysis_id: int):
    """Return a single analysis record."""
    record = db.get_analysis_by_id(analysis_id, session["user_id"])
    if not record:
        return jsonify({"status": "error", "message": "Analysis not found"}), 404
    return jsonify({"status": "success", "analysis": record})


# ─────────────────────────────────────────────
# PDF download
# ─────────────────────────────────────────────

@app.route("/download/<int:analysis_id>", methods=["GET"])
@login_required
def download_pdf(analysis_id: int):
    """Generate and stream a PDF report for an analysis."""
    record = db.get_analysis_by_id(analysis_id, session["user_id"])
    if not record:
        return jsonify({"status": "error", "message": "Analysis not found"}), 404

    pdf_path = generate_pdf_report(
        username = session["username"],
        filename = record.get("filename", "resume"),
        career   = record["career"],
        skills   = record["skills"],
        roadmap  = record["roadmap"],
        courses  = record["courses"],
    )

    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"career_report_{analysis_id}.pdf",
    )


# ─────────────────────────────────────────────
# Error handlers
# ─────────────────────────────────────────────

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({"status": "error", "message": "File too large. Max allowed size is 5 MB."}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "message": "Route not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"status": "error", "message": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error(e):
    logger.error("Internal server error: %s", e, exc_info=True)
    return jsonify({"status": "error", "message": "Internal server error"}), 500


# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, port=5000)
