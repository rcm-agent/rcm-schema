const { Client } = require('pg')

async function applyMigration() {
  const connectionString = process.env.DATABASE_URL || 'postgresql://rcm_user:rcm_password@localhost:5432/rcm_db'
  const client = new Client({ connectionString })
  
  try {
    await client.connect()
    console.log('Connected to database\n')
    
    // 1. Check current tables
    console.log('=== Current Tables ===')
    const tablesResult = await client.query(`
      SELECT table_name 
      FROM information_schema.tables 
      WHERE table_schema = 'public' 
      ORDER BY table_name
    `)
    tablesResult.rows.forEach(row => console.log(' -', row.table_name))
    
    // 2. Create organization table
    console.log('\n=== Creating organization table ===')
    try {
      await client.query(`
        CREATE TABLE IF NOT EXISTS organization (
          org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_type TEXT NOT NULL CHECK (org_type IN ('hospital','billing_firm','credentialer')),
          name TEXT NOT NULL UNIQUE,
          email_domain TEXT UNIQUE,
          created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
      `)
      console.log('✅ Organization table created')
    } catch (err) {
      console.error('❌ Error:', err.message)
    }
    
    // 3. Create app_user table
    console.log('\n=== Creating app_user table ===')
    try {
      await client.query(`
        CREATE TABLE IF NOT EXISTS app_user (
          user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id UUID REFERENCES organization(org_id),
          email TEXT NOT NULL UNIQUE,
          full_name TEXT,
          role TEXT NOT NULL,
          is_active BOOLEAN NOT NULL DEFAULT true,
          api_key_ssm_parameter_name VARCHAR(512),
          last_login_at TIMESTAMP WITH TIME ZONE,
          created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
          updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
        )
      `)
      console.log('✅ App_user table created')
    } catch (err) {
      console.error('❌ Error:', err.message)
    }
    
    // 4. Insert default organization
    console.log('\n=== Creating default organization ===')
    try {
      await client.query(`
        INSERT INTO organization (org_id, org_type, name, email_domain)
        VALUES ('00000000-0000-0000-0000-000000000000', 'hospital', 'Default Organization', 'default.com')
        ON CONFLICT (name) DO NOTHING
      `)
      console.log('✅ Default organization created')
    } catch (err) {
      console.error('❌ Error:', err.message)
    }
    
    // 5. Add columns to user_workflow
    console.log('\n=== Updating user_workflow table ===')
    
    // Check if status column exists
    const statusCol = await client.query(`
      SELECT column_name 
      FROM information_schema.columns 
      WHERE table_name='user_workflow' AND column_name='status'
    `)
    
    if (statusCol.rowCount === 0) {
      try {
        await client.query(`ALTER TABLE user_workflow ADD COLUMN status VARCHAR(50) DEFAULT 'active'`)
        console.log('✅ Added status column')
      } catch (err) {
        console.error('❌ Error adding status:', err.message)
      }
    }
    
    // Check if org_id column exists
    const orgIdCol = await client.query(`
      SELECT column_name 
      FROM information_schema.columns 
      WHERE table_name='user_workflow' AND column_name='org_id'
    `)
    
    if (orgIdCol.rowCount === 0) {
      try {
        await client.query(`ALTER TABLE user_workflow ADD COLUMN org_id UUID`)
        await client.query(`UPDATE user_workflow SET org_id = '00000000-0000-0000-0000-000000000000' WHERE org_id IS NULL`)
        await client.query(`ALTER TABLE user_workflow ALTER COLUMN org_id SET NOT NULL`)
        await client.query(`ALTER TABLE user_workflow ADD CONSTRAINT fk_user_workflow_org FOREIGN KEY (org_id) REFERENCES organization(org_id)`)
        console.log('✅ Added org_id column')
      } catch (err) {
        console.error('❌ Error adding org_id:', err.message)
      }
    }
    
    // 6. Create workflow_trace table
    console.log('\n=== Creating workflow_trace table ===')
    try {
      await client.query(`
        CREATE TABLE IF NOT EXISTS workflow_trace (
          trace_id BIGSERIAL PRIMARY KEY,
          batch_job_item_id UUID,
          org_id UUID NOT NULL REFERENCES organization(org_id),
          workflow_id UUID REFERENCES user_workflow(workflow_id),
          action_type TEXT,
          action_detail JSONB,
          success BOOLEAN DEFAULT false,
          duration_ms INTEGER,
          error_detail JSONB,
          llm_prompt TEXT,
          llm_response TEXT,
          llm_model VARCHAR(100),
          llm_tokens_used INTEGER,
          status VARCHAR(50) NOT NULL DEFAULT 'pending',
          started_by UUID,
          completed_at TIMESTAMP WITH TIME ZONE,
          node_count INTEGER DEFAULT 0,
          completed_node_count INTEGER DEFAULT 0,
          execution_time_ms BIGINT,
          error_message TEXT,
          run_metadata JSONB DEFAULT '{}',
          tier SMALLINT,
          tier_reason TEXT,
          created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
          user_id UUID,
          session_id UUID,
          CONSTRAINT workflow_trace_status_check CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout'))
        )
      `)
      console.log('✅ Workflow_trace table created')
    } catch (err) {
      console.error('❌ Error:', err.message)
    }
    
    // 7. Create workflow_trace_screenshot table
    console.log('\n=== Creating workflow_trace_screenshot table ===')
    try {
      await client.query(`
        CREATE TABLE IF NOT EXISTS workflow_trace_screenshot (
          screenshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          trace_id BIGINT NOT NULL REFERENCES workflow_trace(trace_id) ON DELETE CASCADE,
          org_id UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
          node_id INTEGER NOT NULL,
          node_name VARCHAR(255) NOT NULL,
          step_index INTEGER NOT NULL,
          screenshot_url TEXT NOT NULL,
          thumbnail_url TEXT,
          action_description TEXT NOT NULL,
          element_selector TEXT,
          screenshot_metadata JSONB DEFAULT '{}',
          created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
      `)
      console.log('✅ Workflow_trace_screenshot table created')
    } catch (err) {
      console.error('❌ Error:', err.message)
    }
    
    // 8. Create indexes
    console.log('\n=== Creating indexes ===')
    const indexes = [
      'CREATE INDEX IF NOT EXISTS idx_workflow_trace_started_by ON workflow_trace(started_by)',
      'CREATE INDEX IF NOT EXISTS idx_workflow_trace_status_org ON workflow_trace(org_id, status)',
      'CREATE INDEX IF NOT EXISTS idx_trace_screenshots ON workflow_trace_screenshot(trace_id, step_index)',
      'CREATE INDEX IF NOT EXISTS idx_screenshot_org ON workflow_trace_screenshot(org_id)',
      'CREATE INDEX IF NOT EXISTS idx_screenshot_created ON workflow_trace_screenshot(created_at)'
    ]
    
    for (const idx of indexes) {
      try {
        await client.query(idx)
        console.log('✅', idx.match(/idx_\w+/)[0])
      } catch (err) {
        console.error('❌ Error creating index:', err.message)
      }
    }
    
    // 9. Check final state
    console.log('\n=== Final Tables ===')
    const finalTables = await client.query(`
      SELECT table_name 
      FROM information_schema.tables 
      WHERE table_schema = 'public' 
      ORDER BY table_name
    `)
    finalTables.rows.forEach(row => console.log(' -', row.table_name))
    
    // 10. Check workflows again
    console.log('\n=== Workflows in Database ===')
    const workflows = await client.query(`
      SELECT w.workflow_id, w.name, w.status, o.name as org_name
      FROM user_workflow w
      LEFT JOIN organization o ON w.org_id = o.org_id
      ORDER BY w.created_at DESC
    `)
    
    if (workflows.rowCount > 0) {
      workflows.rows.forEach((row, idx) => {
        console.log(`${idx + 1}. ${row.name}`)
        console.log('   ID:', row.workflow_id)
        console.log('   Status:', row.status)
        console.log('   Organization:', row.org_name || 'No org')
      })
    }
    
  } catch (error) {
    console.error('❌ Connection error:', error.message)
  } finally {
    await client.end()
  }
}

applyMigration()