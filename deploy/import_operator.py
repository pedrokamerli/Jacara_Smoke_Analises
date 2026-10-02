"""Envio pelo operador via SSH; não cria nem falsifica sessão Google."""
import argparse
from datetime import date
from pathlib import Path
from jacare_analytics.source_files import collect_uploads
from jacare_analytics.upload_jobs import _enqueue_job,atomic_json,timestamp
from jacare_analytics.upload_worker import process_job

parser=argparse.ArgumentParser()
parser.add_argument('archive',type=Path)
parser.add_argument('--cutoff',required=True,type=date.fromisoformat)
parser.add_argument('--qa',action='store_true')
args=parser.parse_args()
bundle=collect_uploads([(args.archive.name,args.archive.read_bytes())],updated_dates=True)
jobs=Path('/imports')
if args.qa:
    if not Path('/qa_upload_test_marker').is_file(): raise ValueError('Somente QA isolado')
    atomic_json(jobs/'heartbeat.json',{'at':timestamp()})
job=_enqueue_job(jobs,bundle,args.cutoff,actor='ssh-authorized-operator')
print('job_id='+job,flush=True)
if args.qa:
    process_job(Path('/app'),jobs,Path('/app/data'),job,Path('/worker-secrets/hmac.key'),raise_errors=True)
    print('QA concluído com aprovação e previsão anterior preservada',flush=True)
