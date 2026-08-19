# MONĒKI 经营罗盘

面向连锁餐饮运营的 Django 数据看板：审计 POS 脏数据，以真实数据库聚合驱动经营指标、经营雷达和可追溯 AI 问答。

## 三步运行

```bash
cp .env.example .env          # 填入 DEEPSEEK_API_KEY；不填也可用可靠本地解析
pip install -r requirements.txt
python manage.py migrate && python manage.py import_sales && python manage.py runserver
```

打开 <http://127.0.0.1:8000>。项目语言为简体中文，时区为 `Asia/Shanghai`。

## 架构

```text
浏览器（原生 HTML/CSS/JS）
  ├─ 看板 API ──> Django 指标服务 ──> SQLite（Sale JOIN Store/Product）
  └─ 问答 API ──> DeepSeek V4 Flash（只生成白名单查询计划）
                    └─> Django 参数校验与 ORM 工具 ──> 证据 + 确定性答案
                                      └─ 失败时本地解析器降级
CSV ──> 幂等 import_sales ──> 质量审计批次 ──> SQLite
```

选择 Django 是为了在一个可复现工程内完成模型、导入命令、HTTP API、模板和测试；SQLite 足以承载约 1.2 万行作业数据，并便于评审启动。前端不需要 Node 构建链，静态资源随应用交付。

## 数据口径与审计

- 完全重复明细去重；日期/数值不可解析、脏外键、`qty <= 0`、`amount < 0` 均隔离。
- 营业额 = 有效明细 `amount` 之和；订单数 = 去重 `order_id`；客单价 = 营业额 / 订单数。
- 同一源文件组合以 SHA-256 标识，重复执行不会重复入库。

当前数据导入审计：原始 12,131 行；有效 11,630；重复 76；日期异常 150；脏外键 46；数值异常 229（分类合计完全闭合）。

## 可信 AI

模型不能执行 SQL。它只能选择 `query_product_revenue`、`query_revenue_by_store_category`、`query_aov_trend` 等白名单工具；Django 校验参数并用 ORM 聚合。页面展示工具、筛选条件、结果和执行模式。网络失败、非法 JSON 或未知工具最多重试三次后降级；数据集外问题明确拒答。

```env
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

## 测试

```bash
python manage.py test
RUN_LLM_TESTS=1 python manage.py test  # 预留给显式网络测试；会产生 API 费用
```

测试覆盖幂等导入、脏数据审计、指标口径、三个指定问句、上下文追问、拒答、非法工具、网络降级、页面和健康检查。

## API

- `GET /api/dashboard/{summary,trend,top-products,store-comparison}`
- `GET /api/insights/radar`
- `POST /api/assistant/sessions`、`POST /api/assistant/chat`
- `DELETE /api/assistant/sessions/<uuid>`
- `GET /health/`

筛选参数使用 `start=YYYY-MM-DD&end=YYYY-MM-DD`，默认取数据最新日期向前 30 天。

## Docker

```bash
docker build -t moneki-dashboard .
docker run --rm -p 8000:8000 --env-file .env -v moneki-data:/data moneki-dashboard
```

SQLite 位于持久卷 `/data`。入口脚本会幂等执行迁移、数据导入和静态资源收集。作业开发环境为 iSH，未提供 Docker daemon，因此镜像配置经过静态检查但未在本机实际构建。

## 生产注意

作业容器为自包含演示而使用 Django `runserver`；正式公网部署应改用 Gunicorn、配置反向代理和 HTTPS，并将 `DJANGO_DEBUG=false`、随机 `DJANGO_SECRET_KEY`、准确的 `DJANGO_ALLOWED_HOSTS` 注入环境。
