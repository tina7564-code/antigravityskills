from app.schemas import SentimentResult


class ReplyGenerator:
    def generate(self, content: str, risk_level: str, sentiment: SentimentResult) -> str:
        if risk_level == 'high':
            return (
                '感谢反馈，我们已经记录您的问题并启动核查流程。'
                '为避免误解，请您通过私信提供订单/时间等事实信息，我们会专人跟进。'
            )

        if risk_level == 'medium':
            return (
                '感谢指出体验问题，我们理解您的感受。'
                '我们正在优化相关流程，也欢迎补充细节帮助我们更快定位。'
            )

        return (
            '谢谢你的留言！我们会持续优化体验。'
            '如果你愿意，也可以告诉我们你最希望改进的点。'
        )
