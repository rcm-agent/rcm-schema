const { Client } = require('pg')

// Simple script to check what's in the database
async function checkDatabase() {
  // Try to read DATABASE_URL from .env.local
  let connectionString = process.env.DATABASE_URL
  
  if (!connectionString) {
    // Read .env.local manually
    try {
      const fs = require('fs')
      const envContent = fs.readFileSync('.env.local', 'utf8')
      const dbUrlLine = envContent.split('\n').find(line => line.startsWith('DATABASE_URL='))
      if (dbUrlLine) {
        connectionString = dbUrlLine.split('=')[1].trim()
      }
    } catch (err) {
      console.log('Could not read .env.local')
    }
  }
  
  if (!connectionString) {
    connectionString = 'postgresql://rcm_user:rcm_password@localhost:5432/rcm_db'
  }
  
  console.log('Using connection string:', connectionString.replace(/:[^:@]+@/, ':****@'))
  
  const client = new Client({ connectionString })
  
  try {
    await client.connect()
    console.log('\n✅ Connected to database\n')
    
    // Get all tables
    const tablesResult = await client.query(`
      SELECT table_name 
      FROM information_schema.tables 
      WHERE table_schema = 'public' 
      AND table_type = 'BASE TABLE'
      ORDER BY table_name
    `)
    
    console.log('Tables in database:')
    tablesResult.rows.forEach(row => console.log('  -', row.table_name))
    
    // Check if user_workflow table exists and has data
    const hasWorkflowTable = tablesResult.rows.some(row => row.table_name === 'user_workflow')
    
    if (hasWorkflowTable) {
      console.log('\n✅ user_workflow table exists\n')
      
      const workflowsResult = await client.query(`
        SELECT * FROM user_workflow
        ORDER BY created_at DESC
      `)
      
      console.log('Workflows found:', workflowsResult.rowCount)
      
      if (workflowsResult.rowCount > 0) {
        console.log('\nWorkflow details:')
        workflowsResult.rows.forEach((row, idx) => {
          console.log(`\n${idx + 1}. ${row.name || 'Unnamed'}`)
          console.log('   ID:', row.workflow_id)
          console.log('   Status:', row.status || 'N/A')
          console.log('   Created:', row.created_at || 'N/A')
        })
      } else {
        console.log('  No workflows in the database yet.')
        console.log('  You can create sample data with: npm run db:seed')
      }
    } else {
      console.log('\n❌ user_workflow table does not exist')
      console.log('   Migrations may not have been run properly.')
    }
    
    // Check workflow_trace table
    const hasTraceTable = tablesResult.rows.some(row => row.table_name === 'workflow_trace')
    if (hasTraceTable) {
      const tracesResult = await client.query('SELECT COUNT(*) as count FROM workflow_trace')
      console.log('\nWorkflow runs (traces):', tracesResult.rows[0].count)
    }
    
  } catch (error) {
    console.error('\n❌ Error:', error.message)
    
    if (error.message.includes('database') && error.message.includes('does not exist')) {
      console.log('\nThe database may not exist. Create it with:')
      console.log('  createdb rcm_db')
    } else if (error.message.includes('password authentication failed')) {
      console.log('\nAuthentication failed. Check your credentials in .env.local')
    }
  } finally {
    await client.end()
  }
}

checkDatabase()