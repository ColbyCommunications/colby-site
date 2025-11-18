from __future__ import annotations

"""
Application entrypoint that composes the RAG assistant API and the admin panel API.

- `rag_app.app` exposes the /ask, /ask/stream, /health, /info endpoints.
- `admin_api.admin_router` exposes the /admin CRUD + /admin/dashboard endpoints.
- Static dashboard assets (CSS/JS) are served from /admin/static.
"""

from fastapi.staticfiles import StaticFiles

from admin_api import admin_router
from rag_app import app, agent_os

# Attach the admin API router.
app.include_router(admin_router)

if __name__ == "__main__":
    # Run the combined app (RAG + admin) using AgentOS' built-in server helper.
    # This preserves the old behaviour where `python api.py` starts the server.
    agent_os.serve(app="api:app", reload=True)



