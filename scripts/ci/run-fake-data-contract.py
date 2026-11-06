"""Run only the fake-data contract, split into bounded CI batches."""
import argparse
import os
import subprocess
import sys

FILES = [
    'content/tests/management/test_fake_data_contract.py',
    'content/tests/management/test_fake_data_qa_cases.py',
    'content/tests/management/test_fake_data_operations.py',
    'secure_links/tests/test_folder_seed.py',
    'accounts/tests/billing/test_seed_context.py',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shard', type=int, required=True)
    parser.add_argument('--shards', type=int, default=4)
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        parser.error('Fake-data automated validation runs exclusively in CI.')
    if not 1 <= args.shard <= args.shards:
        parser.error('Invalid shard.')
    collected = subprocess.run(
        [sys.executable, '-m', 'pytest', '-o', 'addopts=', '--collect-only', '-q', '--no-cov', *FILES],
        capture_output=True, text=True,
    )
    if collected.returncode:
        print(collected.stdout)
        print(collected.stderr, file=sys.stderr)
        return collected.returncode
    nodes = [line.strip() for line in collected.stdout.splitlines()
             if line.startswith(tuple(FILES)) and '::' in line]
    selected = nodes[args.shard - 1::args.shards]
    if not selected:
        raise RuntimeError('No contract tests collected for this shard.')
    print(f'Fake-data contract: {len(nodes)} collected, {len(selected)} in this shard.', flush=True)
    for offset in range(0, len(selected), 20):
        result = subprocess.run([
            sys.executable, '-m', 'pytest', '--no-cov', '-v', '--tb=short',
            f'--junitxml=fake-data-{args.shard}-{offset // 20}.xml', *selected[offset:offset + 20],
        ])
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
