#!/usr/bin/env python3

"""Batch process all studies from 2024-01-01 to today using store_study_info.py"""

import subprocess
import sys
from datetime import datetime, timedelta

def generate_date_range(start_date_str, end_date_str):
    """Generate all dates between start and end (inclusive)"""
    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    end = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    current = start
    while current <= end:
        yield current.strftime("%Y%m%d")
        current += timedelta(days=1)

def main():
    start_date = "2024-01-01"
    end_date = "2025-09-02"  # Today
    
    print(f"Processing studies from {start_date} to {end_date}")
    
    total_dates = 0
    processed_dates = 0
    
    # Count total dates first
    for _ in generate_date_range(start_date, end_date):
        total_dates += 1
    
    print(f"Total dates to process: {total_dates}")
    
    for date_str in generate_date_range(start_date, end_date):
        processed_dates += 1
        print(f"[{processed_dates}/{total_dates}] Processing {date_str}...")
        
        try:
            # Run store_study_info.py with the date
            result = subprocess.run(
                [sys.executable, "store_study_info.py", date_str],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per date
            )
            
            if result.returncode != 0:
                print(f"  ERROR processing {date_str}: {result.stderr}")
            elif result.stdout.strip():
                # Only print if there was output (studies processed)
                lines = result.stdout.strip().split('\n')
                print(f"  Processed {len(lines)} studies")
            else:
                print(f"  No studies found")
                
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT processing {date_str}")
        except Exception as e:
            print(f"  EXCEPTION processing {date_str}: {e}")
    
    print(f"Batch processing complete. Processed {processed_dates} dates.")

if __name__ == "__main__":
    main()