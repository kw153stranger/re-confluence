-- Confluence AI 재구성 — M6 Postgres/pgvector 스키마 (구현설계 §12.2, §12.6)
-- 적용: psql "$DSN" -f migrations/001_init.sql

create extension if not exists vector;

-- 문서 메타 (raw 본문·첨부는 파일/오브젝트 스토리지, DB엔 경로·메타만) §12.6
create table if not exists documents (
    source_page_id text primary key,
    title          text,
    source_url     text,
    author         text,
    updated_at     text,
    raw_path       text
);

-- Analyze 결과
create table if not exists analyses (
    source_page_id text primary key references documents(source_page_id),
    business text, project text, system text,
    year int, month int,
    summary text,
    labels text[],
    duplicate_of text,
    confidence jsonb
);

-- Cluster 결과(정본/중복/관련)
create table if not exists cluster_members (
    source_page_id text primary key references documents(source_page_id),
    business text, year int,
    role text,                 -- canonical | duplicate | related
    similarity real
);

-- 전역 라벨 마스터 §6.4a
create table if not exists labels (
    id bigserial primary key,
    namespace text not null,
    canonical text not null,
    aliases text[] default '{}',
    status text default 'approved',   -- approved | candidate
    count int default 0,
    unique (namespace, canonical)
);

-- 검수 결정 §6.5
create table if not exists reviews (
    source_page_id text primary key references documents(source_page_id),
    status text default 'pending',    -- approved | rejected | pending
    overrides jsonb default '{}',
    reviewer text,
    decided_at timestamptz default now()
);

-- 파이프라인 실행(잡) 상태 §12.1
create table if not exists runs (
    id bigserial primary key,
    stage text not null,
    status text not null,             -- queued | running | done | failed
    detail text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- 임베딩 벡터 (ANN 검색) §12.2 — bge-m3 = 1024차원
create table if not exists doc_embeddings (
    source_page_id text primary key references documents(source_page_id),
    model text,
    dim int,
    content_hash text,
    business text,
    year int,
    title text,
    embedding vector(1024)
);

create index if not exists doc_embeddings_hnsw
    on doc_embeddings using hnsw (embedding vector_cosine_ops);
create index if not exists doc_embeddings_business on doc_embeddings (business);
create index if not exists doc_embeddings_year on doc_embeddings (year);
