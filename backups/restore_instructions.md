# Database Restoration Instructions

## Overview
This document provides step-by-step instructions for restoring the March Madness database from CSV backups created before implementing scoring fixes.

## When to Use This Guide
- **Rollback Required**: If the scoring fix implementation causes issues
- **Data Corruption**: If database integrity is compromised
- **Testing**: To restore to a known good state for testing

## Backup Structure
```
/workspace/backups/YYYY-MM-DD_HH-MM-SS/
├── users.csv                  # User accounts and permissions
├── games.csv                  # Game data with spreads and winners
├── picks.csv                  # User picks with points_awarded (CRITICAL)
├── leaderboard.csv           # User total points (CRITICAL)
├── tiebreakers.csv           # Tiebreaker questions
├── tiebreaker_picks.csv      # Tiebreaker answers and points
├── backup_metadata.json     # Schema and verification data
├── backup_summary.txt        # Human-readable summary
└── verification_report.txt   # Integrity verification results
```

## Pre-Restoration Checklist
- [ ] **Stop the application** to prevent new data changes
- [ ] **Backup current state** (if needed for comparison)
- [ ] **Verify backup integrity** using verification script
- [ ] **Confirm restoration scope** (full vs partial restore)

## Full Database Restoration

### Step 1: Prepare Database Connection
```python
import psycopg2
from psycopg2.extras import RealDictCursor
import csv
import os

# Connect to database
conn = psycopg2.connect(DATABASE_URL)
```

### Step 2: Clear Existing Data (if full restore)
```sql
-- ⚠️  WARNING: This will delete all current data!
-- Execute in dependency order to avoid foreign key conflicts

TRUNCATE TABLE tiebreaker_picks CASCADE;
TRUNCATE TABLE tiebreakers CASCADE;
TRUNCATE TABLE leaderboard CASCADE;
TRUNCATE TABLE picks CASCADE;
TRUNCATE TABLE games CASCADE;
TRUNCATE TABLE users CASCADE;
```

### Step 3: Restore Tables (in dependency order)
```python
# Restore in this exact order to maintain referential integrity
RESTORE_ORDER = [
    'users',           # No dependencies
    'games',           # No dependencies  
    'tiebreakers',     # No dependencies
    'picks',           # Depends on users, games
    'leaderboard',     # Depends on users
    'tiebreaker_picks' # Depends on users, tiebreakers
]

for table_name in RESTORE_ORDER:
    restore_table_from_csv(conn, table_name, backup_dir)
```

### Step 4: Restore Individual Table
```python
def restore_table_from_csv(conn, table_name, backup_dir):
    """Restore a single table from CSV backup."""
    csv_path = os.path.join(backup_dir, f"{table_name}.csv")
    
    with conn.cursor() as cur:
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                # Build INSERT statement dynamically
                columns = list(row.keys())
                values = list(row.values())
                
                # Handle NULL values
                values = [None if v == '' else v for v in values]
                
                placeholders = ', '.join(['%s'] * len(values))
                columns_str = ', '.join(columns)
                
                insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                cur.execute(insert_sql, values)
        
        conn.commit()
        print(f"✅ Restored {table_name}")
```

## Partial Restoration (Points Only)

If you only need to restore scoring data without affecting users/games:

### Step 1: Backup Current Non-Critical Data
```sql
-- Save current game and user data
CREATE TEMP TABLE temp_games AS SELECT * FROM games;
CREATE TEMP TABLE temp_users AS SELECT * FROM users;
```

### Step 2: Restore Only Critical Tables
```python
CRITICAL_TABLES = ['picks', 'leaderboard']

for table_name in CRITICAL_TABLES:
    # Clear current data
    cursor.execute(f"TRUNCATE TABLE {table_name}")
    # Restore from backup
    restore_table_from_csv(conn, table_name, backup_dir)
```

## Post-Restoration Validation

### Step 1: Verify Data Integrity
```sql
-- Check row counts match backup
SELECT 'users' as table_name, COUNT(*) FROM users
UNION ALL
SELECT 'games', COUNT(*) FROM games  
UNION ALL
SELECT 'picks', COUNT(*) FROM picks
UNION ALL
SELECT 'leaderboard', COUNT(*) FROM leaderboard;

-- Verify referential integrity
SELECT COUNT(*) FROM picks p 
LEFT JOIN users u ON p.user_id = u.id 
WHERE u.id IS NULL; -- Should be 0

SELECT COUNT(*) FROM picks p 
LEFT JOIN games g ON p.game_id = g.id 
WHERE g.id IS NULL; -- Should be 0
```

### Step 2: Verify Critical Data
```sql
-- Check point distributions match backup
SELECT points_awarded, COUNT(*) 
FROM picks 
GROUP BY points_awarded 
ORDER BY points_awarded;

-- Verify leaderboard totals
SELECT user_id, total_points 
FROM leaderboard 
ORDER BY total_points DESC 
LIMIT 10;
```

### Step 3: Test Application Functionality
- [ ] **Login works** for test users
- [ ] **Leaderboard displays** correctly
- [ ] **User picks show** proper points
- [ ] **Admin functions** work normally

## Troubleshooting

### Foreign Key Constraint Errors
```sql
-- Temporarily disable foreign key checks (PostgreSQL)
SET session_replication_role = replica;
-- Restore data
SET session_replication_role = DEFAULT;
```

### Sequence Reset Issues
```sql
-- Reset sequences after restoration
SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));
SELECT setval('games_id_seq', (SELECT MAX(id) FROM games));
SELECT setval('picks_id_seq', (SELECT MAX(id) FROM picks));
SELECT setval('tiebreakers_id_seq', (SELECT MAX(id) FROM tiebreakers));
SELECT setval('tiebreaker_picks_id_seq', (SELECT MAX(id) FROM tiebreaker_picks));
```

### Data Type Conversion Issues
```python
# Handle common data type conversions
def convert_value(value, data_type):
    if value == '' or value is None:
        return None
    
    if data_type in ['integer', 'bigint']:
        return int(value)
    elif data_type in ['real', 'double precision', 'numeric']:
        return float(value)
    elif data_type == 'boolean':
        return value.lower() in ['true', 't', '1', 'yes']
    elif data_type.startswith('timestamp'):
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    else:
        return str(value)
```

## Emergency Contacts & Resources

### Key Files
- **Backup Script**: `/workspace/backups/backup_database.py`
- **Verification**: `/workspace/backups/verify_backup.py`
- **Database Schema**: `/workspace/march_madness_backend/db.py`

### Validation Queries
```sql
-- Critical validation queries for post-restore testing
SELECT COUNT(DISTINCT user_id) as active_users FROM picks;
SELECT COUNT(*) as total_games, COUNT(winning_team) as completed_games FROM games;
SELECT SUM(points_awarded) as total_points_awarded FROM picks;
SELECT COUNT(*) as users_on_leaderboard FROM leaderboard WHERE total_points > 0;
```

## Success Criteria
- [ ] All table row counts match backup metadata
- [ ] No referential integrity violations
- [ ] Application loads and functions normally
- [ ] Leaderboard displays correctly
- [ ] User point totals match expectations
- [ ] Admin functions work properly

## Final Notes
- **Always test restoration** in a development environment first
- **Document any issues** encountered during restoration
- **Keep multiple backup versions** for different restore points
- **Verify application functionality** thoroughly before going live

---
**Last Updated**: Generated automatically with backup creation
**Backup Location**: Check backup_metadata.json for specific details