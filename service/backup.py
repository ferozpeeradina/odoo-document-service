"""Encrypted pg_dump, isolated validation restore; active database never overwritten."""
import base64, hashlib, json, os, pathlib, secrets, subprocess, sys
from cryptography.fernet import Fernet
ROOT=pathlib.Path(__file__).resolve().parents[1]
CMD=['docker','compose','--env-file','/dev/null','-f','compose.service.yaml']
if os.environ.get('SERVICE_BACKUP_PRODUCTION_RUNTIME_DIR'):
    os.environ['PRODUCTION_RUNTIME_DIR']=os.environ['SERVICE_BACKUP_PRODUCTION_RUNTIME_DIR']
    CMD+=['-f','compose.production.yaml']
CMD+=['exec','-T','db']
DB=os.environ.get('SERVICE_BACKUP_DB','document_service_test')
RUNTIME=pathlib.Path(os.environ.get('SERVICE_BACKUP_RUNTIME_DIR',str(ROOT/'service-runtime')))
def cmd(args,data=None):
    p=subprocess.run(CMD+args,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if p.returncode: raise RuntimeError('database command failed (output withheld)')
    return p.stdout
def crypt():
    key=(RUNTIME/'backup.key').read_bytes().strip()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key).digest()))
def inventory(db):
    sql="SELECT json_build_object('fileAttachments',(SELECT count(*) FROM ir_attachment WHERE store_fname IS NOT NULL),'versions',(SELECT count(*) FROM poc_version),'envelopes',(SELECT count(*) FROM poc_envelope),'operations',(SELECT count(*) FROM poc_operation),'evidence',(SELECT string_agg(evidence_hash,',' ORDER BY id) FROM poc_envelope),'pdf',(SELECT string_agg(signed_hash,',' ORDER BY id) FROM poc_envelope),'files',(SELECT count(*) FROM dms_file))"
    return json.loads(cmd(['psql','-U','odoo','-d',db,'-At','-c',sql]))
try:
    if sys.argv[1]=='backup':
        assert inventory(DB)['fileAttachments']==0,'database-only backup requires database attachment storage'
        raw=cmd(['pg_dump','-U','odoo','-d',DB,'-Fc'])
        path=pathlib.Path(sys.argv[2]); fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(crypt().encrypt(raw))
        print('PASS encrypted database backup (no keys in archive)')
    elif sys.argv[1]=='validate':
        path=pathlib.Path(sys.argv[2]); name='document_restore_validation_'+secrets.token_hex(5)
        before=inventory(DB); raw=crypt().decrypt(path.read_bytes())
        cmd(['createdb','-U','odoo',name])
        try:
            cmd(['pg_restore','-U','odoo','--no-owner','--exit-on-error','-d',name],raw)
            restored=inventory(name)
            assert restored==before,'restore inventory differs'
            # Compare actual binary records independently of saved hash fields.
            for table,cols in [('ir_attachment','id,checksum,db_datas'),('dms_file','id,name,content_binary')]:
                sql='COPY (SELECT '+cols+' FROM '+table+' ORDER BY id) TO STDOUT'
                assert cmd(['psql','-U','odoo','-d',name,'-c',sql])==cmd(['psql','-U','odoo','-d',DB,'-c',sql]),'restore binary data differs'
            assert inventory(DB)==before,'active database changed'
            (ROOT/'artifacts/backup-restore-tests.json').write_text(json.dumps(dict(result='PASS',checks=['encrypted pg_dump','isolated throwaway DB restore','matching record counts and artifact anchors','matching actual attachment bytes','active DB preserved'],validationDatabase=name),indent=2))
            print('PASS isolated encrypted backup restore; active DB preserved')
        finally:cmd(['dropdb','-U','odoo',name])
    else:raise ValueError('unknown command')
except Exception as e:
    print('FAIL backup/restore '+type(e).__name__);sys.exit(1)
