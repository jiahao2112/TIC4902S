from pymongo import ASCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.user_config import MONGODB_DB_NAME, MONGODB_URL


def create_client() -> AsyncMongoClient:
    return AsyncMongoClient(MONGODB_URL)


def get_database(client: AsyncMongoClient) -> AsyncDatabase:
    return client[MONGODB_DB_NAME]


async def create_indexes(db: AsyncDatabase) -> None:
    # Unique index so the same email can't be registered twice
    await db.users.create_index([("email", ASCENDING)], unique=True)
