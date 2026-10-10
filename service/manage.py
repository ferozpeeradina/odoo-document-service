"""Bounded subprocess runner. Odoo output never displayed; diagnostic is exception class only."""
import pathlib, subprocess, sys, json, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
CMD=['docker','compose','--env-file','/dev/null','--profile','test','-f','compose.service.yaml']
def run(args,stdin=None,timeout=240):
    p=subprocess.run(CMD+args,cwd=ROOT,input=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if p.returncode:
        # Do not show raw output (can contain credentials, URLs or worker logs).
        print('FAIL: isolated service command '+args[0]+' exit '+str(p.returncode))
        sys.exit(1)
    print('PASS: isolated service command '+args[0])
if sys.argv[1]=='init':
    run(['up','-d','db'])
    run(['run','--rm','odoo','--config=/run/config/odoo.conf','--stop-after-init','-i','document_service','--without-demo=all'],timeout=240)
    run(['run','--rm','-T','odoo','shell','--config=/run/config/odoo.conf','--no-http'],(ROOT/'service/bootstrap.py').read_bytes())
    run(['up','-d'])
elif sys.argv[1]=='shell':
    p=subprocess.run(CMD+['exec','-T','odoo','odoo','shell','--config=/run/config/odoo.conf','--no-http'],input=pathlib.Path(sys.argv[2]).read_bytes(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if p.returncode: print('FAIL: isolated shell'); sys.exit(1)
    # Only structured marker records explicitly written by our scripts may be displayed.
    for line in p.stdout.decode(errors='replace').splitlines():
        if line.startswith('SAFE_RESULT '): print(line)
else:
    run(sys.argv[1:])
    if sys.argv[1]=='restart' and len(sys.argv)==2 or sys.argv[1]=='up' and sys.argv[2:]==['-d']:
        for _ in range(45):
            p=subprocess.run(CMD+['ps','--format','json','sealer'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
            try:
                raw=p.stdout.decode(); data=json.loads(raw); row=data[0] if isinstance(data,list) and data else data
                if row.get('Health')=='healthy': break
            except Exception: pass
            time.sleep(1)
        else: print('FAIL: bounded sealer readiness');sys.exit(1)
        print('PASS: bounded sealer readiness')
