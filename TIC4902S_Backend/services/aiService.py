from fastapi import FastAPI, HTTPException, Request
from typing import Optional
from groq import APIConnectionError, APIStatusError, AsyncGroq, RateLimitError
from schemas.aiSchemas import ChatRequest, ChatResponse, SystemMessage, GeneratedPlan, UserMessage, QuizRequest
from collections.abc import AsyncIterator
from settings.aiConfig import GROQ_API_KEY
import json
from logger import logger
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

    yield

    if app.state.groq_client is not None:
        await app.state.groq_client.close()


aiService = FastAPI(version="1.0.0", lifespan=lifespan)

@aiService.get("/")
async def health():
    return "AI service is running."

@aiService.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    # body = await request.body()
    errors = []
    for error in exc.errors():
        field_path = ".".join(str(x) for x in error["loc"])
        message = f"Validation failed: {error['msg']} at '{field_path}' | Input: {error.get('input')}"
        logger.error(message)
        errors.append(message)
    return JSONResponse(status_code=422, content={"detail": errors})


@aiService.exception_handler(ValidationError)
async def validationExceptionLogger(request: Request, exc: ValidationError):
    errors = []
    for error in exc.errors():
        field_path = ".".join(str(x) for x in error["loc"])
        message = f"Validation failed: {error['msg']} at '{field_path}' | Input: {error.get('input')}"
        logger.error(message)
        errors.append(message)
    return JSONResponse(status_code=422, content={"detail": message})


@aiService.post("/generate")
async def generate(userMessage: UserMessage, request: Request) -> ChatResponse:
    client: Optional[AsyncGroq] = request.app.state.groq_client
    if client is None:
        logger.warning("Groq is not configured. Set GROQ_API_KEY in your .env file.")
        raise HTTPException(
            status_code=503,
            detail="Groq is not configured. Set GROQ_API_KEY in your .env file.",
        )
    try:
        generateRequest = ChatRequest(messages=[userMessage])
        setupMessage=SystemMessage()
        generateRequest.messages.insert(0,setupMessage)
        messages = []
        for message in generateRequest.messages:
            if isinstance(message, UserMessage):
                # Convert each content item into a JSON string
                converted_content = [c.model_dump_json() for c in message.content]
                # Join them into one string (API requires content to be a string)
                msg_dict = {"role": message.role, "content": " ".join(converted_content)}
            else:
                # If content is already a string
                msg_dict = {"role": message.role, "content": str(message.content)}
            messages.append(msg_dict)

        payload = {
            "model": generateRequest.model,
            "messages":messages,
            "temperature": generateRequest.temperature,
            "max_tokens": generateRequest.max_tokens,
            "response_format": generateRequest.response_format.model_dump(by_alias=True)
        }
        # print(json.dumps(payload, indent=2))
        completion = await client.chat.completions.create(
            **payload    
        )
        logger.info("Plan generated successfully from Groq")
    except RateLimitError as exc:
        logger.warning("Groq rate limit exceeded")
        raise HTTPException(
            status_code=429, detail="Groq rate limit exceeded."
        ) from exc
    except APIConnectionError as exc:
        logger.warning("Could not connect to Groq. Please try again.")
        raise HTTPException(
            status_code=502, detail="Could not connect to Groq. Please try again."
        ) from exc
    except APIStatusError as exc:
        logger.warning(exc)
        raise HTTPException(
            status_code=502,
            detail="Groq returned an error while generating a response.",
        ) from exc

    content = completion.choices[0].message.content or None
    # Try to parse the JSON string into a dict
    parsed = json.loads(content)
    # Validate against your Pydantic model
    plan = GeneratedPlan.model_validate(parsed)
    logger.info("Plan generated is of correct structure")
    return ChatResponse(content=plan.destinations)