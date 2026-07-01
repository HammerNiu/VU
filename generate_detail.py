import json
import time
import re
from typing import List, Dict, Any
from openai import OpenAI

INPUT_FILE = "/home/n50059067/Vman/students.json"
OUTPUT_FILE = "student_detail.json"

SLEEP_INTERVAL = 2

DETAIL_PROMPT = """
你是一个专为中国大学生群体设计的人物画像生成引擎。请根据以下学生画像，补充该角色的具体生活细节。

【原始画像】
{student_json}

【需要补充的字段及要求】

1. "city"
该学生目前所在的城市（需与画像中的 "city_tier" 匹配），只输出城市名。

2. "university"
该学生就读的大学（需与 education 中的 university_tier 和 city_tier 对应，必须是真实存在的中国高校，不允许虚构），只输出大学全称。

3. "recent_social_posts"
最近3条朋友圈/小红书/抖音内容（需与画像中的 social_platform 匹配），每条包含：
- platform
- content
- images（简短图片描述）

4. "relationships"
包含：
   - "parents": 与父母的关系描述（含频率、内容、核心冲突或默契点）
   - "friends": 与核心朋友的关系描述（含人数、相处模式、聊天内容）
   - "partner": 与恋人的关系描述（含相处节奏、核心张力；若画像中无恋爱关系则写"无"）
   - "roommates": 与室友的关系描述（含人数、各自状态、宿舍氛围）

要求：
- 尽量简洁
- 不要过度发挥
- 保持人物设定一致
- 所有字段必须填写
- 不允许输出 null、空字符串
- 如果无法确定，请生成最合理、最符合现实的内容

【输出格式】

严格输出 JSON，不允许输出任何解释。

{
  "city":"xxx",
  "university":"xxx",
  "recent_social_posts":[
    {
      "platform":"朋友圈",
      "content":"xxx",
      "images":"xxx"
    },
    {
      "platform":"小红书",
      "content":"xxx",
      "images":"xxx"
    },
    {
      "platform":"抖音",
      "content":"xxx",
      "images":"xxx"
    }
  ],
  "relationships":{
    "parents":"xxx",
    "friends":"xxx",
    "partner":"xxx",
    "roommates":"xxx"
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
                    {
                        "role": "system",
                        "content": "你是一个准确、严谨的 JSON 生成器，只输出 JSON，不输出任何解释。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.5,
                max_tokens=2048,
                response_format={"type": "json_object"}
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
