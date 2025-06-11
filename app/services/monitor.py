# scripts/monitor.py
#!/usr/bin/env python3
"""
System monitoring script for News Dashboard
"""

import os
import sys
import time
import psutil
import psycopg2
import logging
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Settings

def get_system_metrics() -> Dict[str, Any]:
    """Get system performance metrics"""
    return {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
        'load_average': os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0,
        'timestamp': datetime.now()
    }

def check_database_health(db_params: Dict[str, str]) -> Dict[str, Any]:
    """Check database connection and basic metrics"""
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        
        # Check connection
        cursor.execute('SELECT 1')
        
        # Get database size
        cursor.execute("""
            SELECT pg_size_pretty(pg_database_size(current_database()))
        """)
        db_size = cursor.fetchone()[0]
        
        # Get table counts
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                n_tup_ins as inserts,
                n_tup_upd as updates,
                n_tup_del as deletes
            FROM pg_stat_user_tables
            WHERE tablename IN ('articles', 'scraper_logs', 'publishing_logs')
        """)
        table_stats = cursor.fetchall()
        
        conn.close()
        
        return {
            'status': 'healthy',
            'database_size': db_size,
            'table_stats': table_stats,
            'timestamp': datetime.now()
        }
        
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now()
        }

def log_metrics(metrics: Dict[str, Any], db_params: Dict[str, str]):
    """Log metrics to database"""
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        
        # Insert system metrics
        for metric_name, value in metrics.items():
            if isinstance(value, (int, float)):
                cursor.execute("""
                    INSERT INTO monitoring.system_metrics (metric_name, metric_value, metric_unit)
                    VALUES (%s, %s, %s)
                """, (metric_name, value, '%' if 'percent' in metric_name else None))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logging.error(f"Failed to log metrics: {e}")

def main():
    """Main monitoring loop"""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/monitor.log'),
            logging.StreamHandler()
        ]
    )
    
    # Load configuration
    config = Settings()
    db_params = config.get_database_params()
    
    logging.info("Starting system monitoring...")
    
    try:
        while True:
            # Collect metrics
            system_metrics = get_system_metrics()
            db_health = check_database_health(db_params)
            
            # Log to console
            logging.info(f"CPU: {system_metrics['cpu_percent']:.1f}%, "
                        f"Memory: {system_metrics['memory_percent']:.1f}%, "
                        f"Disk: {system_metrics['disk_usage']:.1f}%")
            
            logging.info(f"Database: {db_health['status']}")
            
            # Log to database
            log_metrics(system_metrics, db_params)
            
            # Check thresholds and alert if needed
            if system_metrics['cpu_percent'] > 80:
                logging.warning(f"High CPU usage: {system_metrics['cpu_percent']:.1f}%")
            
            if system_metrics['memory_percent'] > 80:
                logging.warning(f"High memory usage: {system_metrics['memory_percent']:.1f}%")
            
            if db_health['status'] != 'healthy':
                logging.error(f"Database unhealthy: {db_health.get('error', 'Unknown error')}")
            
            # Wait before next check
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user")
    except Exception as e:
        logging.error(f"Monitoring error: {e}")

if __name__ == "__main__":
    main()