import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from id_roundtrip import AuditError, audit


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = self.root / 'a.csv'
        self.b = self.root / 'b.csv'

    def put(self, a, b=None):
        self.a.write_bytes(a.encode('utf-8'))
        self.b.write_bytes((a if b is None else b).encode('utf-8'))

    def check(self, **kw):
        return audit(self.a, self.b, keys=['key'], fields=['id'], **kw)

    def test_reorder_is_safe_and_hashes_record_bytes(self):
        self.put('key,id\na,001\nb,12345678901234567\n', 'id,key\n12345678901234567,b\n001,a\n')
        result = self.check()
        self.assertTrue(result['ok'])
        self.assertNotEqual(result['reference_sha256'], result['observed_sha256'])
        self.assertEqual(result['matched_rows'], 2)

    def test_corruptions_are_never_coerced(self):
        for before, after in [('001','1'),('12345678901234567','12345678901234500'),
                              ('SEPT2','2-Sep'),('1E10','10000000000'),('NA',''),
                              ('a','A'),('a','a '),('é','e\u0301')]:
            with self.subTest(before=before):
                self.put(f'key,id\nx,{before}\n', f'key,id\nx,{after}\n')
                r = self.check()
                self.assertFalse(r['ok'])
                self.assertEqual(len(r['changed_cells']), 1)

    def test_unknown_key_is_missing_plus_added_not_guessed(self):
        self.put('key,id\nx,001\n','key,id\ny,001\n')
        r=self.check()
        self.assertEqual(r['missing_reference_records'],[1])
        self.assertEqual(r['added_observed_records'],[1])
        self.assertEqual(r['changed_cells'],[])
        self.assertFalse(r['ok'])

    def test_blank_identifiers_fail_even_unchanged(self):
        self.put('key,id\nx, \n')
        self.assertFalse(self.check()['ok'])

    def test_literal_null_names_preserved(self):
        for value in ['NA','NaN','NULL','None','0']:
            self.put(f'key,id\nx,{value}\n')
            self.assertTrue(self.check()['ok'])

    def test_malformed_inputs_rejected(self):
        for data in ['', 'key,id\n','key,id,id\nx,a,b\n', 'key,\nx,a\n',
                     'key,id\nx,a,b\n','key,id\nx\n','key,id\nx,"a\n',
                     'key,id\nx,a\nx,b\n','key,id\n ,a\n', 'key,id\nx,a\x00\n',
                     'key,id\n\nx,a\n','other,id\nx,a\n']:
            with self.subTest(data=data):
                self.put(data)
                with self.assertRaises(AuditError): self.check()

    def test_invalid_encoding(self):
        self.put('key,id\nx,a\n')
        self.a.write_bytes(b'\xff')
        with self.assertRaises(AuditError): self.check()

    def test_bom_and_quoted_multiline(self):
        self.put('\ufeffkey,id\r\nx,"A\r\nB"\r\n')
        self.assertTrue(self.check()['ok'])

    def test_delimiters(self):
        self.put('key;id\nx;001\n','key\tid\nx\t001\n')
        self.assertTrue(self.check(delimiter=';', observed_delimiter='\t')['ok'])
        with self.assertRaises(AuditError): self.check(delimiter='|')
        for invalid in ['', False, 0, []]:
            with self.assertRaises(AuditError): self.check(observed_delimiter=invalid)

    def test_composite_key_not_concatenated(self):
        self.put('key,second,id\na,bc,001\nab,c,002\n')
        r=audit(self.a,self.b,keys=['key','second'],fields=['id'])
        self.assertTrue(r['ok'])
        self.assertEqual(r['matched_rows'],2)

    def test_invalid_column_specifications(self):
        self.put('key,id\nx,a\n')
        for keys,fields in [([],['id']),(None,['id']),(7,['id']),('key',['id']),(['key'],[]),(['key'],['key']),
                            (['key','key'],['id']),(['key'],['id','id']),(['key'],[' '])]:
            with self.subTest(keys=keys,fields=fields):
                with self.assertRaises(AuditError): audit(self.a,self.b,keys=keys,fields=fields)

    def test_no_values_in_report(self):
        self.put('key,id\nsecret-key,secret-id\n','key,id\nsecret-key,other-secret\n')
        text=json.dumps(self.check())
        self.assertNotIn('secret',text)

    def test_cli_codes_and_stable_inputs(self):
        for expected, observed in [(0,'key,id\nx,001\n'),(1,'key,id\nx,1\n'),(2,'key,id\nx\n')]:
            self.put('key,id\nx,001\n',observed)
            before=(self.a.read_bytes(),self.b.read_bytes())
            p=subprocess.run([sys.executable,'-m','id_roundtrip',str(self.a),str(self.b),
                              '--key','key','--field','id'],capture_output=True,text=True)
            self.assertEqual(p.returncode,expected,p.stderr)
            self.assertEqual(before,(self.a.read_bytes(),self.b.read_bytes()))
            if expected != 2: json.loads(p.stdout)

    def test_randomized_order_and_mutations(self):
        import random
        rng=random.Random(42)
        rows=[[f'row-{i}',f'{i:08d}'] for i in range(200)]
        def dump(items):
            stream=io.StringIO(newline='')
            writer=csv.writer(stream)
            writer.writerow(['key','id']);writer.writerows(items)
            return stream.getvalue()
        shuffled=rows.copy();rng.shuffle(shuffled)
        self.put(dump(rows),dump(shuffled))
        self.assertTrue(self.check()['ok'])
        shuffled[0]=[shuffled[0][0],'corrupt']
        self.put(dump(rows),dump(shuffled))
        self.assertEqual(len(self.check()['changed_cells']),1)


if __name__ == '__main__': unittest.main()
