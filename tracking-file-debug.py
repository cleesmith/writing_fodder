#!/usr/bin/env python
"""
Tracking File Debug Script

This standalone script helps debug issues with the UUID tracking file system
for the Writer's Toolkit application. It creates a tracking file, writes to it,
and attempts to read from it, printing diagnostic information at each step.

Run this script from various directories to test path resolution issues.
"""

import os
import uuid
import sys
import tempfile
from datetime import datetime

def debug_tracking_file():
    """
    Debug the creation and reading of a UUID tracking file.
    """
    print("\n==================== TRACKING FILE DEBUG ====================\n")
    
    # Print system information
    print(f"Python version: {sys.version}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Script location: {os.path.abspath(__file__)}")
    print(f"User home directory: {os.path.expanduser('~')}")
    print(f"Temp directory: {tempfile.gettempdir()}")
    print("\n")
    
    # Generate a UUID
    run_uuid = str(uuid.uuid4())
    print(f"Generated UUID: {run_uuid}")
    
    # Try creating tracking files in different locations
    tracking_locations = [
        # Current directory
        os.path.join(os.getcwd(), f"{run_uuid}.txt"),
        
        # Script directory
        os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{run_uuid}.txt"),
        
        # User's home directory
        os.path.join(os.path.expanduser("~"), f"{run_uuid}.txt"),
        
        # System temp directory
        os.path.join(tempfile.gettempdir(), f"{run_uuid}.txt")
    ]
    
    # Sample files that would be "created" by a tool
    sample_files = [
        "/Users/username/Documents/file1.txt",
        "/Users/username/Documents/file2.txt",
        os.path.join(os.getcwd(), "local_file.txt")
    ]
    
    for i, tracking_file in enumerate(tracking_locations):
        print(f"\n--- Test Location {i+1}: {tracking_file} ---")
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(tracking_file)), exist_ok=True)
            
            print(f"  Writing to tracking file...")
            print(f"  Absolute path: {os.path.abspath(tracking_file)}")
            
            # Create a tracker file
            with open(tracking_file, 'w', encoding='utf-8') as f:
                for file_path in sample_files:
                    f.write(f"{file_path}\n")
            
            print(f"  ✓ Successfully wrote to tracking file")
            print(f"  File exists after writing: {os.path.exists(tracking_file)}")
            print(f"  File size: {os.path.getsize(tracking_file)} bytes")
            
            # Try to read it back
            print(f"  Reading from tracking file...")
            if os.path.exists(tracking_file):
                with open(tracking_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                print(f"  ✓ Successfully read {len(lines)} lines from tracking file")
                print(f"  Content:")
                for line in lines:
                    print(f"    - {line.strip()}")
            else:
                print(f"  ✗ File doesn't exist when trying to read it")
            
            # Try different ways of accessing the file
            print(f"  Testing different file path methods:")
            print(f"    - os.path.isfile: {os.path.isfile(tracking_file)}")
            print(f"    - os.access(read): {os.access(tracking_file, os.R_OK)}")
            print(f"    - os.access(write): {os.access(tracking_file, os.W_OK)}")
            
            # Clean up
            try:
                os.remove(tracking_file)
                print(f"  ✓ Successfully removed tracking file")
            except Exception as e:
                print(f"  ✗ Error removing tracking file: {e}")
        
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
    
    print("\n==================== END DEBUG ====================\n")

if __name__ == "__main__":
    debug_tracking_file()
