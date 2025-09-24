# RCM Schema Task Completion Checklist

## After Making Schema Changes

### 1. Update Models
- [ ] Update `models.py` or `models_v8.py` with new/changed tables
- [ ] Add appropriate SQLAlchemy relationships
- [ ] Include proper indexes and constraints

### 2. Update Pydantic Schemas
- [ ] Add request/response schemas in `schemas.py`
- [ ] Ensure validation rules match database constraints
- [ ] Add ConfigDict with from_attributes=True for ORM mode

### 3. Create Migration
```bash
alembic revision -m "Clear description of changes"
```
- [ ] Review generated migration file
- [ ] Add any special SQL (triggers, functions, RLS policies)
- [ ] Test both upgrade and downgrade functions

### 4. Update Documentation
- [ ] Update README.md if adding major features
- [ ] Update relevant guides in /docs:
  - `hybrid_rcm_db_guide_v8.md` for table documentation
  - `hybrid_rcm_schema_v8.sql` for complete SQL schema
  - Feature-specific guides (hierarchical_requirements_guide.md, etc.)
- [ ] Update CHANGELOG.md with version and changes

### 5. Test Changes
```bash
# Test migration up and down
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# Run schema tests
python test_rcm_schema.py
pytest
```

### 6. Update Dependent Services
- [ ] Check if change affects rcm-frontend, rcm-web-agent, etc.
- [ ] Coordinate deployment with infrastructure team
- [ ] Update service documentation if interfaces change

### 7. Pre-commit Checks
- [ ] All tests pass
- [ ] Migration runs cleanly
- [ ] No hardcoded values or credentials
- [ ] Code follows project conventions
- [ ] Documentation is updated

## For Major Schema Updates (like V8)
1. Create migration guide (V8_MIGRATION_GUIDE.md)
2. Write validation scripts (verify_v8_migration.sql)
3. Prepare rollback procedure (rollback_v8_migration.sh)
4. Update all backward compatibility views
5. Communicate breaking changes to all teams