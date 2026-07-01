import json
import time
import re
from typing import List, Dict, Any
from openai import OpenAI

# =========================
# 配置
# =========================
CLIENT = OpenAI(
    api_key="token-abc123",
    base_url="http://100.102.218.124:3236/v1",
    timeout=120,
)

MODEL = "Qwen3-32B"

INPUT_FILE = "/home/n50059067/Vman/students.json"
OUTPUT_FILE = "student_detail.json"

# 每处理一条休息（秒）
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

parents：
与父母关系（联系频率、聊天内容、核心冲突或默契）

friends：
与核心朋友关系（人数、相处模式、聊天内容）

partner：
与恋人的关系（若无恋爱则写"无"）

roommates：
与室友关系（人数、宿舍氛围、各自状态）

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
      "platform":"朋友圈",
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


# =========================
# 工具函数
# =========================
def load_students(filepath: str) -> List[Dict[str, Any]]:
    """支持 JSON 数组或单个对象"""

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return [data]

    raise ValueError("输入 JSON 格式错误，应为对象或数组。")


def extract_json(text: str) -> Dict[str, Any]:
    """尽可能从模型输出中提取 JSON"""

    text = text.strip()

    # 去掉 think
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)

    # 去 markdown
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]

    text = text.strip()

    # 找第一个 {
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("模型未返回 JSON")

    text = text[start:end + 1]

    return json.loads(text)


def generate_detail(student: Dict[str, Any]) -> Dict[str, Any]:
    """生成单个学生补充信息"""

    prompt = DETAIL_PROMPT.format(
        student_json=json.dumps(
            student,
            ensure_ascii=False,
            indent=2
        )
    )

    last_error = None

    for retry in range(3):

        try:

            response = CLIENT.chat.completions.create(
                model=MODEL,
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
                temperature=0.3,
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


# =========================
# 主程序
# =========================
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
