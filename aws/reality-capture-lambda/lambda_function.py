import os
import json
import urllib3
import base64
import tempfile
import time
import cgi
from io import BytesIO

# Autodesk API URLs
AUTH_URL = "https://developer.api.autodesk.com/authentication/v2/token"
REALITYCAPTURE_BASE_URL = "https://developer.api.autodesk.com/photo-to-3d/v1/photoscene"

# Credentials from Lambda environment variables
CLIENT_ID = os.getenv("AUTODESK_CLIENT_ID")
CLIENT_SECRET = os.getenv("AUTODESK_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError(
        "Missing Autodesk credentials. Set AUTODESK_CLIENT_ID and AUTODESK_CLIENT_SECRET."
    )

# Token cache (per Lambda invocation)
ACCESS_TOKEN_CACHE = None
TOKEN_EXPIRY_CACHE = 0  # Unix timestamp

# Initialize urllib3 HTTP client
http = urllib3.PoolManager()


def lambda_handler(event, context):
    """Handle binary image upload and process for RealityCapture API."""
    try:
        # Ensure the content type is multipart/form-data
        content_type = event["headers"].get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            return respond(400, {"error": "Invalid content type. Expected multipart/form-data."})

        # Extract scene name and images
        scene_name, image_paths = extract_multipart_data(event)

        if not image_paths:
            return respond(400, {"error": "No images received."})

        # Get Autodesk API token
        token = get_access_token()

        # Step 1: Create photoscene
        photoscene_id = create_photoscene(scene_name, token)
        if not photoscene_id:
            return respond(500, "Failed to create photoscene.")

        # Step 2: Upload each photo
        for image_path in image_paths:
            if not upload_image_to_photoscene(photoscene_id, image_path, token):
                return respond(500, f"Failed to upload {image_path}.")

        # Step 3: Start processing
        if not start_photoscene_processing(photoscene_id, token):
            return respond(500, "Failed to start processing.")

        # Step 4: Poll for completion
        if not poll_photoscene_progress(photoscene_id, token):
            return respond(500, "Photoscene processing timed out or failed.")

        # Step 5: Retrieve final model URL
        model_url = get_photoscene_result_url(photoscene_id, token)
        if not model_url:
            return respond(500, "Failed to retrieve final model URL.")

        # Cleanup temporary files
        cleanup_temp_files(image_paths)

        return respond(200, {"status": "success", "download_url": model_url})

    except Exception as e:
        return respond(500, {"error": str(e)})


### Autodesk OAuth v2 Authentication ###
def get_access_token():
    global ACCESS_TOKEN_CACHE, TOKEN_EXPIRY_CACHE

    if ACCESS_TOKEN_CACHE and TOKEN_EXPIRY_CACHE > time.time():
        return ACCESS_TOKEN_CACHE

    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials',
        'scope': 'data:read data:write'
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = http.request("POST", AUTH_URL, body=urllib3.request.urlencode(payload), headers=headers)
    if response.status != 200:
        raise Exception(f"Failed to get access token: {response.status} - {response.data.decode()}")

    token_data = json.loads(response.data.decode())
    ACCESS_TOKEN_CACHE = token_data['access_token']
    TOKEN_EXPIRY_CACHE = time.time() + token_data['expires_in'] - 60

    return ACCESS_TOKEN_CACHE


### RealityCapture Workflow ###
def create_photoscene(scene_name, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = json.dumps({"scenename": scene_name, "format": "obj"})

    response = http.request("POST", REALITYCAPTURE_BASE_URL, body=payload, headers=headers)
    if response.status == 201:
        return json.loads(response.data.decode()).get('photosceneid')
    return None


def upload_image_to_photoscene(photoscene_id, photo_path, token):
    url = f"{REALITYCAPTURE_BASE_URL}/{photoscene_id}/files"
    headers = {"Authorization": f"Bearer {token}"}

    with open(photo_path, 'rb') as file:
        file_data = file.read()

    response = http.request("POST", url, body=file_data, headers=headers)
    return response.status == 200


def start_photoscene_processing(photoscene_id, token):
    url = f"{REALITYCAPTURE_BASE_URL}/{photoscene_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = http.request("POST", url, headers=headers)
    return response.status == 202


def poll_photoscene_progress(photoscene_id, token, max_attempts=30, delay=5):
    url = f"{REALITYCAPTURE_BASE_URL}/{photoscene_id}/progress"
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(max_attempts):
        response = http.request("GET", url, headers=headers)
        if response.status == 200:
            progress = json.loads(response.data.decode()).get('progress')
            if progress == '100':
                return True
        time.sleep(delay)
    return False


def get_photoscene_result_url(photoscene_id, token):
    url = f"{REALITYCAPTURE_BASE_URL}/{photoscene_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = http.request("GET", url, headers=headers)
    if response.status == 200:
        files = json.loads(response.data.decode()).get('files', [])
        for file in files:
            if file['format'] == 'obj':
                return file['url']
    return None


### Photo Handling ###
def extract_multipart_data(event):
    """Extract binary images from a multipart request."""
    body = event["body"]
    headers = event["headers"]

    fs = cgi.FieldStorage(fp=BytesIO(body.encode("utf-8")), headers=headers, environ={"REQUEST_METHOD": "POST"})

    scene_name = fs.getvalue("sceneName", "UntitledScene")
    image_paths = []

    for key in fs.keys():
        if "image" in key:
            file_item = fs[key]
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            temp_file.write(file_item.file.read())
            temp_file.close()
            image_paths.append(temp_file.name)

    return scene_name, image_paths


def cleanup_temp_files(image_paths):
    """Delete temporary files."""
    for path in image_paths:
        if os.path.exists(path):
            os.remove(path)


### Response Helper ###
def respond(status_code, body):
    """Format a structured Lambda response."""
    return {
        "statusCode": status_code,
        "body": json.dumps(body),
        "headers": {"Content-Type": "application/json"}
    }
