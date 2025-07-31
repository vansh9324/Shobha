"""
Executed by the GitHub Actions job.
• Downloads raw image from Drive
• Calls plate_maker.build_plate
• Uploads finished JPEG back to Drive
"""

import io, os, json, tempfile
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build as gbuild
from googleapiclient.http import MediaIoBaseDownload, MediaInMemoryUpload
from plate_maker import build_plate

FILE_ID  = os.environ["FILE_ID"]
CATALOG  = os.environ["CATALOG"]
DESIGN   = os.environ["DESIGN"]
FINISHED = os.environ["FINISHED_FOLDER_ID"]

creds = Credentials.from_service_account_info(
    json.loads(os.environ["SA_JSON"]),
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive = gbuild("drive","v3",credentials=creds,cache_discovery=False)

# ─ download raw image ─
buf = io.BytesIO()
request = drive.files().get_media(fileId=FILE_ID)
down = MediaIoBaseDownload(buf, request)
done = False
while not done:
    status, done = down.next_chunk()
buf.seek(0)

tmp_dir = Path(tempfile.mkdtemp())
raw_path = tmp_dir/"raw.jpg"
with open(raw_path, "wb") as f:
    f.write(buf.read())

# ─ process ─
out_path = tmp_dir / "plate.jpg"
build_plate(raw_path, out_path, CATALOG, DESIGN)

# ─ upload ─
meta = {"name": f"{DESIGN}_{CATALOG}.jpg", "parents":[FINISHED]}
media = MediaInMemoryUpload(out_path.read_bytes(), mimetype="image/jpeg")
file = drive.files().create(body=meta, media_body=media, fields="id").execute()
print("✅ Uploaded:", f"https://drive.google.com/uc?id={file['id']}")
