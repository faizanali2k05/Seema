#!/usr/bin/env python3
"""
WSGI Entry Point for Gunicorn
Wraps the Seema demo-server for production deployment
"""

import os
import sys
import io

# Fix encoding on Windows/Linux
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Set up path and environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['DATA_DIR'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# Import the demo server
from app import demo_server

# Create and cache the request handler class
class WSGIApplication:
    """WSGI application wrapper for Gunicorn"""
    
    def __init__(self):
        # Pre-initialize the database and other resources
        self.handler_class = demo_server.RequestHandler
    
    def __call__(self, environ, start_response):
        """
        WSGI callable that processes requests
        """
        try:
            # Parse the request
            method = environ.get('REQUEST_METHOD', 'GET')
            path = environ.get('PATH_INFO', '/')
            query_string = environ.get('QUERY_STRING', '')
            
            # Create a mock socket-like object for the handler
            # This is necessary because RequestHandler expects socket operations
            class MockSocket:
                def __init__(self):
                    self.data = b''
                
                def makefile(self, mode):
                    return io.BytesIO(self.data)
            
            # For now, we'll handle the request directly
            # Route to appropriate handler in demo_server
            response_body = demo_server.handle_request(method, path, query_string, environ)
            
            status = '200 OK'
            headers = [('Content-Type', 'application/json; charset=utf-8')]
            
            start_response(status, headers)
            
            if isinstance(response_body, str):
                return [response_body.encode('utf-8')]
            return [response_body]
        
        except Exception as e:
            # Error handling
            import traceback
            error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            status = '500 Internal Server Error'
            headers = [('Content-Type', 'text/plain')]
            start_response(status, headers)
            return [error_msg.encode('utf-8')]


# Instantiate the WSGI application for Gunicorn
application = WSGIApplication()
