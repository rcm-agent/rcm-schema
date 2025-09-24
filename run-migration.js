const { Client } = require('pg')
const fs = require('fs')

async function runMigration() {
  const connectionString = process.env.DATABASE_URL || 'postgresql://rcm_user:rcm_password@localhost:5432/rcm_db'
  const client = new Client({ connectionString })
  
  try {
    await client.connect()
    console.log('Connected to database')
    
    // Read the migration file
    const migration = fs.readFileSync('test-simple-migration.sql', 'utf8')
    
    // Split by statements (simple split by semicolon)
    const statements = migration
      .split(/;\s*$(?=[\s\S]*?(?:--|SELECT|CREATE|ALTER|DO|INSERT|UPDATE))/m)
      .filter(stmt => stmt.trim())
    
    for (const statement of statements) {
      const trimmed = statement.trim()
      if (trimmed && !trimmed.startsWith('--')) {
        try {
          console.log('\nExecuting:', trimmed.substring(0, 50) + '...')
          const result = await client.query(trimmed)
          if (result.rows && result.rows.length > 0) {
            console.table(result.rows)
          } else {
            console.log('✅ Success')
          }
        } catch (err) {
          console.error('❌ Error:', err.message)
        }
      }
    }
    
  } catch (error) {
    console.error('❌ Connection error:', error.message)
  } finally {
    await client.end()
  }
}

runMigration()