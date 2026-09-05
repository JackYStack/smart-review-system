#!/usr/bin/env bash
set -Eeuo pipefail

case "${MYSQL_USER:-}" in
  ""|*[!A-Za-z0-9_]*)
    echo "MYSQL_USER must contain only letters, numbers, and underscores" >&2
    exit 2
    ;;
esac
case "${MYSQL_DATABASE:-}" in
  ""|*[!A-Za-z0-9_]*)
    echo "MYSQL_DATABASE must contain only letters, numbers, and underscores" >&2
    exit 2
    ;;
esac

# SQL string literals escape backslashes and single quotes. Identifiers have
# already been restricted to a conservative character set above.
escaped_password=${MYSQL_PASSWORD//\\/\\\\}
escaped_password=${escaped_password//\'/\'\'}

mysql \
  --host=mysql \
  --user=root \
  --password="${MYSQL_ROOT_PASSWORD}" \
  --default-character-set=utf8mb4 \
  --execute="CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'%' IDENTIFIED BY '${escaped_password}'; ALTER USER '${MYSQL_USER}'@'%' IDENTIFIED BY '${escaped_password}'; GRANT ALL PRIVILEGES ON \`${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'%'; FLUSH PRIVILEGES;"

echo "MySQL application account is ready."
