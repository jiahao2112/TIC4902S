from fastapi import FastAPI, Request
from app.core.service_manager import ServiceManager
import httpx
from app.core.logger import logger

serviceManager = ServiceManager()

async def lifespan(app: FastAPI):
    serviceManager.start_services()
    yield

    serviceManager.stop_services()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health():
    return "Gateway is running"

@app.api_route("/ai/{path:path}", methods=["GET", "POST"])
async def aiRoute(path:str, request:Request):
    url = f"http://localhost:8001/{path}"
    async with httpx.AsyncClient() as client:
        logger.info(f"Routing to url: {url}")
        response = await client.request(
            method=request.method,
            url=url,
            headers=request.headers,
            content=await request.body()
        )
        return response.json()