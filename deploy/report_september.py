"""Relatório confidencial da previsão congelada; nunca publicar sua saída no Git."""
import argparse,hashlib,json
from pathlib import Path
import duckdb
import pandas as pd
from jacare_analytics.forecast_archive import compare_projection

parser=argparse.ArgumentParser()
parser.add_argument('--data',type=Path,default=Path('/app/data'))
args=parser.parse_args()
data=args.data
root=data.parent
manifest=json.loads((data/'current_run.json').read_text())
new=json.loads((root/manifest['forecast_metrics']).read_text())
saved=[json.loads(file.read_text()) for file in (data/'forecast_archive').glob('*.json')]
origin=next(entry for entry in saved if entry['source_end']=='2026-08-19')
old=origin['metrics']
old_path=root/'data/runs'/origin['run_id']/'ml/forecast_metrics.json'
assert hashlib.sha256(old_path.read_bytes()).hexdigest()==origin['metrics_sha256']
report={'source_end':manifest['source_end'],'original_source_end':origin['source_end'],'original_forecast_unchanged':True,'targets':{}}
with duckdb.connect(str(root/manifest['warehouse']),read_only=True) as db:
    actual=db.execute("select sale_date as date,paid_orders,amount_received_brl,has_source_records from analytics.fct_daily_sales where sale_date between '2026-09-01' and '2026-09-30' order by 1").df()
    for target,entry in old['targets'].items():
        projection=entry['monthly_projection']
        assert projection['month']=='2026-09'
        scores,compared,chart=compare_projection(projection,actual,target)
        selected=new['targets'][target]['selected_model']
        refreshed=new['targets'][target]
        report['targets'][target]={**scores,'original_model':entry['selected_model'],'original_full_month_projection':projection['summary']['predicted_total'],'new_selected_model':selected,'new_holdout':refreshed['candidate_models'][selected]['holdout'],'new_candidates':{name:row['holdout'] for name,row in refreshed['candidate_models'].items()},'new_statistical_gate':refreshed['statistical_gate_passed'],'new_projection_month':refreshed['monthly_projection']['month'],'new_projection_total':refreshed['monthly_projection']['summary']['predicted_total']}
    names=pd.read_parquet(root/manifest['customer_directory'])
    keys=set(db.execute('select distinct customer_key from analytics.stg_orders where customer_key is not null').df().customer_key)
    report['customer_directory']={'private_names':len(names),'identities_matching_orders':int(names.customer_key.isin(keys).sum()),'contacts_persisted':False}
    report['september_paid_orders_on_monday']=db.execute("select count(*) from analytics.stg_orders where order_status='paid' and opened_at>='2026-09-01' and opened_at<'2026-10-01' and dayofweek(opened_at)=1").fetchone()[0]
report['source_availability']=manifest['source_availability']
output=(root/manifest['forecast_metrics']).with_name('september_validation.json')
output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
output.chmod(0o400)
print(json.dumps(report,ensure_ascii=False,allow_nan=False))
