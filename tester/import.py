#!/usr/bin/env python3
"""
import.py — Import unit tests from S3 into local test runner.

Steps implemented:
  1) Process CLI args (overrides env defaults).
  2) Create local directories: tests/ and tmp/tests/.
  3) Download objects from S3 prefix to tmp/tests/.
  4) Unzip any *.zip found in tmp/tests/ into tests/.
  5) Copy other non-zip files from tmp/tests/ into tests/.
  6) Log activity; capture and report errors.
"""
from __future__ import annotations

# stdlib
import argparse
import logging
import os
import shutil
import sys
import zipfile
from typing import List

# third-party
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# constants ----------------------------------------------------------------------------
ISO_TIMESTAMP='%Y-%m-%d %H:%M:%S'
LOG_FORMAT='%(asctime)s | %(levelname)s | %(message)s'


# Global S3 client (lazy)
_s3_client = None


# Defaults from environment ------------------------------------------------------------
# can be overridden via CLI args
AWS_REGION = os.environ.get('AWS_REGION', 'ap-southeast-1')
S3_BUCKET = os.environ.get('S3_BUCKET', 'mcfpipe')
TESTS_S3_DIR = os.environ.get('TESTS_S3_DIR', 'apps/tests')
TESTS_LOCAL_DIR = os.environ.get('TESTS_LOCAL_DIR', 'tests')
TMP_TESTS_DIR_DEFAULT = os.environ.get('TMP_TESTS_DIR', 'tmp/tests')
LOG_FILE = os.environ.get('IMPORT_LOG_FILE', 'import.log')
LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'INFO')

# --------------------------------------------------------------------------------------
# Logging
def init_logging(log_file: str = LOG_FILE, verbose: bool = True, logging_level: str = 'DEBUG') -> logging.Logger:
    logger = logging.getLogger('tests_import')
    if logger.handlers:
        return logger  # already configured

    if logging_level == 'WARNING':
        logger.setLevel(logging.WARNING)
    elif logging_level == 'DEBUG':
        logger.setLevel(logging.DEBUG)
    elif logging_level == 'DEBUG':
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(LOG_FORMAT, ISO_TIMESTAMP)
    return logger

# --------------------------------------------------------------------------------------
# Filesystem helpers
def create_dirs(tmp_dir: str, tests_dir: str, logger: logging.Logger) -> None:
    for d in {tmp_dir, tests_dir}:
        try:
            os.makedirs(d, exist_ok=True)
            logger.info(f'Ensured directory exists: {d}.')
        except Exception as e:
            logger.exception(f'Failed to create directory: {d}.')
            raise


def clean_dir(path: str, logger: logging.Logger) -> None:
    if os.path.exists(path):
        logger.info(f'Cleaning directory: {path}')
        shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)

# --------------------------------------------------------------------------------------
# S3 helpers
def s3_client(region: str) -> boto3.client:
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3', region_name=region)
    return _s3_client


def s3_list_dir(bucket: str, s3_dir: str, region: str, logger: logging.Logger) -> List[str]:
    """Return a list of S3 object keys under the given prefix (excluding 'folders')."""
    cli = s3_client(region)
    prefix = s3_dir.strip('/') + '/' if not s3_dir.endswith('/') else s3_dir
    logger.info(f'Listing s3://{bucket}/{prefix}')
    keys: List[str] = []
    try:
        paginator = cli.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get('Contents', []):
                key = item['Key']
                # skip 'directory' placeholders
                if key.endswith('/'):
                    continue
                keys.append(key)
    except (BotoCoreError, ClientError) as e:
        logger.exception(f'Error listing S3 directory s3://{bucket}/{prefix}')
        raise
    return keys


def s3_obj_download(bucket: str, key: str, dest_dir: str, region: str, logger: logging.Logger) -> str:
    """Download a single S3 object to dest_dir using its basename. Return local filepath."""
    cli = s3_client(region)
    filename = os.path.basename(key)
    local_path = os.path.join(dest_dir, filename)
    try:
        logger.info(f"Downloading s3://{bucket}/{key} -> {local_path}")
        cli.download_file(bucket, key, local_path)
    except (BotoCoreError, ClientError) as e:
        logger.exception(f'Failed to download s3://{bucket}/{key}')
        raise
    return local_path


# --------------------------------------------------------------------------------------
# Unzip and copy
def unzip_all_from(src_dir: str, dest_dir: str, logger: logging.Logger) -> None:
    for name in sorted(os.listdir(src_dir)):
        path = os.path.join(src_dir, name)
        if not os.path.isfile(path):
            continue
        if name.lower().endswith('.zip'):
            logger.info(f'Unzipping {path} -> {dest_dir}')
            try:
                with zipfile.ZipFile(path, 'r') as zf:
                    zf.extractall(dest_dir)
            except zipfile.BadZipFile:
                logger.error(f'Bad zip file: {path}')
                continue
            except Exception:
                logger.exception(f'Error unzipping: {path}')
                continue


def copy_non_zip_files(src_dir: str, dest_dir: str, logger: logging.Logger) -> None:
    for name in sorted(os.listdir(src_dir)):
        path = os.path.join(src_dir, name)
        if not os.path.isfile(path):
            continue
        if name.lower().endswith('.zip'):
            continue
        target = os.path.join(dest_dir, name)
        logger.info(f'Copying {path} -> {target}')
        try:
            shutil.copy2(path, target)
        except Exception:
            logger.exception(f"Failed to copy {path} -> {target}")
            continue

# --------------------------------------------------------------------------------------
# Core workflow
def import_files(*, bucket: str, s3_dir: str, tests_dir: str, tmp_dir: str, region: str, dry_run: bool, clean_tmp: bool, logger: logging.Logger) -> None:
    logger.info(f'importing files from S3 bucket {bucket} at location {s3_dir} ...')
    if clean_tmp:
        clean_dir(tmp_dir, logger)
    create_dirs(tmp_dir=tmp_dir, tests_dir=tests_dir, logger=logger)

    # 1) List S3 keys
    keys = s3_list_dir(bucket=bucket, s3_dir=s3_dir, region=region, logger=logger)
    if not keys:
        logger.warning('No objects found under prefix. Nothing to import.')
        return
    logger.info(f'Found {len(keys)} object(s) to download.')

    if dry_run:
        for k in keys:
            logger.info(f'[DRY-RUN] Would download: s3://{bucket}/{k}')
        return

    # 2) Download all keys to tmp_dir
    downloaded = []
    for k in keys:
        try:
            local = s3_obj_download(bucket=bucket, key=k, dest_dir=tmp_dir, region=region, logger=logger)
            downloaded.append(local)
        except Exception:
            # already logged
            continue

    # 3) Unzip *.zip to tests_dir
    unzip_all_from(tmp_dir, tests_dir, logger)

    # 4) Copy all remaining non-zip files from tmp_dir to tests_dir
    copy_non_zip_files(tmp_dir, tests_dir, logger)

    logger.info('Import complete.')


# --------------------------------------------------------------------------------------
# CLI
def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Import test files from S3 into local tests/ directory.")
    p.add_argument("--region", default=AWS_REGION, help=f"AWS region (default: {AWS_REGION})")
    p.add_argument("--bucket", default=S3_BUCKET, help=f"S3 bucket (default: {S3_BUCKET})")
    p.add_argument("--s3-dir", default=TESTS_S3_DIR, help=f"S3 prefix containing tests (default: {TESTS_S3_DIR})")
    p.add_argument("--tests-dir", default=TESTS_LOCAL_DIR, help=f"Destination tests directory (default: {TESTS_LOCAL_DIR})")
    p.add_argument("--tmp-dir", default=TMP_TESTS_DIR_DEFAULT, help=f"Temporary download directory (default: {TMP_TESTS_DIR_DEFAULT})")
    p.add_argument("--log-file", default=LOG_FILE, help=f"Log file path (default: {LOG_FILE})")
    p.add_argument("--no-verbose", action="store_true", help="Reduce console logging.")
    p.add_argument("--dry-run", action="store_true", help="List actions without downloading/copying.")
    p.add_argument("--clean-tmp", action="store_true", help="Wipe the tmp directory before import.")
    return p.parse_args(argv)


# --------------------------------------------------------------------------------------
def main(argv: List[str]) -> int:
    args = parse_args(argv)
    logger = init_logging(log_file=args.log_file, verbose=not args.no_verbose)
    logger.info("import.py starting...")
    logger.info(f"Args: region={args.region}, bucket={args.bucket}, s3_dir={args.s3_dir}, tests_dir={args.tests_dir}, tmp_dir={args.tmp_dir}, dry_run={args.dry_run}, clean_tmp={args.clean_tmp}")
    try:
        import_files(
            bucket=args.bucket,
            s3_dir=args.s3_dir,
            tests_dir=args.tests_dir,
            tmp_dir=args.tmp_dir,
            region=args.region,
            dry_run=args.dry_run,
            clean_tmp=args.clean_tmp,
            logger=logger,
        )
        logger.info('Done.')
        return 0
    except Exception:
        logger.exception('Fatal error during import.')
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
