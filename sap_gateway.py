from flask import Flask, request, jsonify
from datetime import datetime
import os

app = Flask(__name__)


@app.route("/api/pernr-from-email", methods=["POST"])
def pernr_from_email():
    data = request.get_json() or {}
    email = data.get("email") or data.get("username") or "unknown@demo"
    # Simple deterministic demo PERNR for local/dev
    prefix = os.getenv("GATEWAY_PREFIX", "DEMO")
    pernr = f"{prefix}{len(email.split('@')[0]):04d}"
    return jsonify({"success": True, "pernr": pernr, "email": email})


@app.route("/api/leave-balance", methods=["POST"])
def leave_balance():
    payload = request.get_json() or {}
    pernr = payload.get("pernr") or payload.get("personnel_number") or "00001234"
    # Demo deterministic leave balance
    year = datetime.now().year
    result = {
        "success": True,
        "total_leave_days": 20,
        "used_leave_days": 7,
        "remaining_leave_days": 13,
        "pending_leave_requests": 2,
        "year": year,
        "rfc_function": "PT_GET_LEAVE_BALANCE",
        "personnel_id": pernr,
        "raw_result": {"note": "demo gateway response"}
    }
    return jsonify(result)


@app.route("/", methods=["GET"])
def home():
    return jsonify({"service": "yatas-demo-gateway", "ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
