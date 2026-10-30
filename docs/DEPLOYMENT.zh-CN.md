# 双门店点餐系统部署指南

[English](DEPLOYMENT.md) | 简体中文 · [返回 README](<../README (中文).md>)

本指南使用 Docker Compose 部署本仓库的 PostgreSQL、FastAPI 和 Nginx，涵盖首次安装、核验、更新及备份。三套 Vue 应用共用后端和数据库，Nginx 通过固定的内部 Host 映射选择门店。

## 1. 准备主机与源码

Linux 服务器需要 Git、Docker Engine、Docker Compose v2、OpenSSL 和 curl。macOS 或 Windows 本地开发可使用 Docker Desktop，在兼容的 POSIX shell 中运行这些命令。除非另有说明，命令都从仓库根目录执行。如果 Docker 需要提权，请统一在 Docker 命令前加 `sudo`。

```bash
git clone https://github.com/JackieHe12345/dual-store-takeout-ordering-system.git
cd dual-store-takeout-ordering-system
```

仓库的 `nginx/html/` 已包含三套生产构建文件，直接部署这些文件无需在主机安装 Python 或 Node.js；后端镜像自带 Python 3.12。构建时需要连接镜像仓库和 Python 包源，当前 Docker 配置使用腾讯镜像源。

修改前端源码后，需要使用符合锁文件要求的 Node.js（Node 20 的 `20.19+` 版本，或 `22.12+`），重新构建三套应用：

```bash
npm ci
npm run build
```

构建先执行 TypeScript 检查，再将顾客端、员工端和总管理端分别写入对应的 `nginx/html/` 目录。应将生成文件与对应源码版本一起保留。

## 2. 创建私有配置

```bash
./scripts/bootstrap-env.sh
```

脚本读取 `.env.example`，创建权限为 `600` 的 `.env`，分别生成数据库密码、JWT 密钥和三个初始账号密码，并把数据库密码同时写入 `POSTGRES_PASSWORD` 和 `DATABASE_URL`。脚本不会打印密码，也不会覆盖已有 `.env`；更新现有安装时应保留原文件。

启动前，用本机编辑器打开 `.env`。本地核验或在宿主机配置 HTTPS 反向代理时，可使用：

```dotenv
NGINX_BIND_ADDRESS=127.0.0.1
NGINX_PORT=8080
```

下文示例使用 `http://127.0.0.1:8080`。仓库原始默认值是 **`0.0.0.0:80`**，会在主机所有网卡发布 HTTP。请明确选择需要的监听地址和端口；使用其他端口时，相应调整示例 URL。

| 配置项 | 需要保持一致的内容 |
| --- | --- |
| `POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD` | PostgreSQL 初始化值应与 `DATABASE_URL` 中的连接信息对应；Compose 内的数据库地址是 `postgres:5432`。 |
| `DATABASE_URL` | 使用 `postgresql+asyncpg://…`；手动设置的密码含 URL 保留字符时需要百分号编码，脚本生成的十六进制密码无需处理。 |
| `JWT_SECRET` | 使用生成的随机值；生产环境要求至少 32 个字符。 |
| `ADMIN_DOMAIN` | 使用现有 Nginx 配置时保留 `admin.localhost`；它是内部路由值，不是网站的公网域名。 |
| `SEED_SUPER_ADMIN_PASSWORD`、`SEED_STORE_A_PASSWORD`、`SEED_STORE_B_PASSWORD` | 只在显式初始化空业务数据库时使用。 |

Compose 为后端显式设置 `APP_ENV=production`、`ENABLE_COMMERCE=true`、`ENABLE_TEST_COMMERCE=false`，优先级高于 `.env` 中同名设置。普通实例应保留这套生产配置。将 `.env` 作为安装备份的一部分私下保存。

## 3. 启动并初始化空实例

```bash
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
docker compose exec -T backend python -m app.seed
curl --fail http://127.0.0.1:8080/Adiandiancan/api/health
```

`--wait` 会等待服务达到运行或健康状态。PostgreSQL 先启动，后端在启动 Uvicorn 前执行 `alembic upgrade head`，Nginx 等待后端健康后启动。健康接口成功时返回 `{"status":"ok","database":"ok"}`。启动失败时，先查看 `docker compose logs --tail=100 backend postgres nginx` 再重试。

种子命令是独立、显式的初始化步骤，会创建两个示例门店、顾客/员工域名绑定、角色、三个管理账号和示例菜单。CLI 会先检查 `Store`、`AdminUser`、`Category`、`Dish`：**其中任意一张表已有记录，就跳过整次初始化**。重复执行不会修复部分初始化、重建已删除门店，也不会重置已有密码。修改 `SEED_*_PASSWORD` 同样不会改变已有账号的密码。

| 账号 | 角色与登录入口 | `.env` 中的密码项 |
| --- | --- | --- |
| `admin` | 总管理员：`/neibuguanli/` | `SEED_SUPER_ADMIN_PASSWORD` |
| `staff_a` | A 店管理员：`/Adianneibuguanli/` | `SEED_STORE_A_PASSWORD` |
| `staff_b` | B 店管理员：`/Bdianneibuguanli/` | `SEED_STORE_B_PASSWORD` |

使用本机编辑器读取生成的密码，再通过管理界面替换示例门店资料、菜单、员工配置和营业策略。启用配送前，需要确认各门店的坐标、坐标系、配送半径及费用阶梯；位置未确认或费用未配置时，配送不可用。

## 4. 打开并核验五个入口

| 页面 | 本地 URL | 内部 API `Host` |
| --- | --- | --- |
| A 店点餐 | [打开](http://127.0.0.1:8080/Adiandiancan/) | `shop-a.localhost` |
| B 店点餐 | [打开](http://127.0.0.1:8080/Bdiandiancan/) | `shop-b.localhost` |
| A 店管理 | [打开](http://127.0.0.1:8080/Adianneibuguanli/) | `staff-a.localhost` |
| B 店管理 | [打开](http://127.0.0.1:8080/Bdianneibuguanli/) | `staff-b.localhost` |
| 总管理 | [打开](http://127.0.0.1:8080/neibuguanli/) | `admin.localhost` |

根地址只显示入口提示。请使用完整路径并保留末尾斜杠。内部 `.localhost` 名称不需要配置公网 DNS，Nginx 会在转发 API 时设置它们。例如，`/Adiandiancan/api/menu` 会转换为 `/api/menu`，并携带 `Host: shop-a.localhost`。现有 Nginx 配置对裸 `/api/` 请求返回 `404`。

检查公共菜单和能力接口：

```bash
curl --fail http://127.0.0.1:8080/Adiandiancan/api/menu
curl --fail http://127.0.0.1:8080/Bdiandiancan/api/menu
curl --fail http://127.0.0.1:8080/Adiandiancan/api/commerce/capabilities
```

这套生产配置应返回 `enabled=true`、`is_test=false`、`payment_enabled=false`。公共菜单无需员工登录；会员操作使用独立的门店会话，管理操作则校验 JWT 身份、角色/权限及门店或总管理员范围。

仓库还提供验收脚本：

```bash
docker compose exec -T backend python < scripts/verify-live.py
```

这里通过标准输入传入脚本，因为后端镜像没有复制 `scripts/` 目录。脚本检查五个页面、数据库健康、能力、两店菜单、管理权限，以及 A 店令牌经 B 店入口访问时被拒绝的行为。它依赖原始 `admin`、`staff_a`、`staff_b` 账号和容器环境中对应的种子密码；修改账号或门店名称后，可能需要调整脚本。虽然脚本头部标注“read-only”，登录仍会更新账号的 `last_login_at`；它不会创建订单。最终成功标记为 `LIVE_ACCEPTANCE_PASSED`。

## 5. 持久化与公网访问

| 组件 | 职责与存储 |
| --- | --- |
| `postgres` | PostgreSQL 16；命名卷 `postgres_data` 持久保存数据库文件。 |
| `backend` | 容器内 8000 端口的 FastAPI；执行 Alembic 迁移，将上传图片写入 `/app/media/uploads`。 |
| `nginx` | 唯一发布端口的服务；提供三套静态应用并代理其 API 路径。 |
| `media_uploads` | FastAPI 可写；Nginx 以只读方式挂载到 `/usr/share/nginx/html/media/uploads`。 |
| `nginx/html/` | 绑定挂载的静态应用和内置菜品图片；Nginx 通过 `/media/` 提供媒体。 |

数据库和后端端口没有发布到宿主机。Compose 默认项目名为 `takeaway`；启动第二套独立实例时，应选择不同项目名和主机端口。项目名改变，也会改变 Compose 选择的命名卷。

使用 `docker compose stop` 暂停服务，使用 `docker compose up -d --wait` 恢复。普通 `docker compose down` 会保留命名卷；删除卷的操作（包括 `down -v`）会删除数据库和媒体持久数据，不属于更新流程。

公网服务需要自行配置域名、DNS、TLS 证书和 HTTPS 反向代理。代理运行在 Docker 宿主机时，可以将前述回环地址作为上游。应完整转发五个应用路径**以及 `/media/`**，不要剥离路径前缀，内层 Nginx 继续保留固定内部 `Host` 映射。代理位于另一台主机时，需要使用它能够访问且访问范围受限的监听地址。仓库没有提供证书自动申请或可直接使用的 HTTPS server 配置。

完成部署不会接通支付服务。订单仍为 `UNPAID`，在线支付仍关闭，`real_revenue_cents` 仍为 `0`；更改部署配置不能实现支付发起、回调或退款。

## 6. 备份与恢复安排

应一起保留 PostgreSQL 数据库、上传媒体、私有 `.env` 和精确的源码/构建版本。备份期间暂停应用写入和图片上传，以得到一致的恢复材料。以下命令在**仓库外**创建私有备份；确认每一步成功后再继续：

```bash
umask 077
mkdir -p ../takeaway-backups
chmod 700 ../takeaway-backups
takeaway_backup_dir="$(mktemp -d ../takeaway-backups/manual-XXXXXXXX)"
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$takeaway_backup_dir/database.dump"
docker compose exec -T postgres pg_restore --list < "$takeaway_backup_dir/database.dump" > "$takeaway_backup_dir/database-index.txt"
docker compose exec -T backend tar -C /app/media -czf - uploads > "$takeaway_backup_dir/uploads.tar.gz"
cp .env "$takeaway_backup_dir/environment.private"
git rev-parse HEAD > "$takeaway_backup_dir/source-commit.txt"
git archive --format=tar.gz HEAD > "$takeaway_backup_dir/source.tar.gz"
tar -tzf "$takeaway_backup_dir/uploads.tar.gz" > "$takeaway_backup_dir/uploads-index.txt"
```

`git archive` 只保存已提交的 `HEAD`；安装所需的本地配置或生成资源改动需要另外保存。完成后，将恢复材料复制到权限受限的持久存储。列出 PostgreSQL 或 tar 归档内容，只说明文件可读，不代表恢复已成功。

[`scripts/backup-live.sh`](../scripts/backup-live.sh) 可作为匹配 Linux 环境中的另一种方式：它要求非交互式 `sudo -n docker` 可用，并依赖 `sha256sum`，输出位于仓库内的 `backups/`。当前 `.gitignore` **没有忽略该目录**，其中 `environment.private` 含有凭据，暂存 Git 改动前应先把备份移到仓库外。该脚本选取的源码包遗漏了 `package-lock.json`、`.env.example` 等文件，仍需另外保留完整源码版本。

仓库没有自动恢复脚本。先在另一份源码目录演练，使用不同 Compose 项目名、新卷和不同的回环端口。将数据库归档恢复到隔离的 PostgreSQL，将 `uploads/` 恢复到其媒体卷，并保证后端 `app` 用户可写，再配置匹配的私有环境。使用对应应用版本启动，检查迁移后，核验两店菜单、账号、媒体和门店隔离。不要对恢复后的数据库执行种子初始化。应以数据库备份加隔离恢复验证作为恢复依据，不要先在运行中的实例尝试恢复命令。

## 7. 更新已有实例

更新前记录正在运行的提交、完成备份，并审阅迁移、依赖、Nginx 和环境配置的变化。保留现有 `.env`、项目名和命名卷；更新源码前先处理或保存本地改动。

跟踪本仓库 `main` 分支的安装可以使用：

```bash
git pull --ff-only
docker compose config --quiet
docker compose up -d --build --wait
docker compose exec -T nginx nginx -t
docker compose restart nginx
curl --fail http://127.0.0.1:8080/Adiandiancan/api/health
```

前端源码变化而没有对应生成资源时，先重新构建 Vue 应用再重启。后端启动会执行待应用的迁移；重启 Nginx 会加载绑定挂载配置的改动。之后重复第 4 节的公共检查和适用的账号检查，并查看两店界面。普通更新不需要执行种子命令。

切回旧应用提交不会撤销数据库迁移。应根据实际迁移变化安排回滚；需要时，先在隔离环境恢复匹配的数据库/媒体备份，再切换服务。

## 8. 常见问题

| 现象 | 检查方式 |
| --- | --- |
| 提示 `.env` 已存在 | 初始化脚本在保护现有配置；有目的地编辑原文件，不要重新生成整套凭据。 |
| 拉取镜像或安装 Python 包失败 | 检查腾讯镜像仓库和包源的连通性；按所在环境检查镜像地址和 Dockerfile 的 `PIP_INDEX_URL`。 |
| 后端不健康或 Nginx 返回 `502` | 查看后端和 PostgreSQL 日志中的连接、生产密钥及 Alembic 错误，确认 `DATABASE_URL` 与实际数据库凭据一致。 |
| 修改 `POSTGRES_PASSWORD` 未生效 | 官方镜像的初始化配置不会重置已有数据库角色密码；需要协调实际数据库密码和连接字符串的变更。 |
| 菜单返回 `404` | 使用完整门店入口，确认首次种子初始化以及对应门店/域名绑定已启用。 |
| 管理接口返回 `401` 或 `403` | 检查账号密码、令牌有效期、启用状态、角色，以及是否使用了正确门店或总管理入口。 |
| 无法配送 | 确认门店坐标与坐标系、位置确认状态、配送半径和费用阶梯。 |
| 迁移安装后图片丢失 | 同时恢复内置 `nginx/html/media/` 文件和 `media_uploads` 卷，保留 `/media/` 代理路径。 |
| 找不到 API 文档 | 生产配置关闭 FastAPI 文档页面，现有 Nginx 也不代理裸 `/docs` 路径。 |

应用行为、测试和请求流程图请见 [README](<../README (中文).md>)。
