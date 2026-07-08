# 固定的答题约束，所有学生共用，直接拼进 profile_str 末尾
ANSWER_CONSTRAINTS = """<answer_constraints>

所有回答都发生在同一时间。

不要为了迎合题目而改变设定。

如果某件事情已经发生，
后续涉及它时保持一致。

不要重复解释自己的身份。
</answer_constraints>"""

# 用画像里已有的 mbti 维度，把"人设"转成具体的语气/文风差异，
# 而不是只让模型看到不同内容、却用同一种腔调去写
MBTI_EI_STYLE = {
    "E": "性格外向，表达更热烈、爱举生活化的例子，句子可以稍长一些",
    "I": "性格内向，表达更简洁内敛，不做过多铺陈和解释",
}
MBTI_SN_STYLE = {
    "S": "关注具体细节和实际经验，描述时习惯举具体例子、讲清楚步骤或数字，不太说抽象大道理",
    "N": "更关注感觉和大方向，表达时容易联想、打比方，不太纠结具体细节和精确数字，说法可以模糊一点、跳跃一点",
}
MBTI_TF_STYLE = {
    "T": "偏理性思考，回答里会带一点分析和条理感",
    "F": "偏感性表达，回答里更容易带情绪和感受词",
}
MBTI_JP_STYLE = {
    "J": "做事有计划、比较较真，回答问题喜欢想清楚了再说、尽量说完整，不喜欢留半截",
    "P": "做事随性、不喜欢被条条框框束缚，答题全凭当下心情，想到哪答到哪，有的题会答得很简短甚至有点敷衍，不会每题都很用心",
}


def build_style_hint(student):
    """根据 mbti 拼出一句写作风格提示，让不同人设的回答在语气上也有区别"""
    mbti = student.get("mbti", "")
    hints = []
    if len(mbti) >= 1 and mbti[0] in MBTI_EI_STYLE:
        hints.append(MBTI_EI_STYLE[mbti[0]])
    if len(mbti) >= 2 and mbti[1] in MBTI_SN_STYLE:
        hints.append(MBTI_SN_STYLE[mbti[1]])
    if len(mbti) >= 3 and mbti[2] in MBTI_TF_STYLE:
        hints.append(MBTI_TF_STYLE[mbti[2]])
    if len(mbti) >= 4 and mbti[3] in MBTI_JP_STYLE:
        hints.append(MBTI_JP_STYLE[mbti[3]])
    return "，".join(hints)


def _fmt(value):
    if isinstance(value, list):
        return '、'.join(str(x) for x in value)
    return str(value)


# behavior.phone_usage 里各项的中文标签
_PHONE_USAGE_LABELS = {
    'short_video': '刷短视频',
    'gaming': '打游戏',
    'long_video': '长视频',
    'study_reading': '学习阅读',
    'photo_video': '拍摄录像',
}

# relationship_with_* 字段的中文标签
_RELATIONSHIP_LABELS = {
    'relationship_with_parents': '与父母的关系',
    'relationship_with_friends': '与朋友的关系',
    'relationship_with_roommates': '与室友的关系',
    'relationship_with_partner': '与伴侣的关系',
}


def build_phone_hint(student):
    """
    根据 phone_brand / phone / phone_purchase_priority 拼一句提示：
    1) 约束回答里提到的品牌、系统、功能名称要和自己的手机保持一致，不要串到别的品牌上
    2) 让"当初买手机在意什么"决定这个人对相关话题懂不懂行、愿不愿意展开讲细节
    """
    phone_brand = student.get("phone_brand", "")
    phone = student.get("phone", "")
    priority = student.get("phone_purchase_priority", [])

    parts = []
    if phone_brand or phone:
        device = "、".join(p for p in [phone_brand, phone] if p)
        parts.append(f"你现在用的手机是「{device}」，回答里凡是涉及手机品牌、系统或功能名称的地方，都要和这台手机保持一致，不要写成其他品牌/机型的说法")
    if priority:
        parts.append(f"当初买手机最看重「{'、'.join(priority)}」，问题涉及这些方面时你会更懂行、更愿意展开细节；不涉及的方面可以答得更随意、更外行一点")
    return "；".join(parts)


def build_profile_xml(student):
    """
    把学生画像字典转成带 XML 标签的结构化 profile_str：
    <role_identity> 放一句话人设，后面按 hard_facts/personality/lifestyle/relationship
    分成几个平级标签，每个标签内部是自然语言的事实条目（"- ..."），
    让模型既能区分"我是谁"和"关于我的具体设定"，又不会把所有信息堆在一个标签里。
    """
    gender = student.get('gender', '')
    age = student.get('age', '')
    grade = student.get('grade', '')
    university = student.get('university', '')
    major = student.get('major', '')
    role_identity = (
        "<role_identity>\n"
        f"你是{university}{grade}{major}专业的学生，性别{gender}，{age}岁。\n"
        "</role_identity>"
    )

    hard_facts_bullets = []
    personality_bullets = []
    lifestyle_bullets = []
    relationship_bullets = []
    device_bullets = []

    def add(bullets, text):
        if text:
            bullets.append(f"- {text}")

    # ---- hard_facts：客观背景事实 ----
    if student.get('hometown'):
        add(hard_facts_bullets, f"来自{student['hometown']}")

    school_parts = []
    if student.get('university_tier'):
        school_parts.append(f"学校层次{student['university_tier']}")
    if student.get('city'):
        city_part = f"所在城市{student['city']}"
        if student.get('city_tier'):
            city_part += f"（{student['city_tier']}）"
        school_parts.append(city_part)
    add(hard_facts_bullets, "，".join(school_parts))

    study_parts = []
    if student.get('field'):
        study_parts.append(f"专业方向{student['field']}")
    if student.get('academic_performance'):
        study_parts.append(f"学业成绩{student['academic_performance']}")
    add(hard_facts_bullets, "，".join(study_parts))

    money_parts = []
    if student.get('family_income_level'):
        money_parts.append(f"家庭年收入在{student['family_income_level']}")
    if student.get('monthly_budget'):
        money_parts.append(f"每月生活费{student['monthly_budget']}")
    add(hard_facts_bullets, "，".join(money_parts))

    # ---- personality：性格、爱好、心理 ----
    personality_parts = []
    if student.get('mbti'):
        personality_parts.append(f"性格是{student['mbti']}")
    if student.get('hobbies'):
        personality_parts.append(f"兴趣爱好包括{_fmt(student['hobbies'])}")
    add(personality_bullets, "，".join(personality_parts))

    if student.get('primary_stressor'):
        add(personality_bullets, f"主要压力来源：{_fmt(student['primary_stressor'])}")
    if student.get('consumption_psychology'):
        add(personality_bullets, f"消费心理：{student['consumption_psychology']}")

    # ---- lifestyle：日常生活、设备、习惯 ----
    if student.get('living_situation'):
        add(lifestyle_bullets, f"居住情况：{student['living_situation']}")
    if student.get('phone_purchase_priority'):
        add(lifestyle_bullets, f"当初买手机最看重：{_fmt(student['phone_purchase_priority'])}")
    if student.get('social_platform'):
        add(lifestyle_bullets, f"常用社交平台：{_fmt(student['social_platform'])}")
    if student.get('life_goal'):
        add(lifestyle_bullets, f"人生目标：{student['life_goal']}")

    behavior = student.get('behavior') or {}
    if behavior.get('social_network_size'):
        add(lifestyle_bullets, f"社交网络规模：{behavior['social_network_size']}")
    if behavior.get('screen_time'):
        add(lifestyle_bullets, f"每日屏幕使用时长：{behavior['screen_time']}")

    phone_usage = behavior.get('phone_usage') or {}
    usage_items = [f"{_PHONE_USAGE_LABELS.get(k, k)}：{v}" for k, v in phone_usage.items() if v]
    if usage_items:
        add(lifestyle_bullets, "手机使用习惯：" + "；".join(usage_items))

    # ---- device：设备清单 + 手机背景 ----
    if student.get('device_stack'):
        add(device_bullets, f"拥有设备：{_fmt(student['device_stack'])}")
    if student.get('phone_brand') or student.get('phone'):
        device = " ".join(p for p in [student.get('phone_brand'), student.get('phone')] if p)
        add(device_bullets, f"手机：{device}")

    # 手机背景是一句提示性文字（约束品牌一致性 + 是否懂行）
    phone_hint = build_phone_hint(student)
    if phone_hint:
        add(device_bullets, phone_hint)

    # ---- relationship：感情状态 + 各类人际关系 ----
    if student.get('relationship'):
        add(relationship_bullets, f"感情状态：{student['relationship']}")
    for key, label in _RELATIONSHIP_LABELS.items():
        value = student.get(key)
        if value and value != '无':
            add(relationship_bullets, f"{label}：{value}")

    # ---- 兜底：没被上面覆盖到的字段放进 hard_facts，避免漏掉画像信息 ----
    covered_keys = {
        'name', 'gender', 'age', 'grade', 'university', 'major',
        'hometown', 'university_tier', 'city', 'city_tier', 'field', 'academic_performance',
        'family_income_level', 'monthly_budget', 'living_situation', 'device_stack',
        'phone_brand', 'phone', 'phone_purchase_priority', 'mbti', 'hobbies',
        'primary_stressor', 'consumption_psychology', 'social_platform', 'life_goal',
        'relationship', 'behavior',
    } | set(_RELATIONSHIP_LABELS.keys())
    for key, value in student.items():
        if key in covered_keys or value in (None, '', []):
            continue
        add(hard_facts_bullets, f"{key}：{_fmt(value)}")

    sections = [
        ("hard_facts", hard_facts_bullets),
        ("personality", personality_bullets),
        ("lifestyle", lifestyle_bullets),
        ("device", device_bullets),
        ("relationship", relationship_bullets),
    ]
    tags = [role_identity]
    for tag, bullets in sections:
        if bullets:
            tags.append(f"<{tag}>\n" + '\n'.join(bullets) + f"\n</{tag}>")

    tags.append(ANSWER_CONSTRAINTS)

    return '\n\n'.join(tags)
