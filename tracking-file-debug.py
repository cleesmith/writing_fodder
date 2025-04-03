#!/usr/bin/env python
"""
Simple Tracking File Debug Script

Tests the exact pattern used in the Writer's Toolkit for creating tracking files.
"""

import os
import uuid

def test_tracking_file_creation():
    print("\n=== TRACKING FILE CREATION TEST ===")
    
    # Get current working directory
    cwd = os.getcwd()
    print(f"Current working directory: {cwd}")
    
    # Generate a UUID
    run_uuid = str(uuid.uuid4())
    print(f"Generated UUID: {run_uuid}")
    
    # Create the tracking file path
    tracking_file = os.path.join(cwd, f"{run_uuid}.txt")
    print(f"@@@ Tracking file path: {tracking_file}")
    
    # Sample created files
    created_files = [
        os.path.join(cwd, "file1.txt"),
        os.path.join(cwd, "file2.txt"),
        os.path.join(os.path.expanduser("~"), "document.txt")
    ]
    
    print(f"Attempting to create tracking file...")
    
    # This is the exact pattern you're using
    try:
        print(f">>> tracking_file={tracking_file}")
        with open(tracking_file, 'w', encoding='utf-8') as file:
            for file_path in created_files:
                print(f"### file_path={file_path}")
                file.write(f"{file_path}\n")
        
        print(f"✓ SUCCESS: Tracking file created at {tracking_file}")
        print(f"*** File exists after writing: {os.path.exists(tracking_file)}")
        
        # Read back the file to verify contents
        if os.path.exists(tracking_file):
            print(f"Reading contents of tracking file:")
            with open(tracking_file, 'r', encoding='utf-8') as file:
                content = file.readlines()
                print(f"Read {len(content)} lines from tracking file:")
                for i, line in enumerate(content):
                    print(f"  Line {i+1}: {line.strip()}")
        else:
            print(f"✗ ERROR: Tracking file doesn't exist after writing")
    
    except Exception as e:
        print(f"✗ ERROR: {type(e).__name__}: {e}")
    
    # Check if file exists after the entire operation
    print(f"\nFile exists at end of test: {os.path.exists(tracking_file)}\n")
    
    # # If file exists, try to remove it
    # if os.path.exists(tracking_file):
    #     try:
    #         os.remove(tracking_file)
    #         print(f"✓ Tracking file successfully removed")
    #     except Exception as e:
    #         print(f"✗ Error removing tracking file: {e}")

if __name__ == "__main__":
    test_tracking_file_creation()
