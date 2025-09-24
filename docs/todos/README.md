# RCM Schema TODO Documentation

This directory contains documentation for architectural decisions, pending tasks, and implementation notes that require future action or consideration for the RCM Schema centralized database layer.

## Purpose
- Track database schema architectural decisions
- Document migration strategies and improvements
- Maintain a record of data model TODOs
- Provide context for future schema refactoring

## Categories

### 🏗️ Architectural Decisions
Documents that capture important database design choices and their rationale:
- _None currently documented_

### 🔄 Pending Refactors
Major schema refactoring efforts that have been identified:
- _None currently documented_

### 🐛 Known Issues
Documented schema issues that need addressing:
- _None currently documented_

### 💡 Future Enhancements
Ideas and proposals for schema improvements:
- _None currently documented_

### 📊 Migration Strategies
Database migration and versioning improvements:
- _None currently documented_

## How to Use This Directory

### Adding New TODOs
1. Create a new markdown file with a descriptive name in UPPER_SNAKE_CASE
2. Use the following template:

```markdown
# [Title]

## Date
YYYY-MM-DD

## Context
Brief description of the schema situation

## Problem/Opportunity
What database issue needs to be addressed

## Proposed Solution
How to address it (schema changes, migrations, etc.)

## Migration Impact
- Services affected
- Backward compatibility
- Data migration requirements

## Implementation Status
- [ ] Not started
- [ ] In progress  
- [ ] Completed

## References
- Related SQLAlchemy models
- Alembic migrations
- Issues/tickets
```

3. Update this README.md to include a link to your new document

### Review Schedule
- Schema design should be reviewed quarterly
- Migration strategies should be evaluated before major changes
- Performance optimizations should be continuous

## Quick Reference

### High Priority TODOs
1. _None currently identified_

### Schema Debt Items
1. _None currently identified_

### Migration Blockers
1. _None currently blocked_

## Schema-Specific Considerations

When documenting Schema TODOs, consider:
- Multi-tenancy implications (RLS policies)
- Backward compatibility requirements
- Service integration patterns
- Index optimization opportunities
- pgvector performance considerations
- Alembic migration ordering
- Pydantic validation schemas

## Contributing
When adding TODO documentation:
- Include migration scripts where applicable
- Document breaking changes clearly
- Consider performance implications
- Tag with appropriate priority level
- Include rollback procedures

## Archive
Completed or obsolete TODO documents should be moved to `./archive/` subdirectory with completion date noted.