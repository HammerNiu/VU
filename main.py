import re
import random
import pandas as pd
from openai import OpenAI
import json

client = OpenAI(
    api_key="token-abc123",
    base_url="http://100.102.218.124:3236/v1"
)

def load_students_from_json(file_path):
    """从JSON文件读取学生列表"""
    with open(file_path, 'r', encoding='utf-8') as f:
        students = json.load(f)
    return students


def extract_questions_from_excel(excel_path, question_col=2, skip_header=True):
    """
    从Excel提取问题文本（默认C列，跳过表头）
    返回问题列表（按顺序）和问题行索引（从0开始）
    """
    df = pd.read_excel(excel_path, header=None)
    start = 1 if skip_header else 0
    questions = []
    row_indices = []
    for i in range(start, df.shape[0]):
        q = str(df.iloc[i, question_col]).strip() if pd.notna(df.iloc[i, question_col]) else ''
        if q:
            # 将问题中的换行替换为空格，确保每个问题是一行
            q = q.replace('\n', ' ').replace('\r', '')
            questions.append(q)
            row_indices.append(i)
    return questions, row_indices, df


def parse_tagged_answers(result, expected_count):
    """
    按 "Q<题号>|答案" 标记解析模型输出。
    相比按行数直接对齐，标记式解析不会因为某一题多输出/漏输出一个换行，
    导致后面所有题目的答案整体错位。
    """
    matches = dict(re.findall(r'Q(\d+)\|(.*)', result))
    answers = []
    missing = []
    for i in range(1, expected_count + 1):
        ans = matches.get(str(i), "").strip()
        if not ans:
            missing.append(i)
        answers.append(ans)
    if missing:
        print(f"  警告：题号 {missing} 未能从模型输出中解析到答案")
    return answers


# 同一套硬性格式要求的几种等价措辞，每个学生随机选一版，
# 避免所有请求都锚定在完全相同的指令文本上（Q<题号>| 的标记格式本身保持不变，不能变）
RULE_TEMPLATES = [
    """【强制规则】
1. 下面有若干道编号的题目，每题必须以 "Q<题号>|" 开头，紧接答案内容，例如：
   Q1|大概拍了450张左右，其中约80张是有意识用动态模式拍摄的
   Q2|主要用后置人像模式拍摄朋友合影
2. 每题只占一行，即使答案较长也不要换行，用句号或分号连接
3. 题号必须与题目编号一一对应，不要跳号、不要重复
4. 不要加解释、不要加多余空行、不要用 markdown""",
    """【输出格式】
- 逐题作答，每一行对应一道题，格式固定为 "Q<题号>|你的回答"，比如：
  Q1|大概拍了450张左右，其中约80张是有意识用动态模式拍摄的
  Q2|主要用后置人像模式拍摄朋友合影
- 一行写完一题，答案再长也不要换行，中间用句号/分号隔开
- 题号顺序不能乱，也不能漏题或重复
- 除了这些答案行，什么都不要多写（不要解释、不要空行、不要 markdown）""",
    """作答时请严格遵守：
① 每道题对应一行，行首固定写 "Q<题号>|"，后面直接跟答案，例如：
   Q1|大概拍了450张左右，其中约80张是有意识用动态模式拍摄的
   Q2|主要用后置人像模式拍摄朋友合影
② 一行只答一题，长答案用句号/分号连接，不要换行
③ 题号要和题目顺序对齐，既不跳号也不重复
④ 除答案本身外不要输出任何解释、空行或 markdown 格式""",
]

# 用画像里已有的 mbti 维度，把"人设"转成具体的语气/文风差异，
# 而不是只让模型看到不同内容、却用同一种腔调去写
MBTI_EI_STYLE = {
    "E": "性格外向，表达更热烈、爱举生活化的例子，句子可以稍长一些",
    "I": "性格内向，表达更简洁内敛，不做过多铺陈和解释",
}
MBTI_TF_STYLE = {
    "T": "偏理性思考，回答里会带一点分析和条理感",
    "F": "偏感性表达，回答里更容易带情绪和感受词",
}


def build_style_hint(student):
    """根据 mbti 拼出一句写作风格提示，让不同人设的回答在语气上也有区别"""
    mbti = student.get("mbti", "")
    hints = []
    if len(mbti) >= 1 and mbti[0] in MBTI_EI_STYLE:
        hints.append(MBTI_EI_STYLE[mbti[0]])
    if len(mbti) >= 3 and mbti[2] in MBTI_TF_STYLE:
        hints.append(MBTI_TF_STYLE[mbti[2]])
    return "，".join(hints)


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


def generate_answers_for_student(student, questions):
    """
    为单个学生生成问卷答案
    student: 学生画像字典
    questions: 问题文本列表（按顺序）
    返回答案列表（字符串列表，与 questions 一一对应）
    """
    # 构建学生画像描述字符串（用于system_prompt）
    def format_dict(d, indent=0):
        lines = []
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append("  " * indent + f"{k}:")
                lines.extend(format_dict(v, indent + 1))
            elif isinstance(v, list):
                lines.append("  " * indent + f"{k}: {', '.join(v)}")
            else:
                lines.append("  " * indent + f"{k}: {v}")
        return lines

    profile_lines = []
    for key, value in student.items():
        if key == 'name':
            continue
        if isinstance(value, dict):
            profile_lines.append(f"{key}:")
            profile_lines.extend(format_dict(value, 1))
        elif isinstance(value, list):
            profile_lines.append(f"{key}: {', '.join(value)}")
        else:
            profile_lines.append(f"{key}: {value}")
    profile_str = '\n'.join(profile_lines)

    style_hint = build_style_hint(student)
    style_block = f"\n【说话风格】{style_hint}，回答时让这种性格特点体现在语气和用词上，不要每个人听起来都是一个调调。\n" if style_hint else ""

    phone_hint = build_phone_hint(student)
    phone_block = f"\n【手机背景】{phone_hint}。\n" if phone_hint else ""

    rules_block = random.choice(RULE_TEMPLATES)

    system_prompt = f"""你是一个真实的大学生，以下是你的个人信息：
                    {profile_str}
                    **充分代入角色**，把自己当成一个有血有肉的人。可以适当添加一些人物背景，人物性格。
                    针对问卷问题，给出真实、合理的个人回答，保证一致性。涉及具体数量、占比等数值时，请结合你的个人画像自行给出一个合理且有个人特色的数字，不要凑整、不要和"大多数人"给出相似的数值。
                    {style_block}{phone_block}
                    **直接逐题作答**

                    {rules_block}
                """

    questions_text = '\n'.join(f"{i + 1}. {q}" for i, q in enumerate(questions))

    response = client.chat.completions.create(
        model="Qwen3-32B",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": questions_text},
        ],
        temperature=1.0,
        top_p=0.95,
        presence_penalty=0.4,
    )

    result = response.choices[0].message.content
    return parse_tagged_answers(result, len(questions))


def fill_excel_with_students(excel_path, students, questions, row_indices, output_path):
    """
    将每个学生的答案填入对应的列（D列开始）
    每处理完一个学生就落盘一次，避免中途某个学生失败导致前面已完成的结果全部丢失
    """
    df = pd.read_excel(excel_path, header=None)
    # 确保有足够的列
    num_students = len(students)
    start_col = 3  # D列索引
    if df.shape[1] < start_col + num_students:
        for _ in range(start_col + num_students - df.shape[1]):
            df.insert(df.shape[1], df.shape[1], None)  # 添加空列

    # 第一行写入学生姓名
    for idx, student in enumerate(students):
        col = start_col + idx
        df.iloc[0, col] = student['name']

    # 为每个学生生成答案并填充
    for idx, student in enumerate(students):
        col = start_col + idx
        print(f"正在生成学生 {student['name']} 的答案...")

        try:
            answers = generate_answers_for_student(student, questions)
        except Exception as e:
            print(f"❌ 学生 {student['name']} 生成失败，已跳过：{e}")
            df.to_excel(output_path, index=False, header=False)
            continue

        # 检查答案数量
        expected = len(questions)
        if len(answers) != expected:
            print(f"警告：学生 {student['name']} 的答案数量({len(answers)})与问题数量({expected})不匹配，将进行截断或补空")
            if len(answers) > expected:
                answers = answers[:expected]
            else:
                answers += [""] * (expected - len(answers))

        # 填充到对应列（从第2行开始，索引1）
        for i, row_idx in enumerate(row_indices):
            df.iloc[row_idx, col] = answers[i] if i < len(answers) else ""

        # 增量保存：即使后面某个学生失败，之前的结果也已经落盘
        df.to_excel(output_path, index=False, header=False)
        print(f"  已保存进度 -> {output_path}")

    print(f"完成！所有答案已填回：{output_path}")


# ---------- 主程序 ----------
if __name__ == "__main__":
    students_file = "/home/n50059067/Vman/students.json"
    excel_path = "/home/n50059067/Vman/动图.xlsx"
    output_path = "问卷答案_已填.xlsx"

    # 加载学生数据
    students = load_students_from_json(students_file)
    print(f"成功加载 {len(students)} 个学生画像。")

    # 提取问题
    questions, row_indices, _ = extract_questions_from_excel(excel_path)
    print(f"共提取 {len(questions)} 个问题。")

    # 批量生成并填充
    fill_excel_with_students(excel_path, students, questions, row_indices, output_path)
