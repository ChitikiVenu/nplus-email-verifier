# app.py
from flask import Flask, render_template_string, request, send_file, jsonify
import os, csv, tempfile, shutil, threading, json
from datetime import datetime, timedelta
from io import BytesIO

# import the check_email module (make sure check_email.py is in same folder)
import check_email

app = Flask(__name__)

TMP = tempfile.gettempdir()
WORK_FOLDER = os.path.join(TMP, "verifier_tmp")
HISTORY_FOLDER = os.path.join(os.getcwd(), "results_history")
os.makedirs(WORK_FOLDER, exist_ok=True)
os.makedirs(HISTORY_FOLDER, exist_ok=True)

from globals import progress_status
import threading

from globals import progress_status
progress_lock = threading.Lock()
task_control = {}
task_control_lock = threading.Lock()

# ---------------- HTML (upgraded UI with live progress card) ----------------
page_html = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>N+ Verifier — Live Progress</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root{--bg:#f5f7fb;--card:#fff;--muted:#7b8794;--accent:#00a99d;--good:#24a148;--risky:#f0ad4e;--bad:#e15759;}
  body{margin:0;font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;background:var(--bg);color:#0b2740;}
  header{padding:18px 28px;background:#fff;border-bottom:1px solid #e6eef6;}
  .topbar{max-width:1100px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;}
  .brand{display:flex;gap:12px;align-items:center;}
  .container{max-width:1100px;margin:20px auto;padding:0 14px;}
  .panel{background:var(--card);border-radius:12px;padding:18px;box-shadow:0 6px 18px rgba(18,38,63,0.06);}
  .tabs{display:flex;gap:8px;margin-bottom:16px;}
  .tab{padding:10px 14px;border-radius:10px;background:#f3f6f9;font-weight:700;color:#20303f;cursor:pointer;}
  .tab.active{background:linear-gradient(90deg,#f8ffff,#e7f7f6);color:var(--accent);box-shadow:0 6px 12px rgba(10,70,65,0.04);}
  .upload-area{border:2px dashed #e3eef0;border-radius:10px;padding:22px;text-align:center;background:linear-gradient(180deg,rgba(255,255,255,0.6),transparent);color:var(--muted);}
  .btn{display:inline-block;padding:10px 16px;border-radius:8px;background:var(--accent);color:#fff;font-weight:700;border:none;cursor:pointer;}
  .progress-card{margin-top:18px;display:flex;gap:14px;align-items:center;background:#fff;border-radius:12px;padding:16px;border:1px solid #eef6f7;}
  .progress-left{width:72px;height:72px;display:flex;align-items:center;justify-content:center;border-radius:50%;background:linear-gradient(180deg,#f7fffc,#f0fffb);}
  .progress-circle{width:64px;height:64px;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:14px;color:var(--accent);}
  .file-meta{flex:1;}
  .controls{display:flex;gap:8px;}
  .small{font-size:13px;color:var(--muted);}
  .stats{display:flex;gap:12px;margin-top:10px;}
  .stat{background:#fbfeff;padding:10px;border-radius:9px;border:1px solid #eef6f7;flex:1;}
  .stat strong{display:block;font-size:18px;}
  .control-btn{padding:8px 10px;border-radius:8px;border:1px solid #dfeff0;background:#fff;cursor:pointer;}
  .results-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-top:16px;}
  .result-card{background:linear-gradient(180deg,#fff,#fbfeff);border-radius:12px;padding:14px;border:1px solid #eef6f7;}
  .download{padding:8px 12px;border-radius:8px;background:linear-gradient(180deg,var(--accent),#007b6f);color:#fff;text-decoration:none;font-weight:700;}
</style>
</head>
<body>
<header>
  <div class="topbar">
    <div class="brand">
      <div style="width:44px;height:44px;border-radius:8px;background:linear-gradient(180deg,var(--accent),#007b6f);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:900;">N+</div>
      <div>
        <div style="font-weight:800;">N+ AI Email Verifier</div>
        <div class="small">Local verification • Live progress • Split reports</div>
      </div>
    </div>
    <div class="small">Local mode • Saved: results_history/</div>
  </div>
</header>

<div class="container">
  <div class="panel">
    <div class="tabs">
      <div class="tab active" onclick="openTab('upload')">FILE UPLOAD</div>
      <div class="tab" onclick="openTab('paste')">PASTE EMAIL LIST</div>
      <div class="tab" onclick="openTab('single')">SINGLE EMAIL</div>
      <div class="tab" onclick="openTab('integrate')">INTEGRATION</div>
    </div>

    <div id="upload">
      <form id="form_upload" action="/upload" method="post" enctype="multipart/form-data" onsubmit="startJob(event)">
        <input type="hidden" name="progressID" id="progressID">
        <div class="upload-area">
          <div style="font-weight:800;">Drag & Drop or select file</div>
          <div class="small">(.csv / .txt / .xlsx) — Name,Email</div>
          <div style="margin-top:12px;"><input type="file" name="email_file" accept=".csv" required></div>
          <div style="margin-top:12px;"><button class="btn" type="submit">Upload & Verify</button></div>
        </div>
      </form>
    </div>

    <div id="paste" style="display:none;">
      <form id="form_paste" action="/paste" method="post" onsubmit="startJob(event)">
        <input type="hidden" name="progressID" id="progressID2">
        <textarea name="email_text" rows="6" style="width:100%;padding:10px;border-radius:8px;" placeholder="Name,Email one per line or email per line" required></textarea>
        <div style="margin-top:10px;"><button class="btn" type="submit">Verify Pasted List</button></div>
      </form>
    </div>

    <div id="single" style="display:none;">
      <form id="form_single" action="/single" method="post" onsubmit="startJob(event)">
        <input type="hidden" name="progressID" id="progressID3">
        <input type="text" name="single_email" placeholder="example@domain.com" style="padding:10px;border-radius:8px;width:60%;" required>
        <div style="margin-top:10px;"><button class="btn" type="submit">Check Single Email</button></div>
      </form>
    </div>

    <div id="integrate" style="display:none;">
      <div style="padding:12px;background:#fbfeff;border-radius:8px;border:1px solid #eef6f7;">
        <div style="font-weight:800;margin-bottom:6px;">Integration</div>
        <div class="small">Manual uploads, paste lists and single checks — no external API required.</div>
      </div>
    </div>

    <div id="live_area"></div>
  </div>

  <div style="margin-top:18px;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h3 style="margin:0;">Results</h3>
      <div class="small">Showing last 10 days</div>
    </div>

    <div class="results-grid" id="results_grid">
      {% for e in history %}
        {% set total = e.total if e.total>0 else 1 %}
        {% set good_pct = (e.valid / total * 100) | round(0) %}
        {% set risky_pct = (e.catchall / total * 100) | round(0) %}
        {% set bad_pct = (e.invalid / total * 100) | round(0) %}
        <div class="result-card">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div style="font-weight:800;">{{ e.filename }}</div>
              <div class="small">{{ e.completed }} • id: {{ e.id }}</div>
            </div>
            <div style="text-align:right;">
              <div class="small">Total</div><div style="font-weight:800">{{ e.total }}</div>
            </div>
          </div>

          <div style="display:flex;gap:8px;margin-top:12px;">
            <div style="flex:1;padding:10px;border-radius:8px;border:1px solid #eef6f7;background:#fff;">
              <div class="small">Good</div>
              <div style="font-weight:800">{{ good_pct }}% <span class="small">({{ e.valid }})</span></div>
            </div>
            <div style="flex:1;padding:10px;border-radius:8px;border:1px solid #eef6f7;background:#fff;">
              <div class="small">Risky</div>
              <div style="font-weight:800">{{ risky_pct }}% <span class="small">({{ e.catchall }})</span></div>
            </div>
            <div style="flex:1;padding:10px;border-radius:8px;border:1px solid #eef6f7;background:#fff;">
              <div class="small">Bad</div>
              <div style="font-weight:800">{{ bad_pct }}% <span class="small">({{ e.invalid }})</span></div>
            </div>
          </div>

          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;">
            <div class="small">Google Hosted: <strong>{{ e.googlehosted }}</strong></div>
            <div style="display:flex;gap:8px;align-items:center;">
              <a class="download" href="/download/{{ e.excel }}">Download</a>
              <button onclick="deleteResult('{{ e.excel }}')" 
                style="border:none;background:#ffeaea;color:#a60000;padding:6px 10px;border-radius:6px;cursor:pointer;">
                🗑️
              </button>
            </div>
          </div>
        </div>
      {% endfor %}
    </div>
  </div>
</div>

<script>
function openTab(id){
  document.getElementById('upload').style.display='none';
  document.getElementById('paste').style.display='none';
  document.getElementById('single').style.display='none';
  document.getElementById('integrate').style.display='none';
  document.getElementById(id).style.display='block';
  let tabs = document.getElementsByClassName('tab');
  for(let t of tabs) t.classList.remove('active');
  for(let t of tabs){
    if(t.innerText.replace(/\\s+/g,'').toUpperCase().includes(id.toUpperCase())){ t.classList.add('active'); break; }
  }
}

function startJob(evt){
  evt.preventDefault();
  const form = evt.currentTarget;
  const pid = Math.random().toString(36).slice(2,10);
  let h = form.querySelector('input[type=hidden]');
  if(h) h.value = pid;
  const data = new FormData(form);
  fetch(form.action, { method: 'POST', body: data }).then(res => res.text()).then(()=>{
    showLiveCard(pid, data.get('email_file') ? data.get('email_file').name : (data.get('single_email') || 'Pasted List'));
    pollProgress(pid);
  }).catch(err=>{ alert('Upload failed: '+err); });
}

function showLiveCard(pid, filename){
  const live = document.getElementById('live_area');
  live.innerHTML = `
    <div class="progress-card" id="card_${pid}">
      <div class="progress-left">
        <div class="progress-circle" id="circle_${pid}">0%</div>
      </div>
      <div class="file-meta">
        <div style="font-weight:800;" id="name_${pid}">${filename}</div>
        <div class="small" id="meta_${pid}">${new Date().toLocaleString()}</div>
        <div class="stats">
          <div class="stat"><div class="small">Verified</div><strong id="verified_${pid}">0</strong></div>
          <div class="stat"><div class="small">In queue</div><strong id="queue_${pid}">0</strong></div>
          <div class="stat"><div class="small">ETA</div><strong id="eta_${pid}">--</strong></div>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:8px;">
        <button class="control-btn" id="pause_${pid}" onclick="pauseJob('${pid}')">Pause</button>
        <button class="control-btn" id="resume_${pid}" onclick="resumeJob('${pid}')" style="display:none;">Resume</button>
        <button class="control-btn" id="stop_${pid}" onclick="stopJob('${pid}')" style="background:#ffefef;border-color:#ffd6d6;color:#a60d0d;">Stop</button>
      </div>
    </div>`;
}

function pollProgress(pid){
  fetch('/progress/'+pid).then(r=>r.json()).then(data=>{
    if(!data || Object.keys(data).length===0) {
      setTimeout(()=>pollProgress(pid), 800);
      return;
    }
    const pct = data.percent || 0;
    const verified = data.verified || 0;
    const queue = data.queue || 0;
    document.getElementById('circle_'+pid).innerText = Math.round(pct)+'%';
    if(document.getElementById('verified_'+pid)) document.getElementById('verified_'+pid).innerText = verified;
    if(document.getElementById('queue_'+pid)) document.getElementById('queue_'+pid).innerText = queue;
    if(pct >= 100 || data.state === 'stopped'){
      setTimeout(()=>{ location.reload(); }, 1200);
      return;
    }
    setTimeout(()=>pollProgress(pid), 1000);
  }).catch(()=>{ setTimeout(()=>pollProgress(pid), 1200); });
}

function pauseJob(pid){ fetch('/control/'+pid+'/pause'); }
function resumeJob(pid){ fetch('/control/'+pid+'/resume'); }
function stopJob(pid){ if(confirm('Stop this verification?')) fetch('/control/'+pid+'/stop'); }

function deleteResult(file){
  if(!confirm('Delete this result?')) return;
  fetch('/delete/'+file, {method:'DELETE'}).then(r=>r.json()).then(res=>{
    if(res.ok){ location.reload(); }
    else{ alert('Delete failed'); }
  });
}
</script>
</body>
</html>
"""

# -------- helpers --------
def clean_tmp():
    if os.path.exists(WORK_FOLDER):
        shutil.rmtree(WORK_FOLDER, ignore_errors=True)
    os.makedirs(WORK_FOLDER, exist_ok=True)

def read_history():
    ledger = os.path.join(HISTORY_FOLDER, "history.json")
    if not os.path.exists(ledger):
        return []
    try:
        with open(ledger, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def write_history(data):
    ledger = os.path.join(HISTORY_FOLDER, "history.json")
    try:
        with open(ledger, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_history(days=10):
    data = read_history()
    cutoff = datetime.now() - timedelta(days=days)
    filtered = []
    for h in sorted(data, key=lambda x: x.get("completed", ""), reverse=True):
        try:
            if datetime.strptime(h['completed'], '%Y-%m-%d_%H-%M-%S') >= cutoff:
                filtered.append(h)
        except Exception:
            filtered.append(h)
    return filtered

@app.route('/')
def home():
    return render_template_string(page_html, history=load_history(), now_year=datetime.now().year)

@app.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('email_file')
    pid = request.form.get('progressID') or (request.form.get('progressID') if 'progressID' in request.form else None)
    if not pid:
        pid = threading.current_thread().name + "_" + datetime.now().strftime("%s")
    if not f or f.filename == '':
        return render_template_string(page_html, history=load_history(), message="Please choose a file.", now_year=datetime.now().year)
    clean_tmp()
    path = os.path.join(WORK_FOLDER, f.filename); f.save(path)
    with progress_lock:
        progress_status[pid] = {"percent": 0, "verified": 0, "queue": 0, "start_time": datetime.now().isoformat(), "eta_seconds": None, "state": "running", "status_text": "Queued"}
    with task_control_lock:
        task_control[pid] = {"state": "running"}
    threading.Thread(target=verify_task, args=(path, f.filename, pid), daemon=True).start()
    return render_template_string(page_html, history=load_history(), message="Verification started...", now_year=datetime.now().year)

@app.route('/paste', methods=['POST'])
def paste():
    data = request.form.get('email_text', '').strip()
    pid = request.form.get('progressID') or (request.form.get('progressID2') if 'progressID2' in request.form else None)
    if not pid:
        pid = threading.current_thread().name + "_" + datetime.now().strftime("%s")
    if not data:
        return render_template_string(page_html, history=load_history(), message="No emails pasted.", now_year=datetime.now().year)
    clean_tmp()
    path = os.path.join(WORK_FOLDER, "Pasted.csv")
    rows = []
    for i, l in enumerate(data.splitlines()):
        if not l.strip(): continue
        p = [x.strip() for x in l.split(',') if x.strip()]
        name = p[0] if len(p) > 1 and '@' not in p[0] else f"User{i+1}"
        email = p[-1]
        rows.append({'Name': name, 'Email': email})
    try:
        with open(path, 'w', newline='', encoding='utf-8') as fcsv:
            w = csv.DictWriter(fcsv, fieldnames=['Name', 'Email'])
            w.writeheader()
            w.writerows(rows)
    except Exception as ex:
        return f"Failed to write pasted file: {ex}", 500

    with progress_lock:
        progress_status[pid] = {"percent": 0, "verified": 0, "queue": 0, "start_time": datetime.now().isoformat(), "eta_seconds": None, "state": "running", "status_text": "Queued"}
    with task_control_lock:
        task_control[pid] = {"state": "running"}
    threading.Thread(target=verify_task, args=(path, "Pasted.csv", pid), daemon=True).start()
    return render_template_string(page_html, history=load_history(), message="Verification started...", now_year=datetime.now().year)

@app.route('/single', methods=['POST'])
def single():
    email = request.form.get('single_email', '').strip()
    pid = request.form.get('progressID') or (request.form.get('progressID3') if 'progressID3' in request.form else None)
    if not pid:
        pid = threading.current_thread().name + "_" + datetime.now().strftime("%s")
    if not email:
        return render_template_string(page_html, history=load_history(), message="No email entered.", now_year=datetime.now().year)
    clean_tmp()
    path = os.path.join(WORK_FOLDER, "SingleEmail.csv")
    try:
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['Name', 'Email'])
            w.writeheader()
            w.writerow({'Name': 'Single', 'Email': email})
    except Exception as ex:
        return f"Failed to write single file: {ex}", 500

    with progress_lock:
        progress_status[pid] = {"percent": 0, "verified": 0, "queue": 0, "start_time": datetime.now().isoformat(), "eta_seconds": None, "state": "running", "status_text": "Queued"}
    with task_control_lock:
        task_control[pid] = {"state": "running"}
    threading.Thread(target=verify_task, args=(path, "SingleEmail.csv", pid), daemon=True).start()
    return render_template_string(page_html, history=load_history(), message="Verification started...", now_year=datetime.now().year)

def verify_task(csv_path, filename, pid):
    """
    Calls check_email.main(csv_path, progress_id=pid, orig_filename=filename).
    Expected return: (stats_dict, excel_bytes_io)
    check_email should update app.progress_status[pid] while running if desired.
    """
    try:
        stats, excel_data = check_email.main(csv_path, progress_id=pid, orig_filename=filename)
    except Exception as ex:
        stats = {"valid": 0, "invalid": 0, "catchall": 0, "googlehosted": 0, "total": 0}
        excel_data = BytesIO()
        with open(os.path.join(HISTORY_FOLDER, "error.log"), "a", encoding="utf-8") as ef:
            ef.write(f"{datetime.now().isoformat()} - verify_task error for {filename}: {repr(ex)}\\n")

    # Save output workbook
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = filename.replace('.csv','').replace(' ', '_')
    file_out = f"{timestamp}_{safe_name}.xlsx"
    try:
        with open(os.path.join(HISTORY_FOLDER, file_out), "wb") as f:
            if hasattr(excel_data, "getbuffer"):
                f.write(excel_data.getbuffer())
            else:
                f.write(excel_data.read())
    except Exception:
        pass

    # Update ledger
    history = read_history()
    entry = {
        "id": (history[-1]['id'] + 1) if history else 1,
        "filename": filename,
        "completed": timestamp,
        "valid": int(stats.get("valid", 0)),
        "invalid": int(stats.get("invalid", 0)),
        "catchall": int(stats.get("catchall", 0)),
        "googlehosted": int(stats.get("googlehosted", 0)),
        "total": int(stats.get("total", (stats.get('valid', 0) + stats.get('invalid', 0) + stats.get('catchall', 0)))),
        "excel": file_out
    }
    history.append(entry)
    write_history(history)

    # finalize progress
    with progress_lock:
        if pid in progress_status:
            progress_status[pid].update({"percent": 100, "verified": entry["valid"], "queue": 0, "state": "finished", "eta_seconds": 0, "status_text": "Completed"})
        else:
            progress_status[pid] = {"percent": 100, "verified": entry["valid"], "queue": 0, "state": "finished", "eta_seconds": 0, "status_text": "Completed"}

@app.route('/progress/<pid>')
def progress(pid):
    with progress_lock:
        data = progress_status.get(pid, {})
    return jsonify(data or {})

@app.route('/control/<pid>/pause')
def control_pause(pid):
    with task_control_lock:
        task_control[pid] = {"state": "paused"}
    with progress_lock:
        if pid in progress_status:
            progress_status[pid]["state"] = "paused"
    return jsonify({"ok": True})

@app.route('/control/<pid>/resume')
def control_resume(pid):
    with task_control_lock:
        task_control[pid] = {"state": "running"}
    with progress_lock:
        if pid in progress_status:
            progress_status[pid]["state"] = "running"
    return jsonify({"ok": True})

@app.route('/control/<pid>/stop')
def control_stop(pid):
    with task_control_lock:
        task_control[pid] = {"state": "stopped"}
    with progress_lock:
        if pid in progress_status:
            progress_status[pid]["state"] = "stopped"
    return jsonify({"ok": True})

@app.route('/download/<excel>')
def download(excel):
    path = os.path.join(HISTORY_FOLDER, excel)
    if not os.path.exists(path): return "Not found", 404
    return send_file(path, as_attachment=True, download_name=excel, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/delete/<excel>', methods=['DELETE'])
def delete_result(excel):
    # remove ledger entry
    history = read_history()
    new_history = [h for h in history if h.get("excel") != excel]
    write_history(new_history)
    # remove file
    fpath = os.path.join(HISTORY_FOLDER, excel)
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
        except Exception:
            pass
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
