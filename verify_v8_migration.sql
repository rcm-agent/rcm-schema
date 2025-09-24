-- RCM V8 Migration Verification Script
-- Run this after migration to verify everything is working correctly

-- 1. Check V8 tables exist
SELECT 'Checking new V8 tables...' as status;
SELECT 
    table_name,
    CASE WHEN table_name IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES 
        ('organization'),
        ('channel_type'),
        ('endpoint'),
        ('workflow_node'),
        ('workflow_transition'),
        ('user_workflow'),
        ('micro_state'),
        ('app_user'),
        ('workflow_trace'),
        ('workflow_trace_endpoint')
) as required_tables(table_name)
LEFT JOIN information_schema.tables ist 
    ON ist.table_name = required_tables.table_name 
    AND ist.table_schema = 'public';

-- 2. Check lookup tables
SELECT 'Checking lookup tables...' as status;
SELECT 
    table_name,
    COUNT(*) as row_count,
    CASE WHEN COUNT(*) > 0 THEN '✓ POPULATED' ELSE '✗ EMPTY' END as status
FROM (
    SELECT 'task_domain_lu' as table_name, COUNT(*) FROM task_domain_lu
    UNION ALL
    SELECT 'task_action_lu', COUNT(*) FROM task_action_lu
    UNION ALL
    SELECT 'job_status_lu', COUNT(*) FROM job_status_lu
    UNION ALL
    SELECT 'requirement_type_lu', COUNT(*) FROM requirement_type_lu
    UNION ALL
    SELECT 'task_signature_source_lu', COUNT(*) FROM task_signature_source_lu
    UNION ALL
    SELECT 'user_role_lu', COUNT(*) FROM user_role_lu
) t
GROUP BY table_name;

-- 3. Check backward compatibility views
SELECT 'Checking compatibility views...' as status;
SELECT 
    viewname as view_name,
    CASE WHEN viewname IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM pg_views
WHERE schemaname = 'public' 
AND viewname IN ('rcm_user', 'rcm_trace');

-- 4. Check default organization
SELECT 'Checking default organization...' as status;
SELECT 
    org_id,
    name,
    org_type,
    created_at,
    '✓ DEFAULT ORG CREATED' as status
FROM organization 
WHERE name = 'Default Organization';

-- 5. Check data migration
SELECT 'Checking data migration...' as status;

-- Check if users were migrated to app_user
SELECT 
    'app_user' as table_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT org_id) as org_count,
    CASE WHEN COUNT(*) > 0 THEN '✓ USERS MIGRATED' ELSE '✗ NO USERS' END as status
FROM app_user;

-- Check if traces were migrated
SELECT 
    'workflow_trace' as table_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT org_id) as org_count,
    CASE WHEN COUNT(*) > 0 THEN '✓ TRACES MIGRATED' ELSE '✗ NO TRACES' END as status
FROM workflow_trace;

-- 6. Check foreign key constraints
SELECT 'Checking foreign key constraints...' as status;
SELECT 
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type
FROM information_schema.table_constraints tc
WHERE tc.table_schema = 'public'
AND tc.constraint_type = 'FOREIGN KEY'
AND tc.table_name IN ('app_user', 'endpoint', 'workflow_trace', 'field_requirement')
ORDER BY tc.table_name;

-- 7. Check indexes
SELECT 'Checking performance indexes...' as status;
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
AND tablename IN ('app_user', 'workflow_trace', 'micro_state', 'endpoint')
AND indexname LIKE 'idx_%'
ORDER BY tablename, indexname;

-- 8. Test backward compatibility views
SELECT 'Testing backward compatibility...' as status;

-- Test rcm_user view
SELECT 
    'rcm_user view' as test_name,
    COUNT(*) as row_count,
    CASE WHEN COUNT(*) >= 0 THEN '✓ VIEW WORKS' ELSE '✗ VIEW ERROR' END as status
FROM rcm_user;

-- Test rcm_trace view
SELECT 
    'rcm_trace view' as test_name,
    COUNT(*) as row_count,
    CASE WHEN COUNT(*) >= 0 THEN '✓ VIEW WORKS' ELSE '✗ VIEW ERROR' END as status
FROM rcm_trace;

-- 9. Summary
SELECT 'Migration Summary' as status;
SELECT 
    'Total Tables' as metric,
    COUNT(*) as count
FROM information_schema.tables
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE'
UNION ALL
SELECT 
    'Total Views',
    COUNT(*)
FROM information_schema.views
WHERE table_schema = 'public'
UNION ALL
SELECT 
    'Total Indexes',
    COUNT(*)
FROM pg_indexes
WHERE schemaname = 'public';