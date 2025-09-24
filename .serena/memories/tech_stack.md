# RCM Schema Tech Stack

## Core Technologies
- **Database**: PostgreSQL 16+ (managed by infrastructure, not this repo)
- **Extensions**: 
  - pgcrypto (UUID generation)
  - uuid-ossp (UUID support)
  - pgvector 0.5.0+ (vector similarity search)
- **ORM**: SQLAlchemy 2.0+ with async support
- **Validation**: Pydantic 2.0+
- **Migrations**: Alembic
- **Language**: Python 3.9+

## Vector Embeddings
- **Text embeddings**: 768 dimensions (BGE model compatible)
- **Image embeddings**: 512 dimensions (SigLIP model compatible)
- **Indexing**: HNSW (Hierarchical Navigable Small World) for fast similarity search

## Development Dependencies
- pytest for testing
- python-dotenv for environment management
- asyncpg for async PostgreSQL connections

## JavaScript Dependencies
- @types/pg and pg for TypeScript/JavaScript PostgreSQL access (limited use)