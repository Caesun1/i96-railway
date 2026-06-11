#!/usr/bin/env python3
"""
I-96 Home Buyers — Lead capture backend + static site server (Railway-ready).

This single FastAPI app does two things:
  1. Serves the website (index.html, css/, js/, images/) at "/"
  2. Exposes the lead-capture API at /api/leads

Lead handling:
  * Every submission is stored in SQLite (data.db) so no lead is ever lost.
  * If Podio credentials are set via environment variables, the lead is ALSO
    pushed into your Podio app.
  * If a NOTIFY_EMAIL_TO + Postmark/SMTP settings are set (optional, future),
    you can extend this to email yourself on each lead.

Environment variables (set these in the Railway dashboard → Variables):

  # Podio (all optional — leave unset and leads still save to SQLite)
  PODIO_CLIENT_SECRET   (SECRET)
  PODIO_APP_TOKEN       (SECRET)

  # Protect the leads list (recommended). If set, GET /api/leads requires
  # header  X-Admin-Key: <value>
  ADMIN_KEY             (SECRET) any random string you choose

Railway provides PORT automatically; this server binds to it.
"""
import os
import sqlite3
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

HERE = os.path.dirname(os.path.abspath(__file__))
# Store the database on a writable path. On Railway, attach a Volume mounted at
# /data and set DB_PATH=/data/data.db so leads survive redeploys.
DB_PATH = os.environ.get("DB_PATH", os.path.join(HERE, "data.db"))

# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.execute(
    """CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        condition TEXT,
        timeline TEXT,
        visitor_id TEXT,
        podio_status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""
)
db.commit()


@asynccontextmanager
async def lifespan(app):
    yield
    db.close()


app = FastAPI(lifespan=lifespan, title="I-96 Home Buyers")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
class Lead(BaseModel):
    name: str
    phone: str
    email: str
    address: str
    condition: str = ""
    timeline: str = ""

    @field_validator("name", "phone", "email", "address")
    @classmethod
    def not_blank(cls, v):
        if not v or not v.strip():
            raise ValueError("required")
        return v.strip()


# --------------------------------------------------------------------------- #
# Podio integration
# --------------------------------------------------------------------------- #
PODIO_BASE = "https://api.podio.com"


PODIO_CLIENT_ID = "claude-6i0be2"
PODIO_APP_ID = "30585648"


def podio_configured() -> bool:
    return all(
        os.environ.get(k)
        for k in ("PODIO_CLIENT_SECRET", "PODIO_APP_TOKEN")
    )


async def push_to_podio(lead: Lead) -> str:
    if not podio_configured():
        return "skipped:not_configured"

    client_secret = os.environ["PODIO_CLIENT_SECRET"]
    app_token = os.environ["PODIO_APP_TOKEN"]

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            tok = await client.post(
                f"{PODIO_BASE}/oauth/token",
                data={
                    "grant_type": "app",
                    "app_id": PODIO_APP_ID,
                    "app_token": app_token,
                    "client_id": PODIO_CLIENT_ID,
                    "client_secret": client_secret,
                },
            )
            tok.raise_for_status()
            access_token = tok.json()["access_token"]

            fields = {
                "title": lead.name,
                "property-address": lead.address,
                "seller-phone": [{"type": "mobile", "value": lead.phone}],
                "seller-email": [{"type": "other", "value": lead.email}],
                "stage-of-lead": [{"value": 21}],
                "lead-source": [{"value": 9}],  # 9 = "Website Form"
            }

            # Combine condition and timeline into the Notes field
            notes_parts = []
            if lead.condition:
                notes_parts.append(f"Condition: {lead.condition}")
            if lead.timeline:
                notes_parts.append(f"Timeline: {lead.timeline}")
            if notes_parts:
                fields["notes"] = "\n".join(notes_parts)

            res = await client.post(
                f"{PODIO_BASE}/item/app/{PODIO_APP_ID}/",
                headers={"Authorization": f"OAuth2 {access_token}"},
                json={"fields": fields},
            )
            res.raise_for_status()
            return f"ok:item_{res.json().get('item_id', '?')}"
    except httpx.HTTPStatusError as e:
        return f"error:{e.response.status_code}"
    except Exception as e:  # noqa: BLE001
        return f"error:{type(e).__name__}"


# --------------------------------------------------------------------------- #
# API routes
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health():
    return {"ok": True, "podio_configured": podio_configured()}


@app.post("/api/leads", status_code=201)
async def create_lead(lead: Lead, request: Request):
    visitor = request.headers.get("X-Visitor-Id", "")
    podio_status = await push_to_podio(lead)
    cur = db.execute(
        """INSERT INTO leads (name, phone, email, address, condition, timeline, visitor_id, podio_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [lead.name, lead.phone, lead.email, lead.address, lead.condition,
         lead.timeline, visitor, podio_status],
    )
    db.commit()
    return {"id": cur.lastrowid, "received": True, "podio": podio_status}


@app.get("/api/leads")
def list_leads(request: Request):
    admin_key = os.environ.get("ADMIN_KEY")
    if admin_key:
        if request.headers.get("X-Admin-Key") != admin_key:
            raise HTTPException(status_code=401, detail="unauthorized")
    rows = db.execute(
        """SELECT id, name, phone, email, address, condition, timeline, podio_status, created_at
           FROM leads ORDER BY id DESC"""
    ).fetchall()
    cols = ["id", "name", "phone", "email", "address", "condition", "timeline", "podio_status", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


# --------------------------------------------------------------------------- #
# Static site (mounted LAST so /api/* takes priority)
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "index.html"))


@app.get("/privacy.html")
def privacy():
    return FileResponse(os.path.join(HERE, "privacy.html"))


@app.get("/terms.html")
def terms():
    return FileResponse(os.path.join(HERE, "terms.html"))


@app.get("/sitemap.xml", response_class=Response)
def sitemap():
    content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.i96homebuyers.com/</loc>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return Response(content=content, media_type="application/xml")


@app.get("/robots.txt", response_class=Response)
def robots():
    return FileResponse(os.path.join(HERE, "robots.txt"), media_type="text/plain")


@app.get("/guide.pdf")
def guide():
    return FileResponse(os.path.join(HERE, "guide.pdf"), media_type="application/pdf", filename="I96-Cash-Offer-Guide.pdf")


@app.get("/llms.txt", response_class=Response)
def llmstxt():
    return FileResponse(os.path.join(HERE, "llms.txt"), media_type="text/plain")


app.mount("/", StaticFiles(directory=HERE, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
