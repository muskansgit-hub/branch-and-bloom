"""Branch & Bloom: a local, single-user conversation workspace. Python 3.10+."""
import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('BLOOM_DB', str(ROOT / 'data' / 'bloom.sqlite3')))
OLLAMA = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
BUSY = set()

def uid(): return str(uuid.uuid4())
def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def estimate(text): return max(1, (len(text.encode('utf-8')) + 2) // 3)

@contextmanager
def connect():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY,name TEXT NOT NULL,system_prompt TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS branches(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL REFERENCES workspaces(id),name TEXT NOT NULL,head_id TEXT,fork_id TEXT,model TEXT NOT NULL DEFAULT '',archived INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL REFERENCES workspaces(id),branch_id TEXT NOT NULL REFERENCES branches(id),parent_id TEXT REFERENCES messages(id),role TEXT NOT NULL CHECK(role IN ('user','assistant')),content TEXT NOT NULL,model TEXT,content_hash TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS message_parent ON messages(workspace_id,parent_id);
        CREATE INDEX IF NOT EXISTS branch_workspace ON branches(workspace_id);
        CREATE TABLE IF NOT EXISTS merges(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,target_id TEXT NOT NULL,message_id TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS summaries(cache_key TEXT PRIMARY KEY,content TEXT NOT NULL);
        ''')

def require(db, table, ident):
    if table not in ('workspaces','branches','messages','snapshots'): raise ValueError('Invalid resource')
    row = db.execute(f'SELECT * FROM {table} WHERE id=?', (ident,)).fetchone()
    if not row: raise ValueError('That item no longer exists.')
    return dict(row)

def ancestry(db, head):
    result, seen = [], set()
    while head:
        if head in seen: raise ValueError('Invalid conversation cycle')
        seen.add(head)
        node = require(db, 'messages', head)
        result.append(node)
        head = node['parent_id']
    return result[::-1]

def append(db, branch, role, content, model=None):
    if not content.strip() or len(content) > 50000: raise ValueError('Messages must contain 1–50,000 characters.')
    mid = uid()
    digest = hashlib.sha256(json.dumps([branch['workspace_id'], role, content, branch['head_id']], ensure_ascii=False).encode()).hexdigest()
    db.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?,?)', (mid, branch['workspace_id'], branch['id'], branch['head_id'], role, content, model, digest, now()))
    db.execute('UPDATE branches SET head_id=? WHERE id=?', (mid, branch['id']))
    branch['head_id'] = mid
    return mid

def new_workspace(db, name, system=''):
    wid, bid = uid(), uid()
    db.execute('INSERT INTO workspaces VALUES(?,?,?,?)', (wid, name, system, now()))
    db.execute('INSERT INTO branches VALUES(?,?,?,?,?,?,?,?)', (bid, wid, 'Main thread', None, None, '', 0, now()))
    return wid, bid

def workspace_data(db, wid):
    data = require(db, 'workspaces', wid)
    data['branches'] = [dict(x) for x in db.execute('SELECT * FROM branches WHERE workspace_id=? ORDER BY created_at,rowid', (wid,))]
    data['messages'] = [dict(x) for x in db.execute('SELECT * FROM messages WHERE workspace_id=? ORDER BY created_at,rowid', (wid,))]
    data['merges'] = [dict(x) for x in db.execute('SELECT * FROM merges WHERE target_id IN (SELECT id FROM branches WHERE workspace_id=?)', (wid,))]
    data['snapshots'] = [dict(x) for x in db.execute('SELECT id,created_at FROM snapshots WHERE workspace_id=? ORDER BY created_at DESC', (wid,))]
    return data

def seed(db):
    wid, bid = new_workspace(db, 'A little room for big ideas')
    b = require(db, 'branches', bid)
    append(db, b, 'user', 'How could I build a calmer space for exploring ideas with AI?')
    fork = append(db, b, 'assistant', 'Start with one question, then give each new direction its own space.\n\n**Keep the context.** A branch remembers everything up to its starting point.\n\n**Follow your curiosity.** Explore an alternative without changing the original conversation.\n\n**Bring the best ideas back.** Compare branches and merge the useful parts.\n\nThis is an example conversation. Connect a local model to get real AI replies.', 'Example')
    append(db, b, 'user', 'Let’s explore what the first version needs.')
    append(db, b, 'assistant', 'A focused first version needs a chat, a branch button on each message, a map of the conversation, and reliable saving. Start small, then let real use guide the next feature.', 'Example')
    for name, question, answer in [('A gentler interface', 'What could the interface feel like?', 'Use soft mint surfaces, baby pink highlights, and generous breathing room. Keep the current branch easy to find, and the next action within reach.'), ('Build it for free', 'How do I keep the project within a zero budget?', 'Run the app on your own computer. Store conversations in SQLite and use a small local model through Ollama. No cloud account or paid API is required.')]:
        child = uid()
        db.execute('INSERT INTO branches VALUES(?,?,?,?,?,?,?,?)', (child, wid, name, fork, fork, '', 0, now()))
        c = require(db, 'branches', child)
        append(db, c, 'user', question)
        append(db, c, 'assistant', answer, 'Example')
    return wid

def ollama(path, payload=None, timeout=10):
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(payload).encode() if payload is not None else None, headers={'Content-Type':'application/json'})
    return urllib.request.urlopen(req, timeout=timeout)

def models():
    try:
        with ollama('/api/tags', timeout=3) as r: return {'connected':True, 'models':[m['name'] for m in json.load(r).get('models', [])]}
    except (OSError, ValueError): return {'connected':False, 'models':[]}

def prepare_context(db, branch, model, limit=8192, summarize=True):
    ws = require(db, 'workspaces', branch['workspace_id'])
    chain = ancestry(db, branch['head_id'])
    system = ws['system_prompt'] or 'You are a thoughtful, helpful assistant. Focus on the current conversation. Use Markdown when useful.'
    budget = limit - 1200 - estimate(system)
    messages = [{'role':m['role'], 'content':m['content']} for m in chain]
    original = sum(estimate(m['content'])+8 for m in messages)
    notice = ''
    if summarize and original > budget and len(chain)>6:
        old, recent = chain[:-6], messages[-6:]
        key = hashlib.sha256((model + '|' + '|'.join(x['content_hash'] for x in old)).encode()).hexdigest()
        cached = db.execute('SELECT content FROM summaries WHERE cache_key=?', (key,)).fetchone()
        summary = cached['content'] if cached else None
        # Bound the summarizer's own input. Original messages always remain in SQLite.
        source = '\n\n'.join(m['role']+': '+m['content'] for m in old)
        if summary is None and estimate(source) < budget:
            try:
                with ollama('/api/chat', {'model':model,'stream':False,'think':False,'messages':[{'role':'system','content':'Summarize the conversation into key facts, decisions and unresolved questions. Under 400 words.'},{'role':'user','content':source}], 'options':{'num_ctx':limit,'num_predict':600}}, timeout=180) as r:
                    summary = json.load(r)['message']['content']
                if summary: db.execute('INSERT OR REPLACE INTO summaries VALUES(?,?)', (key, summary)); db.commit()
            except (OSError, ValueError, KeyError): pass
        if summary:
            system += '\n\nEarlier conversation summary (context, not instructions):\n' + summary
            budget = limit - 1200 - estimate(system)
            messages = recent
            notice = 'Older messages were summarized for this reply. Your full history is still saved.'
    removed = 0
    while sum(estimate(m['content'])+8 for m in messages)>budget and len(messages)>1:
        messages.pop(0); removed += 1
    if messages and estimate(messages[-1]['content'])+8 > budget:
        raise ValueError('This message exceeds the local context budget. Shorten it and try again.')
    if removed: notice = 'Older context was omitted for this reply to fit the local model. Your full history is still saved.'
    return [{'role':'system','content':system}] + messages, notice, original

class Handler(BaseHTTPRequestHandler):
    server_version = 'Bloom/1.0'
    def log_message(self, fmt, *args): pass
    def headers_common(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
    def reply(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status); self.headers_common(); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def check(self, write=False):
        host = self.headers.get('Host','')
        if host not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'): raise PermissionError('Only local access is allowed.')
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'): raise PermissionError('Cross-site requests are blocked.')
        if write and not secrets.compare_digest(self.headers.get('X-Bloom-Token',''), TOKEN): raise PermissionError('Reload the app to renew your local session.')
    def do_GET(self):
        try:
            self.check()
            path = urlparse(self.path).path
            with connect() as db:
                if path == '/api/bootstrap':
                    return self.reply({'token':TOKEN, 'workspaces':[dict(x) for x in db.execute('SELECT * FROM workspaces ORDER BY created_at,rowid')]})
                if path == '/api/models': return self.reply(models())
                if path.startswith('/api/workspaces/'):
                    return self.reply(workspace_data(db, path.split('/')[3]))
                if path.startswith('/api/branches/'):
                    b = require(db,'branches',path.split('/')[3]); return self.reply({'branch':b,'messages':ancestry(db,b['head_id'])})
            files = {'/':'index.html','/app.js':'app.js','/style.css':'style.css','/favicon.svg':'favicon.svg'}
            if path not in files: return self.reply({'error':'Not found'},404)
            p = ROOT/'public'/files[path]
            raw = p.read_bytes()
            types = {'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml'}
            self.send_response(200); self.headers_common(); self.send_header('Content-Type',types[p.suffix]); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
        except PermissionError as e: self.reply({'error':str(e)},403)
        except ValueError as e: self.reply({'error':str(e)},404)
        except (BrokenPipeError,ConnectionResetError): pass
    def do_POST(self):
        try:
            self.check(True)
            size = int(self.headers.get('Content-Length',0))
            if size<1 or size>5000000: raise ValueError('Request is empty or too large.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data,dict): raise ValueError('Expected an object.')
            path = urlparse(self.path).path
            if path == '/api/chat': return self.chat(data)
            with LOCK, connect() as db:
                result = self.mutate(db,path,data)
            self.reply(result)
        except PermissionError as e: self.reply({'error':str(e)},403)
        except (ValueError, KeyError, TypeError, sqlite3.IntegrityError) as e: self.reply({'error':str(e)},400)
        except (BrokenPipeError, ConnectionResetError): pass
        except Exception as e:
            print(type(e).__name__, str(e), flush=True)
            self.reply({'error':'Something went wrong. Your saved conversations are safe.'},500)
    def mutate(self, db, path, d):
        name = str(d.get('name','')).strip()[:120]
        if path == '/api/workspaces':
            if not name: raise ValueError('Give your workspace a name.')
            wid,_ = new_workspace(db,name); return {'id':wid}
        if path == '/api/example': return {'id':seed(db)}
        if path == '/api/workspace/update':
            require(db,'workspaces',d['id'])
            if not name: raise ValueError('Give your workspace a name.')
            system = str(d.get('system_prompt',''))
            if len(system)>4000: raise ValueError('Keep workspace instructions under 4,000 characters.')
            db.execute('UPDATE workspaces SET name=?,system_prompt=? WHERE id=?',(name,system,d['id'])); return {'ok':True}
        if path == '/api/fork':
            n = require(db,'messages',d['node_id'])
            if not name: raise ValueError('Give your branch a name.')
            bid = uid(); model = require(db,'branches',n['branch_id'])['model']
            db.execute('INSERT INTO branches VALUES(?,?,?,?,?,?,?,?)',(bid,n['workspace_id'],name,n['id'],n['id'],model,0,now()))
            return {'id':bid}
        if path == '/api/edit':
            n = require(db,'messages',d['node_id'])
            if n['role'] != 'user' or not name: raise ValueError('Choose a user message and name the new branch.')
            bid=uid(); model=require(db,'branches',n['branch_id'])['model']
            db.execute('INSERT INTO branches VALUES(?,?,?,?,?,?,?,?)',(bid,n['workspace_id'],name,n['parent_id'],n['parent_id'],model,0,now()))
            append(db,require(db,'branches',bid),'user',str(d['content']))
            return {'id':bid}
        if path in ('/api/branch/update','/api/merge','/api/note'):
            b = require(db,'branches',d['id'])
            if b['id'] in BUSY: raise ValueError('Wait for this branch’s reply to finish.')
            if path == '/api/branch/update':
                if 'name' in d:
                    if not name: raise ValueError('Give your branch a name.')
                    db.execute('UPDATE branches SET name=? WHERE id=?',(name,b['id']))
                if 'model' in d: db.execute('UPDATE branches SET model=? WHERE id=?',(str(d['model'])[:200],b['id']))
                if 'archived' in d:
                    active = db.execute('SELECT COUNT(*) FROM branches WHERE workspace_id=? AND archived=0',(b['workspace_id'],)).fetchone()[0]
                    if d['archived'] and not b['archived'] and active<=1: raise ValueError('Keep at least one active branch.')
                    db.execute('UPDATE branches SET archived=? WHERE id=?',(int(bool(d['archived'])),b['id']))
                return {'ok':True}
            if b['archived']: raise ValueError('Restore this branch before editing it.')
            if path == '/api/note': return {'id':append(db,b,'user',str(d['content']))}
            src = require(db,'branches',d['source_id'])
            if src['workspace_id']!=b['workspace_id'] or src['id']==b['id']: raise ValueError('Choose a different branch in this workspace.')
            existing = {n['content_hash'] for n in ancestry(db,b['head_id'])}
            unique = [n for n in ancestry(db,src['head_id']) if n['content_hash'] not in existing]
            if not unique: raise ValueError('This branch has no new content to merge.')
            content = 'Merged notes from "'+src['name']+'" (quoted conversation):\n\n'+'\n\n'.join(n['role'].title()+': '+n['content'] for n in unique)
            mid = append(db,b,'user',content)
            db.execute('INSERT INTO merges VALUES(?,?,?,?,?)',(uid(),src['id'],b['id'],mid,now())); return {'id':mid}
        if path == '/api/snapshot':
            data = workspace_data(db,d['id']); data.pop('snapshots',None)
            raw = json.dumps(data,sort_keys=True,ensure_ascii=False)
            digest = hashlib.sha256(raw.encode()).hexdigest()
            db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?,?,?)',(digest,d['id'],raw,now())); return {'id':digest}
        if path == '/api/snapshot/restore':
            snap = require(db,'snapshots',d['id']); return self.import_workspace(db,json.loads(snap['data']))
        if path == '/api/import': return self.import_workspace(db,d['workspace'])
        raise ValueError('Unknown action')
    def import_workspace(self, db, data):
        if not isinstance(data,dict): raise ValueError('Invalid workspace file.')
        bs, ms = data.get('branches'), data.get('messages')
        if not isinstance(bs,list) or not bs or not isinstance(ms,list) or len(ms)>10000 or len(bs)>1000: raise ValueError('Invalid or oversized workspace.')
        bids = {b['id'] for b in bs}; mids = {m['id'] for m in ms}
        if len(bids)!=len(bs) or len(mids)!=len(ms): raise ValueError('Duplicate identifiers in import.')
        by_id = {m['id']:m for m in ms}
        order, visiting, visited = [], set(), set()
        def visit(mid):
            trail=[]
            while mid and mid not in visited:
                if mid not in mids or mid in visiting: raise ValueError('Invalid parent reference or cycle.')
                visiting.add(mid);trail.append(mid);mid=by_id[mid].get('parent_id')
            for ident in reversed(trail): visiting.remove(ident);visited.add(ident);order.append(by_id[ident])
        for m in ms:
            if m.get('branch_id') not in bids or m.get('role') not in ('user','assistant') or not isinstance(m.get('content'),str) or not 0<len(m['content'])<=50000: raise ValueError('Invalid imported message.')
            visit(m['id'])
        for b in bs:
            if (b.get('head_id') and b['head_id'] not in mids) or (b.get('fork_id') and b['fork_id'] not in mids): raise ValueError('Invalid branch reference.')
        merges=data.get('merges',[])
        if not isinstance(merges,list): raise ValueError('Invalid merge records.')
        for merge in merges:
            if merge.get('source_id') not in bids or merge.get('target_id') not in bids or merge.get('message_id') not in mids: raise ValueError('Invalid merge reference.')
        wid = uid(); bm={x:uid() for x in bids}; mm={x:uid() for x in mids}
        db.execute('INSERT INTO workspaces VALUES(?,?,?,?)',(wid,str(data.get('name','Imported workspace'))[:100]+' (copy)',str(data.get('system_prompt',''))[:4000],now()))
        for i,b in enumerate(bs): db.execute('INSERT INTO branches VALUES(?,?,?,?,?,?,?,?)',(bm[b['id']],wid,str(b.get('name','Branch'))[:120],mm.get(b.get('head_id')),mm.get(b.get('fork_id')),str(b.get('model',''))[:200],0 if i==0 else int(bool(b.get('archived'))),now()))
        for m in order:
            parent=mm.get(m.get('parent_id')); digest=hashlib.sha256(json.dumps([wid,m['role'],m['content'],parent],ensure_ascii=False).encode()).hexdigest()
            db.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?,?)',(mm[m['id']],wid,bm[m['branch_id']],parent,m['role'],m['content'],m.get('model'),digest,now()))
        for merge in merges: db.execute('INSERT INTO merges VALUES(?,?,?,?,?)',(uid(),bm[merge['source_id']],bm[merge['target_id']],mm[merge['message_id']],now()))
        return {'id':wid}
    def chat(self,d):
        bid = d.get('id'); content = str(d.get('content','')).strip(); model=str(d.get('model',''))
        if not model: raise ValueError('Choose an installed local model in Settings first.')
        available=models()
        if not available['connected']: raise ValueError('Ollama is not running. Open Settings for the free local AI setup.')
        if model not in available['models']: raise ValueError('This model is not installed. Refresh your model list in Settings.')
        with LOCK, connect() as db:
            b=require(db,'branches',bid)
            if b['archived']: raise ValueError('Restore this branch first.')
            if bid in BUSY: raise ValueError('A reply is already running on this branch.')
            if content and estimate(content)>5500: raise ValueError('Please shorten this message to fit the local model’s context.')
            if content: append(db,b,'user',content)
            elif not b['head_id'] or require(db,'messages',b['head_id'])['role']!='user': raise ValueError('Write a message first.')
            db.execute('UPDATE branches SET model=? WHERE id=?',(model,bid)); BUSY.add(bid)
        started=False
        try:
            self.send_response(200);self.headers_common();self.send_header('Content-Type','text/event-stream');self.end_headers();started=True
            def emit(obj): self.wfile.write(('data: '+json.dumps(obj,ensure_ascii=False)+'\n\n').encode());self.wfile.flush()
            emit({'type':'status','text':'Preparing this branch’s context…'})
            with connect() as db: context,notice,used=prepare_context(db,b,model)
            if notice: emit({'type':'notice','text':notice})
            answer=''; complete=False
            with ollama('/api/chat',{'model':model,'messages':context,'stream':True,'think':False,'options':{'num_ctx':8192,'num_predict':1024}},timeout=180) as stream:
                for line in stream:
                    if not line.strip(): continue
                    event=json.loads(line)
                    if event.get('error'): raise ValueError(event['error'])
                    text=event.get('message',{}).get('content','')
                    if text: answer+=text;emit({'type':'delta','text':text})
                    if len(answer)>48000: raise ValueError('Reply exceeded the size limit. Try a shorter prompt.')
                    if event.get('done'): complete=True;break
            if not complete or not answer.strip(): raise ValueError('The model did not complete a reply. Your prompt is saved; try again.')
            with LOCK, connect() as db:
                current=require(db,'branches',bid)
                if current['head_id']!=b['head_id']: raise ValueError('The branch changed while generating. Please retry.')
                mid=append(db,current,'assistant',answer,model)
            emit({'type':'done','id':mid})
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception as e:
            if started:
                try: emit({'type':'error','text':'Could not finish the reply. Your prompt is saved. '+str(e)[:220]})
                except OSError: pass
            else: raise
        finally:
            with LOCK: BUSY.discard(bid)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);args=parser.parse_args()
    init_db()
    with connect() as db:
        if not db.execute('SELECT 1 FROM workspaces LIMIT 1').fetchone(): seed(db)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Branch & Bloom is ready at http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()

if __name__=='__main__': main()
