#!/usr/bin/env python3
"""
Backup verification script for March Madness database backups.
Validates backup integrity and provides detailed analysis.
"""

import os
import sys
import csv
import json
import hashlib
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def calculate_file_checksum(filepath):
    """Calculate MD5 checksum of a file."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def verify_backup_directory(backup_dir):
    """Verify backup directory structure and files."""
    logger.info(f"Verifying backup directory: {backup_dir}")
    
    if not os.path.exists(backup_dir):
        raise Exception(f"Backup directory does not exist: {backup_dir}")
    
    # Check for metadata file
    metadata_path = os.path.join(backup_dir, "backup_metadata.json")
    if not os.path.exists(metadata_path):
        raise Exception(f"Backup metadata file missing: {metadata_path}")
    
    # Load and validate metadata
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    required_keys = ['backup_time', 'database_info', 'tables']
    for key in required_keys:
        if key not in metadata:
            raise Exception(f"Missing key in metadata: {key}")
    
    logger.info("✅ Backup directory structure valid")
    return metadata

def verify_table_backup(backup_dir, table_meta):
    """Verify individual table backup."""
    table_name = table_meta['table']
    csv_path = os.path.join(backup_dir, f"{table_name}.csv")
    
    logger.info(f"Verifying {table_name}...")
    
    # Check file exists
    if not os.path.exists(csv_path):
        raise Exception(f"CSV file missing: {csv_path}")
    
    # Verify file size
    actual_size = os.path.getsize(csv_path)
    expected_size = table_meta['file_size']
    if actual_size != expected_size:
        raise Exception(f"File size mismatch for {table_name}: expected {expected_size}, got {actual_size}")
    
    # Verify checksum
    actual_checksum = calculate_file_checksum(csv_path)
    expected_checksum = table_meta['checksum']
    if actual_checksum != expected_checksum:
        raise Exception(f"Checksum mismatch for {table_name}: expected {expected_checksum}, got {actual_checksum}")
    
    # Verify CSV structure and row count
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        rows = list(reader)
        
        if len(rows) == 0:
            actual_rows = 0
            headers = []
        else:
            headers = rows[0]
            actual_rows = len(rows) - 1  # Subtract header row
        
        expected_rows = table_meta['rows']
        if actual_rows != expected_rows:
            raise Exception(f"Row count mismatch for {table_name}: expected {expected_rows}, got {actual_rows}")
        
        expected_columns = table_meta['columns']
        if len(headers) != len(expected_columns):
            raise Exception(f"Column count mismatch for {table_name}: expected {len(expected_columns)}, got {len(headers)}")
        
        # Check column names match
        for i, (expected_col, actual_col) in enumerate(zip(expected_columns, headers)):
            if expected_col != actual_col:
                raise Exception(f"Column name mismatch in {table_name} at position {i}: expected '{expected_col}', got '{actual_col}'")
    
    logger.info(f"✅ {table_name}: {actual_rows} rows, {actual_size} bytes - VERIFIED")
    return True

def analyze_critical_data(backup_dir, metadata):
    """Analyze critical data in the backup."""
    logger.info("Analyzing critical data...")
    
    analysis = {
        'users': {'total': 0, 'admin': 0, 'make_picks': 0},
        'games': {'total': 0, 'completed': 0, 'push': 0},
        'picks': {'total': 0, 'locked': 0, 'with_points': 0, 'point_distribution': {}},
        'leaderboard': {'total': 0, 'point_distribution': {}}
    }
    
    # Analyze users
    users_path = os.path.join(backup_dir, "users.csv")
    if os.path.exists(users_path):
        with open(users_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                analysis['users']['total'] += 1
                if row.get('admin') == 'True':
                    analysis['users']['admin'] += 1
                if row.get('make_picks') == 'True':
                    analysis['users']['make_picks'] += 1
    
    # Analyze games
    games_path = os.path.join(backup_dir, "games.csv")
    if os.path.exists(games_path):
        with open(games_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                analysis['games']['total'] += 1
                if row.get('winning_team'):
                    analysis['games']['completed'] += 1
                    if row.get('winning_team') == 'PUSH':
                        analysis['games']['push'] += 1
    
    # Analyze picks
    picks_path = os.path.join(backup_dir, "picks.csv")
    if os.path.exists(picks_path):
        with open(picks_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                analysis['picks']['total'] += 1
                if row.get('lock') == 'True':
                    analysis['picks']['locked'] += 1
                
                points = int(row.get('points_awarded', 0))
                if points > 0:
                    analysis['picks']['with_points'] += 1
                
                # Track point distribution
                if points not in analysis['picks']['point_distribution']:
                    analysis['picks']['point_distribution'][points] = 0
                analysis['picks']['point_distribution'][points] += 1
    
    # Analyze leaderboard
    leaderboard_path = os.path.join(backup_dir, "leaderboard.csv")
    if os.path.exists(leaderboard_path):
        with open(leaderboard_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                analysis['leaderboard']['total'] += 1
                points = int(row.get('total_points', 0))
                
                # Group points into ranges for analysis
                point_range = f"{(points // 10) * 10}-{(points // 10) * 10 + 9}"
                if point_range not in analysis['leaderboard']['point_distribution']:
                    analysis['leaderboard']['point_distribution'][point_range] = 0
                analysis['leaderboard']['point_distribution'][point_range] += 1
    
    return analysis

def generate_verification_report(backup_dir, metadata, analysis):
    """Generate detailed verification report."""
    report_lines = [
        "=" * 70,
        "MARCH MADNESS BACKUP VERIFICATION REPORT",
        "=" * 70,
        f"Backup Directory: {backup_dir}",
        f"Verification Time: {datetime.now().isoformat()}",
        f"Original Backup Time: {metadata['backup_time']}",
        "",
        "BACKUP INTEGRITY: ✅ VERIFIED",
        "",
        "TABLE VERIFICATION:",
        "-" * 50
    ]
    
    for table_meta in metadata['tables']:
        report_lines.append(f"{table_meta['table']:<20} ✅ {table_meta['rows']:>6} rows  {table_meta['file_size']:>8} bytes")
    
    report_lines.extend([
        "",
        "CRITICAL DATA ANALYSIS:",
        "-" * 50,
        f"Users: {analysis['users']['total']} total ({analysis['users']['admin']} admin, {analysis['users']['make_picks']} active)",
        f"Games: {analysis['games']['total']} total ({analysis['games']['completed']} completed, {analysis['games']['push']} push)",
        f"Picks: {analysis['picks']['total']} total ({analysis['picks']['locked']} locked, {analysis['picks']['with_points']} scored)",
        f"Leaderboard: {analysis['leaderboard']['total']} users ranked",
        "",
        "PICK POINT DISTRIBUTION:",
        "-" * 30
    ])
    
    for points, count in sorted(analysis['picks']['point_distribution'].items()):
        report_lines.append(f"{points} points: {count} picks")
    
    report_lines.extend([
        "",
        "BACKUP STATUS: ✅ READY FOR IMPLEMENTATION",
        "=" * 70
    ])
    
    return "\n".join(report_lines)

def main(backup_dir=None):
    """Verify backup integrity and generate report."""
    try:
        if not backup_dir:
            # Find most recent backup directory
            backups_root = "/workspace/backups"
            if not os.path.exists(backups_root):
                raise Exception("No backups directory found")
            
            backup_dirs = [d for d in os.listdir(backups_root) 
                          if os.path.isdir(os.path.join(backups_root, d)) and d != "__pycache__"]
            
            if not backup_dirs:
                raise Exception("No backup directories found")
            
            backup_dir = os.path.join(backups_root, sorted(backup_dirs)[-1])
        
        logger.info(f"🔍 Verifying backup: {backup_dir}")
        
        # Verify directory structure and load metadata
        metadata = verify_backup_directory(backup_dir)
        
        # Verify each table backup
        for table_meta in metadata['tables']:
            verify_table_backup(backup_dir, table_meta)
        
        # Analyze critical data
        analysis = analyze_critical_data(backup_dir, metadata)
        
        # Generate verification report
        report = generate_verification_report(backup_dir, metadata, analysis)
        
        # Save verification report
        report_path = os.path.join(backup_dir, "verification_report.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print("\n" + report)
        
        logger.info("🎉 Backup verification completed successfully!")
        return True, analysis
        
    except Exception as e:
        logger.error(f"❌ Backup verification failed: {str(e)}")
        return False, None

if __name__ == "__main__":
    import sys
    backup_dir = sys.argv[1] if len(sys.argv) > 1 else None
    success, analysis = main(backup_dir)
    sys.exit(0 if success else 1)