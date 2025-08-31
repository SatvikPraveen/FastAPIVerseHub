# API Usage Guide

**File Location: `docs/api_usage_guide.md`**

## Getting Started

### Base URL

```
http://localhost:8000
```

### API Documentation

- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json

## Authentication

### 1. Register a New User

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123",
    "full_name": "John Doe"
  }'
```

**Response**:

```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2025-08-26T10:30:00Z",
  "is_active": true
}
```

### 2. Login

```bash
curl -X POST "http://localhost:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=securepassword123"
```

**Response**:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 3. Using the Token

Include the token in the `Authorization` header for protected endpoints:

```bash
curl -X GET "http://localhost:8000/api/v1/users/me" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## User Management

### Get Current User

```bash
GET /api/v1/users/me
Authorization: Bearer <token>
```

### Update Current User

```bash
curl -X PUT "http://localhost:8000/api/v1/users/me" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "John Smith",
    "bio": "Software Developer"
  }'
```

### Get User by ID

```bash
GET /api/v1/users/{user_id}
Authorization: Bearer <token>
```

### List Users (with pagination)

```bash
GET /api/v1/users/?skip=0&limit=10
Authorization: Bearer <token>
```

## Course Management

### Create Course

```bash
curl -X POST "http://localhost:8000/api/v1/courses/" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "FastAPI Basics",
    "description": "Learn the fundamentals of FastAPI",
    "category": "Programming",
    "difficulty": "beginner",
    "estimated_duration": 120
  }'
```

### Get Course

```bash
GET /api/v1/courses/{course_id}
```

### Update Course

```bash
curl -X PUT "http://localhost:8000/api/v1/courses/{course_id}" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Advanced FastAPI",
    "description": "Deep dive into FastAPI features"
  }'
```

### List Courses

```bash
GET /api/v1/courses/?category=Programming&difficulty=beginner&skip=0&limit=10
```

### Delete Course

```bash
DELETE /api/v1/courses/{course_id}
Authorization: Bearer <token>
```

## File Operations

### Upload File

```bash
curl -X POST "http://localhost:8000/api/v1/uploads/" \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/your/file.pdf" \
  -F "description=Course material"
```

**Response**:

```json
{
  "id": "uuid-string",
  "filename": "file.pdf",
  "content_type": "application/pdf",
  "size": 1024000,
  "description": "Course material",
  "uploaded_at": "2025-08-26T10:30:00Z",
  "download_url": "/api/v1/uploads/uuid-string/download"
}
```

### Download File

```bash
GET /api/v1/uploads/{file_id}/download
Authorization: Bearer <token>
```

### List User Files

```bash
GET /api/v1/uploads/my-files
Authorization: Bearer <token>
```

## Real-time Communication

### WebSocket Connection

```javascript
const ws = new WebSocket("ws://localhost:8000/api/v1/ws");

// Authentication
ws.onopen = function () {
  ws.send(
    JSON.stringify({
      type: "authenticate",
      token: "your-jwt-token",
    })
  );
};

// Send message
ws.send(
  JSON.stringify({
    type: "message",
    content: "Hello World!",
    room: "general",
  })
);

// Receive messages
ws.onmessage = function (event) {
  const data = JSON.parse(event.data);
  console.log("Received:", data);
};
```

### Server-Sent Events

```javascript
const eventSource = new EventSource(
  "http://localhost:8000/api/v1/sse/notifications?token=your-jwt-token"
);

eventSource.onmessage = function (event) {
  const data = JSON.parse(event.data);
  console.log("Notification:", data);
};

eventSource.addEventListener("user_registered", function (event) {
  const data = JSON.parse(event.data);
  console.log("New user registered:", data.user_email);
});
```

## Form Data Examples

### Submit Contact Form

```bash
curl -X POST "http://localhost:8000/api/v1/forms/contact" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "name=John Doe&email=john@example.com&message=Hello&subject=Inquiry"
```

### Upload with Form Data

```bash
curl -X POST "http://localhost:8000/api/v1/forms/upload" \
  -F "title=My Document" \
  -F "file=@document.pdf" \
  -F "category=education"
```

## Error Handling

### Common Error Responses

#### 400 Bad Request

```json
{
  "detail": "Invalid input data",
  "errors": [
    {
      "field": "email",
      "message": "Invalid email format"
    }
  ]
}
```

#### 401 Unauthorized

```json
{
  "detail": "Could not validate credentials"
}
```

#### 404 Not Found

```json
{
  "detail": "User not found"
}
```

#### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Rate Limiting

The API implements rate limiting:

- **Anonymous requests**: 100 requests per hour
- **Authenticated requests**: 1000 requests per hour

Rate limit headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1693056000
```

## Pagination

List endpoints support pagination:

```bash
GET /api/v1/users/?skip=20&limit=10
```

**Response**:

```json
{
  "items": [...],
  "total": 150,
  "skip": 20,
  "limit": 10,
  "has_next": true,
  "has_previous": true
}
```

## Filtering and Searching

### Filter Courses

```bash
GET /api/v1/courses/?category=Programming&difficulty=beginner&search=python
```

### Sort Results

```bash
GET /api/v1/courses/?sort=created_at&order=desc
```

## Health Check

```bash
GET /health
```

**Response**:

```json
{
  "status": "healthy",
  "timestamp": "2025-08-26T10:30:00Z",
  "version": "1.0.0"
}
```

## API Versioning

### Version 1 (Current)

```bash
GET /api/v1/users/
```

### Version 2 (Future)

```bash
GET /api/v2/users/
```

Version 2 includes enhanced features:

- Improved response formats
- Additional filter options
- Enhanced real-time capabilities

## Testing with Python

```python
import requests

# Base configuration
BASE_URL = "http://localhost:8000"
headers = {"Content-Type": "application/json"}

# Register user
response = requests.post(
    f"{BASE_URL}/api/v1/auth/register",
    json={
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User"
    },
    headers=headers
)
print(response.json())

# Login
response = requests.post(
    f"{BASE_URL}/api/v1/auth/token",
    data={
        "username": "test@example.com",
        "password": "testpass123"
    }
)
token = response.json()["access_token"]

# Use authenticated endpoints
auth_headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

response = requests.get(
    f"{BASE_URL}/api/v1/users/me",
    headers=auth_headers
)
print(response.json())
```

## Postman Collection

Import the provided Postman collection for easy API testing:

1. Download `postman_collection.json` from the project root
2. Import into Postman
3. Set environment variables:
   - `base_url`: http://localhost:8000
   - `token`: Your JWT token

## Common Use Cases

### 1. User Registration Flow

1. Register user → `POST /api/v1/auth/register`
2. Login → `POST /api/v1/auth/token`
3. Get profile → `GET /api/v1/users/me`
4. Update profile → `PUT /api/v1/users/me`

### 2. Course Management Flow

1. Create course → `POST /api/v1/courses/`
2. Upload course materials → `POST /api/v1/uploads/`
3. List courses → `GET /api/v1/courses/`
4. Get specific course → `GET /api/v1/courses/{id}`

### 3. Real-time Notifications

1. Connect to WebSocket → `ws://localhost:8000/api/v1/ws`
2. Authenticate connection
3. Join rooms and receive notifications
4. Alternative: Use SSE for one-way notifications

## Best Practices

1. **Always use HTTPS in production**
2. **Store JWT tokens securely** (not in localStorage for web apps)
3. **Handle token expiration** gracefully
4. **Implement proper error handling**
5. **Use pagination** for large datasets
6. **Respect rate limits**
7. **Validate input** on the client side
8. **Use appropriate HTTP methods**

## Support

For API support:

- Check the interactive documentation at `/docs`
- Review error messages carefully
- Check rate limit headers
- Ensure proper authentication
- Validate request payload format
