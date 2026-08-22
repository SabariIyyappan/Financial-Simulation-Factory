"""
Mock Pricing API Documentation Site

Serves documentation with two different HTML layouts (V1 and V2)
to demonstrate Bright Data self-healing scraper capability.

The content remains the same, but DOM structure changes.
"""

import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI(title="Pricing API Documentation")

# Track current layout
current_layout = {"version": "v1"}

# Setup templates
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "layouts"))


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve documentation with current layout"""
    layout_version = current_layout["version"]
    template_path = f"{layout_version}/pricing-docs.html"
    
    return templates.TemplateResponse(
        template_path,
        {
            "request": request,
            "layout_version": layout_version
        }
    )


@app.get("/api/docs/pricing", response_class=HTMLResponse)
async def get_pricing_docs(request: Request):
    """Get Pricing API documentation (main scraping target)"""
    layout_version = current_layout["version"]
    template_path = f"{layout_version}/pricing-docs.html"
    
    return templates.TemplateResponse(
        template_path,
        {
            "request": request,
            "layout_version": layout_version
        }
    )


@app.get("/api/docs/layout/current")
async def get_current_layout():
    """Get current layout version"""
    return JSONResponse(current_layout)


@app.post("/api/docs/layout")
async def switch_layout(version: str):
    """Switch between layout versions"""
    if version not in ["v1", "v2"]:
        return JSONResponse(
            {"error": "Invalid layout version. Use 'v1' or 'v2'"},
            status_code=400
        )
    
    old_version = current_layout["version"]
    current_layout["version"] = version
    
    return JSONResponse({
        "message": f"Layout switched from {old_version} to {version}",
        "previous": old_version,
        "current": version
    })


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "layout": current_layout["version"]}


if __name__ == "__main__":
    # PaaS hosts inject the port to bind as $PORT; fall back to the local
    # default so `python provider-docs-site/server.py` still works unchanged.
    port = int(os.getenv("PORT") or os.getenv("DOCS_SITE_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
