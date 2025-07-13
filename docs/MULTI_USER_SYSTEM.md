# OpenManus Multi-User Conversation System

This document describes the multi-user conversation system built on top of the OpenManus agent framework.

## Overview

The multi-user conversation system extends OpenManus with:

- **Multi-User Support**: User authentication and conversation management
- **Real-Time Communication**: WebSocket-based real-time messaging
- **Event-Driven Architecture**: Complete event tracking and persistence
- **RESTful API**: Comprehensive API for all system operations
- **Modern Frontend**: React-based user interface with real-time updates
- **System Monitoring**: Built-in monitoring and alerting capabilities

## Architecture

### Backend Components

1. **Event System** (`app/event/`)
   - Event bus with persistence and tracking
   - Event handlers for different event types
   - WebSocket integration for real-time updates

2. **Database Layer** (`app/database/`)
   - SQLAlchemy models with async support
   - User, Conversation, and Event models
   - Database migrations and management

3. **API Layer** (`app/api/`)
   - FastAPI with authentication and WebSocket support
   - RESTful endpoints for all operations
   - JWT-based authentication

4. **Services** (`app/services/`)
   - UserService for user management
   - ConversationService for conversation handling
   - AuthService for authentication
   - AgentService for AI agent integration

5. **WebSocket** (`app/websocket/`)
   - Real-time communication management
   - Connection handling and message routing
   - Event broadcasting

### Frontend Components (`frontend/`)

- **React Application**: Modern UI with TypeScript
- **Real-Time Updates**: WebSocket integration for live messaging
- **Authentication**: JWT-based user authentication
- **Responsive Design**: Mobile-friendly interface

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- npm or yarn

### Installation and Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   cd frontend && npm install && cd ..
   ```

2. **Setup database**
   ```bash
   python scripts/db_manager.py setup --with-test-data
   ```

3. **Start the system**
   ```bash
   python scripts/start_system.py
   ```

The system will start:
- Backend API: http://localhost:8000
- Frontend UI: http://localhost:3000
- API Documentation: http://localhost:8000/docs

### Usage

1. Open http://localhost:3000 in your browser
2. Register a new account or login with test credentials
3. Create a new conversation or select an existing one
4. Start chatting with the AI agent

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/register` - User registration
- `GET /api/v1/auth/verify` - Token verification

### Users
- `GET /api/v1/users/me` - Get current user profile
- `PUT /api/v1/users/me` - Update user profile
- `GET /api/v1/users/{id}/conversations` - Get user conversations

### Conversations
- `POST /api/v1/conversations` - Create conversation
- `GET /api/v1/conversations/{id}` - Get conversation
- `PUT /api/v1/conversations/{id}` - Update conversation
- `DELETE /api/v1/conversations/{id}` - Delete conversation
- `POST /api/v1/conversations/{id}/messages` - Send message
- `POST /api/v1/conversations/{id}/interrupt` - Interrupt conversation
- `GET /api/v1/conversations/{id}/history` - Get message history

### Events
- `GET /api/v1/events/{id}` - Get event details
- `GET /api/v1/events/{id}/trace` - Get event trace
- `GET /api/v1/events/{id}/related` - Get related events

### WebSocket
- `WS /api/v1/ws/conversations/{id}?token={jwt}` - Real-time conversation

## Event System

The system uses an event-driven architecture where all actions generate events:

### Event Types

- **User Events**: `user.input`, `user.login`, `user.logout`
- **Agent Events**: `agent.response`, `agent.step.start`, `agent.step.complete`
- **System Events**: `conversation.created`, `conversation.closed`, `interrupt`
- **Tool Events**: `tool.execution`

### Event Flow

1. User sends message → `user.input` event
2. Agent processes message → `agent.step.start`, `tool.execution`, etc.
3. Agent responds → `agent.response` event
4. All events are persisted and broadcast via WebSocket

## WebSocket Protocol

### Connection
```
WS /api/v1/ws/conversations/{conversation_id}?token={jwt_token}
```

### Message Types

**Client to Server:**
```json
{"type": "send_message", "content": "Hello"}
{"type": "interrupt"}
{"type": "ping"}
```

**Server to Client:**
```json
{"type": "message.user", "content": "Hello", "role": "user"}
{"type": "message.assistant", "content": "Hi!", "role": "assistant"}
{"type": "agent.thinking"}
{"type": "conversation.interrupted"}
```

## Database Schema

### Users Table
- `id`: Primary key (UUID)
- `username`: Unique username
- `email`: Unique email
- `password_hash`: Hashed password
- `preferences`: JSON preferences
- `created_at`, `last_login`: Timestamps

### Conversations Table
- `id`: Primary key (UUID)
- `user_id`: Foreign key to users
- `title`: Conversation title
- `status`: active/paused/closed
- `metadata`: JSON metadata
- `created_at`, `updated_at`: Timestamps

### Events Table
- `id`: Primary key (UUID)
- `event_type`: Type of event
- `conversation_id`: Foreign key to conversations
- `user_id`: User ID
- `timestamp`: Event timestamp
- `data`: JSON event data
- `parent_events`: JSON array of parent event IDs
- `status`: Event processing status

## Development

### Backend Development

```bash
# Start backend only
python scripts/start_system.py --backend-only

# Run database migrations
python scripts/db_manager.py migrate

# Check database status
python scripts/db_manager.py check
```

### Frontend Development

```bash
# Start frontend only
cd frontend && npm run dev

# Build for production
cd frontend && npm run build
```

### Testing

```bash
# Run backend tests
pytest

# Test API endpoints
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password"}'
```

## Monitoring

### System Monitoring

```bash
python scripts/monitor_system.py
```

Monitors:
- System resources (CPU, memory, disk)
- Application metrics (events, conversations, errors)
- Database performance
- Alert conditions

### Health Checks

- **API Health**: `GET /health`
- **System Status**: `GET /status`
- **WebSocket Stats**: `GET /api/v1/ws/stats`

## Configuration

### Environment Variables

- `DATABASE_URL`: Database connection string
- `SECRET_KEY`: JWT secret key
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `DEBUG`: Debug mode (default: false)

### Database Configuration

The system supports SQLite (default) and PostgreSQL:

```bash
# SQLite (default)
export DATABASE_URL="sqlite+aiosqlite:///./openmanus.db"

# PostgreSQL
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/openmanus"
```

## Deployment

### Production Setup

1. **Set environment variables**
   ```bash
   export DATABASE_URL="postgresql://user:pass@localhost/openmanus"
   export SECRET_KEY="your-secret-key"
   export DEBUG="false"
   ```

2. **Build frontend**
   ```bash
   cd frontend && npm run build
   ```

3. **Start with production server**
   ```bash
   gunicorn app.api.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

### Docker Deployment

```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "scripts/start_system.py", "--backend-only"]
```

## Security

- JWT-based authentication with configurable expiration
- CORS protection with configurable origins
- Input validation on all API endpoints
- SQL injection prevention through SQLAlchemy
- XSS protection in frontend
- WebSocket authentication required

## Troubleshooting

### Common Issues

1. **Database connection errors**
   - Check DATABASE_URL environment variable
   - Ensure database server is running
   - Run `python scripts/db_manager.py check`

2. **WebSocket connection failures**
   - Verify JWT token is valid
   - Check user has access to conversation
   - Monitor WebSocket logs

3. **Frontend build errors**
   - Ensure Node.js 16+ is installed
   - Clear node_modules and reinstall
   - Check for TypeScript errors

### Logs

- Backend logs: Console output with configurable log levels
- Frontend logs: Browser console
- System monitoring: `scripts/monitor_system.py`

## Contributing

1. Follow existing code patterns and architecture
2. Add tests for new functionality
3. Update documentation for API changes
4. Test both backend and frontend changes
5. Monitor system performance impact
