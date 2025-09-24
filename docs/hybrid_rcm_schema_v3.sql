-- Hybrid RCM Platform – Database Schema v3 (full, merged)
-- NOTE: run inside PostgreSQL 16 with pgvector extension
-- 
-- ⚠️ DEPRECATED: This is the V3 schema. 
-- For the current V8 schema with multi-tenancy and graph workflows, 
-- see hybrid_rcm_schema_v8.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

------------------------------------------------------------------
-- 0.  Core reference tables
------------------------------------------------------------------

-- 0.1  Organizations
CREATE TABLE organization (
  org_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_type     TEXT NOT NULL CHECK (org_type IN ('hospital','billing_firm','credentialer')),
  name         TEXT NOT NULL UNIQUE,
  email_domain TEXT UNIQUE,
  created_at   TIMESTAMPTZ DEFAULT now()
);

-- 0.2  Portal catalogue
CREATE TABLE portal_type (
  portal_type_id SERIAL PRIMARY KEY,
  code           TEXT UNIQUE,
  name           TEXT NOT NULL,
  base_url       TEXT NOT NULL,
  endpoint_kind  TEXT NOT NULL CHECK (endpoint_kind IN ('payer','provider'))
);

-- 0.3  Integration endpoints
CREATE TABLE integration_endpoint (
  portal_id      SERIAL PRIMARY KEY,
  org_id         UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
  name           TEXT NOT NULL,
  portal_type_id INT  NOT NULL REFERENCES portal_type(portal_type_id),
  base_url       TEXT,
  config         JSONB DEFAULT '{}'::jsonb,
  created_at     TIMESTAMP DEFAULT now(),
  UNIQUE (org_id, name),
  UNIQUE (org_id, portal_type_id)
);

------------------------------------------------------------------
-- 1.  Task types and enums
------------------------------------------------------------------
CREATE TYPE task_domain AS ENUM ('eligibility','claim','prior_auth');
CREATE TYPE task_action AS ENUM ('status_check','submit','denial_follow_up');
CREATE TYPE task_signature_source AS ENUM ('human','ai');

-- 1.1  Task types (workflow templates)
CREATE TABLE task_type (
  task_type_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  domain       task_domain NOT NULL,
  action       task_action NOT NULL,
  display_name TEXT NOT NULL,
  description  TEXT,
  created_at   TIMESTAMPTZ DEFAULT now()
);

-- 1.2  Field requirements
CREATE TABLE field_requirement (
  requirement_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_type_id     UUID NOT NULL REFERENCES task_type(task_type_id),
  portal_id        INT REFERENCES integration_endpoint(portal_id),
  required_fields  JSONB NOT NULL DEFAULT '[]'::jsonb,
  optional_fields  JSONB NOT NULL DEFAULT '[]'::jsonb,
  field_metadata   JSONB NOT NULL DEFAULT '{}'::jsonb,
  version          INT NOT NULL DEFAULT 1,
  active           BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ DEFAULT now(),
  updated_at       TIMESTAMPTZ
);

------------------------------------------------------------------
-- 2.  Batch ingress
------------------------------------------------------------------
CREATE TABLE batch_job (
  batch_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
  portal_id    INT  NOT NULL REFERENCES integration_endpoint(portal_id) ON DELETE CASCADE,
  workflow_type TEXT NOT NULL CHECK (workflow_type IN ('eligibility','claim_status','prior_auth')),
  status        TEXT NOT NULL CHECK (status IN ('queued','processing','success','error')),
  created_at    TIMESTAMP DEFAULT now(),
  completed_at  TIMESTAMP,
  result_url    TEXT
);
CREATE INDEX idx_batch_status ON batch_job (status);

CREATE TABLE batch_row (
  row_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id       UUID NOT NULL REFERENCES batch_job(batch_id) ON DELETE CASCADE,
  row_idx        INT  NOT NULL,
  task_signature UUID,
  trace_id       UUID,
  status         TEXT NOT NULL CHECK (status IN ('queued','processing','success','error')),
  error_code     TEXT,
  error_msg      TEXT,
  created_at     TIMESTAMP DEFAULT now(),
  updated_at     TIMESTAMP
);
CREATE INDEX idx_batch_row_batch  ON batch_row (batch_id);
CREATE INDEX idx_batch_row_status ON batch_row (status);

------------------------------------------------------------------
-- 3.  Web‑agent state memory
------------------------------------------------------------------
CREATE TABLE rcm_state (
  state_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portal_id      INT  NOT NULL REFERENCES integration_endpoint(portal_id) ON DELETE CASCADE,
  text_emb       VECTOR(768) NOT NULL,
  image_emb      VECTOR(512) NOT NULL,
  semantic_spec  JSONB NOT NULL,
  action         JSONB NOT NULL,
  success_ema    FLOAT NOT NULL DEFAULT 1.0,
  page_caption   TEXT,
  action_caption TEXT,
  caption_conf   NUMERIC(3,2),
  macro_state_id UUID,
  is_retired     BOOLEAN NOT NULL DEFAULT FALSE,
  alias_state_id UUID REFERENCES rcm_state(state_id)
);

------------------------------------------------------------------
-- 4.  Macro state
------------------------------------------------------------------
CREATE TABLE macro_state (
  macro_state_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portal_id         INT REFERENCES integration_endpoint(portal_id) ON DELETE CASCADE,
  canonical_caption TEXT,
  description       TEXT,
  sample_state_id   UUID REFERENCES rcm_state(state_id)
);

------------------------------------------------------------------
-- 5.  Task signatures (workflow execution patterns)
------------------------------------------------------------------
CREATE TABLE task_signature (
  signature_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portal_id        INT REFERENCES integration_endpoint(portal_id),
  portal_type_id   INT REFERENCES portal_type(portal_type_id),
  domain           task_domain NOT NULL,
  action           task_action NOT NULL,
  source           task_signature_source NOT NULL,
  text_emb         VECTOR(768),
  image_emb        VECTOR(512),
  sample_trace_id  UUID,
  alias_of         UUID REFERENCES task_signature(signature_id),
  composed         BOOLEAN DEFAULT FALSE,
  updated_at       TIMESTAMPTZ DEFAULT now(),
  UNIQUE (portal_id, domain, action)      WHERE portal_id IS NOT NULL,
  UNIQUE (portal_type_id, domain, action) WHERE portal_type_id IS NOT NULL,
  CHECK ( (portal_id IS NOT NULL) <> (portal_type_id IS NOT NULL) )
);

------------------------------------------------------------------
-- 6.  rcm_trace (execution logs)
------------------------------------------------------------------
CREATE TABLE rcm_trace (
  trace_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portal_id      INT  NOT NULL REFERENCES integration_endpoint(portal_id) ON DELETE CASCADE,
  org_id         UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
  workflow_type  TEXT NOT NULL,
  task_signature UUID REFERENCES task_signature(signature_id),
  prompt_version VARCHAR(20),
  used_fallback  BOOLEAN DEFAULT FALSE,
  fallback_model TEXT,
  trace          JSONB NOT NULL,
  duration_ms    INT,
  success        BOOL,
  created_at     TIMESTAMP DEFAULT now()
);

------------------------------------------------------------------
-- 7.  Transition graph
------------------------------------------------------------------
CREATE TABLE rcm_transition (
  from_state     UUID REFERENCES rcm_state(state_id) ON DELETE CASCADE,
  to_state       UUID REFERENCES rcm_state(state_id) ON DELETE CASCADE,
  action_caption TEXT,
  freq           INT NOT NULL DEFAULT 1 CHECK (freq >= 1),
  PRIMARY KEY (from_state, to_state, action_caption)
);

------------------------------------------------------------------
-- 8.  Users
------------------------------------------------------------------
CREATE TABLE app_user (
  user_id      UUID PRIMARY KEY,
  org_id       UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
  email        TEXT NOT NULL UNIQUE,
  full_name    TEXT,
  role         TEXT NOT NULL CHECK (role IN ('org_admin','firm_user','hospital_user','sys_admin')),
  created_at   TIMESTAMPTZ DEFAULT now()
);

------------------------------------------------------------------
-- 9.  Indexes for performance
------------------------------------------------------------------

-- Vector similarity search indexes
CREATE INDEX idx_rcm_state_text_emb ON rcm_state USING ivfflat (text_emb vector_l2_ops);
CREATE INDEX idx_rcm_state_image_emb ON rcm_state USING ivfflat (image_emb vector_l2_ops);
CREATE INDEX idx_task_signature_text_emb ON task_signature USING ivfflat (text_emb vector_l2_ops);
CREATE INDEX idx_task_signature_image_emb ON task_signature USING ivfflat (image_emb vector_l2_ops);

-- Additional performance indexes
CREATE INDEX idx_rcm_trace_portal_workflow ON rcm_trace (portal_id, workflow_type, created_at DESC);
CREATE INDEX idx_rcm_state_portal_active ON rcm_state (portal_id, is_retired);