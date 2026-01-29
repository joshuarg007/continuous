-- Schema v2: Additional fields for source tracking, confidence, and model migration
-- Run this against your existing Supabase database

-- Source tracking: where did this memory come from?
ALTER TABLE memories ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'inferred';
-- Values: 'user_stated', 'inferred', 'file', 'corrected', 'auto_extracted'

-- Confidence score: how certain are we?
ALTER TABLE memories ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT 1.0;
-- 1.0 = certain, 0.5 = moderate, 0.0 = uncertain

-- Token count for context budget management
ALTER TABLE memories ADD COLUMN IF NOT EXISTS token_count INT;

-- Embedding model tracking for migration
ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding_model TEXT DEFAULT 'all-MiniLM-L6-v2';

-- Verification tracking
ALTER TABLE memories ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ;
ALTER TABLE memories ADD COLUMN IF NOT EXISTS verification_count INT DEFAULT 0;

-- Version history (soft reference, not FK to avoid complexity)
ALTER TABLE memories ADD COLUMN IF NOT EXISTS previous_version_id UUID;
ALTER TABLE memories ADD COLUMN IF NOT EXISTS superseded_by_id UUID;

-- Project field (denormalized for fast filtering)
ALTER TABLE memories ADD COLUMN IF NOT EXISTS project TEXT;

-- Create index for project queries
CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project);
CREATE INDEX IF NOT EXISTS idx_memories_source_type ON memories(source_type);
CREATE INDEX IF NOT EXISTS idx_memories_confidence ON memories(confidence);

-- Update match_memories function to support new fields
CREATE OR REPLACE FUNCTION match_memories(
  query_embedding vector(384),
  match_count int DEFAULT 10,
  filter_type text DEFAULT NULL,
  min_importance float DEFAULT 0.0,
  filter_project text DEFAULT NULL,
  min_confidence float DEFAULT 0.0
)
RETURNS TABLE (
  id uuid,
  content text,
  memory_type text,
  importance float,
  tags text[],
  source text,
  related_to text[],
  created_at timestamptz,
  updated_at timestamptz,
  similarity float,
  source_type text,
  confidence float,
  project text
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id,
    m.content,
    m.memory_type,
    m.importance,
    m.tags,
    m.source,
    m.related_to,
    m.created_at,
    m.updated_at,
    1 - (m.embedding <=> query_embedding) as similarity,
    m.source_type,
    m.confidence,
    m.project
  FROM memories m
  WHERE m.importance >= min_importance
    AND m.confidence >= min_confidence
    AND (filter_type IS NULL OR m.memory_type = filter_type)
    AND (filter_project IS NULL OR m.project = filter_project)
  ORDER BY m.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
