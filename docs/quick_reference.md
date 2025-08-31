# FastAPI Quick Reference Guide

**File Location: `docs/quick_reference.md`**

## Essential FastAPI Patterns

### Basic Route Definition

```python
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel

app = FastAPI()

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}
```

### Pydantic Models

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    email: str = Field(..., example="user@example.com")
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
```

### Dependency Injection

```python
from fastapi import Depends
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/users/")
async def read_users(db: Session = Depends(get_db)):
    return db.query(User).all()
```

### Authentication

```python
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    # Validate token and return user
    return user
```

### Exception Handling

```python
from fastapi import HTTPException, status

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user
```

### Request Body

```python
@app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate):
    # Process user creation
    return created_user
```

### Query Parameters

```python
@app.get("/items/")
async def read_items(skip: int = 0, limit: int = 100, q: str = None):
    return {"skip": skip, "limit": limit, "q": q}
```

### Path Parameters

```python
@app.get("/users/{user_id}/items/{item_id}")
async def read_user_item(user_id: int, item_id: str):
    return {"user_id": user_id, "item_id": item_id}
```

### File Uploads

```python
from fastapi import File, UploadFile

@app.post("/upload/")
async def create_upload_file(file: UploadFile = File(...)):
    return {"filename": file.filename}
```

### Form Data

```python
from fastapi import Form

@app.post("/form/")
async def form_data(username: str = Form(...), password: str = Form(...)):
    return {"username": username}
```

### Background Tasks

```python
from fastapi import BackgroundTasks

def write_log(message: str):
    # Write to log file
    pass

@app.post("/send-email/")
async def send_email(background_tasks: BackgroundTasks):
    background_tasks.add_task(write_log, "Email sent")
    return {"message": "Email sent"}
```

### WebSockets

```python
from fastapi import WebSocket

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message: {data}")
```

### Server-Sent Events

```python
from fastapi.responses import StreamingResponse
import json

@app.get("/stream")
async def stream_data():
    def event_stream():
        for i in range(10):
            yield f"data: {json.dumps({'count': i})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/plain")
```

### Middleware

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Database Models (SQLAlchemy)

```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

## Common Status Codes

- `200` - OK
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Unprocessable Entity
- `500` - Internal Server Error

## Response Models

```python
@app.post("/users/", response_model=UserResponse, status_code=201)
async def create_user(user: UserCreate):
    return created_user
```

## Validation

```python
from pydantic import validator

class UserCreate(BaseModel):
    email: str
    age: int

    @validator('age')
    def validate_age(cls, v):
        if v < 0:
            raise ValueError('Age must be positive')
        return v
```

## Testing

```python
from fastapi.testclient import TestClient

client = TestClient(app)

def test_create_user():
    response = client.post("/users/", json={"email": "test@example.com"})
    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
```

## Configuration

```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    app_name: str = "FastAPI App"
    database_url: str

    class Config:
        env_file = ".env"

settings = Settings()
```

## Key Imports

```python
from fastapi import (
    FastAPI, Depends, HTTPException, status,
    File, UploadFile, Form, Query, Path,
    BackgroundTasks, WebSocket
)
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
```
