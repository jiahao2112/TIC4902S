from fastapi import FastAPI, HTTPException

from app.core.logger import logger
from app.schemas.user import LoginRequest, LoginResponse, SignupRequest, UserResponse

user_service = FastAPI(version="1.0.0")

# Temporary in-memory storage, cleared on restart. Replace with a database later.
# Passwords are stored as plain text for now. Hash them before using real data.
users: dict[str, dict] = {}


@user_service.get("/")
async def health():
    return "User service is running."


@user_service.post("/signup", status_code=201)
async def signup(signup_request: SignupRequest) -> UserResponse:
    email = signup_request.email.lower()
    if email in users:
        logger.warning(f"Signup failed: {email} is already registered")
        raise HTTPException(status_code=409, detail="Email is already registered.")

    user = {"id": len(users) + 1, "email": email, "password": signup_request.password}
    users[email] = user
    logger.info(f"User {user['id']} signed up")
    return UserResponse(id=user["id"], email=user["email"])


@user_service.post("/login")
async def login(login_request: LoginRequest) -> LoginResponse:
    email = login_request.email.lower()
    user = users.get(email)
    if user is None or user["password"] != login_request.password:
        logger.warning(f"Login failed for {email}")
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    logger.info(f"User {user['id']} logged in")
    return LoginResponse(
        message="Login successful.",
        user=UserResponse(id=user["id"], email=user["email"]),
    )
