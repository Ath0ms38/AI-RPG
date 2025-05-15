from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from web.config import templates
from web.user_management import (
    register_user, authenticate_user, get_user_stories, create_story,
    get_story, update_story
)

router = APIRouter()

def get_username_from_session(request: Request):
    return request.session.get("username")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/api/register")
async def api_register(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return {"success": False, "message": "Username and password required"}
    result = register_user(username, password)
    return result

@router.post("/api/login")
async def api_login(request: Request, data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return {"success": False, "message": "Username and password required"}
    result = authenticate_user(username, password)
    if result.get("success"):
        request.session["username"] = username
    return result

@router.post("/api/logout")
async def api_logout(request: Request):
    request.session.clear()
    return {"success": True}

@router.get("/api/check-auth")
async def api_check_auth(request: Request):
    username = get_username_from_session(request)
    return {"authenticated": bool(username), "username": username}
