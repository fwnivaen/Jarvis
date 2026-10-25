"""Install optional pinned helpers only. Does not configure providers or enable flags."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PYTHON_VERSION=(3,12)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('helper',choices=('deepagents','gepa'))
    args=parser.parse_args()
    if sys.version_info[:2]!=PYTHON_VERSION:parser.error('Run with CPython 3.12 for these locks.')
    venv=ROOT/'.local'/(args.helper+'-venv')
    venv.parent.mkdir(exist_ok=True,mode=0o700)
    if venv.is_symlink():parser.error('Unsafe environment directory.')
    if not (venv/'bin/python').exists():subprocess.run([sys.executable,'-m','venv',str(venv)],check=True)
    python=str(venv/'bin/python')
    subprocess.run([python,'-m','pip','install','--require-hashes','--only-binary=:all:',
                    '-r',str(ROOT/'optional'/args.helper/'requirements.lock')],check=True)
    subprocess.run([python,'-m','pip','check'],check=True)
    print('Optional helper installed; feature activation remains off.')


if __name__=='__main__':main()
