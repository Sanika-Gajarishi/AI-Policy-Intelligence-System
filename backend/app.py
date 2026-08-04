from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from services.scraper import clear_pending_scrape_artifacts, run_scraper
from routes.upload import router as upload_router
from routes.query import router as query_router
from routes.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
from routes.policies import router as policies_router
from routes.documents import router as doc_router
from routes.export import router as export_router
from routes.conversations import router as conversations_router
from routes.scraper import router as scraper_router

import tracemalloc
tracemalloc.start()
app = FastAPI()

scheduler = BackgroundScheduler()
scheduler.add_job(run_scraper, "cron", hour=6, minute=0)
scheduler.start()
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # explicit frontend origins
   
    allow_origins=[
        "https://ai-policy-dashboard-neon.vercel.app",
        "https://climatehub-frontend-2r5w.onrender.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(query_router)
app.include_router(auth_router)
app.include_router(policies_router)
app.include_router(doc_router)
app.include_router(export_router)
app.include_router(conversations_router)
app.include_router(scraper_router)

@app.on_event("startup")
def cleanup_test_scrape_artifacts():
    result = clear_pending_scrape_artifacts()
    failed_deletes = result.get("failed_deletes", [])
    print(
        "[scraper] Startup cleanup: "
        f"{result.get('cleared_pending', 0)} pending items, "
        f"{result.get('deleted_files', 0)} staging PDFs removed"
        + (f", {len(failed_deletes)} locked PDFs skipped" if failed_deletes else "")
    )


@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()

@app.get("/")
def home():
    return {"message": "Policy AI Backend Running 🚀"}

@app.get("/debug/memory")
def memory_snapshot():
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics("lineno")[:15]
    return {"top_allocations": [str(s) for s in top_stats]}