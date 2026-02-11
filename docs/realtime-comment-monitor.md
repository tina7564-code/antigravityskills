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

## 启动方式

1. 复制环境变量：
   `cp .env.example .env`
2. Docker 启动：
   `docker compose up --build`
3. 服务地址：
   - API: `http://localhost:8000`
   - 健康检查: `GET /healthz`

## 典型 API

- 创建账号: `POST /accounts`
- 评论 Webhook: `POST /webhook/comments`（Header: `X-Webhook-Secret`）
- 评论列表: `GET /comments`
