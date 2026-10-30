#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
env_file="$project_dir/.env"
example_file="$project_dir/.env.example"

if [ -e "$env_file" ]; then
    echo "已存在 $env_file；为避免覆盖密钥，未做修改。" >&2
    exit 1
fi

umask 077
db_password=$(openssl rand -hex 24)
jwt_secret=$(openssl rand -hex 32)
admin_password=$(openssl rand -base64 24 | tr -d '/+=')
staff_a_password=$(openssl rand -base64 24 | tr -d '/+=')
staff_b_password=$(openssl rand -base64 24 | tr -d '/+=')

sed \
    -e "s|replace-with-a-long-random-password|$db_password|g" \
    -e "s|replace-with-at-least-32-random-characters|$jwt_secret|g" \
    -e "s|^SEED_SUPER_ADMIN_PASSWORD=.*|SEED_SUPER_ADMIN_PASSWORD=$admin_password|" \
    -e "s|^SEED_STORE_A_PASSWORD=.*|SEED_STORE_A_PASSWORD=$staff_a_password|" \
    -e "s|^SEED_STORE_B_PASSWORD=.*|SEED_STORE_B_PASSWORD=$staff_b_password|" \
    "$example_file" > "$env_file"

echo "已生成 $env_file（权限 600）。"
echo "初始账号：admin、staff_a、staff_b；密码仅保存在该文件中。"
