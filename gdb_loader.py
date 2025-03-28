#!/usr/bin/env python3
import argparse
import requests
import json
import time
import sys

def request_server(endpoint, method='GET', data=None):
    """Make a request to the GDB server."""
    url = f"http://localhost:13946/api/{endpoint}"
    try:
        if method == 'GET':
            response = requests.get(url)
        else:  # POST
            response = requests.post(url, json=data)
        return response.json()
    except Exception as e:
        print(f"Error communicating with server: {str(e)}")
        return None

def load_program(program_path, server_running=False):
    """Load a program into GDB."""
    # First, check if GDB is already running
    if not server_running:
        status = request_server('status')
        if not status or not status.get('isRunning', False):
            # Start GDB if not running
            result = request_server('start', method='POST')
            if not result or not result.get('success', False):
                print(f"Failed to start GDB: {result.get('message', 'Unknown error')}")
                return False
            print("GDB started successfully")
        else:
            print("GDB is already running")
    
    # Load program into GDB
    result = request_server('execute', method='POST', data={'command': f"file {program_path}"})
    if not result or not result.get('success', False):
        print(f"Failed to load program: {result.get('output', 'Unknown error')}")
        return False
    
    print(f"Program loaded: {program_path}")
    print(result.get('output', ''))
    return True

def main():
    parser = argparse.ArgumentParser(description='Load a program into GDB via the MCP server')
    parser.add_argument('program', help='Path to the program file to load')
    parser.add_argument('--gdb-args', help='Additional arguments to pass to GDB', default='')
    
    args = parser.parse_args()
    
    # Check if server is running
    status = request_server('status')
    if not status:
        print("Error: Unable to connect to the GDB MCP server. Make sure it's running.")
        sys.exit(1)
    
    server_running = status.get('isRunning', False)
    
    # Load the program
    if load_program(args.program, server_running):
        # If there are additional GDB arguments, pass them
        if args.gdb_args:
            result = request_server('execute', method='POST', data={'command': args.gdb_args})
            if result and result.get('success', False):
                print(f"Applied GDB arguments: {args.gdb_args}")
                print(result.get('output', ''))
        
        print("Program ready for debugging!")
    else:
        print("Failed to set up debugging session")
        sys.exit(1)

if __name__ == "__main__":
    main() 