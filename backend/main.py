import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, create_engine, Session, select
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv
from jinja2 import Template

from models import User, SharedItem

# Load environment variables
load_dotenv()

DATABASE_URL = "sqlite:///./database.db"
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-please-change")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# DB Setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)
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
def read_root(request: Request, db: Session = Depends(get_session)):
    user = request.session.get('user')
    if user:
        items = db.exec(select(SharedItem).where(SharedItem.user_email == user['email']).order_by(SharedItem.created_at.desc())).all()
        # Simple dashboard template inline for simplicity
        template = """
        <html>
            <head>
                <title>Analyze This Dashboard</title>
                <link rel="icon" href="/static/favicon.png">
            </head>
            <body style="font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
                <h1>Analyze This</h1>
                <p>Welcome, {{ user.name }} | <a href="/logout">Logout</a></p>
                <hr/>
                <h2>Shared Items</h2>
                <ul>
                {% for item in items %}
                    <li style="margin-bottom: 20px; border: 1px solid #ddd; padding: 10px; border-radius: 8px;">
                        <strong>{{ item.title or 'No Title' }}</strong> <small>({{ item.type }})</small><br/>
                        {{ item.content }}<br/>
                        <small style="color: grey;">{{ item.created_at }}</small>
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
    redirect_uri = request.url_for('auth')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth")
async def auth(request: Request, db: Session = Depends(get_session)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        return HTMLResponse(f'<h1>{error.error}</h1>')
    user_info = token.get('userinfo')
    if user_info:
        request.session['user'] = user_info
        
        # Create/Update User in DB
        existing_user = db.exec(select(User).where(User.email == user_info['email'])).first()
        if not existing_user:
            new_user = User(email=user_info['email'], name=user_info.get('name'), picture=user_info.get('picture'))
            db.add(new_user)
            db.commit()
            
    return RedirectResponse(url='/')

@app.get("/logout")
async def logout(request: Request):
    request.session.pop('user', None)
    return RedirectResponse(url='/')

# --- API Endpoints ---
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

def verify_google_token(token: str):
    try:
        id_info = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        return id_info
    except ValueError:
        return None

@app.post("/api/share")
async def share_item(request: Request, item: SharedItem, db: Session = Depends(get_session)):
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
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@app.get("/api/items")
async def get_items(request: Request, db: Session = Depends(get_session)):
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

    items = db.exec(select(SharedItem).where(SharedItem.user_email == user_email).order_by(SharedItem.created_at.desc())).all()
    return items
