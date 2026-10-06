from fastapi import FastAPI, HTTPException, Request
from typing import Optional
from fastapi.responses import FileResponse
from groq import APIConnectionError, APIStatusError, AsyncGroq, RateLimitError
from schemas.aiSchemas import ChatRequest, ChatResponse, SetupMessage, GeneratedPlan
from collections.abc import AsyncIterator
from settings.aiConfig import GROQ_API_KEY
import json

async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    yield
    if app.state.groq_client is not None:
        await app.state.groq_client.close()


aiService = FastAPI(version="1.0.0", lifespan=lifespan)

@aiService.get("/")
async def health():
    return "AI service is running."


@aiService.post("/generate")
async def generate(generateRequest: ChatRequest, request: Request) -> ChatResponse:
    client: Optional[AsyncGroq] = request.app.state.groq_client
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Groq is not configured. Set GROQ_API_KEY in your .env file.",
        )
    try:
        setupMessage=SetupMessage()
        generateRequest.messages.insert(0,setupMessage)
        messages = []
        for message in generateRequest.messages:
            if isinstance(message.content, list):
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
    except RateLimitError as exc:
        raise HTTPException(
            status_code=429, detail="Groq rate limit exceeded."
        ) from exc
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=502, detail="Could not connect to Groq. Please try again."
        ) from exc
    except APIStatusError as exc:
        print (exc)
        raise HTTPException(
            status_code=502,
            detail="Groq returned an error while generating a response.",
        ) from exc

    content = completion.choices[0].message.content or None

    try:
    # Try to parse the JSON string into a dict
        parsed = json.loads(content)
        # Validate against your Pydantic model
        plan = GeneratedPlan.model_validate(parsed)
        return ChatResponse(content=plan.destinations)
    except Exception as e:
        # Fallback: just return the raw string if parsing fails
        print(e)
        return ChatResponse(content=content, model=completion.model)