const { Pool } = require('pg');
const fs = require('fs');
const path = require('path');

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
    console.log('Starting org_id migration for workflow tables...');
    
    // Check if tables exist
    const checkTablesQuery = `
      SELECT table_name 
      FROM information_schema.tables 
      WHERE table_schema = 'public' 
      AND table_name IN ('workflow_revision', 'workflow_event', 'workflow_checkpoint')
      ORDER BY table_name;
    `;
    
    const tablesResult = await client.query(checkTablesQuery);
    console.log('Found tables:', tablesResult.rows.map(r => r.table_name));
    
    // Check if org_id columns already exist
    const checkColumnsQuery = `
      SELECT table_name, column_name 
      FROM information_schema.columns 
      WHERE table_schema = 'public' 
      AND table_name IN ('workflow_revision', 'workflow_event', 'workflow_checkpoint')
      AND column_name = 'org_id'
      ORDER BY table_name;
    `;
    
    const columnsResult = await client.query(checkColumnsQuery);
    const existingColumns = columnsResult.rows.map(r => r.table_name);
    
    if (existingColumns.length > 0) {
      console.log('WARNING: org_id column already exists in:', existingColumns);
      console.log('Skipping migration for tables that already have org_id');
    }
    
    // Read migration SQL
    const migrationSQL = fs.readFileSync(
      path.join(__dirname, 'add-org-id-to-workflow-tables.sql'), 
      'utf8'
    );
    
    // Split into individual statements and group by phase
    const allStatements = migrationSQL
      .split(';')
      .map(s => s.trim())
      .filter(s => s.length > 0 && !s.startsWith('--'));
    
    console.log(`Found ${allStatements.length} total statements`);
    
    // Execute statements in phases to ensure proper order
    console.log('\n📋 Executing migration in phases...\n');
    
    // Phase 1: Add columns
    console.log('PHASE 1: Adding org_id columns...');
    const columnStatements = allStatements.filter(s => 
      s.includes('ADD COLUMN org_id')
    );
    console.log(`Found ${columnStatements.length} column statements`);
    
    for (const statement of columnStatements) {
      const tableMatch = statement.match(/ALTER TABLE (\w+)/);
      const tableName = tableMatch ? tableMatch[1] : 'unknown';
      
      // Skip if column already exists
      if (existingColumns.includes(tableName)) {
        console.log(`⚠ Skipping ${tableName} - org_id column already exists`);
        continue;
      }
      
      try {
        console.log(`Executing: Add org_id to ${tableName}...`);
        await client.query(statement);
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
    const constraintStatements = allStatements.filter(s => 
      s.includes('ADD CONSTRAINT')
    );
    
    for (const statement of constraintStatements) {
      try {
        const constraintMatch = statement.match(/ADD CONSTRAINT (\w+)/);
        const constraintName = constraintMatch ? constraintMatch[1] : 'unknown';
        console.log(`Executing: Add constraint ${constraintName}...`);
        await client.query(statement);
        console.log('✓ Success');
      } catch (error) {
        if (error.code === '42710') { // duplicate_object
          console.log('⚠ Constraint already exists, skipping');
        } else {
          console.error('✗ Error:', error.message);
          throw error;
        }
      }
    }
    
    // Phase 3: Create indexes
    console.log('\nPHASE 3: Creating indexes...');
    const indexStatements = allStatements.filter(s => 
      s.includes('CREATE INDEX')
    );
    
    for (const statement of indexStatements) {
      try {
        const indexMatch = statement.match(/CREATE INDEX (\w+)/);
        const indexName = indexMatch ? indexMatch[1] : 'unknown';
        console.log(`Executing: Create index ${indexName}...`);
        await client.query(statement);
        console.log('✓ Success');
      } catch (error) {
        if (error.code === '42P07') { // duplicate_table (for indexes)
          console.log('⚠ Index already exists, skipping');
        } else {
          console.error('✗ Error:', error.message);
          throw error;
        }
      }
    }
    
    // Verify the migration
    console.log('\nVerifying migration...');
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
    
    const verifyResult = await client.query(verifyQuery);
    console.log('\norg_id columns added:');
    verifyResult.rows.forEach(row => {
      console.log(`- ${row.table_name}.${row.column_name}: ${row.data_type} (nullable: ${row.is_nullable}, default: ${row.column_default})`);
    });
    
    // Update existing records to use the default organization
    console.log('\nUpdating existing records with default organization...');
    const tables = ['workflow_revision', 'workflow_event', 'workflow_checkpoint'];
    
    for (const table of tables) {
      if (!existingColumns.includes(table)) {
        const updateQuery = `
          UPDATE ${table} 
          SET org_id = '00000000-0000-0000-0000-000000000000'
          WHERE org_id = '00000000-0000-0000-0000-000000000000';
        `;
        const result = await client.query(updateQuery);
        console.log(`✓ Updated ${result.rowCount} rows in ${table}`);
      }
    }
    
    console.log('\n✅ Migration completed successfully!');
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