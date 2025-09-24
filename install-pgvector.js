const { Client } = require('pg')

async function installPgVector() {
  const connectionString = process.env.DATABASE_URL || 'postgresql://rcm_user:rcm_password@localhost:5432/rcm_db'
  const client = new Client({ connectionString })
  
  try {
    await client.connect()
    console.log('Connected to database')
    
    // Create pgvector extension
    try {
      await client.query('CREATE EXTENSION IF NOT EXISTS pgvector')
      console.log('✅ pgvector extension created successfully')
    } catch (err) {
      console.error('❌ Error creating pgvector extension:', err.message)
      console.log('\nYou may need to run this as superuser:')
      console.log('psql -U postgres -d rcm_db -c "CREATE EXTENSION pgvector;"')
    }
    
  } catch (error) {
    console.error('❌ Connection error:', error.message)
  } finally {
    await client.end()
  }
}

installPgVector()