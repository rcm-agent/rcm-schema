# RCM Schema Project Overview

## Purpose
RCM Schema is the centralized database schema management repository for the Hybrid RCM (Revenue Cycle Management) platform. It serves as the single source of truth for the database schema shared across all RCM services.

## Core Features
- **Multi-tenant architecture** with organization-based data isolation
- **Graph-based workflow system** using DAG (Directed Acyclic Graph) for flexible workflow execution
- **ML-powered state management** with 768D vector embeddings for semantic search
- **PostgreSQL 16+** with pgvector extension for vector similarity search
- **SQLAlchemy 2.0+ ORM** with async support
- **Pydantic 2.0+ schemas** for data validation
- **Alembic migrations** for version-controlled schema evolution

## V8 Migration Status
The schema has been recently upgraded to V8 (as of August 2025) introducing:
- Multi-tenancy with Row Level Security (RLS)
- Graph workflows replacing linear task sequences
- Lookup tables replacing PostgreSQL ENUMs for runtime flexibility
- Channel/endpoint abstraction for flexible portal configuration
- Backward compatibility views for legacy code

## Key Services Using This Schema
- **rcm-frontend**: User interface for managing workflows
- **rcm-web-agent**: Browser automation with AI-powered state memory
- **rcm-memory**: Semantic memory and embedding management
- **rcm-orchestrator**: Workflow coordination and batch processing