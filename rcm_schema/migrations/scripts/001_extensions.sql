-- PostgreSQL Extensions required by RCM Schema
-- This script must be run with superuser privileges

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable vector similarity search
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Verify extensions are installed
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto') THEN
        RAISE EXCEPTION 'pgcrypto extension is required but not installed';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp') THEN
        RAISE EXCEPTION 'uuid-ossp extension is required but not installed';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgvector') THEN
        RAISE EXCEPTION 'pgvector extension is required but not installed';
    END IF;
    
    RAISE NOTICE 'All required extensions are installed';
END $$;