#!/usr/bin/env python3
"""
Comprehensive database backup script for March Madness scoring fix.
Creates timestamped CSV backups of all tables with data integrity verification.
"""

import os
import sys
import csv
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from dotenv import load_dotenv
import logging

# Add parent directory to path to import db module
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'march_madness_backend'))
from db import get_db_connection

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Tables to backup in dependency order
BACKUP_TABLES = [
    'users',
    'games', 
    'picks',           # CRITICAL - contains points_awarded
    'leaderboard',     # CRITICAL - contains total_points
    'tiebreakers',
    'tiebreaker_picks'
]

# Critical columns for validation
CRITICAL_COLUMNS = {
    'users': ['id', 'username', 'full_name', 'email', 'make_picks', 'admin', 'created_at'],
    'games': ['id', 'home_team', 'away_team', 'spread', 'game_date', 'winning_team', 'created_at'],
    'picks': ['id', 'user_id', 'game_id', 'picked_team', 'points_awarded', 'lock', 'created_at'],
    'leaderboard': ['user_id', 'total_points', 'last_updated'],
    'tiebreakers': ['id', 'question', 'start_time', 'answer', 'is_active', 'created_at'],
    'tiebreaker_picks': ['id', 'user_id', 'tiebreaker_id', 'answer', 'points_awarded', 'created_at']
}

def create_backup_directory():
    """Create timestamped backup directory."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = os.path.join("/workspace/backups", timestamp)
    os.makedirs(backup_dir, exist_ok=True)
    logger.info(f"Created backup directory: {backup_dir}")
    return backup_dir

def get_table_schema(cursor, table_name):
    """Get table schema information."""
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = %s 
        ORDER BY ordinal_position
    """, (table_name,))
    return cursor.fetchall()

def calculate_file_checksum(filepath):
    """Calculate MD5 checksum of a file."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def backup_table_to_csv(cursor, table_name, backup_dir):
    """
    Export table to CSV with metadata tracking.
    Returns metadata dictionary.
    """
    logger.info(f"Backing up table: {table_name}")
    
    # Get table schema
    schema = get_table_schema(cursor, table_name)
    column_names = [col['column_name'] for col in schema]
    
    # Verify critical columns exist
    if table_name in CRITICAL_COLUMNS:
        missing_columns = set(CRITICAL_COLUMNS[table_name]) - set(column_names)
        if missing_columns:
            raise Exception(f"Missing critical columns in {table_name}: {missing_columns}")
    
    # Export data
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY 1")
    rows = cursor.fetchall()
    
    # Write to CSV
    csv_path = os.path.join(backup_dir, f"{table_name}.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        if rows:
            writer = csv.DictWriter(csvfile, fieldnames=column_names)
            writer.writeheader()
            for row in rows:
                # Convert datetime objects to strings
                clean_row = {}
                for key, value in row.items():
                    if isinstance(value, datetime):
                        clean_row[key] = value.isoformat()
                    else:
                        clean_row[key] = value
                writer.writerow(clean_row)
        else:
            # Empty table - just write headers
            writer = csv.DictWriter(csvfile, fieldnames=column_names)
            writer.writeheader()
    
    # Calculate metadata
    file_size = os.path.getsize(csv_path)
    checksum = calculate_file_checksum(csv_path)
    
    metadata = {
        'table': table_name,
        'rows': len(rows),
        'columns': column_names,
        'file_size': file_size,
        'checksum': checksum,
        'schema': [dict(col) for col in schema],
        'backup_time': datetime.now().isoformat()
    }
    
    logger.info(f"✅ {table_name}: {len(rows)} rows, {file_size} bytes")
    return metadata

def verify_backup_integrity(backup_dir, metadata):
    """Verify all CSV files are readable and contain expected data."""
    logger.info("Verifying backup integrity...")
    
    for table_meta in metadata['tables']:
        table_name = table_meta['table']
        csv_path = os.path.join(backup_dir, f"{table_name}.csv")
        
        # Check file exists
        if not os.path.exists(csv_path):
            raise Exception(f"Backup file missing: {csv_path}")
        
        # Verify file size
        actual_size = os.path.getsize(csv_path)
        if actual_size != table_meta['file_size']:
            raise Exception(f"File size mismatch for {table_name}: expected {table_meta['file_size']}, got {actual_size}")
        
        # Verify checksum
        actual_checksum = calculate_file_checksum(csv_path)
        if actual_checksum != table_meta['checksum']:
            raise Exception(f"Checksum mismatch for {table_name}")
        
        # Verify CSV is readable and has correct row count
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)
            # Subtract 1 for header row
            actual_rows = len(rows) - 1 if len(rows) > 0 else 0
            if actual_rows != table_meta['rows']:
                raise Exception(f"Row count mismatch for {table_name}: expected {table_meta['rows']}, got {actual_rows}")
        
        logger.info(f"✅ {table_name} verification passed")
    
    logger.info("🎉 All backup files verified successfully!")
    return True

def generate_backup_report(backup_dir, metadata):
    """Generate human-readable backup summary."""
    report_lines = [
        "=" * 60,
        "MARCH MADNESS DATABASE BACKUP REPORT",
        "=" * 60,
        f"Backup Time: {metadata['backup_time']}",
        f"Backup Directory: {backup_dir}",
        f"Database: {metadata['database_info']['database']}",
        "",
        "TABLE SUMMARY:",
        "-" * 40
    ]
    
    total_rows = 0
    total_size = 0
    
    for table_meta in metadata['tables']:
        total_rows += table_meta['rows']
        total_size += table_meta['file_size']
        
        report_lines.append(f"{table_meta['table']:<20} {table_meta['rows']:>8} rows  {table_meta['file_size']:>10} bytes")
    
    report_lines.extend([
        "-" * 40,
        f"{'TOTAL':<20} {total_rows:>8} rows  {total_size:>10} bytes",
        "",
        "CRITICAL DATA SUMMARY:",
        "-" * 40
    ])
    
    # Add critical data insights
    for table_meta in metadata['tables']:
        if table_meta['table'] == 'picks':
            report_lines.append(f"Game Picks: {table_meta['rows']} picks recorded")
        elif table_meta['table'] == 'leaderboard':
            report_lines.append(f"Leaderboard: {table_meta['rows']} users ranked")
        elif table_meta['table'] == 'users':
            report_lines.append(f"Users: {table_meta['rows']} registered users")
        elif table_meta['table'] == 'games':
            report_lines.append(f"Games: {table_meta['rows']} games in database")
    
    report_lines.extend([
        "",
        "BACKUP STATUS: ✅ COMPLETE AND VERIFIED",
        "=" * 60
    ])
    
    report_content = "\n".join(report_lines)
    
    # Write report to file
    report_path = os.path.join(backup_dir, "backup_summary.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    return report_content

def main():
    """Execute complete database backup process."""
    try:
        logger.info("🚀 Starting March Madness database backup...")
        
        # Load environment variables
        load_dotenv()
        
        # Create backup directory
        backup_dir = create_backup_directory()
        
        # Connect to database
        logger.info("Connecting to database...")
        conn = get_db_connection()
        
        # Get database info
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, version()")
            db_info = cur.fetchone()
            database_info = {
                'database': db_info[0],
                'user': db_info[1],
                'version': db_info[2]
            }
        
        # Backup all tables
        backup_metadata = {
            'backup_time': datetime.now().isoformat(),
            'database_info': database_info,
            'tables': []
        }
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for table_name in BACKUP_TABLES:
                table_meta = backup_table_to_csv(cur, table_name, backup_dir)
                backup_metadata['tables'].append(table_meta)
        
        # Save metadata
        metadata_path = os.path.join(backup_dir, "backup_metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(backup_metadata, f, indent=2, default=str)
        
        # Verify backup integrity
        verify_backup_integrity(backup_dir, backup_metadata)
        
        # Generate report
        report = generate_backup_report(backup_dir, backup_metadata)
        print("\n" + report)
        
        # Close connection
        conn.close()
        
        logger.info(f"🎉 Backup completed successfully! Files saved to: {backup_dir}")
        return backup_dir, backup_metadata
        
    except Exception as e:
        logger.error(f"❌ Backup failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()