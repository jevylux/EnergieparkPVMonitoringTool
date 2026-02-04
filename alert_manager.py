#!/usr/bin/env python3
"""
Alert Management Utility for Energy Data Collector

This script allows manual management of alert flags in the database.
Use this to reset or acknowledge alerts as needed.
@MarcDurbach 2026
"""

import argparse
import sqlite3
from datetime import datetime
from typing import Optional
import sys


class AlertManager:
    """Manage alert flags in the energy data database."""
    
    def __init__(self, db_path: str = 'energy_data_energiepark.db'):
        self.db_path = db_path
    
    def list_alerts(self, status: str = 'all'):
        """
        List alerts from the database.
        
        Args:
            status: 'all', 'pending', 'sent', 'acknowledged'
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                date,
                pod_code,
                pod_name,
                value_kwh,
                expected_kwh,
                performance_ratio,
                alert_sent,
                alert_acknowledged
            FROM energy_data
            WHERE is_underperforming = 1
        '''
        
        if status == 'pending':
            query += ' AND alert_sent = 0 AND alert_acknowledged = 0'
        elif status == 'sent':
            query += ' AND alert_sent = 1 AND alert_acknowledged = 0'
        elif status == 'acknowledged':
            query += ' AND alert_acknowledged = 1'
        
        query += ' ORDER BY date DESC, pod_name'
        
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            print(f"No {status} alerts found.")
            return
        
        print(f"\n{'='*100}")
        print(f"{status.upper()} ALERTS")
        print(f"{'='*100}")
        print(f"{'Date':<12} | {'POD Code':<20} | {'Installation':<25} | "
              f"{'Actual':>8} | {'Expected':>8} | {'Perf%':>6} | {'Status':<15}")
        print("-"*100)
        
        for row in results:
            date, pod_code, pod_name, actual, expected, perf, sent, acked = row
            
            if acked:
                status_str = "Acknowledged"
            elif sent:
                status_str = "Sent"
            else:
                status_str = "Pending"
            
            print(f"{date:<12} | {pod_code[:20]:<20} | {pod_name[:25]:<25} | "
                  f"{actual:8.2f} | {expected:8.2f} | {perf*100:5.1f}% | {status_str:<15}")
        
        print(f"{'='*100}\n")
        print(f"Total: {len(results)} alerts")
    
    def reset_alerts(self, pod_code: Optional[str] = None, 
                    date: Optional[str] = None,
                    confirm: bool = False):
        """Reset alert flags (allows alerts to be sent again)."""
        if not confirm:
            print("ERROR: Must use --confirm flag to reset alerts")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if pod_code and date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                    WHERE pod_code = ? AND date = ?
                ''', (pod_code, date))
                affected = cursor.rowcount
                print(f"Reset alerts for POD {pod_code} on {date} ({affected} records)")
            elif pod_code:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                    WHERE pod_code = ?
                ''', (pod_code,))
                affected = cursor.rowcount
                print(f"Reset all alerts for POD {pod_code} ({affected} records)")
            elif date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                    WHERE date = ?
                ''', (date,))
                affected = cursor.rowcount
                print(f"Reset all alerts for date {date} ({affected} records)")
            else:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                    WHERE is_underperforming = 1
                ''')
                affected = cursor.rowcount
                print(f"Reset ALL alerts ({affected} records)")
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error resetting alerts: {e}")
        finally:
            conn.close()
    
    def acknowledge_alerts(self, pod_code: Optional[str] = None,
                          date: Optional[str] = None,
                          confirm: bool = False):
        """Acknowledge alerts (prevents them from being sent)."""
        if not confirm:
            print("ERROR: Must use --confirm flag to acknowledge alerts")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if pod_code and date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE pod_code = ? AND date = ? AND is_underperforming = 1
                ''', (pod_code, date))
                affected = cursor.rowcount
                print(f"Acknowledged alerts for POD {pod_code} on {date} ({affected} records)")
            elif pod_code:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE pod_code = ? AND is_underperforming = 1
                ''', (pod_code,))
                affected = cursor.rowcount
                print(f"Acknowledged all alerts for POD {pod_code} ({affected} records)")
            elif date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE date = ? AND is_underperforming = 1
                ''', (date,))
                affected = cursor.rowcount
                print(f"Acknowledged all alerts for date {date} ({affected} records)")
            else:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE is_underperforming = 1
                ''')
                affected = cursor.rowcount
                print(f"Acknowledged ALL alerts ({affected} records)")
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error acknowledging alerts: {e}")
        finally:
            conn.close()
    
    def get_statistics(self):
        """Display alert statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total underperforming records
        cursor.execute('SELECT COUNT(*) FROM energy_data WHERE is_underperforming = 1')
        total_alerts = cursor.fetchone()[0]
        
        # Pending alerts
        cursor.execute('''
            SELECT COUNT(*) FROM energy_data 
            WHERE is_underperforming = 1 AND alert_sent = 0 AND alert_acknowledged = 0
        ''')
        pending = cursor.fetchone()[0]
        
        # Sent alerts
        cursor.execute('''
            SELECT COUNT(*) FROM energy_data 
            WHERE is_underperforming = 1 AND alert_sent = 1 AND alert_acknowledged = 0
        ''')
        sent = cursor.fetchone()[0]
        
        # Acknowledged alerts
        cursor.execute('''
            SELECT COUNT(*) FROM energy_data 
            WHERE is_underperforming = 1 AND alert_acknowledged = 1
        ''')
        acknowledged = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\n{'='*50}")
        print("ALERT STATISTICS")
        print(f"{'='*50}")
        print(f"Total underperforming records: {total_alerts}")
        print(f"Pending alerts:                {pending}")
        print(f"Sent (not acknowledged):       {sent}")
        print(f"Acknowledged:                  {acknowledged}")
        print(f"{'='*50}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Manage alert flags in the energy data database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # List all pending alerts
  python alert_manager.py list --status pending
  
  # List all alerts
  python alert_manager.py list
  
  # Acknowledge all alerts for a specific POD
  python alert_manager.py acknowledge --pod LU0000010637000000000000070232023 --confirm
  
  # Acknowledge alerts for a specific date
  python alert_manager.py acknowledge --date 2025-02-01 --confirm
  
  # Reset all alerts (allows them to be sent again)
  python alert_manager.py reset --confirm
  
  # Reset alerts for specific POD on specific date
  python alert_manager.py reset --pod LU0000010637000000000000070232023 --date 2025-02-01 --confirm
  
  # Show statistics
  python alert_manager.py stats
        '''
    )
    
    parser.add_argument('action', 
                       choices=['list', 'reset', 'acknowledge', 'stats'],
                       help='Action to perform')
    
    parser.add_argument('--status',
                       choices=['all', 'pending', 'sent', 'acknowledged'],
                       default='all',
                       help='Filter alerts by status (for list action)')
    
    parser.add_argument('--pod',
                       help='POD code to filter by')
    
    parser.add_argument('--date',
                       help='Date to filter by (YYYY-MM-DD)')
    
    parser.add_argument('--confirm',
                       action='store_true',
                       help='Required flag to confirm reset or acknowledge actions')
    
    parser.add_argument('--db',
                       default='energy_data_energiepark.db',
                       help='Path to database file')
    
    args = parser.parse_args()
    
    manager = AlertManager(args.db)
    
    if args.action == 'list':
        manager.list_alerts(args.status)
    
    elif args.action == 'reset':
        manager.reset_alerts(args.pod, args.date, args.confirm)
    
    elif args.action == 'acknowledge':
        manager.acknowledge_alerts(args.pod, args.date, args.confirm)
    
    elif args.action == 'stats':
        manager.get_statistics()


if __name__ == '__main__':
    main()
