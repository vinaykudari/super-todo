# Super Todo API

FastAPI-based super todo list API with Supabase backend and browser automation capabilities.

## Features

- **Todo Management**: Create, update, and manage todo items
- **File Attachments**: Attach files to todo items
- **Real-time Logging**: Log events to Convex for real-time monitoring
- **Browser Automation**: Automate web tasks like Amazon returns using AI agents
- ✅ CRUD operations for todo items
- 📎 File attachments support via Supabase Storage
- 🔄 State management (pending, processing, completed)
- 🚀 FastAPI with automatic OpenAPI documentation
- 🗄️ PostgreSQL database via Supabase

## Setup

1. **Install uv (if not already installed):**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Environment setup:**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase credentials
   ```

4. **Database setup:**
   - Go to your Supabase project dashboard
   - Navigate to **SQL Editor**
   - Copy and paste the contents of `sql/setup.sql`
   - Click **Run** to execute the SQL
   - Go to **Storage** → **Buckets** and create a new public bucket named "attachments"

5. **Run the server:**
   ```bash
   uv run uvicorn app.main:app --reload
   ```

## Browser Automation

The API includes browser automation capabilities powered by `browser-use` and OpenAI. Simply describe what you want to do in natural language!

### Natural Language Tasks
The agent understands natural language instructions and can automate complex web tasks.

**Main Endpoint**: `POST /browser/natural-task`

**Parameters**:
- `item_id`: Todo item ID to associate logs with
- `task`: Natural language description of what to do
- `allowed_domains`: Optional list of allowed domains for security

**Examples**:
```bash
# Return a specific product
curl -X POST "http://localhost:8000/browser/natural-task" \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": "your-item-id",
    "task": "Return my sunscreen order from Amazon because it arrived damaged"
  }'

# Return by order number
curl -X POST "http://localhost:8000/browser/natural-task" \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": "your-item-id", 
    "task": "Go to Amazon and return order 123-4567890-1234567"
  }'

# Find and return recent order
curl -X POST "http://localhost:8000/browser/natural-task" \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": "your-item-id",
    "task": "Find my recent Amazon order for wireless headphones and process a return"
  }'
```

### Convenience Endpoint
**Amazon Returns**: `POST /browser/amazon-return`

**Parameters**:
- `item_id`: Todo item ID to associate logs with  
- `order_number`: Optional specific order number
- `return_reason`: Reason for return (optional)
- `product_description`: Optional product description to help find it

**Example**:
```bash
curl -X POST "http://localhost:8000/browser/amazon-return" \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": "your-item-id",
    "product_description": "sunscreen",
    "return_reason": "damaged"
  }'
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Required for browser automation
OPENAI_API_KEY=your_openai_api_key_here
AMAZON_EMAIL=your_amazon_email@example.com
AMAZON_PASSWORD=your_amazon_password_here

# Database
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here

# Logging
CONVEX_URL=your_convex_url_here
```

## API Endpoints

### Todo Management
- `GET /health` - Health check
- `POST /items` - Create a new todo item
- `GET /items` - List todo items (with optional state filter)
- `GET /items/{item_id}` - Get item with attachments
- `PATCH /items/{item_id}/state` - Update item state
- `POST /items/{item_id}/attachments` - Add file attachment

### Browser Automation
- `POST /browser/execute-task` - Execute browser automation task
- `POST /browser/amazon-return` - Convenience endpoint for Amazon returns
- `GET /browser/task/{task_id}/status` - Get task status

### Logging
- `POST /logs` - Add log entry
- `GET /logs/item/{item_id}` - Get logs for specific item
- `GET /logs/recent` - Get recent logs

## Documentation

Once running, visit:
- API docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
