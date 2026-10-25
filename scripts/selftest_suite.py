#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest_suite.py — synthetic regression checks for str-fixer scripts.
Runs without committing or requiring any media/subtitle files.
"""
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'scripts'


def run_cmd(args):
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise AssertionError(f'Command failed ({proc.returncode}): {args}')
    return proc.stdout


def main():
    for name in ('fix_srt.py', 'resync_srt.py', 'extract_pgs.py'):
        path = SCRIPTS / name
        compile(path.read_bytes(), str(path), 'exec')

    run_cmd(['scripts/extract_pgs.py', '--selftest'])

    sample_text = (
        '1\r\n'
        '00:00:01,000 --> 00:00:03,000\r\n'
        '29 Ağustos 1997 günü hayatı değişti.\r\n\r\n'
        '2\r\n'
        '00:00:04,000 --> 00:00:06,000\r\n'
        'Şimdi ışık görünüyor.\r\n'
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # Case 1: CP1254 single-byte Turkish -> BOM-less UTF-8 round-trip
        cp1254_file = tmp_dir / 'cp1254.srt'
        cp1254_file.write_bytes(sample_text.encode('cp1254'))
        run_cmd(['scripts/fix_srt.py', str(cp1254_file)])
        fixed_bytes = cp1254_file.read_bytes()
        assert not fixed_bytes.startswith(b'\xef\xbb\xbf'), 'BOM must not be present'
        assert fixed_bytes.decode('utf-8') == sample_text, 'CP1254 round-trip mismatch'

        # Case 2: UTF-8 mojibake (UTF-8 read as CP1254 then re-encoded as UTF-8)
        mojibake_sample = (
            '1\r\n'
            '00:00:01,000 --> 00:00:03,000\r\n'
            '29 Ağustos 1997 günü büyük çözüm göründü.\r\n'
        )
        mojibake_file = tmp_dir / 'mojibake.srt'
        mojibake_text = mojibake_sample.encode('utf-8').decode('cp1254')
        mojibake_file.write_bytes(mojibake_text.encode('utf-8'))
        run_cmd(['scripts/fix_srt.py', str(mojibake_file)])
        assert mojibake_file.read_bytes().decode('utf-8') == mojibake_sample, 'Mojibake reversal mismatch'

    print('SELFTEST SUITE PASSED: py_compile + extract_pgs + fix_srt (cp1254 & mojibake)')


if __name__ == '__main__':
    main()
