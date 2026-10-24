from collections.abc import AsyncIterator
from datetime import datetime, timezone

import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.logger import logger
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.core.user_config import SECRET_KEY
from app.db.database import create_client, create_indexes, get_database
from app.schemas.user import LoginRequest, SignupRequest, TokenResponse, UserResponse


async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if not SECRET_KEY:
        logger.critical("SECRET_KEY is not set. Set SECRET_KEY in your .env file.")
        raise RuntimeError("SECRET_KEY is not set. Set SECRET_KEY in your .env file.")

    app.state.mongo_client = create_client()
    app.state.db = get_database(app.state.mongo_client)
    try:
        await create_indexes(app.state.db)
        logger.info("Connected to MongoDB")
    except PyMongoError as exc:
        logger.critical(f"Could not connect to MongoDB: {exc}")
        await app.state.mongo_client.close()
        raise

    yield

    await app.state.mongo_client.close()


user_service = FastAPI(version="1.0.0", lifespan=lifespan)
bearer_scheme = HTTPBearer(auto_error=False)


def to_user_response(user: dict) -> UserResponse:
    return UserResponse(id=str(user["_id"]), email=user["email"])


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        user_id = ObjectId(decode_access_token(credentials.credentials))
    except (jwt.InvalidTokenError, InvalidId, KeyError) as exc:
        logger.warning(f"Rejected token: {exc}")
        raise unauthorized from exc

    user = await request.app.state.db.users.find_one({"_id": user_id})
    if user is None:
        logger.warning(f"Token for unknown user {user_id}")
        raise unauthorized
    return user


@user_service.get("/")
async def health():
    return "User service is running."


@user_service.post("/signup", status_code=201)
async def signup(signup_request: SignupRequest, request: Request) -> UserResponse:
    email = signup_request.email.lower()
    user = {
        "email": email,
        "hashed_password": hash_password(signup_request.password),
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = await request.app.state.db.users.insert_one(user)
    except DuplicateKeyError as exc:
        logger.warning(f"Signup failed: {email} is already registered")
        raise HTTPException(status_code=409, detail="Email is already registered.") from exc

    user["_id"] = result.inserted_id
    logger.info(f"User {result.inserted_id} signed up")
    return to_user_response(user)


@user_service.post("/login")
async def login(login_request: LoginRequest, request: Request) -> TokenResponse:
    email = login_request.email.lower()
    user = await request.app.state.db.users.find_one({"email": email})
    if user is None or not verify_password(login_request.password, user["hashed_password"]):
        logger.warning(f"Login failed for {email}")
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    logger.info(f"User {user['_id']} logged in")
    return TokenResponse(access_token=create_access_token(str(user["_id"])))


@user_service.get("/me")
async def me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return to_user_response(current_user)
