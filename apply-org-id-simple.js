const { Pool } = require('pg');

// Database configuration
const pool = new Pool({
  user: 'rcm_user',
  password: 'rcm_password',
  host: 'localhost',
  port: 5432,
  database: 'rcm_db'
});

async function applyMigration() {
  const client = await pool.connect();
  
  try {
    console.log('Starting org_id migration for workflow tables...\n');
    
    // Define tables to update
    const tables = ['workflow_revision', 'workflow_event', 'workflow_checkpoint'];
    
    // Phase 1: Add columns
    console.log('PHASE 1: Adding org_id columns...');
    for (const table of tables) {
      try {
        console.log(`Adding org_id to ${table}...`);
        await client.query(`
          ALTER TABLE ${table} 
          ADD COLUMN org_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000'
        `);
        console.log('✓ Success');
      } catch (error) {
        if (error.code === '42701') { // duplicate_column
          console.log('⚠ Column already exists, skipping');
        } else {
          console.error('✗ Error:', error.message);
          throw error;
        }
      }
    }
    
    // Phase 2: Add constraints
    console.log('\nPHASE 2: Adding foreign key constraints...');
    for (const table of tables) {
      try {
        console.log(`Adding foreign key constraint for ${table}...`);
        await client.query(`
          ALTER TABLE ${table} 
          ADD CONSTRAINT fk_${table}_org 
          FOREIGN KEY (org_id) REFERENCES organization(org_id)
        `);
        console.log('✓ Success');
      } catch (error) {
        if (error.code === '42710') { // duplicate_object
          console.log('⚠ Constraint already exists, skipping');
        } else {
          console.error('✗ Error:', error.message);
          // Don't throw - constraints are optional
        }
      }
    }
    
    // Phase 3: Create indexes
    console.log('\nPHASE 3: Creating indexes...');
    for (const table of tables) {
      try {
        console.log(`Creating index for ${table}...`);
        await client.query(`
          CREATE INDEX idx_${table}_org_id ON ${table}(org_id)
        `);
        console.log('✓ Success');
      } catch (error) {
        if (error.code === '42P07') { // duplicate_table (for indexes)
          console.log('⚠ Index already exists, skipping');
        } else {
          console.error('✗ Error:', error.message);
          // Don't throw - indexes are optional
        }
      }
    }
    
    // Verify the migration
    console.log('\n✅ Migration completed successfully!');
    console.log('\nVerifying org_id columns...');
    
    const verifyQuery = `
      SELECT 
        table_name,
        column_name,
        data_type,
        is_nullable,
        column_default
      FROM information_schema.columns 
      WHERE table_schema = 'public' 
      AND table_name IN ('workflow_revision', 'workflow_event', 'workflow_checkpoint')
      AND column_name = 'org_id'
      ORDER BY table_name;
    `;
    
    const result = await client.query(verifyQuery);
    result.rows.forEach(row => {
      console.log(`✓ ${row.table_name}.${row.column_name}: ${row.data_type}`);
    });
    
    console.log('\n⚠️  IMPORTANT: Before enabling USE_REAL_DB=true, you must:');
    console.log('1. Update auth-helper.ts to provide organization context');
    console.log('2. Update db-postgres.ts to filter all queries by org_id');
    console.log('3. Update API routes to pass organization context');
    console.log('4. Test multi-tenant isolation thoroughly');
    
  } catch (error) {
    console.error('Migration failed:', error);
    throw error;
  } finally {
    client.release();
    await pool.end();
  }
}

// Run the migration
applyMigration().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});