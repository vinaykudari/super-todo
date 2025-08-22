# Super Todo API

A FastAPI-based service layer for a super todo list app with Supabase backend.

## Features

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

## API Endpoints

- `GET /health` - Health check
- `POST /items` - Create a new todo item
- `GET /items` - List todo items (with optional state filter)
- `GET /items/{item_id}` - Get item with attachments
- `PATCH /items/{item_id}/state` - Update item state
- `POST /items/{item_id}/attachments` - Add file attachment

## Documentation

Once running, visit:
- API docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
