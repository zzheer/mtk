import hashlib
import json
import os
import sys
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_local_release_manifest_and_archive_match_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkout = Path(tmp) / 'repo'
            shutil.copytree(ROOT, checkout, ignore=shutil.ignore_patterns('.git', 'dist', '__pycache__', 'target', 'node_modules'))
            original = (checkout / 'Formula/mtk.rb').read_bytes()
            proc = subprocess.run(['/bin/bash', str(checkout / 'scripts/release.sh'), '9.8.7', '--local'],
                                  capture_output=True, text=True, timeout=20)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            formula = (checkout / 'dist/mtk.rb').read_text()
            archive = checkout / 'dist/mtk-v9.8.7.tar.gz'
            self.assertIn('url "' + archive.resolve().as_uri() + '"', formula)
            self.assertIn('version "9.8.7"', formula)
            self.assertIn(hashlib.sha256(archive.read_bytes()).hexdigest(), formula)
            self.assertEqual((checkout / 'Formula/mtk.rb').read_bytes(), original)
            manifest = json.loads((checkout / 'packaging/manifest.json').read_text())
            self.assertNotIn('depends_on "cpulimit"', formula)
            self.assertIn('GPL-2.0-or-later', formula)
            for dep in manifest['dependencies']:
                self.assertIn('depends_on "' + dep + '"', formula)
            with tarfile.open(archive) as tar:
                names = set(tar.getnames())
            for paths in manifest['install'].values():
                for path in paths:
                    self.assertIn('mtk-9.8.7/' + path, names)
                    self.assertIn('"' + path + '"', formula)
            self.assertIn('libexec/mtk-output.py', formula)
            self.assertIn('libexec/mtk-runner.py', formula)
            self.assertIn('share/mtk/filters.toml', formula)

    def test_published_url_hashes_downloaded_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkout = Path(tmp) / 'repo'
            shutil.copytree(ROOT, checkout, ignore=shutil.ignore_patterns('.git', 'dist', '__pycache__', 'target', 'node_modules'))
            manifest = json.loads((checkout / 'packaging/manifest.json').read_text())
            published = Path(tmp) / 'published.tar.gz'
            with tarfile.open(published, 'w:gz') as tar:
                for path in manifest['source_files']:
                    tar.add(checkout / path, arcname='release/' + path)
                for paths in manifest['install'].values():
                    for path in paths:
                        tar.add(checkout / path, arcname='release/' + path)
            fake = Path(tmp) / 'bin'
            fake.mkdir()
            (fake / 'curl').write_text('#!/bin/bash\nwhile [[ "$1" != "-o" ]]; do shift; done\n/bin/cp "$PUBLISHED" "$2"\n')
            (fake / 'curl').chmod(0o755)
            url = 'https://example.invalid/published.tar.gz'
            proc = subprocess.run(['/bin/bash', str(checkout / 'scripts/release.sh'), '9.8.7', '--url', url],
                                  env={**os.environ, 'PATH': str(fake) + ':' + os.environ['PATH'], 'PUBLISHED': str(published)},
                                  capture_output=True, text=True, timeout=20)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            formula = (checkout / 'dist/mtk.rb').read_text()
            self.assertIn('url "' + url + '"', formula)
            self.assertIn(hashlib.sha256(published.read_bytes()).hexdigest(), formula)

    def test_just_test_parses_as_offline_local_recipe(self):
        proc = subprocess.run(['just', '--dry-run', 'test'], cwd=ROOT,
                              capture_output=True, text=True, timeout=5)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        commands = proc.stdout + proc.stderr
        self.assertIn('unittest discover', commands)
        self.assertNotIn('https://', commands)
        self.assertNotIn('/tmp/codex-just-test', commands)

    def test_extracted_package_builds_and_installs_private_cpu_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkout = Path(tmp) / 'checkout'
            shutil.copytree(ROOT, checkout, ignore=shutil.ignore_patterns('.git', 'dist', '__pycache__', 'target', 'node_modules', '*.o', 'cpulimit'))
            # Directory named cpulimit contains required sources: copy it explicitly.
            shutil.copytree(ROOT / 'vendor/cpulimit', checkout / 'vendor/cpulimit',
                            ignore=shutil.ignore_patterns('*.o', 'cpulimit', '__pycache__'))
            proc = subprocess.run(['/bin/bash', str(checkout / 'scripts/release.sh'), '9.8.7', '--local'],
                                  capture_output=True, text=True, timeout=20)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            extracted = Path(tmp) / 'extracted'
            with tarfile.open(checkout / 'dist/mtk-v9.8.7.tar.gz') as tar:
                tar.extractall(extracted, filter='data')
            source = extracted / 'mtk-9.8.7'
            manifest = json.loads((source / 'packaging/manifest.json').read_text())
            build = manifest['build']
            result = subprocess.run(['/bin/bash', '-c', "ulimit -t 120; exec make -j2 CFLAGS='-Wall -O2 -D_GNU_SOURCE'"],
                                    cwd=source / build['directory'], capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            prefix = Path(tmp) / 'installed'
            for target, paths in manifest['install'].items():
                destination = prefix / ('share/mtk' if target == 'pkgshare' else target)
                destination.mkdir(parents=True, exist_ok=True)
                for path in paths:
                    shutil.copy2(source / path, destination / Path(path).name)
            helper = prefix / 'libexec' / build['install_name']
            shutil.copy2(source / build['binary'], helper)
            isolated_home = Path(tmp) / 'home'
            isolated_home.mkdir()
            env = {**os.environ, 'HOME': str(isolated_home), 'PATH': '/usr/bin:/bin'}
            measurements = []
            for exclude in (False, True):
                output = Path(tmp) / str(exclude)
                child = ("import time; start=time.monotonic(); cpu=time.process_time(); "
                         "exec('while time.monotonic()-start < 2.5: pass'); "
                         f"open({str(output)!r}, 'w').write(str(time.process_time()-cpu))")
                code = f"import subprocess,sys; subprocess.run([sys.executable,'-c',{child!r}])"
                options = ['--cpu-limit', '15', '--time-limit', '5s', '--memory-limit', '120M']
                if exclude:
                    options.append('--exclude-children')
                result = subprocess.run([sys.executable, str(prefix / 'libexec/mtk-runner.py'), *options,
                                         '--', sys.executable, '-c', code],
                                        env=env, capture_output=True, text=True, timeout=8)
                self.assertEqual(result.returncode, 0, result.stderr)
                measurements.append(float(output.read_text()))
            self.assertGreater(measurements[1], 0.8, measurements)
            self.assertLess(measurements[0], measurements[1] * 0.7, measurements)
