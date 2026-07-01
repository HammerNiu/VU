import json
import time
import re
from typing import List, Dict, Any
from openai import OpenAI

INPUT_FILE = "/home/n50059067/Vman/students.json"
OUTPUT_FILE = "student_detail.json"

SLEEP_INTERVAL = 2

DETAIL_PROMPT = """
你是一个专为中国大学生群体设计的人物画像生成引擎。请根据下面提供的学生画像，补充该角色的生活细节。

【原始画像】

{student_json}

【需要补充的字段】

1. city
表示该学生目前所在城市。
要求：
- 必须符合画像中的 city_tier。
- 必须是真实存在的中国城市。
- 只输出城市名称。
- 如果存在多个符合条件的城市，请不要总是选择成都、杭州、武汉等热门城市，应尽量均匀分布到不同城市。

2. university
表示该学生目前就读大学。
要求：
- 必须是真实存在的中国高校。
- 不允许编造学校名称。
- 必须符合画像中的 education.university_tier。
- 应与所在城市尽量对应；若该城市没有符合条件的高校，可选择同省或同等级城市。
- 当存在多个合理学校时，应尽量选择不同高校，不要反复选择四川大学、电子科技大学、浙江大学、武汉大学等少数热门学校。
- 不要为了知名度优先选择985高校，应严格按照 university_tier 进行匹配。
- 只输出大学全称。

3. recent_social_posts
生成最近3条社交平台内容。
要求：
- 平台必须符合画像中的 social_platform。
- 每条包括：
    - platform
    - content
    - images
- 内容自然真实。
- 不要刻意鸡汤。
- 不要所有人都发考研、咖啡、图书馆。
- 图片描述保持简洁。

4. relationships
包括：
parents
描述：
- 联系频率
- 日常聊天内容
- 默契或冲突
friends
描述：
- 核心朋友人数
- 相处模式
- 平时聊天内容
partner
描述：
- 若画像没有恋爱关系，直接写："无"
- 若有恋爱关系，描述相处节奏和主要矛盾。
roommates
描述：
- 室友人数
- 各自特点
- 宿舍氛围

【整体要求】

- 保持与画像设定一致。
- 不要新增设定。
- 尽量简洁。
- 不要写成长篇小说。
- 所有字段必须填写。
- 不允许输出 null。
- 不允许输出空字符串。
- 不允许输出"未知""待补充"等内容。
- 如果存在多个合理答案，请优先选择更少出现的城市、高校和生活方式，而不是重复热门答案。
- 这是一个用于生成大量学生画像的数据集，应尽量保证不同学生之间具有多样性，避免模式化生成。


【输出格式】

严格输出 JSON。

不要输出 markdown。

不要输出解释。

不要输出任何多余文字。

{
  "city": "xxx",
  "university": "xxx",
  "recent_social_posts": [
    {
      "platform": "朋友圈",
      "content": "xxx",
      "images": "xxx"
    },
    {
      "platform": "小红书",
      "content": "xxx",
      "images": "xxx"
    },
    {
      "platform": "抖音",
      "content": "xxx",
      "images": "xxx"
    }
  ],
  "relationships": {
    "parents": "xxx",
    "friends": "xxx",
    "partner": "xxx",
    "roommates": "xxx"
  }
}
"""

def load_students(filepath: str) -> List[Dict[str, Any]]:
    """支持 JSON 数组或单个对象"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError("输入 JSON 格式错误，应为对象或数组。")


def extract_json(raw):
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return json.loads(raw.strip())


def generate_detail(student: Dict[str, Any]) -> Dict[str, Any]:
    prompt = DETAIL_PROMPT.format(
        student_json=json.dumps(
            student,
            ensure_ascii=False,
            indent=2
        )
    )

    CLIENT = OpenAI(
    api_key="token-abc123",
    base_url="http://100.102.218.124:3236/v1",
    )    

    last_error = None

    for retry in range(3):
        try:
            response = CLIENT.chat.completions.create(
                model="Qwen3-32B",
                messages=[
                    {"role": "system","content": "你是一个准确、严谨的 JSON 生成器，只输出 JSON，不输出任何解释。"},
                    {"role": "user","content": prompt}
                ],
                temperature=0.5
            )

            raw = response.choices[0].message.content

            return extract_json(raw)

        except Exception as e:

            last_error = e
            print(f"      第 {retry + 1} 次失败：{e}")

            time.sleep(2)

    raise RuntimeError(last_error)


def main():

    print(f"📂 读取 {INPUT_FILE}")

    students = load_students(INPUT_FILE)

    print(f"✅ 共 {len(students)} 条学生画像")

    results = []

    for idx, student in enumerate(students):

        print(f"\n🔄 正在处理 {idx + 1}/{len(students)}")

        try:

            detail = generate_detail(student)

            enriched = {
                **student,
                **detail
            }

            results.append(enriched)

            print(
                f"   ✅ "
                f"{detail.get('university','未知大学')} | "
                f"{detail.get('city','未知城市')}"
            )

        except Exception as e:

            print(f"   ❌ 失败：{e}")

            enriched = {
                **student,
                "city": "待补充",
                "university": "待补充",
                "recent_social_posts": [],
                "relationships": {
                    "parents": "待补充",
                    "friends": "待补充",
                    "partner": "待补充",
                    "roommates": "待补充"
                }
            }

            results.append(enriched)

        # 实时保存，防止程序中断导致全部丢失
        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                results,
                f,
                ensure_ascii=False,
                indent=2
            )

        time.sleep(SLEEP_INTERVAL)

    print(f"\n🎉 全部完成！")
    print(f"📄 已保存：{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
