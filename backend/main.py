import os
import shutil
import asyncio
import functools
import datetime
import json
import secrets
import tempfile
import zipfile
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import FastAPI, Request, Depends, HTTPException, status, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.concurrency import run_in_threadpool
import requests
import httpx
from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, storage

from models import User, SharedItem, ShareType, ItemNote
from database import DatabaseInterface, FirestoreDatabase, SQLiteDatabase

# Load environment variables
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-please-change").strip()
GOOGLE_CLIENT_ID = (os.getenv("GOOGLE_CLIENT_ID") or "").strip() or None
GOOGLE_CLIENT_SECRET = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip() or None
GOOGLE_EXTENSION_CLIENT_ID = (os.getenv("GOOGLE_EXTENSION_CLIENT_ID") or "").strip() or None
GOOGLE_IOS_CLIENT_ID = (os.getenv("GOOGLE_IOS_CLIENT_ID") or "").strip() or None
GOOGLE_ANDROID_CLIENT_ID = (os.getenv("GOOGLE_ANDROID_CLIENT_ID") or "").strip() or None
GOOGLE_ANDROID_DEBUG_CLIENT_ID = (os.getenv("GOOGLE_ANDROID_DEBUG_CLIENT_ID") or "").strip() or None
APP_ENV = os.getenv("APP_ENV", "production").strip()

MAX_TITLE_LENGTH = 255
MAX_TEXT_LENGTH = 10000
CSRF_KEY = "csrf_token"

# Read Version
try:
    with open("version.txt", "r") as f:
        APP_VERSION = f.read().strip()
except FileNotFoundError:
    APP_VERSION = "unknown"

# --- Database & Storage Initialization ---

db: DatabaseInterface = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    if APP_ENV == "development":
        print("Starting in DEVELOPMENT mode using SQLite")
        db = SQLiteDatabase()
        if hasattr(db, 'init_db'):
            await db.init_db()
    else:
        print("Starting in PRODUCTION mode using Firestore")
        db = FirestoreDatabase()
    yield


app = FastAPI(lifespan=lifespan)

# CORS Setup
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS")
allow_origins = []
allow_origin_regex = None

if ALLOWED_ORIGINS_ENV:
    allow_origins = [origin.strip() for origin in ALLOWED_ORIGINS_ENV.split(",") if origin.strip()]
elif APP_ENV == "development":
    # Allow localhost and 127.0.0.1 for development
    allow_origin_regex = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.png")

# --- Auth Setup ---

oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# --- Routes ---

async def check_csrf(request: Request):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return

    if "user" in request.session:
        session_token = request.session.get(CSRF_KEY)
        header_token = request.headers.get("X-CSRF-Token")

        if not session_token or not header_token or session_token != header_token:
            raise HTTPException(status_code=403, detail="CSRF token mismatch or missing")

@app.get("/")
async def read_root(request: Request):
    user = request.session.get('user')
    csrf_token = None

    if user:
        csrf_token = request.session.get(CSRF_KEY)
        if not csrf_token:
            csrf_token = secrets.token_hex(32)
            request.session[CSRF_KEY] = csrf_token

    if APP_ENV == "development":
        if user:
            # Firestore Query
            items = await db.get_shared_items(user['email'])
            
            # Simple dashboard template
            template = """
            <html>
                <head>
                    <title>Analyze This Dashboard</title>
                    <link rel="icon" href="/static/favicon.png">
                    <script>
                        const CSRF_TOKEN = "{{ csrf_token }}";
                        async function deleteItem(itemId) {
                            if (!confirm('Are you sure you want to delete this item?')) return;
                            
                            try {
                                const response = await fetch('/api/items/' + itemId, {
                                    method: 'DELETE',
                                    headers: {
                                        'X-CSRF-Token': CSRF_TOKEN
                                    }
                                });
                                
                                if (response.ok) {
                                    window.location.reload();
                                } else {
                                    alert('Failed to delete item');
                                }
                            } catch (error) {
                                console.error('Error:', error);
                                alert('An error occurred');
                            }
                        }

                        function showAnalysis(overview) {
                            alert(overview);
                        }
                    </script>
                </head>
                <body style="font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
                    <h1>Analyze This</h1>
                    <p>Welcome, {{ user.name }} | <a href="/logout">Logout</a></p>
                    <hr/>
                    <h2>Shared Items</h2>
                    <ul>
                    {% for item in items %}
                        <li style="margin-bottom: 20px; border: 1px solid #ddd; padding: 10px; border-radius: 8px;">
                            <div style="display: flex; justify-content: space-between; align-items: start;">
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <div>
                                        <strong>{{ item.title or 'No Title' }}</strong> <small>({{ item.type }})</small>
                                    </div>
                                    {% if item.analysis %}
                                        <span data-overview="{{ item.analysis.overview }}" onclick="showAnalysis(this.dataset.overview)" style="cursor: pointer; font-size: 1.2em;" title="View Analysis">✨</span>
                                    {% else %}
                                        <span style="filter: grayscale(100%); opacity: 0.5; font-size: 1.2em; cursor: default;" title="No Analysis">✨</span>
                                    {% endif %}
                                </div>
                                <button data-id="{{ item.firestore_id }}" onclick="deleteItem(this.dataset.id)" style="background: #ff4444; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">Delete</button>
                            </div>
                            <div style="margin-top: 5px;">
                                {{ item.content }}
                            </div>
                            <small style="color: grey; display: block; margin-top: 5px;">{{ item.created_at }}</small>
                        </li>
                    {% endfor %}
                    </ul>
                </body>
            </html>
            """

            from jinja2 import Template
            response = HTMLResponse(Template(template, autoescape=True).render(user=user, items=items, csrf_token=csrf_token))
            if csrf_token:
                 response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, samesite="lax")
            return response
        return HTMLResponse('<a href="/login">Login with Google</a>')
    
    response = FileResponse("static/index.html")
    if csrf_token:
         response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, samesite="lax")
    return response

@app.get("/login")
async def login(request: Request):
    # Ensure fully qualified URL for redirect_uri to avoid mismatches
    # Cloud Run behind load balancer might need X-Forwarded-Proto considerations, but starlette handles some.
    # We'll rely on url_for
    redirect_uri = request.url_for('auth')
    # Force https if deploying
    if 'cloud.google' in str(redirect_uri) or 'interestedparticipant.org' in str(redirect_uri) or '.run.app' in str(redirect_uri):
         redirect_uri = str(redirect_uri).replace('http:', 'https:')

    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth")
async def auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        return HTMLResponse(f'<h1>{error.error}</h1>')
    
    user_info = token.get('userinfo')
    if user_info:
        request.session['user'] = user_info
        
        # Create/Update User in DB
        # Check if exists
        user = User(
            email=user_info['email'],
            name=user_info.get('name'),
            picture=user_info.get('picture'),
            # created_at handled by default
        )
        await db.upsert_user(user)
            
    return RedirectResponse(url='/')

@app.get("/logout")
async def logout(request: Request):
    request.session.pop('user', None)
    return RedirectResponse(url='/')

@app.get("/api/version")
async def get_version():
    return {"version": APP_VERSION}

@app.get("/oauthredirect")
async def oauth_redirect():
    html_content = """
    <html>
        <head>
            <title>Authentication Redirect</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <script>
                window.onload = function() {
                    var hash = window.location.hash;
                    var search = window.location.search;
                    var targetUrl = 'analyzethis://oauthredirect' + search + hash;
                    document.getElementById('link').href = targetUrl;
                    window.location.href = targetUrl;
                }
            </script>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding: 20px; text-align: center; }
                .button { display: inline-block; background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-top: 20px; }
            </style>
        </head>
        <body>
            <h1>Authentication Complete</h1>
            <p>Redirecting back to app...</p>
            <p><a id="link" href="#" class="button">Click here if not redirected</a></p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# --- API Endpoints ---
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

async def verify_google_token(token: str):
    # DEV_BYPASS
    if APP_ENV == "development" and token == "dev-token":
        return {
            "email": "dev@example.com",
            "name": "Developer",
            "picture": "https://via.placeholder.com/150"
        }

    # Method 1: Try verifying as ID Token (Web Client)
    try:
        # Run blocking verification in thread pool
        id_info = await run_in_threadpool(
            id_token.verify_oauth2_token,
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
        return id_info
    except ValueError:
        pass
        
    # Method 2: Try verifying as Access Token (Extension Client)
    try:
        # Call Google UserInfo endpoint
        async with httpx.AsyncClient() as client:
            # First, verify audience using tokeninfo to prevent Confused Deputy attacks
            token_info_resp = await client.get(
                'https://oauth2.googleapis.com/tokeninfo',
                params={'access_token': token}
            )

            if token_info_resp.status_code == 200:
                token_info = token_info_resp.json()
                aud = token_info.get('aud')

                # Check if audience matches our Client IDs
                # We accept either the web client or extension client
                valid_audiences = [aid for aid in [GOOGLE_CLIENT_ID, GOOGLE_EXTENSION_CLIENT_ID, GOOGLE_IOS_CLIENT_ID, GOOGLE_ANDROID_CLIENT_ID, GOOGLE_ANDROID_DEBUG_CLIENT_ID] if aid]

                if aud not in valid_audiences:
                    print(f"Token verification failed: Audience mismatch. Expected one of {valid_audiences}, got {aud}")
                    return None
            else:
                print(f"Token verification failed (TokenInfo). Status: {token_info_resp.status_code}")
                return None

            # If audience is valid, fetch user profile
            response = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {token}'}
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Token verification failed (Method 2). Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        print(f"Token verification exception (Method 2): {e}")
        pass
        
    print("Token verification failed: Invalid token")
    return None

import uuid
import datetime

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff', '.svg')
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.m4v', '.webm', '.avi', '.mkv')
AUDIO_EXTENSIONS = ('.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg')

def normalize_share_type(raw_type: Optional[str], content: Optional[str], file: UploadFile | None, metadata: dict | None) -> ShareType:
    if raw_type:
        normalized = raw_type.strip().lower().replace(' ', '_')
    else:
        normalized = ''

    if normalized in ('weburl', 'web_url'):
        return ShareType.web_url

    mime_type = None
    if metadata:
        mime_type = metadata.get('mimeType') or metadata.get('mime_type')
    if not mime_type and file:
        mime_type = file.content_type

    if normalized == 'file':
        if mime_type:
            if mime_type.startswith('image/'):
                return ShareType.image
            if mime_type.startswith('video/'):
                return ShareType.video
            if mime_type.startswith('audio/'):
                return ShareType.audio
        if content:
            lower_content = content.lower()
            if lower_content.endswith(IMAGE_EXTENSIONS):
                return ShareType.image
            if lower_content.endswith(VIDEO_EXTENSIONS):
                return ShareType.video
            if lower_content.endswith(AUDIO_EXTENSIONS):
                return ShareType.audio
        return ShareType.file

    if normalized in ('text', 'image', 'video', 'audio', 'screenshot'):
        return ShareType(normalized)

    if normalized == 'media' or (not normalized and (file or content)):
        if mime_type:
            if mime_type.startswith('image/'):
                return ShareType.image
            if mime_type.startswith('video/'):
                return ShareType.video
            if mime_type.startswith('audio/'):
                return ShareType.audio

        if content:
            lower_content = content.lower()
            if lower_content.endswith(IMAGE_EXTENSIONS):
                return ShareType.image
            if lower_content.endswith(VIDEO_EXTENSIONS):
                return ShareType.video
            if lower_content.endswith(AUDIO_EXTENSIONS):
                return ShareType.audio

        return ShareType.file

    return ShareType.text

@app.post("/api/share", dependencies=[Depends(check_csrf)])
async def share_item(
    request: Request,
    title: str = Form(None),
    content: str = Form(None),
    type: str = Form(None),
    file: UploadFile = File(None),
    file_name: str = Form(None),
    mime_type: str = Form(None),
    file_size: int = Form(None),
    duration: float = Form(None),
    width: int = Form(None),
    height: int = Form(None),
    # For JSON body support (legacy/extension), we can't easily mix Body and Form in the same endpoint 
    # without a bit of work or separate endpoints.
    # However, existing clients send JSON. FastAPI handles this by checking Content-Type.
    # To support BOTH, we usually inspect Request or use a dependency.
    # A cleaner way is to have the client always send JSON or always send Form, or use separate endpoints.
    # Given the constraint to keep `/api/share`, and that the Extension uses JSON,
    # we'll try to read the body first if content-type is json.
    # BUT FastAPI parsing logic is strict.
    # STRATEGY: Receive Request and parse manually if needed, OR use optional Body & Form.
    # FastAPI doesn't support optional Body AND optional Form in the same route well (it expects one or the other based on media type).
    # workaround: Check Content-Type header.
):
    # Auth Check
    auth_header = request.headers.get('Authorization')
    user_email = None
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        user_info = await verify_google_token(token)
        if user_info:
            user_email = user_info['email']
    elif 'user' in request.session:
        user_email = request.session['user']['email']
    
    if not user_email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Input Validation
    if title and len(title) > MAX_TITLE_LENGTH:
        raise HTTPException(status_code=400, detail="Title too long")
    if content and len(content) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail="Content too long")

    # Determine Input Type
    content_type = request.headers.get('content-type', '')
    
    item_data = {}
    
    if 'application/json' in content_type:
        # JSON Request (Extension)
        try:
            json_body = await request.json()
            item_data = json_body
            # Validate with Pydantic model manually if needed
            # For now, just trust the keys: title, content, type
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")
    elif 'multipart/form-data' in content_type:
        # Form Request (Mobile with Image)
        item_data = {
            'title': title,
            'content': content,
            'type': type
        }

        item_metadata = {
            'fileName': file_name,
            'mimeType': mime_type,
            'fileSize': file_size,
            'duration': duration,
            'width': width,
            'height': height,
        }
        item_data['item_metadata'] = {key: value for key, value in item_metadata.items() if value is not None}
        
        # Handle File Upload
        if file:
            try:
                # Create a unique filename
                extension = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
                blob_name_relative = f"uploads/{user_email}/{uuid.uuid4()}.{extension}"
                
                if APP_ENV == "development":
                    # Local Storage Strategy
                    local_path = Path("static") / blob_name_relative
                    # Ensure directory exists
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(local_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                        
                    # For local dev, we just store the relative path for now, 
                    # similar to prod, but the retrieval needs to handle it.
                    # Actually, let's store the full access URL for simplicity? 
                    # Or keep storing the path and let get_items resolve it.
                    # existing prod logic stores "blob_name" (path).
                    # Let's stick to that.
                    item_data['content'] = blob_name_relative
                    
                else:
                    # Prod: Firebase Storage
                    bucket = storage.bucket()
                    blob = bucket.blob(blob_name_relative)

                    # Stream upload to avoid reading into memory
                    # file.file is a SpooledTemporaryFile (file-like object)
                    await file.seek(0)
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None,
                        functools.partial(blob.upload_from_file, file.file, content_type=file.content_type)
                    )
                    item_data['content'] = blob_name_relative
                
                item_data['type'] = item_data.get('type', 'file')  # Preserve type if provided
                
            except Exception as e:
                print(f"Upload failed: {e}")
                raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported Content-Type")

    # Construct Item
    normalized_type = normalize_share_type(
        item_data.get('type'),
        item_data.get('content'),
        file,
        item_data.get('item_metadata')
    )

    # Security Validation: Prevent IDOR/Traversal on image content paths
    # If the backend is going to read this file (images/screenshots), ensure it belongs to the user.
    content_val = item_data.get('content')
    if content_val and normalized_type in (ShareType.image, ShareType.screenshot):
        is_url = content_val.lower().startswith(('http://', 'https://', 'data:'))
        if not is_url:
            # It implies a storage path that the backend might try to read
            if ".." in content_val or content_val.startswith("/") or "\\" in content_val:
                raise HTTPException(status_code=403, detail="Invalid content path: Traversal detected")

            expected_prefix = f"uploads/{user_email}/"
            if not content_val.startswith(expected_prefix):
                raise HTTPException(status_code=403, detail="Invalid content path: Prefix mismatch")
         
    image_path = None
    if normalized_type in (ShareType.image, ShareType.screenshot):
        image_path = item_data.get('content')

    new_item = SharedItem(
        title=item_data.get('title'),
        content=item_data.get('content'),
        type=normalized_type,
        user_email=user_email,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        item_metadata=item_data.get('item_metadata'),
        image=image_path
    )
    
    # Analysis is now handled by a background worker
    # try:
    #     from analysis import analyze_content
    #     analysis_result = analyze_content(new_item.content, new_item.type)
    #     if analysis_result:
    #         new_item.analysis = analysis_result
    # except Exception as e:
    #     print(f"Analysis failed: {e}")
    
    # Save to DB
    await db.create_shared_item(new_item)

    # Enqueue worker jobs for analysis + normalization
    try:
        await db.enqueue_worker_job(new_item.id, user_email, "analysis", {"source": "share"})
        await db.enqueue_worker_job(new_item.id, user_email, "normalize", {"source": "share"})
    except Exception as e:
        print(f"Failed to enqueue worker jobs for item {new_item.id}: {e}")
    
    return new_item

@app.get("/api/items")
async def get_items(request: Request):
    auth_header = request.headers.get('Authorization')
    user_email = None
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        user_info = await verify_google_token(token)
        if user_info:
            user_email = user_info['email']
    elif 'user' in request.session:
        user_email = request.session['user']['email']
        
    if not user_email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    items = await db.get_shared_items(user_email)
    
    # Process items (Signed URLs etc)
    # We only need to do this for media/screenshot items in PROD or adjust URLs in DEV
    content_types = ('media', 'screenshot', 'image', 'video', 'audio', 'file')

    if APP_ENV == "development":
        # DEV: transform content path to localhost static URL
        base_url = str(request.base_url).rstrip('/')
        for item in items:
            if item.get('type') in content_types and item.get('content') and not item.get('content').startswith('http'):
                # Assumes content is relative path like uploads/email/uuid.ext
                # Mounted at /static
                item['content'] = f"{base_url}/static/{item['content']}"
    else:
        # PROD: Proxy through backend
        # We replace the content path with a URL to our own API
        # This avoids needing a private key for Signed URLs
        base_url = str(request.base_url).rstrip('/')
        if APP_ENV != "development":
             base_url = base_url.replace("http://", "https://")
             
        for item in items:
            if item.get('type') in content_types and item.get('content') and not item.get('content').startswith('http'):
                # Content is "runs/email/uuid.ext"
                # We want /api/content/runs/email/uuid.ext
                item['content'] = f"{base_url}/api/content/{item['content']}"
    
    return items

@app.get("/api/content/{blob_path:path}")
async def get_content(blob_path: str, request: Request):
    # Auth Check
    auth_header = request.headers.get('Authorization')
    user_email = None
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        user_info = await verify_google_token(token)
        if user_info:
            user_email = user_info['email']
    elif 'user' in request.session:
        user_email = request.session['user']['email']
        
    if not user_email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Security Check: Ensure user owns the file and prevent traversal
    # 1. Prevent Directory Traversal (basic string check)
    if ".." in blob_path or blob_path.startswith("/") or "\\" in blob_path:
        print(f"Potential traversal attempt by {user_email}: {blob_path}")
        raise HTTPException(status_code=403, detail="Forbidden")

    # 2. Ensure path starts with the user's upload directory
    # expected prefix: uploads/{user_email}/
    expected_prefix = f"uploads/{user_email}/"
    if not blob_path.startswith(expected_prefix):
        print(f"Access denied for {user_email} to {blob_path} (Prefix mismatch)")
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        if APP_ENV == "development":
             # 3. Additional filesystem path resolution check for Dev environment
             base_dir = Path("static").resolve()
             # Use safe join
             requested_path = (base_dir / blob_path).resolve()

             # Ensure the resolved path is strictly within the user's upload directory
             user_upload_dir = (base_dir / "uploads" / user_email).resolve()

             if not str(requested_path).startswith(str(user_upload_dir)):
                 print(f"Path traversal detected for {user_email}: {blob_path} -> {requested_path}")
                 raise HTTPException(status_code=403, detail="Forbidden")

             if not requested_path.exists():
                 raise HTTPException(status_code=404, detail="File not found")

             return FileResponse(str(requested_path))
        else:
            bucket = storage.bucket()
            blob = bucket.blob(blob_path)
            
            loop = asyncio.get_running_loop()
            # Fetch metadata to get content_type and ensure file exists
            await loop.run_in_executor(None, blob.reload)

            def iterfile():
                # Stream file from GCS in chunks to avoid memory exhaustion
                with blob.open("rb") as f:
                    while chunk := f.read(64 * 1024):  # 64KB chunks
                        yield chunk

            return StreamingResponse(iterfile(), media_type=blob.content_type)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error serving content: {e}")
        raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/user")
async def get_current_user(request: Request):
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Fetch full user profile from DB to get timezone
    db_user = await db.get_user(user_session.get('email'))
    if db_user:
        return {
            "email": db_user.email, 
            "name": db_user.name, 
            "picture": db_user.picture,
            "timezone": db_user.timezone
        }
    
    # Fallback to session data if DB fetch fails (shouldn't happen for valid users)
    return {
        "email": user_session.get('email'), 
        "name": user_session.get('name'), 
        "picture": user_session.get('picture'),
        "timezone": "America/New_York" # Default
    }

def _serialize_value(value):
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize_value(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_serialize_value(val) for val in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value

def _is_safe_user_blob_path(blob_path: str, user_email: str) -> bool:
    if not blob_path:
        return False
    if ".." in blob_path or blob_path.startswith("/") or "\\" in blob_path:
        return False
    expected_prefix = f"uploads/{user_email}/"
    return blob_path.startswith(expected_prefix)

async def _read_user_blob(blob_path: str, user_email: str) -> Optional[bytes]:
    if not _is_safe_user_blob_path(blob_path, user_email):
        return None

    if APP_ENV == "development":
        base_dir = Path("static").resolve()
        requested_path = (base_dir / blob_path).resolve()
        user_upload_dir = (base_dir / "uploads" / user_email).resolve()

        if not str(requested_path).startswith(str(user_upload_dir)):
            return None
        if not requested_path.exists():
            return None
        return requested_path.read_bytes()

    try:
        bucket = storage.bucket()
        blob = bucket.blob(blob_path)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, blob.download_as_bytes)
    except Exception:
        return None

async def get_authenticated_email(request: Request) -> str:
    auth_header = request.headers.get('Authorization')
    user_email = None

    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        user_info = await verify_google_token(token)
        if user_info:
            user_email = user_info['email']
    elif 'user' in request.session:
        user_email = request.session['user']['email']

    if not user_email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return user_email

@app.get("/api/export")
async def export_user_data(request: Request, background_tasks: BackgroundTasks):
    user_email = await get_authenticated_email(request)
    items = await db.get_shared_items(user_email)

    export_items = []
    exported_files = []
    content_types = ('media', 'screenshot', 'image', 'video', 'audio', 'file')

    for item in items:
        item_copy = _serialize_value(item)
        export_file = None

        item_type = item_copy.get("type")
        content_path = item_copy.get("content")
        if item_type in content_types and isinstance(content_path, str) and _is_safe_user_blob_path(content_path, user_email):
            file_bytes = await _read_user_blob(content_path, user_email)
            if file_bytes is not None:
                item_id = item_copy.get("firestore_id") or item_copy.get("id") or "item"
                base_name = os.path.basename(content_path)
                export_file = f"files/{item_id}_{base_name}"
                exported_files.append({
                    "item_id": item_id,
                    "content_path": content_path,
                    "export_path": export_file,
                    "size": len(file_bytes),
                })
                item_copy["export_file"] = export_file
                item_copy["_export_bytes"] = file_bytes
            else:
                item_copy["export_file"] = None
                item_copy["export_error"] = "missing_file"

        export_items.append(item_copy)

    exported_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest = {
        "exported_at": exported_at,
        "user": {"email": user_email},
        "item_count": len(export_items),
        "files": exported_files,
    }

    tmp_file = tempfile.NamedTemporaryFile(prefix="analyze-this-export-", suffix=".zip", delete=False)
    tmp_file.close()
    zip_path = tmp_file.name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for item in export_items:
            file_bytes = item.pop("_export_bytes", None)
            export_path = item.get("export_file")
            if file_bytes is not None and export_path:
                zipf.writestr(export_path, file_bytes)

        zipf.writestr("items.json", json.dumps(export_items, indent=2))
        zipf.writestr("export_manifest.json", json.dumps(manifest, indent=2))

    background_tasks.add_task(os.unlink, zip_path)
    filename = f"analyze-this-export-{exported_at.replace(':', '').replace('.', '')}.zip"
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
        background=background_tasks,
    )

async def set_item_hidden_status(item_id: str, request: Request, hidden: bool):
    user_email = await get_authenticated_email(request)

    item = await db.get_shared_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.get('user_email') != user_email:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this item")

    success = await db.update_shared_item(item_id, {"hidden": hidden})
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")

    return {"status": "success", "item_id": item_id, "hidden": hidden}

@app.patch("/api/items/{item_id}/hide", dependencies=[Depends(check_csrf)])
async def hide_item(item_id: str, request: Request):
    return await set_item_hidden_status(item_id, request, True)

@app.patch("/api/items/{item_id}/unhide", dependencies=[Depends(check_csrf)])
async def unhide_item(item_id: str, request: Request):
    return await set_item_hidden_status(item_id, request, False)

@app.delete("/api/items/{item_id}", dependencies=[Depends(check_csrf)])
async def delete_item(item_id: str, request: Request):
    user_email = await get_authenticated_email(request)

    try:
        success = await db.delete_shared_item(item_id, user_email)
        if not success:
            # Could mean not found or just failed
            # db.delete_shared_item raises ValueError if forbidden
            # and returns False if not found
            raise HTTPException(status_code=404, detail="Item not found")
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this item")

    return {"status": "success", "deleted_id": item_id}


# --- Item Notes Endpoints ---

class NoteCountRequest(BaseModel):
    item_ids: List[str]

class ItemUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=MAX_TITLE_LENGTH)
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    next_step: Optional[str] = None
    follow_up: Optional[str] = None  # Set to "" to clear
    is_favorite: Optional[bool] = None


@app.post("/api/items/{item_id}/notes", dependencies=[Depends(check_csrf)])
async def create_item_note(
    item_id: str,
    request: Request,
    text: str = Form(None),
    file: UploadFile = File(None)
):
    """Create a note for an item (multipart: text + optional file)"""
    user_email = await get_authenticated_email(request)

    # Verify the item exists and belongs to the user
    item = await db.get_shared_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.get('user_email') != user_email:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this item")

    # Validate that at least text or file is provided
    if not text and not file:
        raise HTTPException(status_code=400, detail="Either text or file must be provided")

    if text and len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail="Note text too long")

    image_path = None

    # Handle file upload if provided
    if file:
        try:
            extension = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
            blob_name_relative = f"uploads/{user_email}/notes/{uuid.uuid4()}.{extension}"

            if APP_ENV == "development":
                local_path = Path("static") / blob_name_relative
                local_path.parent.mkdir(parents=True, exist_ok=True)

                with open(local_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                image_path = blob_name_relative
            else:
                # Production: Firebase Storage
                bucket = storage.bucket()
                blob = bucket.blob(blob_name_relative)

                await file.seek(0)
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    functools.partial(blob.upload_from_file, file.file, content_type=file.content_type)
                )
                image_path = blob_name_relative

        except Exception as e:
            print(f"Note file upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

    # Create the note
    note = ItemNote(
        item_id=item_id,
        user_email=user_email,
        text=text,
        image_path=image_path
    )

    created_note = await db.create_item_note(note)

    # Return note data with image URL if applicable
    response_data = {
        'id': str(created_note.id),
        'item_id': created_note.item_id,
        'user_email': created_note.user_email,
        'text': created_note.text,
        'image_path': created_note.image_path,
        'created_at': created_note.created_at,
        'updated_at': created_note.updated_at
    }

    # Transform image_path to full URL
    if response_data['image_path']:
        base_url = str(request.base_url).rstrip('/')
        if APP_ENV == "development":
            response_data['image_path'] = f"{base_url}/static/{response_data['image_path']}"
        else:
            base_url = base_url.replace("http://", "https://")
            response_data['image_path'] = f"{base_url}/api/content/{response_data['image_path']}"

    return response_data


@app.get("/api/items/{item_id}/notes")
async def get_item_notes(item_id: str, request: Request):
    """Get all notes for an item"""
    user_email = await get_authenticated_email(request)

    # Verify the item exists and belongs to the user
    item = await db.get_shared_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.get('user_email') != user_email:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this item")

    notes = await db.get_item_notes(item_id)

    # Transform image_path to full URL for each note
    base_url = str(request.base_url).rstrip('/')
    if APP_ENV != "development":
        base_url = base_url.replace("http://", "https://")

    for note in notes:
        if note.get('image_path'):
            if APP_ENV == "development":
                note['image_path'] = f"{base_url}/static/{note['image_path']}"
            else:
                note['image_path'] = f"{base_url}/api/content/{note['image_path']}"

    return notes


@app.patch("/api/notes/{note_id}", dependencies=[Depends(check_csrf)])
async def update_item_note(note_id: str, request: Request):
    """Update a note"""
    user_email = await get_authenticated_email(request)

    # Parse the JSON body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Only allow updating text field
    updates = {}
    if 'text' in body:
        text_val = body['text']
        if text_val is not None:
            if not isinstance(text_val, str):
                raise HTTPException(status_code=400, detail="Text must be a string")
            if len(text_val) > MAX_TEXT_LENGTH:
                raise HTTPException(status_code=400, detail="Note text too long")
        updates['text'] = text_val

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    # Add user_email for ownership verification in database layer
    updates['user_email'] = user_email

    try:
        success = await db.update_item_note(note_id, updates)
        if not success:
            raise HTTPException(status_code=404, detail="Note not found")
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this note")

    return {"status": "success", "note_id": note_id}


@app.delete("/api/notes/{note_id}", dependencies=[Depends(check_csrf)])
async def delete_item_note(note_id: str, request: Request):
    """Delete a note"""
    user_email = await get_authenticated_email(request)

    try:
        success = await db.delete_item_note(note_id, user_email)
        if not success:
            raise HTTPException(status_code=404, detail="Note not found")
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this note")

    return {"status": "success", "deleted_id": note_id}


@app.patch("/api/items/{item_id}", dependencies=[Depends(check_csrf)])
async def update_item(item_id: str, request: Request, body: ItemUpdateRequest):
    """Update item (title, tags, status, next_step, follow_up)"""
    user_email = await get_authenticated_email(request)

    # Verify the item exists and belongs to the user
    item = await db.get_shared_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.get('user_email') != user_email:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this item")

    updates = {}

    # Update title directly
    if body.title is not None:
        updates['title'] = body.title

    # Update status directly
    if body.status is not None:
        updates['status'] = body.status

    # Update next_step directly
    if body.next_step is not None:
        updates['next_step'] = body.next_step

    # Update is_favorite directly
    if body.is_favorite is not None:
        updates['is_favorite'] = body.is_favorite

    # Handle analysis fields (tags, follow_up)
    current_analysis = item.get('analysis') or {}
    if not isinstance(current_analysis, dict):
        current_analysis = {}
    analysis_updated = False

    # Update tags within analysis object
    if body.tags is not None:
        current_analysis['tags'] = body.tags
        analysis_updated = True

    # Update follow_up within analysis object (empty string clears it)
    if body.follow_up is not None:
        if body.follow_up == "":
            current_analysis.pop('follow_up', None)
        else:
            current_analysis['follow_up'] = body.follow_up
        analysis_updated = True

    if analysis_updated:
        updates['analysis'] = current_analysis

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    success = await db.update_shared_item(item_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")

    return {"status": "success", "item_id": item_id}


@app.post("/api/items/note-counts", dependencies=[Depends(check_csrf)])
async def get_note_counts(request: Request, body: NoteCountRequest):
    """Batch get note counts for multiple items"""
    user_email = await get_authenticated_email(request)

    # Security: Filter item_ids to only include items owned by the user
    # Get user's items and intersect with requested item_ids
    user_items = await db.get_shared_items(user_email)
    user_item_ids = {item.get('firestore_id') for item in user_items}
    authorized_item_ids = [item_id for item_id in body.item_ids if item_id in user_item_ids]

    # Get note counts only for authorized items
    counts = await db.get_item_note_count(authorized_item_ids)

    return counts


@app.get("/api/metrics")
async def get_user_metrics(request: Request):
    """Get user metrics including item counts by status and worker queue status"""
    user_email = await get_authenticated_email(request)

    # Get item counts grouped by status
    status_counts = await db.get_user_item_counts_by_status(user_email)

    # Get worker queue counts grouped by status
    worker_counts = await db.get_user_worker_job_counts_by_status(user_email)

    # Calculate totals
    total_items = sum(status_counts.values())
    total_jobs = sum(worker_counts.values())

    return {
        "total_items": total_items,
        "by_status": status_counts,
        "worker_queue": {
            "total": total_jobs,
            "by_status": worker_counts
        }
    }
