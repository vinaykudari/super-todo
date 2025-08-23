-- Phase 1: Add orchestrator support to existing schema

-- Add orchestrator fields to items table (no is_ai_task needed)
ALTER TABLE public.items ADD COLUMN IF NOT EXISTS ai_request text;
ALTER TABLE public.items ADD COLUMN IF NOT EXISTS orchestration_status text DEFAULT 'pending';
ALTER TABLE public.items ADD COLUMN IF NOT EXISTS orchestration_result jsonb;

-- Add index for processing items (orchestrator uses state='processing')
CREATE INDEX IF NOT EXISTS idx_items_processing ON public.items(state) WHERE state = 'processing';

-- Add index for orchestration status
CREATE INDEX IF NOT EXISTS idx_items_orchestration_status ON public.items(orchestration_status);

-- Message log for debugging agent communications
CREATE TABLE IF NOT EXISTS public.agent_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id uuid REFERENCES public.items(id) ON DELETE CASCADE,
    from_agent text NOT NULL,
    to_agent text NOT NULL,
    message_type text NOT NULL,
    content jsonb,
    correlation_id text,
    created_at timestamptz DEFAULT now()
);

-- Index for querying messages by item
CREATE INDEX IF NOT EXISTS idx_agent_messages_item_id ON public.agent_messages(item_id);

-- Index for querying messages by correlation
CREATE INDEX IF NOT EXISTS idx_agent_messages_correlation ON public.agent_messages(correlation_id);

-- Add orchestration tracking (for future phases)
CREATE TABLE IF NOT EXISTS public.orchestrations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id uuid NOT NULL REFERENCES public.items(id) ON DELETE CASCADE,
    state jsonb NOT NULL,  -- Full reactive state
    status text NOT NULL DEFAULT 'running',  -- running, completed, failed
    started_at timestamptz DEFAULT now(),
    completed_at timestamptz,
    agent_count integer DEFAULT 0,
    success_rate numeric(5,2),
    created_at timestamptz DEFAULT now()
);

-- Index for active orchestrations
CREATE INDEX IF NOT EXISTS idx_orchestrations_status ON public.orchestrations(status);
CREATE INDEX IF NOT EXISTS idx_orchestrations_item ON public.orchestrations(item_id);

-- Comment the new columns
COMMENT ON COLUMN public.items.ai_request IS 'Original user request for AI processing';
COMMENT ON COLUMN public.items.orchestration_status IS 'Current status of AI orchestration';
COMMENT ON COLUMN public.items.orchestration_result IS 'Results from agent execution';

COMMENT ON TABLE public.agent_messages IS 'Messages passed between agents during orchestration';
COMMENT ON TABLE public.orchestrations IS 'Tracking table for orchestration sessions';