"""
app.py — Smart Career Guidance API
"""

import os
import logging
from datetime import timedelta

from flask import Flask, request, jsonify, session, send_file
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from dotenv import load_dotenv

load_dotenv()  # ← only once (was duplicated before)

# ── Local modules ─────────────────────────────
import database as db
from ai_engine     import analyze_resume
from file_parser   import extract_text, allowed_file
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

# ── FIX: Cookie settings so sessions work cross-origin in production ──
# Without these, the browser blocks the session cookie on every request
# after login and every protected route returns 401.
is_production = os.environ.get("FLASK_ENV", "production") == "production"

app.config.update(
    SESSION_COOKIE_SECURE=is_production,  # False for localhost
    SESSION_COOKIE_SAMESITE="None" if is_production else "Lax",
    SESSION_COOKIE_HTTPONLY=True
)
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── Initialise DB ─────────────────────────────
with app.app_context():
    try:
        db.init_db()
    except Exception as e:
        logger.error("Could not initialise database: %s", e)


# ─────────────────────────────────────────────
# Auth decorator
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
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if db.email_exists(email):
        return jsonify({"status": "error", "message": "Email exists"}), 409

    user_id = db.create_user(username, email, generate_password_hash(password))
    
    return jsonify({
        "status": "success",
        "user": {"id": user_id, "username": username, "email": email}
    }), 201 

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    user = db.get_user_by_email(email)
    if user and check_password_hash(user["password_hash"], password):
        return jsonify({
            "status": "success",
            "user": {"id": user["id"], "username": user["username"], "email": user["email"]}
        })

    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return jsonify({"status": "success", "message": "Logged out successfully"})


@app.route("/me", methods=["GET"])
def me():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 401
    
    user = db.get_user_by_id(user_id) # Assuming this function exists in your db.py
    return jsonify({"status": "success", "user": user})


# ─────────────────────────────────────────────
# Resume analysis
# ─────────────────────────────────────────────

@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    if "resume" not in request.files:
        return jsonify({
            "status":          "error",
            "message":         "No file uploaded — field name must be 'resume'",
            "received_fields": list(request.files.keys()),
            "received_form":   list(request.form.keys()),
        }), 400

    file = request.files["resume"]

    if file.filename == "":
        return jsonify({"status": "error", "message": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"status": "error", "message": "Unsupported file type. Use PDF, DOCX, or TXT"}), 415

    filename  = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, f"{session['user_id']}_{filename}")
    file.save(save_path)
    logger.info("Saved upload: %s", save_path)

    try:
        resume_text = extract_text(save_path)
    except (ValueError, ImportError) as e:
        try: os.remove(save_path)
        except OSError: pass
        return jsonify({"status": "error", "message": str(e)}), 422

    try:
        result = analyze_resume(resume_text)
    except Exception as e:
        logger.error("AI analysis error: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": f"AI analysis failed: {str(e)}"}), 500

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

    try: os.remove(save_path)
    except OSError: pass

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
    records = db.get_user_history(session["user_id"])
    return jsonify({"status": "success", "history": records})


@app.route("/history/<int:analysis_id>", methods=["GET"])
@login_required
def history_detail(analysis_id: int):
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
