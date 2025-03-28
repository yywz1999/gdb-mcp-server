#!/usr/bin/env python3
"""
Demonstration of how to use the GDB MCP client to debug a program.
"""
import os
import sys
import time
import json
import subprocess
from pathlib import Path

# Add parent directory to path so we can import gdb_client.py
sys.path.append(str(Path(__file__).parent.parent))
from gdb_client import GdbClient

def compile_test_program():
    """Compile the test program."""
    print("Compiling test program...")
    script_dir = Path(__file__).parent
    c_file = script_dir / "test_program.c"
    output_file = script_dir / "test_program"
    
    subprocess.run(["gcc", "-g", str(c_file), "-o", str(output_file)], check=True)
    print(f"Compiled: {output_file}")
    return output_file

def main():
    # First, make sure the server is running
    client = GdbClient()
    
    # Try to get status, if fails then server is not running
    try:
        is_running = client.status()
    except:
        print("Error: Unable to connect to GDB MCP server.")
        print("Please start the server with 'python server.py' in a separate terminal window.")
        return
    
    # Compile test program
    try:
        program_path = compile_test_program()
    except subprocess.CalledProcessError:
        print("Error: Failed to compile test program.")
        return
    
    # Start GDB if not already running
    if not is_running:
        print("Starting GDB...")
        success, message = client.start()
        if not success:
            print(f"Error: Failed to start GDB: {message}")
            return
        print("GDB started successfully")
    else:
        print("GDB is already running")
    
    # Load the test program
    print(f"Loading program: {program_path}")
    success, output = client.load_program(str(program_path))
    if not success:
        print(f"Error: Failed to load program: {output}")
        return
    print("Program loaded successfully")
    
    # Set a breakpoint at main
    print("Setting breakpoint at main...")
    success, output = client.set_breakpoint("main")
    if not success:
        print(f"Error: Failed to set breakpoint: {output}")
        return
    print(output)
    
    # Set a breakpoint at vulnerable_function
    print("Setting breakpoint at vulnerable_function...")
    success, output = client.set_breakpoint("vulnerable_function")
    if not success:
        print(f"Error: Failed to set breakpoint: {output}")
        return
    print(output)
    
    # Run the program with a test argument
    print("Running program with test argument...")
    success, output = client.execute("run test_input")
    if not success:
        print(f"Error: Failed to run program: {output}")
        return
    print(output)
    
    # Check local variables
    print("Checking local variables...")
    success, output = client.get_locals()
    if not success:
        print(f"Error: Failed to get local variables: {output}")
        return
    print(output)
    
    # Step to the next instruction
    print("Stepping to next instruction...")
    success, output = client.step()
    if not success:
        print(f"Error: Failed to step: {output}")
        return
    print(output)
    
    # Examine registers
    print("Examining registers...")
    success, output = client.get_registers()
    if not success:
        print(f"Error: Failed to get registers: {output}")
        return
    print(output)
    
    # Continue execution to reach vulnerable_function
    print("Continuing execution to reach vulnerable_function...")
    success, output = client.continue_execution()
    if not success:
        print(f"Error: Failed to continue execution: {output}")
        return
    print(output)
    
    # Examine stack
    print("Examining stack...")
    success, output = client.get_stack()
    if not success:
        print(f"Error: Failed to get stack: {output}")
        return
    print(output)
    
    # Disassemble current function
    print("Disassembling current function...")
    success, output = client.disassemble()
    if not success:
        print(f"Error: Failed to disassemble: {output}")
        return
    print(output)
    
    # Run until completion
    print("Continuing execution until completion...")
    success, output = client.continue_execution()
    if not success:
        print(f"Error: Failed to continue execution: {output}")
        return
    print(output)
    
    # Clean up and stop GDB
    print("Stopping GDB...")
    success, message = client.stop()
    if not success:
        print(f"Error: Failed to stop GDB: {message}")
        return
    print("GDB stopped successfully")
    
    print("Demo completed!")

if __name__ == "__main__":
    main() 