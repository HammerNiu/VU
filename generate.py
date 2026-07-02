import json
import os
import random
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

CONFIG_PATH = "student_profile_config.json"
OUTPUT_FILE = "students.json"
N = 10

client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url="https://api.deepseek.com"
)

# ---------- 条件抽样表（来自 student_profile.md） ----------

GRADE_AGE_OFFSET = {
    "大一": 0, "大二": 1, "大三": 2, "大四": 3,
    "研究生": 4, "考研二战备战中": 4,
}

FIELD_DIST_BY_GENDER = {
    "男": [0.5, 0.05, 0.25, 0.05, 0.1, 0.05],
    "女": [0.2, 0.1, 0.35, 0.1, 0.2, 0.05],
}

CITY_TIER_DIST_BY_UNI_TIER = {
    "双一流": [0.7, 0.3, 0],
    "非双一流的一本": [0.5, 0.4, 0.1],
    "二本": [0.5, 0.4, 0.1],
    "专科": [0.3, 0.4, 0.3],
}

# 收入 3 档合并（monthly_budget 用）：<10万 | 10-30万 | 30-50万及以上（含50-80万、80万+）
MONTHLY_BUDGET_DIST = {
    "<10万": [0.4, 0.5, 0.1, 0, 0],
    "10-30万": [0.1, 0.5, 0.25, 0.1, 0.05],
    "30-50万+": [0, 0.5, 0.3, 0.15, 0.05],
}

# 收入 2 档合并（phone_brand 用）：<10万 | 10-30万及以上（含30-50万、50-80万、80万+）
PHONE_BRAND_DIST = {
    "<10万": [0.1, 0.1, 0.1, 0.15, 0.1, 0.1, 0.2, 0.15],
    "10-30万+": [0.15, 0.15, 0.3, 0.1, 0.1, 0.1, 0.05, 0.05],
}

# university_tier 合并为 双一流 / 普通本科（非双一流的一本+二本）/ 专科
LIVING_SITUATION_DIST = {
    ("双一流", "<10万"): [0.55, 0.35, 0.10, 0.00],
    ("双一流", "≥10万"): [0.55, 0.30, 0.05, 0.10],
    ("普通本科", "<10万"): [0.40, 0.50, 0.10, 0.00],
    ("普通本科", "≥10万"): [0.40, 0.45, 0.10, 0.05],
    ("专科", "<10万"): [0.20, 0.55, 0.25, 0.00],
    ("专科", "≥10万"): [0.20, 0.50, 0.20, 0.10],
}

SOCIAL_PLATFORM_DIST = {
    ("男", "E"): [0.6, 0.4, 0.6, 0.5],
    ("男", "I"): [0.3, 0.2, 0.4, 0.5],
    ("女", "E"): [0.8, 0.6, 0.6, 0.3],
    ("女", "I"): [0.4, 0.5, 0.4, 0.2],
}

GRADE_TO_LIFEGOAL_KEY = {
    "大一": "大一_大二", "大二": "大一_大二",
    "大三": "大三_大四", "大四": "大三_大四",
    "研究生": "研究生", "考研二战备战中": "考研二战备战中",
}

# 输出字段顺序（与生成顺序无关，仅用于最终 JSON 展示）
FIELD_ORDER = [
    "name", "gender", "age", "grade", "hometown", "university_tier", "city_tier",
    "city", "university", "field", "major", "academic_performance", "mbti",
    "relationship", "family_income_level", "living_situation", "monthly_budget",
    "device_stack", "phone_brand", "phone", "social_platform", "life_goal",
    "behavior", "hobbies", "primary_stressor", "consumption_psychology",
    "phone_purchase_priority", "relationship_with_parents", "relationship_with_friends",
    "relationship_with_roommates", "relationship_with_partner",
]


def reorder_fields(student):
    return {key: student[key] for key in FIELD_ORDER}

L3_CORRELATION_RULES = """- "social_network_size" ↔ "mbti" ↔ "screen_time"：
  外向型（E）更多出现"中型"及以上网络，但内向型（I）也可因线上社群拥有较多弱连接。高屏幕时间不必然等于社交活跃。
- "screen_time" ↔ "phone_usage" 下的各项使用强度：
  short_video、gaming、long_video 中任一为"中度"或"重度"时，screen_time 通常是"6-9h"或"9h+"；三项皆为"轻度"或"几乎不看"时，screen_time 应较低。
- "living_situation" ↔ "grade" ↔ "monthly_budget"：
  "校外居住"更可能出现在大三及以上、研究生或考研二战阶段，通常伴随较高预算，但也可能是对集体宿舍不适应的个人选择。
- "phone_usage" 各项 ↔ "hobbies" ↔ "social_platform"：
  短视频中度重度 → 更可能包含"抖音活跃"；游戏中度重度 → 更可能含"游戏电竞"；长视频中重度 → 更可能含"影视追剧"；拍照/录像中度重度 → 更可能含"摄影"；二次元爱好 → 更可能含"B站活跃"。这些只是弱关联，允许大量例外。
- "life_goal" ↔ "primary_stressor"：
  life_goal 为"读研""考公"的往往会有"学业压力"，为"就业"的往往会有"就业焦虑"，为"暂未确定"可能会有"存在性迷茫"。这些只是弱关联，允许大量例外。"""


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def weighted_choice(options, weights):
    return random.choices(options, weights=weights, k=1)[0]


def bernoulli_select(options, probs, min_count=0):
    selected = [opt for opt, p in zip(options, probs) if random.random() < p]
    if min_count and len(selected) < min_count:
        remaining = [(opt, p) for opt, p in zip(options, probs) if opt not in selected]
        while len(selected) < min_count and remaining:
            opts, wts = zip(*remaining)
            pick = random.choices(opts, weights=wts, k=1)[0]
            selected.append(pick)
            remaining = [(o, p) for o, p in remaining if o != pick]
    return selected


def uni_tier_bucket(tier):
    if tier in ("双一流", "专科"):
        return tier
    return "普通本科"  # 非双一流的一本 + 二本


def income_bucket_3(level):
    if level == "<10万":
        return "<10万"
    if level == "10-30万":
        return "10-30万"
    return "30-50万+"


def income_bucket_2(level):
    return "<10万" if level == "<10万" else "10-30万+"


def generate_l1(cfg):
    l1 = cfg["L1"]
    device = l1["device_stack"]
    return {
        "gender": random.choice(l1["gender"]),
        "grade": random.choice(l1["grade"]),
        "hometown": random.choice(l1["hometown"]),
        "university_tier": weighted_choice(l1["university_tier"]["options"], l1["university_tier"]["distribution"]),
        "academic_performance": weighted_choice(l1["academic_performance"]["ranking"], l1["academic_performance"]["distribution"]),
        "family_income_level": weighted_choice(l1["family_income_level"]["options"], l1["family_income_level"]["distribution"]),
        "device_stack": bernoulli_select(device["options"], device["probability_presence"]),
        "mbti": weighted_choice(l1["mbti"]["options"], l1["mbti"]["distribution"]),
        "relationship": weighted_choice(l1["relationship"]["options"], l1["relationship"]["distribution"]),
    }


def generate_l2(cfg, l1):
    l2 = cfg["L2"]

    age = 18 + GRADE_AGE_OFFSET[l1["grade"]] + random.choice([-1, 0, 1])

    field = weighted_choice(l2["field"], FIELD_DIST_BY_GENDER[l1["gender"]])
    major = random.choice(l2["major"][field])

    city_tier = weighted_choice(l2["city_tier"], CITY_TIER_DIST_BY_UNI_TIER[l1["university_tier"]])

    monthly_budget = weighted_choice(l2["monthly_budget"], MONTHLY_BUDGET_DIST[income_bucket_3(l1["family_income_level"])])

    living_key = (uni_tier_bucket(l1["university_tier"]), "<10万" if l1["family_income_level"] == "<10万" else "≥10万")
    living_situation = weighted_choice(l2["living_situation"], LIVING_SITUATION_DIST[living_key])

    phone_brand = weighted_choice(l2["phone_brand"], PHONE_BRAND_DIST[income_bucket_2(l1["family_income_level"])])
    phone = random.choice(l2["phone"][phone_brand])

    mbti_ei = l1["mbti"][0]  # 第一个字母：E 或 I
    social_platform = bernoulli_select(l2["social_platform"], SOCIAL_PLATFORM_DIST[(l1["gender"], mbti_ei)], min_count=1)

    lg_cfg = l2["life_goal"][GRADE_TO_LIFEGOAL_KEY[l1["grade"]]]
    life_goal = weighted_choice(lg_cfg["options"], lg_cfg["distribution"])

    return {
        "age": age, "field": field, "major": major, "city_tier": city_tier,
        "living_situation": living_situation, "monthly_budget": monthly_budget,
        "phone_brand": phone_brand, "phone": phone, "social_platform": social_platform,
        "life_goal": life_goal,
    }


def clean_and_parse(raw):
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return json.loads(raw.strip())


def build_l3_system_prompt(cfg, used_cities, used_universities):
    l3 = cfg["L3"]
    b = l3["behavior"]

    example = {
        "city": "洛阳",
        "university": "河南科技大学",
        "behavior": {
            "social_network_size": "中型(6-15人)",
            "screen_time": "6-9h",
            "phone_usage": {
                "short_video": "中度(60-150min/天)",
                "gaming": "轻度休闲(<60min/天)",
                "long_video": "偶尔追剧/电影",
                "study_reading": "偶尔查资料/背单词",
                "photo_video": "偶尔记录",
            },
        },
        "hobbies": ["吃喝探店", "读书"],
        "primary_stressor": ["学业压力"],
        "consumption_psychology": "实用主义",
        "phone_purchase_priority": ["续航/电池", "价格/性价比"],
        "relationship_with_parents": "每周视频一次，日常报平安，偶尔因为花销唠叨几句，整体关系融洽",
        "relationship_with_friends": "3个核心朋友，平时一起吃饭自习，聊八卦和考试",
        "relationship_with_roommates": "4人宿舍，跟其中2人关系好，一起打游戏点外卖，宿舍氛围轻松",
        "relationship_with_partner": "无",
    }

    used_cities_str = "、".join(used_cities) if used_cities else "（暂无）"
    used_universities_str = "、".join(used_universities) if used_universities else "（暂无）"

    return f"""你是一个专为中国大学生群体设计的人物画像"润色层"生成引擎。用户会给你一份该学生已经确定好的画像（性别、年级、年龄、家乡、学校层次、学业排名、家庭收入、设备、MBTI、恋爱状态、专业、所在城市层级、居住情况、月预算、手机品牌型号、常用社交平台、人生目标），你需要在此基础上补全剩余字段，输出一个合法 JSON 对象。

## 1. 需要生成的字段
- city：该学生目前所在城市。必须符合已知画像的 city_tier，必须是真实存在的中国城市，只输出城市名称。若有多个符合条件的城市，不要总选成都、杭州、武汉等热门城市，应尽量均匀分布到不同城市。本批次已用过：{used_cities_str}，请尽量避开。
- university：该学生目前就读的大学。必须是真实存在的中国高校（不允许编造），必须符合已知画像的 university_tier，应与所在城市尽量对应（该城市没有符合条件的高校时可选同省或同等级城市的），只输出大学全称。存在多个合理学校时应尽量选不同高校，不要反复选四川大学、电子科技大学、浙江大学、武汉大学等少数热门学校。本批次已用过：{used_universities_str}，请尽量避开。
- behavior.social_network_size：{b['social_network_size']['options']}，总体参考分布（多次生成需整体接近，单次可有随机性）：{b['social_network_size']['distribution']}
- behavior.screen_time：{b['screen_time']['options']}，总体参考分布：{b['screen_time']['distribution']}
- behavior.phone_usage.short_video：{b['phone_usage']['short_video']['options']}，总体参考分布：{b['phone_usage']['short_video']['distribution']}
- behavior.phone_usage.gaming：{b['phone_usage']['gaming']['options']}，总体参考分布：{b['phone_usage']['gaming']['distribution']}
- behavior.phone_usage.long_video：{b['phone_usage']['long_video']['options']}，总体参考分布：{b['phone_usage']['long_video']['distribution']}
- behavior.phone_usage.study_reading：{b['phone_usage']['study_reading']['options']}，总体参考分布：{b['phone_usage']['study_reading']['distribution']}
- behavior.phone_usage.photo_video：{b['phone_usage']['photo_video']['options']}，总体参考分布：{b['phone_usage']['photo_video']['distribution']}
- hobbies：从 {l3['hobbies']['options']} 中多选，选 1-3 个。不要总选运动健身、摄影、旅行户外，尽量均匀分布到所有爱好。
- primary_stressor：从 {l3['primary_stressor']['options']} 中选 0-2 个，每个选项独立参考出现概率：{l3['primary_stressor']['probability_presence']}
- consumption_psychology：{l3['consumption_psychology']['options']}，总体参考分布：{l3['consumption_psychology']['distribution']}
- phone_purchase_priority：从 {l3['phone_purchase_priority']['options']} 中多选，选 1-3 个。
- relationship_with_parents：联系频率、日常聊天内容、默契或冲突。
- relationship_with_partner：若画像 relationship 为"母胎单身"或"谈过已分手"，直接写"无"；若为"暧昧期"或"恋爱中"，描述相处节奏和主要矛盾。
- relationship_with_friends：核心朋友人数、相处模式、平时聊天内容。
- relationship_with_roommates：室友人数、要好的室友人数、平常一起做什么、宿舍氛围。

## 2. 隐性关联规则（弱关联，出现反例只要合理即可）
{L3_CORRELATION_RULES}

## 3. 反刻板化
生成时请避免落入性别、专业、性格、阶层的刻板印象，允许并鼓励意外但合理的组合（例如内向的人也可以有活跃社交、男生也可以外貌焦虑等）。

## 4. 输出格式
仅输出一个合法 JSON 对象，不要包含任何解释、注释、代码块标记或额外文本。字段名必须与下面示例完全一致：
{json.dumps(example, ensure_ascii=False, indent=2)}
"""


def generate_l3(cfg, l1, l2, used_cities, used_universities):
    system_prompt = build_l3_system_prompt(cfg, used_cities, used_universities)
    profile_str = json.dumps({**l1, **l2}, ensure_ascii=False)

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": profile_str},
        ],
        temperature=0.7,
    )
    l3 = clean_and_parse(response.choices[0].message.content)

    if len(l3.get("hobbies", [])) > 3:
        l3["hobbies"] = l3["hobbies"][:3]
    if len(l3.get("primary_stressor", [])) > 2:
        l3["primary_stressor"] = l3["primary_stressor"][:2]
    if len(l3.get("phone_purchase_priority", [])) > 3:
        l3["phone_purchase_priority"] = l3["phone_purchase_priority"][:3]

    return l3


def main():
    cfg = load_config(CONFIG_PATH)

    students = []
    used_cities = []
    used_universities = []

    print(f"正在生成 {N} 个学生画像...")
    for i in range(N):
        print(f"  [{i+1}/{N}] 生成中...", end="", flush=True)
        try:
            l1 = generate_l1(cfg)
            l2 = generate_l2(cfg, l1)
            l3 = generate_l3(cfg, l1, l2, used_cities, used_universities)

            student = {"name": f"{i+1:03d}", **l1, **l2, **l3}
            student = reorder_fields(student)
            students.append(student)

            used_cities.append(l3["city"])
            used_universities.append(l3["university"])
            print(" ✅")
        except Exception as e:
            print(f" ❌ 失败: {e}")
        time.sleep(1.5)  # 避免请求过快

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(students, f, ensure_ascii=False, indent=2)

    print(f"共生成 {len(students)} 个画像，保存至 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
