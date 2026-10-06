"""Tests for ingestion semantics that can materially change ML evidence."""
import tempfile
import unittest
import zipfile
from pathlib import Path
import polars as pl
from notebooks.support.external_dataset_intake import COLS, NUMERIC, kind, minute_and_stats, run_intake, read_daily


def frame(n=60):
    return pl.DataFrame({
        'recorded_at': pl.datetime_range(__import__('datetime').datetime(2026, 7, 1),
                                        __import__('datetime').datetime(2026, 7, 1, 0, 0, n-1), interval='1s', eager=True),
        **{c: [float(210) if c.startswith('Hp') else float(20) if c.startswith(('Lp','Temp')) else float(0)] * n
           if c in NUMERIC else [('Run' if c == 'Status' else 'On' if c.startswith('Status') else 'Off')] * n for c in COLS}
    })


class IntakeTests(unittest.TestCase):
    def test_blank_line_firmware_preamble(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'2026_07_01.txt'
            raw=frame(3).with_columns(pl.col('recorded_at').dt.strftime('%H:%M:%S').alias('Time')).drop('recorded_at')
            p.write_text('1.6.8\n\n'+raw.write_csv().replace('\n','\n\n'),encoding='utf-8')
            result,date=read_daily(p)
            self.assertEqual(result.height,3)
            self.assertEqual(date,'2026-07-01')
            p.write_bytes(('1.6.8\n'+raw.write_csv()).replace('\n','\r\r\n').encode('utf-8'))
            result,date=read_daily(p)
            self.assertEqual(result.height,3)

    def test_mixed_sv_or_insufficient_samples_cannot_be_quality_minute(self):
        raw=frame()
        minute,_=minute_and_stats(raw,'017','synthetic')
        self.assertTrue(minute['intake_quality_minute'].all())
        mixed=raw.with_row_index().with_columns(pl.when(pl.col('index')==30).then(pl.lit('On')).otherwise(pl.col('SV_1')).alias('SV_1')).drop('index')
        minute,_=minute_and_stats(mixed,'017','synthetic')
        self.assertFalse(minute.filter(pl.col('module')==1)['intake_quality_minute'].item())
        minute,_=minute_and_stats(raw.head(54),'017','synthetic')
        self.assertFalse(minute['intake_quality_minute'].any())
        minute,_=minute_and_stats(raw.head(55),'017','synthetic')
        self.assertTrue(minute['intake_quality_minute'].all())

    def test_full_overlap_and_conflict_are_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); ext=root/'external'; primary=root/'primary'; out=root/'output'
            (ext/'MX017').mkdir(parents=True)
            partition=primary/'machine=017/year=2026/month=07/day=01'
            partition.mkdir(parents=True)
            original=frame(3)
            original.head(2).write_parquet(partition/'part.parquet')
            changed=original.with_row_index().with_columns(pl.when(pl.col('index')==1).then(pl.lit(170.)).otherwise(pl.col('Hp_2nd_1')).alias('Hp_2nd_1')).drop('index')
            changed.with_columns(pl.col('recorded_at').dt.strftime('%H:%M:%S').alias('Time')).drop('recorded_at').write_csv(ext/'MX017/2026_07_01.csv')
            summary=run_intake(ext,primary,out)
            self.assertEqual(summary['overlap_rows'],2)
            self.assertEqual(summary['overlap_equal_rows'],1)
            self.assertEqual(summary['overlap_conflict_rows'],1)
            self.assertEqual(summary['novel_rows'],1)
            self.assertFalse(summary['train_enabled'])

    def test_special_sources_are_not_daily_training(self):
        for filename in ['2026_08_09.txt.tmp.123', '2026_07_01_Static.txt', '2026_07_01_12_00_00_PM.txt', '2026_05.zip']:
            self.assertNotEqual(kind(Path(filename)), 'DAILY_TELEMETRY')

    def test_archive_daily_preserves_virtual_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); ext=root/'external'; primary=root/'primary'; out=root/'output'
            (ext/'MX057').mkdir(parents=True); primary.mkdir()
            raw=frame(3).with_columns(pl.col('recorded_at').dt.strftime('%H:%M:%S').alias('Time')).drop('recorded_at')
            with zipfile.ZipFile(ext/'MX057/2026_07.zip','w') as archive:
                archive.writestr('2026_07/2026_07_01.csv',raw.write_csv())
            summary=run_intake(ext,primary,out)
            self.assertEqual(summary['archive_daily_audited'],1)
            self.assertEqual(summary['novel_rows'],3)
            manifest=pl.read_csv(out/'source_manifest.csv')
            self.assertIn('MX057/2026_07.zip::2026_07/2026_07_01.csv',manifest['source'].to_list())


if __name__=='__main__':
    unittest.main()
