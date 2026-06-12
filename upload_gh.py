#!/usr/bin/env python3
import base64, json, subprocess, sys, os, time

REPO = "procmeans/hk-stock-bubble-vat"
BASE = "deploy_repo"

# (本地相对路径, 仓库内路径)
# 注意:不要上传 data/manifest.json 和港股日度 json——线上 Actions 每天在更新它们,
# 本地副本是旧的,覆盖会丢数据。
FILES = [
    ("index.html", "index.html"),
    ("fetch_a.py", "fetch_a.py"),
    (".github/workflows/update.yml", ".github/workflows/update.yml"),
    ("data/manifest_a.json", "data/manifest_a.json"),
    ("data/a-2026-06-12.json", "data/a-2026-06-12.json"),
]

def gh(args, inp=None):
    return subprocess.run(["gh"]+args, input=inp, capture_output=True, text=True)

def get_sha(path):
    r = gh(["api", f"/repos/{REPO}/contents/{path}", "--jq", ".sha"])
    return r.stdout.strip() if r.returncode==0 and r.stdout.strip() else None

def put(local, path):
    content = base64.b64encode(open(os.path.join(BASE, local), "rb").read()).decode()
    body = {"message": f"add {path}", "content": content}
    sha = get_sha(path)
    if sha: body["sha"] = sha
    tmp = f"/tmp/_body_{path.replace('/','_')}.json"
    json.dump(body, open(tmp, "w"))
    for i in range(5):
        r = gh(["api", "--method", "PUT", f"/repos/{REPO}/contents/{path}", "--input", tmp])
        if r.returncode==0 and '"content"' in r.stdout:
            print(f"  ✓ {path}"); return True
        time.sleep(3)
    print(f"  ✗ {path}: {(r.stderr or r.stdout)[:160]}"); return False

ok=0
for local, path in FILES:
    if put(local, path): ok+=1
print(f"上传完成 {ok}/{len(FILES)}")
