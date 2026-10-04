#!/usr/bin/env python3
"""Create owned-device packages and formulas from one dependency/install manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def render_formula(template, manifest, url=None, checksum=None):
    dependencies = '\n'.join('  depends_on ' + json.dumps(dep) for dep in manifest['dependencies'])
    build = manifest['build']
    build_command = "ulimit -t 120; exec make -j2 -C " + build['directory'] + " CFLAGS='-Wall -O2 -D_GNU_SOURCE'"
    install = ['  def install', '    system "bash", "-c", ' + json.dumps(build_command),
               '    libexec.install ' + json.dumps(build['binary']) + ' => ' + json.dumps(build['install_name'])]
    for target, paths in manifest['install'].items():
        install.append('    ' + target + '.install ' + ', '.join(json.dumps(path) for path in paths))
    install.append('    rewrite_shebang detected_python_shebang, ' + ', '.join(
        'libexec/' + json.dumps(path) for path in manifest['python_shebangs']))
    install.append('  end')
    template = re.sub(r'  depends_on .*?(?=\n  def install)', dependencies + '\n', template, flags=re.S)
    template = re.sub(r'  def install\n.*?\n  end', '\n'.join(install), template, count=1, flags=re.S)
    template = re.sub(r'^  license .*$', '  license all_of: ' + json.dumps(manifest['licenses']), template, flags=re.M)
    if url is not None:
        template = re.sub(r'^  url .*$', '  url ' + json.dumps(url), template, flags=re.M)
        template = re.sub(r'^  sha256 .*$', '  sha256 ' + json.dumps(checksum), template, flags=re.M)
    return template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--local', action='store_true', help='local tarball + file URL (default)')
    mode.add_argument('--url', help='fetch published archive and hash those exact URL bytes')
    args = parser.parse_args()
    version = args.version.removeprefix('v')
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?', version):
        parser.error('version must be a semantic version')
    manifest = json.loads((ROOT / 'packaging/manifest.json').read_text())
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    archive = dist / ('mtk-v' + version + '.tar.gz')
    if args.url:
        if not args.url.startswith('https://'):
            parser.error('--url must use HTTPS')
        subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
                        '--max-time', '60', '--max-filesize', '52428800', '-o', str(archive), args.url], check=True)
        url = args.url
    else:
        paths = [path for group in manifest['install'].values() for path in group]
        paths += manifest['source_files']
        paths += ['packaging/manifest.json', 'mtk.md', 'justfile', 'README.md', 'LICENSE']
        # Validate every installed helper before creating any partial package.
        for path in paths:
            if not (ROOT / path).is_file():
                parser.error('missing package file: ' + path)
        with tarfile.open(archive, 'w:gz') as tar:
            for path in paths:
                tar.add(ROOT / path, arcname='mtk-' + version + '/' + path, recursive=False)
        url = archive.as_uri()
    # A formula must install every manifested file from its exact URL archive.
    required = {path for group in manifest['install'].values() for path in group}
    required.update(manifest['source_files'])
    found = set()
    prefix = None
    total_size = 0
    # Stream metadata with explicit limits; never extract downloaded archives.
    with tarfile.open(archive, 'r|gz') as tar:
        for count, member in enumerate(tar, 1):
            total_size += member.size
            if count > 10000 or total_size > 104857600:
                parser.error('archive exceeds package validation limits')
            root, _, path = member.name.partition('/')
            if prefix is None:
                prefix = root
            if root != prefix:
                parser.error('archive must contain one package root')
            if path in required:
                if not member.isfile():
                    parser.error('archive package file is not regular: ' + path)
                found.add(path)
    missing = required - found
    if missing:
        parser.error('archive missing package file: ' + sorted(missing)[0])
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    formula = render_formula((ROOT / 'Formula/mtk.rb').read_text(), manifest, url, checksum)
    (dist / 'mtk.rb').write_text(formula)
    print('Archive: ' + str(archive))
    print('SHA256: ' + checksum)
    print('Formula: ' + str(dist / 'mtk.rb'))


if __name__ == '__main__':
    main()
