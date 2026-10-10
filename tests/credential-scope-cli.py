"""Invalid registration scope must fail before touching credential files or Docker."""
import pathlib,subprocess,sys,tempfile
with tempfile.TemporaryDirectory() as directory:
 p=pathlib.Path(directory)/'never-created'
 base=[sys.executable,'service/register_tenant.py','--tenant','synthetic','--operator','synthetic@example.test','--credential-file',str(p)]
 for name,flags in [('missing scope',[]),('ambiguous scope',['--tenant-wide','--project','synthetic-project'])]:
  result=subprocess.run(base+flags,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  assert result.returncode==2,name
  assert not p.exists(),'invalid scope must not create a credential'
  print('PASS '+name+' rejected before credential access')
