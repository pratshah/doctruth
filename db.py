import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "doctruth")

logger = logging.getLogger("doctruth.db")
logging.basicConfig(level=logging.INFO)

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self.use_fallback = False
        self._fallback_cache = {}

    async def connect(self):
        try:
            logger.info(f"Connecting to MongoDB at {MONGO_URI}...")
            self.client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            self.db = self.client[DB_NAME]
            # Verify connection
            await self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB!")
        except Exception as e:
            logger.warning(f"Could not connect to MongoDB: {e}. Falling back to in-memory caching.")
            self.use_fallback = True

    async def cache_get(self, collection_name: str, key: str) -> dict:
        if self.use_fallback:
            return self._fallback_cache.get(f"{collection_name}:{key}")
        try:
            collection = self.db[collection_name]
            return await collection.find_one({"_id": key})
        except Exception as e:
            logger.error(f"Error reading from MongoDB: {e}")
            return None

    async def cache_set(self, collection_name: str, key: str, value: dict):
        if self.use_fallback:
            self._fallback_cache[f"{collection_name}:{key}"] = value
            return
        try:
            collection = self.db[collection_name]
            value["_id"] = key
            await collection.replace_one({"_id": key}, value, upsert=True)
        except Exception as e:
            logger.error(f"Error writing to MongoDB: {e}")

db = Database()
