"""Verify the entire data bundle after copying it to a server."""
import argparse
from configuration import settings
from data_bundle import DataBundle

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root')
    args = parser.parse_args()
    root = settings(args.data_root)['data_root']
    if not root:
        parser.error('Select the data folder first with Configure data folder.cmd, or pass --data-root.')
    print('Checking all file sizes and SHA-256 checksums. This reads about 1.24 GB.', flush=True)
    bundle = DataBundle(root, verify_hashes=True)
    print(f'Verified: {bundle.bundle_id} ({len(bundle.records)} files)')

if __name__ == '__main__':
    main()
