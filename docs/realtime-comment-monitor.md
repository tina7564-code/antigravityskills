# 实时社交媒体评论监听系统设计

## 流程

社交媒体 API -> 评论监听器(Webhook + Polling) -> asyncio 队列 -> 情感分析/毒性识别 -> 风险分级 -> 回复建议 -> PostgreSQL 持久化 -> 高风险告警(邮件/企业微信)

## 模块说明

- `listener.py` / `app/listener.py`
  - Webhook 接收评论
  - 轮询多账号评论
  - Redis 去重 + 游标缓存
- `processor.py` / `app/processor.py`
  - 文本清洗
  - 情感分析（Transformers/OpenAI/mock）
  - 风险分级（高/中/低）
- `reply_generator.py` / `app/reply_generator.py`
  - 按风险等级输出不同回复策略
- `alert_system.py` / `app/alert_system.py`
  - 高风险触发邮件/企业微信通知
- `main.py` / `app/main.py`
  - FastAPI 启动入口
  - 异步 worker 并发处理
  - 账号管理、Webhook、评论查询接口

## 关键能力

- 异步并发：`asyncio.Queue + N workers`
- 多账号支持：`accounts` 表 + 轮询并发抓取
- 情绪识别返回标准结构：

```json
{
  "sentiment": "positive/neutral/negative",
  "score": 0.0,
  "toxicity_score": 0.0
}
```

- 风险逻辑：
  - 高风险：负面 + toxicity>0.7 + 攻击词
  - 中风险：明显负面
  - 低风险：普通抱怨/轻度负面

## Docker 部署（推荐：爪云/Claw Cloud）

### 1) 准备配置

```bash
cp .env.example .env
```

生产环境至少修改：
- `WEBHOOK_SECRET`
- `OPENAI_API_KEY`（如果 `SENTIMENT_PROVIDER=openai`）
- `SMTP_*` / `WECOM_WEBHOOK_URL`（如果要告警）

### 2) 本地验证

```bash
docker compose up --build -d
docker compose ps
curl http://127.0.0.1:8000/healthz
```

### 3) 爪云部署要点

- 选择 **Docker Compose** 部署方式，直接上传本仓库。
- 在平台环境变量中配置 `.env` 中的同名变量。
- 对外仅暴露 `api` 的 `8000` 端口（`db` 和 `redis` 保持内网）。
- 如果平台提供托管 PostgreSQL/Redis，可将 `DATABASE_URL`、`REDIS_URL` 改为托管地址，并移除 compose 里的 `db/redis` 服务。

## 典型 API

- 创建账号: `POST /accounts`
- 评论 Webhook: `POST /webhook/comments`（Header: `X-Webhook-Secret`）
- 评论列表: `GET /comments`
