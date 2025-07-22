#!/usr/bin/env python3
"""
Smart app starter that finds available port and manages existing instances
"""
import socket
import subprocess
import sys
import os
import signal
import time

def find_free_port(start_port=8080, max_port=9000):
    """Find a free port starting from start_port"""
    for port in range(start_port, max_port):
        try:
            # Try to bind to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('', port))
            sock.close()
            return port
        except OSError:
            continue
    raise RuntimeError(f"No free ports found between {start_port} and {max_port}")

def kill_existing_app_instances():
    """Kill any existing Flask/Python app instances on common ports"""
    common_ports = [8080, 8081, 8082, 5000, 5001]
    
    for port in common_ports:
        try:
            # Get PIDs using the port
            result = subprocess.run(
                f"lsof -ti:{port}", 
                shell=True, 
                capture_output=True, 
                text=True
            )
            
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                        print(f"✓ Killed process {pid} on port {port}")
                    except:
                        pass
        except:
            pass

def start_app():
    """Start the Flask app on an available port"""
    # Kill existing instances
    print("🔍 Checking for existing app instances...")
    kill_existing_app_instances()
    time.sleep(1)  # Give time for ports to be released
    
    # Find free port
    port = find_free_port()
    print(f"✅ Found free port: {port}")
    
    # Update app.py to use the new port
    app_path = "app.py"
    
    # Read the current app.py
    with open(app_path, 'r') as f:
        content = f.read()
    
    # Replace the port in the last line
    import re
    content = re.sub(
        r'socketio\.run\(app,.*?port=\d+.*?\)', 
        f'socketio.run(app, debug=True, host="0.0.0.0", port={port}, allow_unsafe_werkzeug=True)',
        content
    )
    
    # Write back
    with open(app_path, 'w') as f:
        f.write(content)
    
    print(f"🚀 Starting app on port {port}...")
    print(f"🌐 Access the app at: http://localhost:{port}")
    print("📝 Press Ctrl+C to stop the server")
    print("-" * 50)
    
    # Start the app
    subprocess.run([sys.executable, "app.py"])

if __name__ == "__main__":
    try:
        start_app()
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Error: {e}")