import re

# ── 硬过滤：这些直接丢弃 ──

BLOCK_PATTERNS = [
    # 政务/公文
    r"关于.{2,20}的通知",
    r"(任免|任命|免去|任职|辞职|拟任)",
    r"(公告|公示|通告|通报)\s*[》\)]",
    r"(人民政府|省政府|市政府|县政府|区委|市委|省委)",
    r"(组织部|人社厅|住建局|教育局)\s*(发布|公示|公告)",
    r"(同志|职务|任前|任免|提名)",
    # 天气
    r"(天气预报|气象台|高温|暴雨|台风|寒潮|大风|雷电).{0,10}(预警|预报|提醒)",
    r"(℃|摄氏度).{0,10}(预警|来了|到达)",
    # 纯营销/PR
    r"(活动预告|直播预告|即将开始|倒计时\d)",
    r"(正式更名|品牌合作|战略合作|签约仪式|盛大开业)",
    # 平台公告
    r"(微信公众平台|平台公告|功能更新|版本更新).{0,10}(通知|公告)",
]

# ── 质量加分关键词 ──

POSITIVE_SIGNALS = {
    "high": [  # +3 分
        r"为什么|为啥|为何",
        r"如何|怎么[做办]|怎样",
        r"深度[解析析读]|万字[解分]析|干货",
        r"方法[论法]|实操|步骤|攻略|指南|教程",
        r"底层[逻逻]辑|真相|内幕|独家",
    ],
    "mid": [  # +1.5 分
        r"\d+个(方法|技巧|习惯|思维|道理|真相|秘密|建议)",
        r"数据|报告|调查|研究|统计",
        r"复盘|总结|经验|思考|认知|感悟",
        r"建议|推荐|值得|必读|收藏",
        r"搞钱|副业|赚钱|收入|变现|商业",
    ],
    "low": [  # +0.5 分
        r"[\?？]",
        r"[\d]{1,3}[万亿千百]",
        r"刚刚|今天|昨天|最近|今年",
        r"终于|原来|没想到|竟然|居然",
        r"但是|然而|可是|不过|却",
    ],
}

# ── 质量扣分关键词 ──

NEGATIVE_SIGNALS = {
    "high": [  # -3 分
        r"^.{1,5}$",  # 极短标题（如纯名字）
        r"(速看|速删|紧急|可怕|震惊|出大事|炸了|绝了|跪了|封了|删前速看)",
        r"(刚刚|突发).{0,5}(发生|传来|曝光)",
        r"(不[看转]不是|再不看就|马上删|不转不是)",
    ],
    "mid": [  # -1.5 分
        r"(出事了|传开了|不得了|太可怕|毛骨悚然)",
        r"[\?？!！]{2,}",  # 连续标点
        r"~{2,}|\.{4,}",  # 滥用标点
        r"点击.*查看|长按.*识别|关注.*领取",
    ],
}


def score_quality(title: str) -> dict:
    """
    对标题进行质量评分。返回 {score, tags, blocked}
    score > 0 = 好内容, score < 0 = 差内容
    blocked = True 表示直接丢弃
    """
    result = {"score": 0.0, "tags": [], "blocked": False}

    # 硬过滤检查
    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, title):
            result["blocked"] = True
            result["tags"].append("blocked")
            return result

    # 加分
    for level, patterns in POSITIVE_SIGNALS.items():
        weight = {"high": 3.0, "mid": 1.5, "low": 0.5}[level]
        for pattern in patterns:
            if re.search(pattern, title):
                result["score"] += weight
                if level == "high":
                    result["tags"].append("优质信号")

    # 扣分
    for level, patterns in NEGATIVE_SIGNALS.items():
        weight = {"high": 3.0, "mid": 1.5}[level]
        for pattern in patterns:
            if re.search(pattern, title):
                result["score"] -= weight
                if level == "high":
                    result["tags"].append("低质信号")

    # 长度奖励（15-60 字最理想）
    length = len(title)
    if 15 <= length <= 60:
        result["score"] += 1.0
    elif length < 6:
        result["score"] -= 1.5

    # 分类标签
    _classify(title, result)

    return result


def _classify(title: str, result: dict):
    """7 大赛道分类"""
    cats = [
        ("科技·AI", r"AI|人工智能|GPT|大模型|芯片|手机|苹果|华为|小米|特斯拉|编程|代码|开源|算法"
         r"|互联网|软件|硬件|机器人|自动驾驶|新能源|电池|半导体|无人机|卫星|航天"
         r"|ChatGPT|Claude|Copilot|模型|算力|智能|科技|数码|数据|云计算|量子|5G"),
        ("情感", r"感情|爱情|恋爱|婚姻|家庭|孩子|父母|朋友|自己|人生|活着|生活|日子"
         r"|女人|男人|夫妻|婆媳|闺蜜|情侣|相亲|离婚|结婚|出轨|分手"),
        ("健康养生", r"健康|养生|疾病|癌症|糖尿病|高血压|减肥|运动|饮食|营养|睡眠"
         r"|中医|中药|体检|症状|治疗|预防|保健|长寿|衰老|免疫|心脏|血管|血糖"),
        ("个人成长", r"职场|工作|面试|跳槽|升职|薪资|中年|管理|领导|团队|效率|自律|习惯"
         r"|认知|思维|成长|学习|读书|技能|方法|底层|逻辑|赚钱|副业|搞钱|收入|认知"),
        ("历史", r"历史|古代|皇帝|王朝|朝代|清朝|明朝|唐朝|宋朝|三国|民国|二战|战争"
         r"|考古|文物|遗址|古人|百年|千年|世纪|秦|汉|唐|宋|元|明|清|乾隆|康熙|史记|博物馆"),
        ("体制", r"公务员|事业编|体制|机关|党建|党性|干部|纪委|巡视|反腐|基层|政策"
         r"|编制|铁饭碗|上岸|考公|遴选|衙门|官僚|党组织|党委|人大|政协|政府工作"),
        ("家居", r"家居|装修|家具|收纳|软装|硬装|厨房|卫生间|卧室|客厅|阳台|玄关"
         r"|布局|风水|家电|窗帘|灯具|地板|瓷砖|壁纸|设计|改造|翻新|空间"),
    ]
    for cat, pattern in cats:
        if re.search(pattern, title):
            result["tags"].append(cat)
            return
    result["tags"].append("其他")
