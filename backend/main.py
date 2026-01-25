import os
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, Response
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

from models import User, SharedItem, ShareType
from database import DatabaseInterface, FirestoreDatabase, SQLiteDatabase

# Load environment variables
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-please-change")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_EXTENSION_CLIENT_ID = os.getenv("GOOGLE_EXTENSION_CLIENT_ID")
APP_ENV = os.getenv("APP_ENV", "production")

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev only. In prod, specify extension ID
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

@app.get("/")
async def read_root(request: Request):
    if APP_ENV == "development":
        user = request.session.get('user')
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
                        async function deleteItem(itemId) {
                            if (!confirm('Are you sure you want to delete this item?')) return;
                            
                            try {
                                const response = await fetch('/api/items/' + itemId, {
                                    method: 'DELETE'
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
                                        <span onclick="showAnalysis('{{ item.analysis.overview | replace('\'', '\\\'') | replace('\n', '\\n') }}')" style="cursor: pointer; font-size: 1.2em;" title="View Analysis">✨</span>
                                    {% else %}
                                        <span style="filter: grayscale(100%); opacity: 0.5; font-size: 1.2em; cursor: default;" title="No Analysis">✨</span>
                                    {% endif %}
                                </div>
                                <button onclick="deleteItem('{{ item.firestore_id }}')" style="background: #ff4444; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">Delete</button>
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
            return HTMLResponse(Template(template).render(user=user, items=items))
        return HTMLResponse('<a href="/login">Login with Google</a>')
    
    return FileResponse("static/index.html")

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

@app.post("/api/share")
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
                    file_content = await file.read()
                    blob.upload_from_string(file_content, content_type=file.content_type)
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
         
    new_item = SharedItem(
        title=item_data.get('title'),
        content=item_data.get('content'),
        type=normalized_type,
        user_email=user_email,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        item_metadata=item_data.get('item_metadata')
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
            
            # Streaming response
            # We need to install 'requests' or use google-cloud-storage transfer
            # simpler: read into memory or use a generator
            
            # Since GCS client is synchronous by default, we'll read as bytes.
            # For large files, this isn't ideal, but for images it's fine.
            content = blob.download_as_bytes()
            return Response(content, media_type=blob.content_type)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error serving content: {e}")
        raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/user")
async def get_current_user(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"email": user.get('email'), "name": user.get('name'), "picture": user.get('picture')}

@app.delete("/api/items/{item_id}")
async def delete_item(item_id: str, request: Request):
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
