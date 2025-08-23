-- Voice Calls Migration SQL
-- This script adds tables to support VAPI voice call functionality

-- Add voice call tracking table
CREATE TABLE IF NOT EXISTS public.voice_calls (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id uuid REFERENCES public.items(id) ON DELETE CASCADE,
    vapi_call_id text UNIQUE,
    assistant_id text NOT NULL,
    phone_number text NOT NULL,
    recipient_name text,
    call_purpose text,
    call_status text NOT NULL DEFAULT 'initiated', -- initiated, ringing, answered, completed, failed
    duration_seconds integer,
    transcript jsonb,
    call_result jsonb,
    created_at timestamptz DEFAULT now(),
    completed_at timestamptz,
    updated_at timestamptz DEFAULT now()
);

-- Add webhook events tracking table for VAPI
CREATE TABLE IF NOT EXISTS public.vapi_webhook_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id uuid REFERENCES public.voice_calls(id) ON DELETE CASCADE,
    vapi_call_id text,
    event_type text NOT NULL,
    event_data jsonb NOT NULL,
    processed boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_voice_calls_item_id ON public.voice_calls(item_id);
CREATE INDEX IF NOT EXISTS idx_voice_calls_vapi_call_id ON public.voice_calls(vapi_call_id);
CREATE INDEX IF NOT EXISTS idx_voice_calls_status ON public.voice_calls(call_status);
CREATE INDEX IF NOT EXISTS idx_voice_calls_created_at ON public.voice_calls(created_at);

CREATE INDEX IF NOT EXISTS idx_vapi_webhook_events_call_id ON public.vapi_webhook_events(call_id);
CREATE INDEX IF NOT EXISTS idx_vapi_webhook_events_vapi_call_id ON public.vapi_webhook_events(vapi_call_id);
CREATE INDEX IF NOT EXISTS idx_vapi_webhook_events_processed ON public.vapi_webhook_events(processed);
CREATE INDEX IF NOT EXISTS idx_vapi_webhook_events_created_at ON public.vapi_webhook_events(created_at);

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to voice_calls table
DROP TRIGGER IF EXISTS update_voice_calls_updated_at ON public.voice_calls;
CREATE TRIGGER update_voice_calls_updated_at
    BEFORE UPDATE ON public.voice_calls
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add some useful views for reporting
CREATE OR REPLACE VIEW public.voice_call_summary AS
SELECT 
    vc.id,
    vc.vapi_call_id,
    i.title as task_title,
    i.description as task_description,
    vc.phone_number,
    vc.recipient_name,
    vc.call_purpose,
    vc.call_status,
    vc.duration_seconds,
    vc.created_at as call_initiated_at,
    vc.completed_at as call_completed_at,
    CASE 
        WHEN vc.call_status = 'completed' AND vc.completed_at IS NOT NULL THEN 
            EXTRACT(EPOCH FROM (vc.completed_at - vc.created_at))::integer 
        ELSE NULL 
    END as actual_duration_seconds
FROM public.voice_calls vc
JOIN public.items i ON vc.item_id = i.id;

-- Grant appropriate permissions (adjust as needed for your security model)
-- These are basic permissions - customize based on your auth setup
GRANT SELECT, INSERT, UPDATE ON public.voice_calls TO anon;
GRANT SELECT, INSERT, UPDATE ON public.vapi_webhook_events TO anon;
GRANT SELECT ON public.voice_call_summary TO anon;

-- Add comments for documentation
COMMENT ON TABLE public.voice_calls IS 'Tracks VAPI voice calls initiated by the voice agent';
COMMENT ON TABLE public.vapi_webhook_events IS 'Stores webhook events received from VAPI for call tracking';
COMMENT ON VIEW public.voice_call_summary IS 'Summary view of voice calls with associated task information';

COMMENT ON COLUMN public.voice_calls.vapi_call_id IS 'Unique identifier from VAPI for the call';
COMMENT ON COLUMN public.voice_calls.call_status IS 'Current status of the call: initiated, ringing, answered, completed, failed';
COMMENT ON COLUMN public.voice_calls.transcript IS 'JSON array of conversation transcript from VAPI';
COMMENT ON COLUMN public.voice_calls.call_result IS 'JSON object containing call results and outcome data';
COMMENT ON COLUMN public.vapi_webhook_events.processed IS 'Whether this webhook event has been processed by the application';