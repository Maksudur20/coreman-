import os
import sys

# Switch to virtualenv Python if not running under it
interp = '/home/coremanfashion/virtualenv/coreman/3.11/bin/python'
if os.path.exists(interp) and sys.executable != interp:
    os.execl(interp, interp, *sys.argv)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import app as application
except Exception:
    import traceback
    err = traceback.format_exc()

    def application(environ, start_response):
        start_response('500 Internal Server Error', [('Content-Type', 'text/html; charset=utf-8')])
        return [f"<h1>Startup Error</h1><pre>{err}</pre>".encode('utf-8')]
