"""Start the app and its optional portable Ollama runtime, without installation."""
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT=Path(__file__).resolve().parent

def ready(url):
    try:
        with urllib.request.urlopen(url,timeout=1) as response:return response.status==200
    except OSError:return False

def main():
    app_url='http://127.0.0.1:8765'
    app_running=ready(app_url+'/api/bootstrap')
    owned=[];log=None
    try:
        runtime=ROOT/'runtime';exe=runtime/'ollama.exe'
        if exe.exists() and not ready('http://127.0.0.1:11434/api/tags'):
            (ROOT/'data').mkdir(exist_ok=True);(runtime/'profile').mkdir(exist_ok=True)
            env=os.environ.copy();env.update({'USERPROFILE':str(runtime/'profile'),'OLLAMA_MODELS':str(ROOT/'data'/'models'),'OLLAMA_NO_CLOUD':'true','OLLAMA_HOST':'127.0.0.1:11434'})
            log=open(ROOT/'data'/'ollama.log','ab')
            owned.append(subprocess.Popen([str(exe),'serve'],env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
            ai=owned[-1]
            for _ in range(40):
                if ready('http://127.0.0.1:11434/api/tags'):break
                if ai.poll() is not None:
                    print('Local AI could not start. Open Settings in the app for setup help.')
                    break
                time.sleep(.25)
            else:print('Local AI is still starting. Refresh its connection in Settings shortly.')
        if app_running:
            print('Branch & Bloom is already running at '+app_url)
            webbrowser.open(app_url)
            if owned and owned[0].poll() is None:
                print('Local AI was restarted. Keep this window open; Ctrl+C stops this AI process only.')
                while owned[0].poll() is None and ready(app_url+'/api/bootstrap'):
                    time.sleep(1)
            return
        server=subprocess.Popen([sys.executable,str(ROOT/'server.py')],cwd=ROOT);owned.append(server)
        for _ in range(40):
            if ready(app_url+'/api/bootstrap'):break
            if server.poll() is not None:raise RuntimeError('The app could not start. Check the message above.')
            time.sleep(.25)
        else:raise RuntimeError('The app did not become ready. Try python server.py for details.')
        webbrowser.open(app_url)
        print('Keep this window open. Press Ctrl+C to stop Branch & Bloom.')
        server.wait()
    except KeyboardInterrupt:print('\nStopping Branch & Bloom…')
    finally:
        for process in reversed(owned):
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill()
        if log:log.close()

if __name__=='__main__':main()
