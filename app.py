import os, json, base64, io
from flask import Flask, request, jsonify
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build as gbuild
from plate_maker import build_plate


raw = os.environ["DRIVE_SA_B64"]
try:
    SA_INFO = json.loads(base64.b64decode(raw))
except (ValueError, base64.binascii.Error):
    # not base64, maybe raw JSON
    SA_INFO = json.loads(raw)

CREDS   = Credentials.from_service_account_info(SA_INFO,
            scopes=["https://www.googleapis.com/auth/drive"])
DRIVE   = gbuild("drive", "v3", credentials=CREDS, cache_discovery=False)

FINISHED_FOLDER_ID = os.environ["FINISHED_FOLDER_ID"]

app = Flask(__name__)

@app.post("/process")
def process():
    data = request.get_json(force=True)
    try:
        url = build_plate(
            DRIVE,
            file_id = data["fileId"],
            catalog = data["catalog"],
            design  = data["design"],
            out_folder_id = FINISHED_FOLDER_ID
        )
        return jsonify({"status":"done","url":url}), 200
    except Exception as e:
        return jsonify({"status":"error","msg":str(e)}), 500

# optional liveness
@app.get("/health")
def health():
    return "ok", 200
