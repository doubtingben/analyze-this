import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import requests
from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv
from jinja2 import Template
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client as FirestoreClient

from models import User, SharedItem

# Load environment variables
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-please-change")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_EXTENSION_CLIENT_ID = os.getenv("GOOGLE_EXTENSION_CLIENT_ID")

# Firebase Init
# If GOOGLE_APPLICATION_CREDENTIALS is set, or in Cloud Run, default app creds will work.
# Helper to check if initialized to avoid errors on reload
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db: FirestoreClient = firestore.client()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # No SQL db to create
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

# Auth Setup
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
def read_root(request: Request):
    user = request.session.get('user')
    if user:
        # Firestore Query
        items_ref = db.collection('shared_items')
        query = items_ref.where(field_path='user_email', op_string='==', value=user['email']).order_by('created_at', direction=firestore.Query.DESCENDING).limit(50)
        items = []
        for doc in query.stream():
            data = doc.to_dict()
            data['firestore_id'] = doc.id
            items.append(data)
        
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
        return HTMLResponse(Template(template).render(user=user, items=items))
    return HTMLResponse('<a href="/login">Login with Google</a>')

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
        
        # Create/Update User in Firestore
        users_ref = db.collection('users')
        # Use email as document ID or query? Let's query to be safe, or use email as ID if unique.
        # Google emails are unique. Let's use email as ID for simplicity and speed.
        
        # Sanitize email for ID? (dots are allowed in IDs, slashes not). Email safety:
        # Just in case, let's query.
        
        # Check if exists
        user_doc_ref = users_ref.document(user_info['email'])  # Direct ID mapping if safe
        # If we worry about characters, we can sha256 it, but email is readable.
        
        user_data = {
            'email': user_info['email'],
            'name': user_info.get('name'),
            'picture': user_info.get('picture'),
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        user_doc_ref.set(user_data, merge=True)
            
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

@app.post("/api/share")
async def share_item(request: Request, item: SharedItem):
    # Check for Bearer token for API access (Extension/Mobile)
    auth_header = request.headers.get('Authorization')
    user_email = None
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        # Validate Google ID Token
        user_info = verify_google_token(token)
        if user_info:
            user_email = user_info['email']
    elif 'user' in request.session:
        user_email = request.session['user']['email']
    
    if not user_email:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    item.user_email = user_email
    
    # Save to Firestore
    item_dict = item.dict()
    # Serialize datetime to be firestore friendly (though dict matches, let's just dump)
    # Pydantic dict with json encoders might be safer logic, but default python types work with firebase-admin
    
    db.collection('shared_items').add(item_dict)
    
    return item

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

    items_ref = db.collection('shared_items')
    query = items_ref.where(field_path='user_email', op_string='==', value=user_email).order_by('created_at', direction=firestore.Query.DESCENDING)
    items = []
    for doc in query.stream():
        data = doc.to_dict()
        data['firestore_id'] = doc.id
        items.append(data)
    
    return items

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

    # Firestore Operation
    item_ref = db.collection('shared_items').document(item_id)
    doc = item_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Item not found")
        
    item_data = doc.to_dict()
    if item_data.get('user_email') != user_email:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this item")
        
    item_ref.delete()
    return {"status": "success", "deleted_id": item_id}
