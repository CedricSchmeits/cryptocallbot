#!/usr/bin/env python3
import os
import aiomysql
import asyncio
from contextlib import asynccontextmanager



class Database:
    __pool = None  # Class-level connection pool

    @classmethod
    async def Init(cls):
        """Initialize the database connection pool (call this once at bot startup)."""
        if cls.__pool is None:
            cls.__pool = await aiomysql.create_pool(host=os.getenv("MYSQL_HOST"),
                                                    port=int(os.getenv("MYSQL_PORT")),
                                                    user=os.getenv("MYSQL_USER"),
                                                    password=os.getenv("MYSQL_PASSWORD"),
                                                    db=os.getenv("MYSQL_DATABASE"),
                                                    autocommit=True,
                                                    minsize=1,  # Minimum connections in pool
                                                    maxsize=10)  # Maximum connections in pool

    @classmethod
    async def Close(cls):
        """Close the database pool (call this when bot shuts down)."""
        if cls.__pool is not None:
            cls.__pool.close()
            await cls.__pool.wait_closed()
            cls.__pool = None

    @classmethod
    def Get(cls):
        """Get the existing pool, ensuring it is initialized."""
        return cls.__pool

    @classmethod
    @asynccontextmanager
    async def GetCursor(cls):
        """Get a cursor from the pool and close it automatically."""
        pool = cls.Get()
        conn = await pool.acquire()
        try:
            cursor = await conn.cursor()
            try:
                yield cursor
            finally:
                await cursor.close()
        finally:
            pool.release(conn)
