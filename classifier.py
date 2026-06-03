"""文章分类器：优先使用 DeepSeek LLM，不可用时降级为关键词匹配"""
import json
import os
import re
import requests

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

CATEGORIES = ["科技·AI", "情感", "健康养生", "个人成长", "历史", "体制", "家居"]

# ── 关键词分类（LLM 不可用时的 fallback） ──
KEYWORD_RULES = [
    ("科技·AI", r"AI|人工智能|GPT|大模型|芯片|手机|苹果|华为|小米|特斯拉|编程|代码|开源|算法"
     r"|互联网|软件|硬件|机器人|自动驾驶|新能源|电池|半导体|无人机|卫星|航天"
     r"|ChatGPT|Claude|Copilot|模型|算力|智能|科技|数码|数据|云计算|量子|5G"
     r"|硬盘|存储|CPU|GPU|显卡|电脑|系统|服务器"),
    ("情感", r"感情|爱情|恋爱|婚姻|家庭|孩子|父母|朋友|自己|人生|活着|生活|日子"
     r"|女人|男人|夫妻|婆媳|闺蜜|情侣|相亲|离婚|结婚|出轨|分手|爱|想念|思念"),
    ("健康养生", r"健康|养生|疾病|癌症|糖尿病|高血压|减肥|运动|饮食|营养|睡眠"
     r"|中医|中药|体检|症状|治疗|预防|保健|长寿|衰老|免疫|心脏|血管|血糖|医生|医院"),
    ("个人成长", r"职场|工作|面试|跳槽|升职|薪资|中年|管理|领导|团队|效率|自律|习惯"
     r"|认知|思维|成长|学习|读书|技能|方法|底层|逻辑|赚钱|副业|搞钱|收入|认知|返贫|退休"),
    ("历史", r"历史|古代|皇帝|王朝|朝代|清朝|明朝|唐朝|宋朝|三国|民国|二战|战争"
     r"|考古|文物|遗址|古人|百年|千年|世纪|秦|汉|唐|宋|元|明|清|乾隆|康熙|史记|博物馆"),
    ("体制", r"公务员|事业编|体制|机关|党建|党性|干部|纪委|巡视|反腐|基层|政策"
     r"|编制|铁饭碗|上岸|考公|遴选|衙门|官僚|党组织|党委|人大|政协|政府工作"),
    ("家居", r"家居|装修|家具|收纳|软装|硬装|厨房|卫生间|卧室|客厅|阳台|玄关"
     r"|布局|风水|家电|窗帘|灯具|地板|瓷砖|壁纸|设计|改造|翻新|空间"),
]


def _classify_by_keyword(title: str) -> str:
    for cat, pattern in KEYWORD_RULES:
        if re.search(pattern, title):
            return cat
    return "其他"


def _classify_batch_by_llm(titles: list[str]) -> list[str]:
    """用 DeepSeek 批量分类（一次 API 调用处理所有标题）"""
    cat_list = "、".join(CATEGORIES)

    prompt = (
        f"将以下文章标题分类到最匹配的一个类别。只能从 [{cat_list}] 中选择，都不匹配选「其他」。\n"
        "返回纯 JSON 对象，key 是序号，value 是类别名。不要解释。\n\n"
        + "\n".join(f"t{i}: {t}" for i, t in enumerate(titles))
    )

    resp = requests.post(
        DEEPSEEK_API_URL,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 500,
        },
        timeout=30,
    )

    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    # 解析 JSON 响应
    try:
        result_map = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[^}]+\}", content)
        if match:
            result_map = json.loads(match.group())
        else:
            return [_classify_by_keyword(t) for t in titles]

    return [result_map.get(f"t{i}", "其他") for i in range(len(titles))]


def classify_articles(articles: list[dict]) -> list[dict]:
    """对文章列表进行分类，就地修改 quality_tags 字段"""
    if not articles:
        return articles

    titles = [a["title"] for a in articles]

    # 尝试 DeepSeek 分类
    if DEEPSEEK_API_KEY:
        try:
            categories = _classify_batch_by_llm(titles)
            for art, cat in zip(articles, categories):
                art["quality_tags"] = [cat]
                art["ai_classified"] = True
            return articles
        except Exception:
            pass  # 失败，降级为关键词

    # 关键词 fallback
    for art in articles:
        cat = _classify_by_keyword(art["title"])
        art["quality_tags"] = [cat]
        art["ai_classified"] = False

    return articles


def analyze_viral_reasons(articles: list[dict]) -> list[dict]:
    """用 DeepSeek 分析每篇文章为什么能爆（一句话）"""
    if not DEEPSEEK_API_KEY or not articles:
        return articles

    titles_text = "\n".join(
        f"t{i}: {a['title']}" for i, a in enumerate(articles)
    )

    prompt = (
        "下面是一些公众号爆款文章标题。请分析每篇为什么会成为爆文。\n"
        "从这几个角度：情绪共鸣、信息差、好奇心缺口、身份认同、争议性、实用性。\n"
        "每篇用一句话（≤25字）回答，返回纯 JSON 对象，key 是序号，value 是分析。\n\n"
        + titles_text
    )

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
            },
            timeout=30,
        )

        content = resp.json()["choices"][0]["message"]["content"]
        try:
            result_map = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{[^}]+\}", content)
            result_map = json.loads(match.group()) if match else {}

        for i, art in enumerate(articles):
            art["viral_reason"] = result_map.get(f"t{i}", "")

    except Exception:
        for art in articles:
            art["viral_reason"] = ""

    return articles
