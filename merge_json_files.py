#!/usr/bin/env python3
"""
Utility script to merge existing separate JSON files into master files
"""
import os
import json
import sys
from datetime import datetime

def merge_json_files(data_dir='data'):
    """Merge all separate JSON files into master files by topic"""
    
    # Dictionary to hold merged data by topic
    master_data = {}
    
    # Process each JSON file in the data directory
    for filename in os.listdir(data_dir):
        if filename.endswith('.json') and not filename.startswith('qa_master_'):
            filepath = os.path.join(data_dir, filename)
            
            # Try to determine topic from filename
            topic = 'angular'  # default
            if 'angular' in filename.lower():
                topic = 'angular'
            elif 'react' in filename.lower():
                topic = 'react'
            elif 'javascript' in filename.lower():
                topic = 'javascript'
            elif 'selected' in filename.lower():
                topic = 'selected'
            
            print(f"Processing {filename} (topic: {topic})...")
            
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                # Initialize topic if not exists
                if topic not in master_data:
                    master_data[topic] = {}
                
                # Merge data
                before_count = len(master_data[topic])
                master_data[topic].update(data)
                after_count = len(master_data[topic])
                
                print(f"  Added {after_count - before_count} entries from {filename}")
                
            except Exception as e:
                print(f"  Error processing {filename}: {e}")
    
    # Save master files
    for topic, data in master_data.items():
        master_filename = f"qa_master_{topic}.json"
        master_filepath = os.path.join(data_dir, master_filename)
        
        # Check if master file already exists
        if os.path.exists(master_filepath):
            try:
                with open(master_filepath, 'r') as f:
                    existing_data = json.load(f)
                print(f"\nExisting master file {master_filename} has {len(existing_data)} entries")
                data.update(existing_data)  # Preserve existing data
            except Exception as e:
                print(f"Error loading existing master file: {e}")
        
        # Save merged data
        with open(master_filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n✅ Saved {master_filename} with {len(data)} total entries")
        
        # Create backup
        backup_dir = os.path.join(data_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        backup_filename = f"qa_master_{topic}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_filepath = os.path.join(backup_dir, backup_filename)
        
        with open(backup_filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Backup saved to {backup_filename}")

def main():
    print("🔄 JSON File Merger")
    print("=" * 50)
    
    data_dir = 'data'
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    
    if not os.path.exists(data_dir):
        print(f"❌ Directory {data_dir} does not exist!")
        return
    
    print(f"📂 Scanning directory: {data_dir}")
    print()
    
    merge_json_files(data_dir)
    
    print("\n✨ Merge complete!")

if __name__ == "__main__":
    main()