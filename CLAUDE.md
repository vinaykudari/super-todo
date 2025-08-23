# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Super Todo is an agentic todo list application that enables hands-free task management through voice and text input. It uses AI agents to understand user intent, plan tasks, and autonomously execute them using specialized agents (voice, browser automation, web search). This FastAPI-based service provides the core API backed by Supabase (PostgreSQL + Storage).

## Key Commands

### Development
```bash
# Install dependencies (uses uv package manager)
uv sync

# Run development server with hot reload
uv run uvicorn app.main:app --reload

# Run on specific port (production uses 8080)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Docker
```bash
# Build image
docker build -t super-todo .

# Run container
docker run -p 8080:8080 --env-file .env super-todo
```

## Architecture

### Stack
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL via Supabase
- **Storage**: Supabase Storage for file attachments
- **Package Manager**: uv

### Project Structure
- `app/main.py`: FastAPI application entry point with CORS middleware
- `app/routers/items.py`: API endpoints using dependency injection
- `app/services/items_service.py`: Business logic layer for todo operations
- `app/dependencies.py`: Dependency injection setup
- `app/schemas.py`: Pydantic models for request/response validation
- `app/supabase_client.py`: Supabase client configuration using service role key
- `sql/setup.sql`: PostgreSQL schema with items and attachments tables

### Key Design Patterns
1. **Service Layer**: Business logic separated from routes using dependency injection
2. **State Management**: Items have three states: pending, processing, completed (PostgreSQL enum)
3. **File Storage**: Attachments stored in Supabase Storage bucket, metadata in PostgreSQL
4. **Authentication**: Currently uses Supabase service role key (bypasses RLS)
5. **Error Handling**: Consistent HTTPException usage with appropriate status codes

### Agentic Architecture (Planned)
- **Orchestrator Agent**: Analyzes user intent and delegates to specialized agents
- **Voice Agents**: VAPI-based agents for voice interaction
- **Browser Agents**: Automate web tasks using browser automation
- **Search Agents**: Perform web searches and compile research
- **Agent Communication**: Tasks are queued and processed asynchronously

### Environment Variables
Required in `.env`:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Service role key for full database access
- `SUPABASE_BUCKET`: Storage bucket name (default: "attachments")

### API Documentation
When running locally:
- Interactive docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development Notes

- To test this project, reload the server using " uv run uvicorn app.main:app --reload" and then call the API through curl