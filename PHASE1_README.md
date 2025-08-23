# Phase 1: Basic LangGraph Integration

This document describes the Phase 1 implementation of the Reactive Agent Network for Super Todo.

## What's Implemented

### 🏗️ Architecture
- **LangGraph Workflow**: Basic supervisor pattern with state management
- **Reactive State**: Message-based communication between components
- **Search Agent**: Simple search agent that processes requests
- **FastAPI Integration**: REST endpoints to trigger orchestration

### 🔧 Key Components

#### 1. Orchestrator Supervisor (`app/orchestrator/supervisor.py`)
- LangGraph-based workflow coordinator
- Manages agent network lifecycle
- Handles state transitions and error recovery

#### 2. Reactive Search Agent (`app/orchestrator/agents/search.py`)
- Processes search and research requests
- Simulated search results for testing
- Confidence-based task handling

#### 3. State Management (`app/orchestrator/state.py`)
- `ReactiveState`: Shared state across the network
- `AgentMessage`: Message protocol between agents
- Helper functions for state manipulation

#### 4. API Endpoints (`app/routers/orchestrator.py`)
- `POST /orchestrator/items/{item_id}/execute`: Trigger orchestration
- `GET /orchestrator/items/{item_id}/status`: Check orchestration status

## How It Works

### Workflow Overview
```
1. User creates AI task → 2. API triggers orchestration → 3. Supervisor initializes network
                                                               ↓
6. Task marked complete ← 5. Results aggregated ← 4. Search agent processes request
```

### Detailed Flow
1. **Task Creation**: User creates todo item with `is_ai_task: true`
2. **Trigger**: API call to `/orchestrator/items/{id}/execute`
3. **Initialize**: Supervisor creates reactive state and initializes agents
4. **Broadcast**: Task request sent to search agent
5. **Process**: Search agent handles request and returns results
6. **Monitor**: Supervisor monitors agent completion
7. **Aggregate**: Results collected and processed
8. **Complete**: Task status updated to "completed"

## Setup Instructions

### 1. Install Dependencies
```bash
# Install new dependencies
uv sync
```

### 2. Update Database Schema
```bash
# Run the Phase 1 schema updates
# In your Supabase dashboard, execute the SQL from:
cat sql/phase1_orchestrator.sql
```

### 3. Environment Variables
Add to your `.env` file:
```bash
# OpenAI API key (for future LLM integration)
OPENAI_API_KEY=your_key_here

# Redis connection (optional for Phase 1)
REDIS_URL=redis://localhost:6379
```

### 4. Start Server
```bash
uv run uvicorn app.main:app --reload
```

## Testing Phase 1

### Automated Test
```bash
# Run the test script
python test_orchestrator.py
```

### Manual Testing

#### 1. Create AI Task
```bash
curl -X POST "http://localhost:8000/items" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Research Python async programming",
    "description": "Find best practices and examples",
    "is_ai_task": true,
    "ai_request": "Research Python async programming best practices"
  }'
```

#### 2. Trigger Orchestration
```bash
# Use the item ID from step 1
curl -X POST "http://localhost:8000/orchestrator/items/{item_id}/execute" \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

#### 3. Check Status
```bash
curl -X GET "http://localhost:8000/orchestrator/items/{item_id}/status"
```

#### 4. View Results
```bash
curl -X GET "http://localhost:8000/items/{item_id}"
```

## API Documentation

### Create AI Task
```http
POST /items
Content-Type: application/json

{
  "title": "Task title",
  "description": "Task description",
  "is_ai_task": true,
  "ai_request": "Detailed request for AI processing"
}
```

### Trigger Orchestration
```http
POST /orchestrator/items/{item_id}/execute
Content-Type: application/json

{
  "force": true  // Optional: force execution even if not AI task
}
```

### Check Status
```http
GET /orchestrator/items/{item_id}/status

Response:
{
  "item_id": "uuid",
  "status": "pending|processing|completed|failed",
  "orchestration_result": {...},
  "last_updated": "timestamp"
}
```

## What's Simulated

For Phase 1, these components are simulated:
- **Search Results**: Returns mock data instead of real search API calls
- **Agent Intelligence**: Simple pattern matching instead of LLM processing
- **Real-time Updates**: Polling instead of WebSocket streams

## Success Criteria ✅

Phase 1 is complete when:
- [x] LangGraph workflow executes successfully
- [x] Search agent processes requests
- [x] Tasks are automatically marked as completed
- [x] Results are stored with the task
- [x] API endpoints work as documented
- [x] End-to-end test passes

## Next Steps (Phase 2)

Phase 2 will add:
- Redis-based message bus for real reactive communication
- Intent analysis agent with LLM integration
- Planning agent for task decomposition
- Parallel agent execution
- Real-time WebSocket updates

## Troubleshooting

### Common Issues

#### LangGraph Import Errors
```bash
# Make sure dependencies are installed
uv sync
```

#### Database Schema Issues
```bash
# Ensure Phase 1 SQL has been executed in Supabase
# Check table structure:
SELECT column_name, data_type FROM information_schema.columns 
WHERE table_name = 'items';
```

#### Orchestration Not Starting
- Check server logs for errors
- Verify item exists and has `is_ai_task: true`
- Use `force: true` in request if needed

#### Task Not Completing
- Check background task execution
- Look for errors in server logs
- Verify search agent is responding

### Debug Mode
Enable detailed logging:
```python
import logging
logging.getLogger("app.orchestrator").setLevel(logging.DEBUG)
```

## File Structure
```
app/orchestrator/
├── __init__.py              # Package exports
├── state.py                 # Reactive state management
├── supervisor.py            # LangGraph supervisor
├── agents/
│   ├── __init__.py
│   ├── base.py             # Base agent interface
│   └── search.py           # Search agent implementation
└── nodes/
    └── __init__.py         # Future: LangGraph nodes

sql/phase1_orchestrator.sql # Database schema updates
test_orchestrator.py        # End-to-end test script
```

## Metrics & Monitoring

Phase 1 includes basic logging:
- Orchestration start/completion
- Agent message passing
- Error tracking
- Execution timing

Future phases will add:
- Performance metrics
- Cost tracking
- Success rate monitoring
- Real-time dashboards