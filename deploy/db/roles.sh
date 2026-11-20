#!/usr/bin/env bash
# Đồng bộ PostgreSQL trong container (service db) với hai secret DATABASE_MIGRATOR_URL và DATABASE_URL.
# deploy.sh gửi hai URL qua stdin, mỗi URL một dòng, rồi chạy script này trong container db ở mỗi lần
# deploy. Chạy lại bao nhiêu lần cũng được: tạo role và database nếu chưa có, đặt lại mật khẩu theo
# secret (xoay mật khẩu chỉ cần đổi secret rồi deploy), quyền như mục "Database managed" của README.
set -euo pipefail

read -r migrator_url
read -r runtime_url

urldecode() { printf '%b' "${1//%/\\x}"; }

# postgresql+psycopg://<user>:<mật khẩu>@<host>:<cổng>/<database>?<tham số> → user, password, dbname
parse() {
  local rest=${1#*://}
  local credentials=${rest%%@*} location=${rest#*@}
  user=$(urldecode "${credentials%%:*}")
  password=$(urldecode "${credentials#*:}")
  dbname=${location#*/}
  dbname=${dbname%%\?*}
}

parse "$migrator_url"
MIG_USER=$user MIG_PW=$password DB_NAME=$dbname
parse "$runtime_url"
RT_USER=$user RT_PW=$password
if [[ $dbname != "$DB_NAME" ]]; then
  echo "DATABASE_URL và DATABASE_MIGRATOR_URL phải trỏ cùng một database" >&2
  exit 1
fi
if [[ $MIG_USER == "$RT_USER" ]]; then
  echo "DATABASE_URL và DATABASE_MIGRATOR_URL phải dùng hai role khác nhau" >&2
  exit 1
fi
export MIG_USER MIG_PW RT_USER RT_PW DB_NAME
export PGOPTIONS='-c client_min_messages=warning'   # bỏ NOTICE "already exists" khi chạy lại

# Giá trị vào psql qua \getenv rồi :'biến' (psql tự đặt dấu nháy), không ghép chuỗi SQL bằng tay.
psql -v ON_ERROR_STOP=1 -q -U postgres -d postgres <<'SQL'
\getenv mig_user MIG_USER
\getenv mig_pw MIG_PW
\getenv rt_user RT_USER
\getenv rt_pw RT_PW
\getenv db_name DB_NAME

SELECT format('CREATE ROLE %I LOGIN', :'mig_user')
 WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'mig_user') \gexec
SELECT format('CREATE ROLE %I LOGIN', :'rt_user')
 WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'rt_user') \gexec
ALTER ROLE :"mig_user" LOGIN PASSWORD :'mig_pw';
ALTER ROLE :"rt_user" LOGIN PASSWORD :'rt_pw';

SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'mig_user')
 WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db_name') \gexec

\connect :"db_name"
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS unaccent;
GRANT CONNECT ON DATABASE :"db_name" TO :"rt_user";
GRANT USAGE ON SCHEMA public TO :"rt_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"mig_user" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"rt_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"mig_user" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"rt_user";
SQL

echo "Role $MIG_USER, $RT_USER và database $DB_NAME đã đồng bộ."
