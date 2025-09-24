const { Client } = require('pg')

async function createDevUser() {
  const connectionString = process.env.DATABASE_URL || 'postgresql://rcm_user:rcm_password@localhost:5432/rcm_db'
  const client = new Client({ connectionString })
  
  try {
    await client.connect()
    console.log('Connected to database')
    
    // Create a dev user
    const result = await client.query(`
      INSERT INTO app_user (
        user_id,
        org_id,
        email,
        full_name,
        role,
        is_active
      ) VALUES (
        '11111111-1111-1111-1111-111111111111',
        '00000000-0000-0000-0000-000000000000',
        'dev@example.com',
        'Dev User',
        'org_admin',
        true
      )
      ON CONFLICT (user_id) DO UPDATE SET
        email = EXCLUDED.email,
        full_name = EXCLUDED.full_name
      RETURNING user_id, email
    `)
    
    console.log('✅ Dev user created/updated:', result.rows[0])
    
  } catch (error) {
    console.error('❌ Error:', error.message)
  } finally {
    await client.end()
  }
}

createDevUser()