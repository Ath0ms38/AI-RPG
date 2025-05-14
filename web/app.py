from web.config import app
from web.routes.auth import router as auth_router
from web.routes.stories import router as stories_router
from web.routes.game import router as game_router
from web.routes.websocket import router as websocket_router

app.include_router(auth_router)
app.include_router(stories_router)
app.include_router(game_router)
app.include_router(websocket_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
