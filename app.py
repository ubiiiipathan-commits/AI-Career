"""
app.py — Smart Career Guidance API (no auth)
"""

import os
import logging
from datetime import timedelta

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

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
app.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("MAX_CONTENT_LENGTH_MB", 5)
) * 1024 * 1024

# ── CORS ───────────────────────────────────────
CORS(
    app,
    origins=[
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:3000",
        "https://your-frontend-domain.com",  # ← replace with real URL
    ],
    supports_credentials=True,
)

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Shared anonymous user ─────────────────────
# All requests are attributed to this single guest user.
# The DB row is created on first boot if it doesn't exist.
GUEST_USER_ID = 1
GUEST_USERNAME = "Guest"

# ── Initialise DB ─────────────────────────────
with app.app_context():
    try:
        db.init_db()
        # Ensure guest user exists (ignore if already present)
        try:
            db.create_user(GUEST_USERNAME, "guest@app.local", "no-password")
        except Exception:
            pass  # already exists
    except Exception as e:
        logger.error("Could not initialise database: %s", e)


# ─────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────

@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Smart Career Guidance API is running 🚀"})


# ─────────────────────────────────────────────
# Stub auth routes (kept so old frontend calls don't 404)
# ─────────────────────────────────────────────

@app.route("/register", methods=["POST"])
def register():
    return jsonify({
        "status": "success",
        "user": {"id": GUEST_USER_ID, "username": GUEST_USERNAME, "email": "guest@app.local"}
    }), 200


@app.route("/login", methods=["POST"])
def login():
    return jsonify({
        "status": "success",
        "user": {"id": GUEST_USER_ID, "username": GUEST_USERNAME, "email": "guest@app.local"}
    })


@app.route("/logout", methods=["POST"])
def logout():
    return jsonify({"status": "success", "message": "Logged out"})


@app.route("/me", methods=["GET"])
def me():
    return jsonify({
        "status": "success",
        "user": {"id": GUEST_USER_ID, "username": GUEST_USERNAME, "email": "guest@app.local"}
    })


# ─────────────────────────────────────────────
# Resume analysis  (no auth required)
# ─────────────────────────────────────────────

@app.route("/analyze", methods=["POST"])
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
    save_path = os.path.join(UPLOAD_FOLDER, f"{GUEST_USER_ID}_{filename}")
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
            user_id    = GUEST_USER_ID,
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
# History  (no auth required)
# ─────────────────────────────────────────────

@app.route("/history", methods=["GET"])
def history():
    records = db.get_user_history(GUEST_USER_ID)
    return jsonify({"status": "success", "history": records})


@app.route("/history/<int:analysis_id>", methods=["GET"])
def history_detail(analysis_id: int):
    record = db.get_analysis_by_id(analysis_id, GUEST_USER_ID)
    if not record:
        return jsonify({"status": "error", "message": "Analysis not found"}), 404
    return jsonify({"status": "success", "analysis": record})


# ─────────────────────────────────────────────
# PDF download  (no auth required)
# ─────────────────────────────────────────────

@app.route("/download/<int:analysis_id>", methods=["GET"])
def download_pdf(analysis_id: int):
    record = db.get_analysis_by_id(analysis_id, GUEST_USER_ID)
    if not record:
        return jsonify({"status": "error", "message": "Analysis not found"}), 404

    pdf_path = generate_pdf_report(
        username = GUEST_USERNAME,
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
