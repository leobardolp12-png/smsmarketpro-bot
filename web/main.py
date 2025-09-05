# web/main.py - minimal FastAPI admin
from fastapi import FastAPI, Request, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
API_TOKEN = os.getenv('API_TOKEN','changeme')
templates = Jinja2Templates(directory="templates")
app = FastAPI()

def check_token(authorization: str = Header(None)):
    if authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail='unauthorized')

@app.get('/', response_class=HTMLResponse)
async def index(request: Request, auth: None = Depends(check_token)):
    return HTMLResponse('<h3>Admin panel minimal - usa la API para ver datos</h3>')
