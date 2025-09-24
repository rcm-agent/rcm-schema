# Debug Patterns

This directory contains documented issues, bugs, and their solutions specific to this repository.

## Structure

Each pattern is documented as a markdown file with:
- Problem description and symptoms
- Root cause analysis  
- Solution implemented
- Verification steps
- Tags for searchability

## Template

Use this template for new patterns:

```markdown
---
id: XXX
title: Issue Title
severity: critical|high|medium|low
language: python|javascript|typescript
category: bug|configuration|performance|security
---

# Issue Title

## Problem Statement
Clear description of the issue

## Root Cause
Technical explanation of why it occurred

## Solution
How it was fixed

## Tags
#component #error-type #solution-type
```

## Integration

All patterns are automatically indexed by the AI Mistakes RAG system for searchable knowledge base across all RCM services.

See also:
- Cross-cutting patterns: `~/rcm-shared-docs/docs/debug-patterns/`
- AI Mistakes Service: `~/ai-mistakes-service/`
