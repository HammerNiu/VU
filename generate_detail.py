import json
import time
from openai import OpenAI
from typing import List, Dict, Any


INPUT_FILE = "/home/n50059067/Vman/students.json"
OUTPUT_FILE = "student_detail.json"

# 每处理一条休息 2 秒，避免触发限流
SLEEP_INTERVAL = 2

DETAIL_PROMPT = """
你是一个专为中国大学生群体设计的人物画像生成引擎。请根据以下学生画像，补充该角色的具体生活细节。

【原始画像】
{student_json}

【需要补充的字段及要求】
1. "city": 该学生目前所在的城市（需与画像中""city_tier"匹配），只输出城市名
2. "university": 该学生就读的大学（需与"education"中的 "university_tier"和"city_tier"对应，必须符合事实，不能胡编乱造），只输出大学全称
3. "recent_social_posts": 最近3条朋友圈/小红书/抖音内容（需与画像中"social_platform"匹配）每条包含"platform"、"content"、"images"(简短的图片描述)
4. "relationships": 包含以下子字段：
   - "parents": 与父母的关系描述（含频率、内容、核心冲突或默契点）
   - "friends": 与核心朋友的关系描述（含人数、相处模式、聊天内容）
   - "partner": 与恋人的关系描述（含相处节奏、核心张力；若画像中无恋爱关系则写"无"）
   - "roommates": 与室友的关系描述（含人数、各自状态、宿舍氛围）
5. 尽量简洁，别随意发挥

【输出格式】
请严格输出 JSON 格式，不要有任何额外文字。格式如下：
{
  "city": "xxx",
  "university": "xxx",
  "recent_social_posts": [
    {"platform": "朋友圈", "content": "xxx", "images": "xxx"},
    {"platform": "小红书", "content": "xxx", "images": "xxx"},
    {"platform": "朋友圈", "content": "xxx", "images": "xxx"}
  ],
  "relationships": {
    "parents": "xxx",
    "friends": "xxx",
    "partner": "xxx",
    "roommates": "xxx"
  }
}

请确保：
- 城市、大学、家乡的选择符合画像中的地域层级要求
- 社交媒体内容自然、真实，不刻意
- 关系描述有具体细节、矛盾和张力，不是泛泛而谈
- 整体风格与画像中的"品质体验派""ENFJ""考研目标"等特质一致
"""

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_and_parse(raw):
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return json.loads(raw.strip())


def generate_detail(student: Dict[str, Any]) -> Dict[str, Any]:
    """调用 LLM 为单个学生生成补充细节"""
    students_json = load_json(INPUT_FILE)
    student_json = json.dumps(students_json, ensure_ascii=False)
    
    client = OpenAI(
        api_key="token-abc123",
        base_url="http://100.102.218.124:3236/v1"
    )
    
    response = client.chat.completions.create(
        model="Qwen3-32B" ,
        messages=[
            {"role": "system", "content": "你是一个准确、细致的JSON生成器，只输出JSON格式内容。"},
            {"role": "user", "content": student_json}
        ],
        temperature=0.7,
        max_tokens=2048
    )
    
    raw = response.choices[0].message.content
    detail_json = clean_and_parse(raw)
    
    return  detail_json


def main():
    print(f"📂 读取 {INPUT_FILE}...")
    students = load_students(INPUT_FILE)
    print(f"✅ 共 {len(students)} 条学生画像")
    
    results = []
    for idx, student in enumerate(students):
        print(f"\n🔄 正在处理第 {idx+1}/{len(students)} 条...")
        try:
            detail = generate_detail(student)
            enriched = {**student, **detail}
            results.append(enriched)
            print(f"   ✅ 完成：{detail.get('university', '未知大学')} | {detail.get('city', '未知城市')}")
        except Exception as e:
            print(f"   ❌ 失败：{e}")
            # 失败时保留原始数据，占位补充
            placeholder = {
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
            results.append({**student, **placeholder})
        
        time.sleep(SLEEP_INTERVAL)
    

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 完成！结果已保存至 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
