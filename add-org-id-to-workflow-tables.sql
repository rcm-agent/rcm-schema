-- Migration to add org_id to workflow tables for multi-tenant support
-- CRITICAL: This migration must be run before enabling USE_REAL_DB=true
-- to prevent security vulnerabilities

-- PHASE 1: Add org_id columns
-- Add org_id to workflow_revision table
ALTER TABLE workflow_revision 
ADD COLUMN org_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000';

-- Add org_id to workflow_event table
ALTER TABLE workflow_event 
ADD COLUMN org_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000';

-- Add org_id to workflow_checkpoint table
ALTER TABLE workflow_checkpoint 
ADD COLUMN org_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000';

-- PHASE 2: Add foreign key constraints (only after columns exist)
-- Add foreign key constraint for workflow_revision
ALTER TABLE workflow_revision 
ADD CONSTRAINT fk_workflow_revision_org 
FOREIGN KEY (org_id) REFERENCES organization(org_id);

-- Add foreign key constraint for workflow_event
ALTER TABLE workflow_event 
ADD CONSTRAINT fk_workflow_event_org 
FOREIGN KEY (org_id) REFERENCES organization(org_id);

-- Add foreign key constraint for workflow_checkpoint
ALTER TABLE workflow_checkpoint 
ADD CONSTRAINT fk_workflow_checkpoint_org 
FOREIGN KEY (org_id) REFERENCES organization(org_id);

-- PHASE 3: Create indexes for performance
CREATE INDEX idx_workflow_revision_org_id ON workflow_revision(org_id);
CREATE INDEX idx_workflow_event_org_id ON workflow_event(org_id);
CREATE INDEX idx_workflow_checkpoint_org_id ON workflow_checkpoint(org_id);

-- PHASE 4: Remove the default constraint after migration (run this separately after verifying data)
-- ALTER TABLE workflow_revision ALTER COLUMN org_id DROP DEFAULT;
-- ALTER TABLE workflow_event ALTER COLUMN org_id DROP DEFAULT;
-- ALTER TABLE workflow_checkpoint ALTER COLUMN org_id DROP DEFAULT;