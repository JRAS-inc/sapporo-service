#!/usr/bin/env bash
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "$0")" && pwd)"
while [[ "${PACKAGE_ROOT}" != "/" && ! -f "${PACKAGE_ROOT}/setup.py" ]]; do
    PACKAGE_ROOT="$(dirname "${PACKAGE_ROOT}")"
done

cd "${PACKAGE_ROOT}"

isort "${PACKAGE_ROOT}" --skip "${PACKAGE_ROOT}/tests/resources" --check
