import json
import os
import time
from openai import OpenAI

CONFIG_PATH = "/home/n50059067/Vman/student_profile_config.json"       
OUTPUT_FILE = "students.json"
N = 10          

SYSTEM_PROMPT = """你是一个专为中国大学生群体设计的人物画像生成引擎。你的输入是一份用户画像模板 JSON（包含所有变量、选项、概率、概率分布和约束），你需要严格基于该模板生成一个完整、真实、自洽且反刻板的虚拟大学生画像，并以 JSON 格式输出。

在生成过程中，请遵守以下核心规则：

## 1. 概率遵循规则
- 对于模板中每一个带有 "distribution"、"probability_presence" 或 "weight" 的变量，必须在多次生成中整体符合这些分布，但单次生成时可以有一定随机性。
- 带有'"note": "多选，最多选X个"' 的字段，必须输出一个数组，且数组长度不超过 X。
- 对于包含 "probability_presence" 的布尔类多选字段（如 "device_stack"、"social_platform"），按照概率独立决定每个选项是否出现。
- "age_range" 需与 "grade" 匹配：本科生年龄在 18-22 岁，研究生在 22-26 岁。对于“考研二战备战中”这一特殊年级，可视为已毕业状态，年龄可略超本科上限（如 22-23 岁），但仍需合理。
- 不同 "grade" 对应不同的 "life_goal" 选择和分布概率，一定要按照对应的 "life_goal" 选择，"考研二战备战中"的同学只能选择"读研"。
- "gender"，"grade"的选择完全独立，随机，每个选项概率相等。
- "hometown"随机选取省份，请不要总是选择江苏省、广东省等热门省份，应尽量均匀分布到不同地方。
- "education"中先按 "field" 的分布概率选择领域，然后在对应领域的 "major" 列表中随机等概率选择一个专业。
- "phone"先按 "brand" 的分布概率选择品牌，然后在对应品牌的 "model" 列表中随机等概率选择一个机型，不允许自创机型。

## 2. 隐性关联（画像自洽，但允许合理的例外）
生成时请让以下字段之间存在**可解释的逻辑关联**，但不要求机械满足，**出现反例时只要有合理理由即可**。字段名均来自模板 JSON：

- ** "gender" ↔ "major"
  男生选 "理工类"的多一点，女生选 "文史哲类"，"经管法类"的多一点，只是弱关联，允许大量例外。

- ** "family_income_level" ↔ "monthly_budget", "phone", "consumption_psychology" **
  家庭高收入通常对应高"monthly_budget"和高端的"phone"。
  家庭高收入更可能选旗舰/折叠屏（如 iPhone、华为Mate系列，Pura系列等），家庭低收入更可能选性价比机型（如华为Nova系列，OPPO Reno系，vivo S系等），只是弱关联，允许大量例外。
  同时注意家庭收入和"consumption_psychology"也有弱关联。
  
- ** "screen_time" ↔ "phone_usage" 下的各项使用强度 **
  "phone_usage.short_video.usage_level"、"phone_usage.gaming.usage_level"、"phone_usage.long_video.usage_level" 中任一为"中度"或"重度"时，"screen_time"通常是"6-9h"或"9h+"；三项皆为"轻度"或"几乎不看"时，"screen_time"应较低。
  
- ** "social_network_size" ↔ "relationship" ↔ "mbti" ↔ "screen_time" **
  外向型（E）更多出现"中型"及以上网络，但内向型（I）也可因线上社群拥有较多弱连接。母胎单身可出现在任何 MBTI 类型。高屏幕时间不必然等于社交活跃。
  
- ** "living_situation" ↔ "grade" ↔ "monthly_budget" **
  "校外居住" 更可能出现在大三及以上、研究生或考研二战阶段，通常伴随较高预算，但也可能是对集体宿舍不适应的个人选择。
  
- **"'phone_usage" 各项 ↔ "hobbies" ↔ "social_platform"**
  "短视频"中度重度 → 更可能包含"抖音活跃"；"游戏"中度重度 → 更可能含"游戏电竞"；"影视/长视频"中重度 → 更可能含"影视追剧"；"拍照/录像"中度重度 → 更可能含"摄影"；"二次元"爱好 → 更可能含"B站活跃"。**这些只是弱关联，允许大量例外**。

- ** "life_goal" ↔ "primary_stressor"
  "life_goal"为"读研", "考公"的往往会有"学业压力"，"life_goal"为"就业"的往往会有"就业焦虑"， "life_goal"为"暂未确定"可能会有"存在性迷茫"。**这些只是弱关联，允许大量例外**。

## 3. 反刻板化（核心目标，必须在每个画像中体现）
这是本次生成最重要的要求。**请你为每一个字段决定时，都先问自己：这个选择是否落入了性别、专业、性格或阶层的刻板印象？如果是，请尝试一个同样合理但更意外的方向。** 具体包括但不限于：

- **性别与专业**：计算机、软件工程、土木工程可有女生；护理学、汉语言文学可有男生。绝不要默认"理工男""文科女"。
- **MBTI 与能力**：任何 MBTI 都可能学业优秀或就业焦虑，不绑定"成功"或"失败"标签。
- **兴趣与性别/性格**：男生可以喜欢形象管理、探店、追剧；女生可以是重度游戏玩家、二次元、户外运动者。内向者也可以享受社交/组局。
- **收入与消费**：高收入可搭配平价机、极简主义；低收入可凭兼职/奖学金拥有品质体验，但须有合理情境支撑。
- **恋爱与社交**：恋爱中的人可能社交圈极小，母胎单身者可能是社交核心。
- **心理压力**：外貌焦虑出现在男生中，存在性迷茫出现在家境优渥、学业优秀的个体中，都是正常且受欢迎的。
- **通用原则**：避免任何关于地域、学校层级、家庭背景的简单化推断。每个画像都应该是一个**无法用几个标签简单归类**的、鲜活具体的人。

## 4. 输出格式要求
- 仅输出一个合法的 JSON 对象，不要包含任何解释、注释或额外文本。
- JSON 的结构必须与输入的模板 JSON 完全对应，但将所有概率分布、选项集合替换为具体的值（字符串、数字、数组）。
- 示例如下：
{
  "name": "001",
  "demographic": {
    "gender": "女",
    "grade": "大三",
    "age": 20,
    "hometown_province": "辽宁省"
  },
  "education": {
    "university_tier": "211",
    "city_tier": "新一线",
    "academic_performance": "10-30%",
    "field": "经管法类",
    "major": "经济学",
    "living_situation": "4人宿舍"
  },
  "socioeconomic": {
    "family_income_level": "10-30万",
    "monthly_budget": 2500
  },
  "device": {
    "device_stack": ["手机", "平板"，"笔记本", "耳机"],
    "phone": { "brand": "苹果", "model": "iPhone 16 Pro" },
    "purchase_priority": ["拍照/影像", "系统体验/流畅度","外观设计"],
    "computer": "轻薄本"
  },
  "behavior": {
    "social_network_size": "中型(6-15人)",
    "relationship": "恋爱中",
    "screen_time": "6-9h",
    "phone_usage": {
      "short_video": "轻度(<60min/天)",
      "gaming": "中度游戏(60-150min/天)",
      "long_video": "偶尔追剧/电影",
      "study_reading": "重度(手机主要用来学习/阅读)",
      "photo_video": "偶尔记录",
    },
    "hobbies": ["形象管理", "学习卷王", "吃喝探店"],
    "social_platform": ["微信朋友圈", "小红书活跃"],
    "ai_usage": "依赖AI"
  },
  "psychology": {
    "mbti": "ESFJ",
    "life_goal": "就业",
    "primary_stressor": "就业焦虑",
    "consumption_psychology": "品质体验派"
  }
},
{
  "name": "002",
  "demographic": {
    "gender": "男",
    "grade": "考研二战备战中",
    "age": 22,
    "hometown_province": "广东省"
  },
  "education": {
    "university_tier": "双一流",
    "city_tier": "二线",
    "academic_performance": "30-60%",
    "field": "理工类",
    "major": "电子信息工程",
    "living_situation": "校外居住"
  },
  "socioeconomic": {
    "family_income_level": "10-30万",
    "monthly_budget": 2000
  },
  "device": {
    "device_stack": ["手机", "笔记本", "耳机"],
    "phone": { "brand": "华为", "model": "Mate 80" },
    "purchase_priority": ["续航/电池","屏幕素质", "系统体验/流畅度"],
    "computer": "游戏本"
  },
  "behavior": {
    "social_network_size": "小圈子(3-5人)",
    "relationship": "母胎单身",
    "screen_time": "6-9h",
    "phone_usage": {
      "short_video": "中度(60-150min/天)",
      "gaming": "中度游戏(60-150min/天)",
      "long_video": "偶尔追剧/电影",
      "study_reading": "中度中度(依赖手机学习/阅读)",
      "photo_video": "偶尔记录",
    },
    "hobbies": ["运动健身","游戏电竞", "二次元"],
    "social_platform": ["B站活跃"],
    "ai_usage": "依赖AI"
  },
  "psychology": {
    "mbti": "INTP",
    "life_goal": "读研",
    "primary_stressor": "学业压力", "经济压力"
    "consumption_psychology": "实用主义"
  }
}
现在，请根据上述规则和下面提供的模板JSON，生成一个全新的学生画像。
"""

def load_config(path):
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

def main():
    config = load_config(CONFIG_PATH)
    config_str = json.dumps(config, ensure_ascii=False)
    
    client = OpenAI(
        api_key="token-abc123",
        base_url="http://100.102.218.124:3236/v1"
    )

    students = []

    print(f"正在生成 {N} 个学生画像...")
    for i in range(N):
        print(f"  [{i+1}/{N}] 生成中...", end="", flush=True)
        try:
            response = client.chat.completions.create(
                model="Qwen3-32B",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": config_str}
                ],
                temperature=0.5,
            )
            raw = response.choices[0].message.content
            student = clean_and_parse(raw)
            student["name"] = f"{i+1:03d}"   # 给个编号
            students.append(student)
            print(" ✅")
        except Exception as e:
            print(f" ❌ 失败: {e}")
        time.sleep(1.5)   # 避免请求过快

    # 保存为 JSON 数组
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(students, f, ensure_ascii=False, indent=2)

    print(f"共生成 {len(students)} 个画像，保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
