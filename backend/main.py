import os
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import requests
from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, storage

from models import User, SharedItem
from database import DatabaseInterface, FirestoreDatabase, SQLiteDatabase

# Load environment variables
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-please-change")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_EXTENSION_CLIENT_ID = os.getenv("GOOGLE_EXTENSION_CLIENT_ID")
APP_ENV = os.getenv("APP_ENV", "production")

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
                                <div>
                                    <strong>{{ item.title or 'No Title' }}</strong> <small>({{ item.type }})</small>
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

def verify_google_token(token: str):
    # DEV_BYPASS
    if APP_ENV == "development" and token == "dev-token":
        return {
            "email": "dev@example.com",
            "name": "Developer",
            "picture": "https://via.placeholder.com/150"
        }

    # Method 1: Try verifying as ID Token (Web Client)
    try:
        id_info = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        return id_info
    except ValueError:
        pass
        
    # Method 2: Try verifying as Access Token (Extension Client)
    try:
        # Call Google UserInfo endpoint
        response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {token}'}
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
        
    return None

import uuid
import datetime

@app.post("/api/share")
async def share_item(
    request: Request,
    title: str = Form(None),
    content: str = Form(None),
    type: str = Form(None),
    file: UploadFile = File(None),
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
        user_info = verify_google_token(token)
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
                
                item_data['type'] = item_data.get('type', 'media')  # Preserve type if provided
                
            except Exception as e:
                print(f"Upload failed: {e}")
                raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported Content-Type")

    # Construct Item
    if not item_data.get('type'):
         item_data['type'] = 'text' # Default
         
    new_item = SharedItem(
        title=item_data.get('title'),
        content=item_data.get('content'),
        type=item_data.get('type'),
        user_email=user_email,
        created_at=datetime.datetime.now(datetime.timezone.utc)
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
        user_info = verify_google_token(token)
        if user_info:
            user_email = user_info['email']
    elif 'user' in request.session:
        user_email = request.session['user']['email']
        
    if not user_email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    items = await db.get_shared_items(user_email)
    
    # Process items (Signed URLs etc)
    # We only need to do this for media/screenshot items in PROD or adjust URLs in DEV
    image_types = ('media', 'screenshot')

    if APP_ENV == "development":
        # DEV: transform content path to localhost static URL
        base_url = str(request.base_url).rstrip('/')
        for item in items:
            if item.get('type') in image_types and item.get('content') and not item.get('content').startswith('http'):
                # Assumes content is relative path like uploads/email/uuid.ext
                # Mounted at /static
                item['content'] = f"{base_url}/static/{item['content']}"
    else:
        # PROD: Firebase Storage public URLs
        from urllib.parse import quote
        bucket = storage.bucket()
        bucket_name = bucket.name
        for item in items:
            if item.get('type') in image_types and item.get('content') and not item.get('content').startswith('http'):
                blob_name = item['content']
                encoded_blob = quote(blob_name, safe='')
                item['content'] = f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded_blob}?alt=media"
    
    return items

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
        user_info = verify_google_token(token)
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
