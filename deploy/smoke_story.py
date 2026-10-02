"""Prova de atualização narrativa sem alterar previsões anteriores."""
import json
from pathlib import Path

root=Path('/app')
before=json.loads(Path('/before.json').read_text())
after=json.loads((root/'data/current_run.json').read_text())
assert after['quality']['all_passed'] and after['source_end']=='2026-09-30'
assert after['quality']==before['quality']
assert after['series_sha256']==before['series_sha256']
old=json.loads((root/before['forecast_metrics']).read_text())
new=json.loads((root/after['forecast_metrics']).read_text())
assert new['development_study']['production_model_changed'] is False
for target in ('paid_orders','total_received_brl'):
    for field in ('selected_model','candidate_models','monthly_projection','experimental_forecast'):
        assert new['targets'][target][field]==old['targets'][target][field]
    assert len(new['development_study']['targets'][target]['summary'])==3
assert any(json.loads(file.read_text())['source_end']=='2026-08-19' for file in (root/'data/forecast_archive').glob('*.json'))
print('Qualidade, série, modelos e previsões preservados; estudo retrospectivo presente no novo snapshot privado.')
