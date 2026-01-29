-- Enable pgvector extension
create extension if not exists vector;

-- Memories table
create table if not exists memories (
    id uuid primary key default gen_random_uuid(),
    content text not null,
    memory_type text not null default 'fact',
    importance float not null default 0.5,
    tags text[] default '{}',
    source text,
    related_to uuid[] default '{}',
    embedding vector(384),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- Index for vector similarity search
create index if not exists memories_embedding_idx
on memories using ivfflat (embedding vector_cosine_ops)
with (lists = 100);

-- Index for filtering
create index if not exists memories_type_idx on memories(memory_type);
create index if not exists memories_importance_idx on memories(importance);
create index if not exists memories_created_idx on memories(created_at desc);

-- Function to search memories by similarity
create or replace function match_memories(
    query_embedding vector(384),
    match_count int default 10,
    filter_type text default null,
    min_importance float default 0.0
)
returns table (
    id uuid,
    content text,
    memory_type text,
    importance float,
    tags text[],
    source text,
    created_at timestamptz,
    similarity float
)
language sql stable
as $$
    select
        m.id,
        m.content,
        m.memory_type,
        m.importance,
        m.tags,
        m.source,
        m.created_at,
        1 - (m.embedding <=> query_embedding) as similarity
    from memories m
    where
        (filter_type is null or m.memory_type = filter_type)
        and m.importance >= min_importance
    order by m.embedding <=> query_embedding
    limit match_count;
$$;

-- Updated_at trigger
create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger memories_updated_at
    before update on memories
    for each row
    execute function update_updated_at();
