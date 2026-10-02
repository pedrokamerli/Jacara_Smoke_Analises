import copy
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd

from jacare_analytics.customer_directory import prepare_customer_directory
from jacare_analytics.forecast_archive import compare_projection
from jacare_analytics.source_files import collect_uploads,logical_name
from jacare_analytics.upload_jobs import REQUIRED


class SeptemberImportTests(unittest.TestCase):
    def test_real_export_names(self):
        names={'Todos os pedidos Data de Abertura [01-01-2026 - 30-09-2026].xlsx':'orders',
               'Historico_Itens_Vendidos de 01-01-26 à 30-09-26.xlsx':'items',
               '99food.xlsx':'food99','relatorio ifood.xlsx':'ifood_report',
               'Lista-Clientes 01-10-26.xlsx':'customers'}
        for name,role in names.items(): self.assertEqual(logical_name(name),role)
        self.assertEqual(REQUIRED,{'orders','items'})
        self.assertIsNone(logical_name('senha.xlsx'))
        self.assertIsNone(logical_name('Produtos mais vendidos.xlsx'))

    def test_comparison_same_days_missing_is_not_zero_and_forecast_immutable(self):
        projection={'predictions':[{'date':f'2026-09-{day:02d}','prediction':10,'scheduled_open':True} for day in range(1,5)]}
        before=copy.deepcopy(projection)
        actual=pd.DataFrame({'date':['2026-09-01','2026-09-02','2026-09-03','2026-09-04'],
            'paid_orders':[20,10,None,2],'amount_received_brl':[200,100,None,20],
            'has_source_records':[True,True,False,True]})
        scores,compared,chart=compare_projection(projection,actual,'paid_orders')
        self.assertEqual(scores['comparable_days'],2)
        self.assertEqual(scores['actual_comparable'],30)
        self.assertEqual(scores['actual_observed_month'],32)
        self.assertEqual(scores['mae'],5)
        self.assertAlmostEqual(scores['wape'],1/3)
        self.assertAlmostEqual(scores['bias_pct'],-1/3)
        self.assertEqual(scores['missing_scheduled_open_days'],1)
        self.assertTrue(pd.isna(chart.loc['2026-09-03','Realizado']))
        self.assertEqual(projection,before)

    def test_customer_directory_excludes_contacts_and_ambiguous_identity(self):
        rows=[('Nome','Telefone Principal','Endereço'),('Cliente A','11987654321','privado'),
              ('Cliente B','11987654321','privado'),('Cliente C','11912345678','privado')]
        sheet=SimpleNamespace(reset_dimensions=lambda:None,iter_rows=lambda **kwargs:iter(rows))
        book=SimpleNamespace(sheetnames=['Sheet'],close=lambda:None)
        class Book:
            sheetnames=['Sheet']
            def __getitem__(self,key): return sheet
            def close(self): pass
        with patch('jacare_analytics.customer_directory.load_workbook',return_value=Book()):
            frame,metadata=prepare_customer_directory(b'fixture','a'*32)
        self.assertEqual(set(frame.columns),{'customer_key','customer_name'})
        self.assertEqual(len(frame),1)
        self.assertEqual(metadata['ambiguous_identifiers_omitted'],1)
        self.assertNotIn('11912345678',frame.to_json())

    def test_actual_private_rar_without_public_fixture(self):
        source=Path(__file__).resolve().parents[1]/'dashboard att setembro.rar'
        if not source.exists(): self.skipTest('Arquivo real não faz parte do Git')
        bundle=collect_uploads([(source.name,source.read_bytes())],updated_dates=True)
        self.assertEqual(set(bundle),{'orders','items','food99','ifood_report','customers'})
        self.assertNotIn('customer_directory',bundle)

    def test_invalid_rar_rejected(self):
        with self.assertRaises(ValueError): collect_uploads([('invalid.rar',b'not-a-rar')],updated_dates=True)

    def test_rar_path_traversal_blocked_before_native_reader(self):
        member=SimpleNamespace(filename='../Todos os pedidos.xlsx',file_size=1,file_redir=None,is_symlink=lambda:False,is_dir=lambda:False)
        class Archive:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def needs_password(self): return False
            def volumelist(self): return ['package.rar']
            def infolist(self): return [member]
        with patch('rarfile.RarFile',return_value=Archive()),patch('jacare_analytics.source_files.subprocess.Popen',side_effect=AssertionError('Não executar leitor nativo')):
            with self.assertRaisesRegex(ValueError,'caminho'): collect_uploads([('bad.rar',b'fixture')],updated_dates=True)


if __name__=='__main__': unittest.main()
