"""A clean process must import the serverless entry without pytest fixture import order."""
import subprocess
import sys

def test_clean_serverless_import():
    result=subprocess.run([sys.executable,'-c','from app.main import app; assert app'],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
