"""Merge a Git release into the existing ZIP installation without overwrites."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from dotenv import dotenv_values
from .one_way_update import ROOT, BACKUP

def main():
    assert (BACKUP/'before.json').exists(), 'Completed backup required'
    checkout=ROOT/'runtime/release_git'
    old=(BACKUP/'previous_revision.txt').read_text().strip()
    paths=subprocess.check_output(['git','-C',str(checkout),'diff','--name-only',old,'HEAD'],text=True).splitlines()
    originals=BACKUP/'application_files'
    originals.mkdir(exist_ok=True)
    prepared={}
    for name in paths:
        target=ROOT/name
        if target.exists():
            saved=originals/name
            saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,saved)
        if name=='.env':continue
        remote=(checkout/name).read_bytes()
        try:base=subprocess.check_output(['git','-C',str(checkout),'show',old+':'+name],stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:base=b''
        normalize=lambda b:b.replace(b'\r\n',b'\n')
        local=target.read_bytes() if target.exists() else b''
        if normalize(local)==normalize(base) or normalize(local)==normalize(remote):
            prepared[name]=remote
        elif base and normalize(local).endswith(normalize(base)):
            prepared[name]=normalize(local)[:-len(normalize(base))]+remote
        else:
            scratch=BACKUP/'merge_scratch'
            scratch.mkdir(exist_ok=True)
            for label,content in [('local',local),('base',base),('remote',remote)]:
                (scratch/label).write_bytes(normalize(content))
            result=subprocess.run(['git','merge-file','-p',str(scratch/'local'),str(scratch/'base'),str(scratch/'remote')],capture_output=True)
            if result.returncode:raise RuntimeError('Manual merge needed: '+name)
            prepared[name]=result.stdout
    before=dotenv_values(ROOT/'.env')
    raw=(ROOT/'.env').read_text(encoding='utf-8')
    lines=raw.splitlines()
    key='HT9046MX_DETECTOR_BRIDGE_ENABLED'
    found=False
    for i,line in enumerate(lines):
        if line.split('=',1)[0].strip()==key:
            lines[i]=key+'=false';found=True
    if not found:lines.append(key+'=false')
    for name,content in prepared.items():
        path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    (ROOT/'.env').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    after=dotenv_values(ROOT/'.env')
    assert {k:v for k,v in before.items() if k!=key}=={k:v for k,v in after.items() if k!=key}
    result=dict(commit=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip(),
                merged_files=list(prepared),config_changed=[key],preserved_server_fixes=True)
    (BACKUP/'applied_release.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
