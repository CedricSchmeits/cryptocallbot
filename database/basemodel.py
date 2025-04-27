import aiomysql
from .database import Database
from enum import Enum
from decimal import Decimal


class BaseModel:
    """Base class for database models that handles table creation, inserts, updates, and deletions."""
    # Override in child class for table name
    _tableName = None
    # Override in child class for table creation
    _fieldDefinitions = {}
    # Override in child class for additional table creation SQL
    _additionalFieldDefinitions = ""
    # Override in child class for initial
    _initialItems = []

    _BIGINT_NOT_NULL = "BIGINT NOT NULL"
    _BIGINT_NULL = "BIGINT NULL"

    def __init__(self, *args, **kwargs):
        self.__originalData = {}  # Store original values for tracking changes
        for idx, field in enumerate(self._fieldDefinitions):
            if idx < len(args):
                value = args[idx]
            else:
                value = kwargs.get(field)

            value = self.__ValueToPython(value, field)
            setattr(self, field, value)
            self.__originalData[field] = value  # Store original values

    def __repr__(self):
        result = f"<{self.__class__.__name__} "
        result += " ".join(
            [f"{key}={getattr(self, key)}" for key in self._fieldDefinitions.keys()])
        result += ">"
        return result

    @classmethod
    async def CreateTable(cls):
        """Creates the table if it does not exist."""
        # Check if the table exists
        createTable = False
        async with Database.GetCursor() as cursor:
            await cursor.execute(f"SHOW TABLES LIKE '{cls._tableName}'")
            result = await cursor.fetchone()
            if not result:
                columns = ", ".join(
                    [f"{name} {definition}" for name, definition in cls._fieldDefinitions.items()])
                query = f"CREATE TABLE IF NOT EXISTS {cls._tableName} ({columns}{cls._additionalFieldDefinitions});"
                await cursor.execute(query)
                print(f"Table '{cls._tableName}' created successfully.")
                createTable = True
            else:
                # Table exists, check for missing columns
                await cursor.execute(f"SHOW COLUMNS FROM {cls._tableName}")
                existingColumns = {row[0] for row in await cursor.fetchall()}
                for columnName, columnDefinition in cls._fieldDefinitions.items():
                    if columnName not in existingColumns:
                        # Add missing column
                        alterQuery = f"ALTER TABLE {cls._tableName} ADD COLUMN {columnName} {columnDefinition};"
                        await cursor.execute(alterQuery)
                        print(f"Added column '{columnName}' to table '{cls._tableName}'.")

        if createTable:
            # Insert initial data if the table was just created
            await cls._InsertInitialData()

    @classmethod
    async def _InsertInitialData(cls):
        """Insert initial data into the table."""
        for item in cls._initialItems:
            await cls.Insert(**item)

    @classmethod
    async def DropTable(cls):
        """Drops the table if it exists."""
        async with Database.GetCursor() as cursor:
            await cursor.execute(f"DROP TABLE IF EXISTS {cls._tableName}")
            print(f"Table '{cls._tableName}' dropped successfully.")

    @classmethod
    async def GetById(cls, recordId):
        """Fetch a record by ID and return an instance of the class."""
        async with Database.GetCursor() as cursor:
            query = f"SELECT {', '.join(cls._fieldDefinitions.keys())} FROM {cls._tableName} WHERE id = %s"
            await cursor.execute(query, (recordId,))
            result = await cursor.fetchone()
            return cls(*result) if result else None

    @classmethod
    def __GetConvertedValues(cls, kwargs):
        """Convert ENUM fields to Python values."""
        values = []
        for field in cls._fieldDefinitions:
            if field in kwargs:
                if cls._fieldDefinitions[field].startswith("ENUM"):
                    values.append(cls.__PythonToValue(
                        cls.__ValueToPython(kwargs.get(field), field), field))
                else:
                    values.append(kwargs.get(field))
        return values

    @classmethod
    async def GetBySelect(cls, **kwargs):
        """Fetch a record by a SELECT query and return an instance of the class."""
        where = ' AND '.join([f'{key} = %s' for key in kwargs.keys()])
        if where:
            query = f"SELECT {', '.join(cls._fieldDefinitions.keys())} FROM {cls._tableName} WHERE {where};"
        else:
            query = f"SELECT {', '.join(cls._fieldDefinitions.keys())} FROM {cls._tableName};"

        values = cls.__GetConvertedValues(kwargs)
        async with Database.GetCursor() as cursor:
            await cursor.execute(query, values)
            result = [cls(*result) for result in await cursor.fetchall()]
            return result

    @classmethod
    async def GetByExclude(cls, **kwargs):
        """Fetch a record by a SELECT query and return an instance of the class."""
        where = ' AND '.join([f'{key} != %s' for key in kwargs.keys()])
        if where:
            query = f"SELECT {', '.join(cls._fieldDefinitions.keys())} FROM {cls._tableName} WHERE {where};"
        else:
            query = f"SELECT {', '.join(cls._fieldDefinitions.keys())} FROM {cls._tableName};"
        values = cls.__GetConvertedValues(kwargs)
        async with Database.GetCursor() as cursor:
            await cursor.execute(query, values)
            result = [cls(*result) for result in await cursor.fetchall()]
            return result

    @classmethod
    def __ValueToPython(cls, value, field):
        """Convert ENUM fields to Python values."""
        if cls._fieldDefinitions[field].startswith("ENUM"):
            # Convert ENUM fields to string
            enumName = field.replace("_", " ").title().replace(" ", "")
            enum = getattr(cls, enumName)
            if not isinstance(value, enum):
                if isinstance(value, str):
                    value = enum[value.upper()]
                else:
                    value = enum(value)
        elif cls._fieldDefinitions[field] == "DECIMAL":
            # Convert DECIMAL fields to Decimal
            if not isinstance(value, Decimal):
                if isinstance(value, str):
                    value = Decimal(value)
                else:
                    value = Decimal.from_float(value)
            value = value.quantize(Decimal('0.0000000001'))  # Set precision for Decimal
        return value

    @classmethod
    def __PythonToValue(cls, value, field):
        """Convert value fields to Enum."""
        if cls._fieldDefinitions[field].startswith("ENUM"):
            # Convert ENUM fields to string
            if not isinstance(value, Enum):
                if isinstance(value, str):
                    enumName = field.replace("_", " ").title().replace(" ", "")
                    value = getattr(cls, enumName)[value].name.lower()
                else:
                    enumName = field.replace("_", " ").title().replace(" ", "")
                    value = cls.getattr(cls, enumName)(value).name.lower()
            value = value.name.lower()
        elif cls._fieldDefinitions[field] == "DECIMAL":
            if isinstance(value, str):
                value = Decimal(value)
            elif isinstance(value, float):
                value = Decimal.from_float(value)
            value = value.quantize(Decimal('0.0000000001'))  # Set precision for Decimal
        return value

    async def Save(self):
        """Update only changed fields in the database."""
        changedFields = {}
        for field in self._fieldDefinitions:
            if getattr(self, field) != self.__originalData[field]:
                value = getattr(self, field)
                value = self.__PythonToValue(self.__ValueToPython(value, field), field)
                changedFields[field] = value

        if not changedFields:
            print("No changes detected, skipping update.")
            return  # No changes, skip update

        setClause = ", ".join(f"{key} = %s" for key in changedFields.keys())
        values = list(changedFields.values()) + \
            [self.id]  # ID is the last parameter

        query = f"UPDATE {self._tableName} SET {setClause} WHERE id = %s"
        async with Database.GetCursor() as cursor:
            await cursor.execute(query, values)

        # Update the original values to the new ones
        self.__originalData.update(changedFields)

    @classmethod
    async def Insert(cls, **kwargs):
        """Insert a new record into the database and return the created instance."""
        fields = []
        for field in cls._fieldDefinitions:
            #if field != "id" or "id" in kwargs:
            if field in kwargs:
                if cls._fieldDefinitions[field].startswith("ENUM"):
                    fields.append(cls.__PythonToValue(cls.__ValueToPython(kwargs.get(field), field), field))
                else:
                    fields.append(field)
        # Exclude auto-increment ID
        placeholders = ", ".join(["%s"] * len(fields))
        columns = ", ".join(fields)
        values = [kwargs.get(field) for field in fields]

        query = f"INSERT INTO {cls._tableName} ({columns}) VALUES ({placeholders})"
        async with Database.GetCursor() as cursor:
            await cursor.execute(query, values)
            newId = cursor.lastrowid  # Get the newly inserted ID

        # Fetch and return the created object
        return await cls.GetById(newId)

    async def Delete(self):
        """Delete the current record from the database."""
        if not hasattr(self, "id") or self.id is None:
            raise ValueError("Cannot delete an object without an ID.")

        query = f"DELETE FROM {self._tableName} WHERE id = %s"

        async with Database.GetCursor() as cursor:
            await cursor.execute(query, (self.id,))

        print(f"Deleted {self._tableName} record with ID {self.id}")
