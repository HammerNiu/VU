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


RULE = """【强制规则】
1. 下面有若干道编号的题目，每题必须以 "Q<题号>|" 开头，紧接答案内容，例如：
   Q1|大概拍了450张左右，其中约80张是有意识用动态模式拍摄的
   Q2|主要用后置人像模式拍摄朋友合影
2. 每题只占一行，即使答案较长也不要换行，用句号或分号连接
3. 题号必须与题目编号一一对应，不要跳号、不要重复
4. 不要加解释、不要加多余空行、不要用 markdown"""

DIARY_PROMPT = """请你以第一人称，回忆一下自己最近一个月的生活，写成一段自然的流水账，内容尽量具体、生活化：
- 日常作息和最近的学习/上课情况
- 娱乐、刷手机、打游戏、追剧等习惯，最近在看什么/玩什么
- 周末通常怎么过
- 和室友、朋友、家人最近的互动，有没有什么印象比较深的小事、小摩擦或小惊喜
不用分点、不用小标题，就像随手回忆一样写成连贯的一段话，350-500字左右，可以写得琐碎一点、有点情绪，不用面面俱到，不要写成总结陈词。"""

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


def generate_life_diary(persona_prompt):
    """
    让模型先以第一人称回忆近一个月的生活，作为后续回答问卷的记忆基础。
    这段回忆会作为 assistant 历史消息带入下一次请求，
    使问卷答案里的细节、数字有据可依，而不是逐题现场编。
    """
    response = client.chat.completions.create(
        model="Qwen3-32B",
        messages=[
            {"role": "system", "content": persona_prompt},
            {"role": "user", "content": DIARY_PROMPT},
        ],
        temperature=1.0,
        top_p=0.95,
        presence_penalty=0.4,
    )
    return response.choices[0].message.content.strip()


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

    persona_prompt = f"""你是一个真实的大学生，以下是你的个人信息：
                    {profile_str}
                    **充分代入角色**，把自己当成一个有血有肉的人。可以适当添加一些人物背景，人物性格。
                    {style_block}{phone_block}
                """

    # 先让模型回忆近一个月的生活，再带着这段"记忆"去答题，
    # 而不是直接甩问题让模型现场编答案
    diary = generate_life_diary(persona_prompt)

    questions_text = '\n'.join(f"{i + 1}. {q}" for i, q in enumerate(questions))

    answer_prompt = f"""现在请回答下面的问卷。结合你刚才回忆的近期生活来作答，能对上的细节就对上，不用刻意每题都扯上；涉及具体数量、占比等数值时，请结合你的个人画像和上面提到的生活细节给出一个合理且有个人特色的数字，不要凑整、不要和"大多数人"给出相似的数值。

{RULE}

{questions_text}"""

    response = client.chat.completions.create(
        model="Qwen3-32B",
        messages=[
            {"role": "system", "content": persona_prompt},
            {"role": "user", "content": DIARY_PROMPT},
            {"role": "assistant", "content": diary},
            {"role": "user", "content": answer_prompt},
        ],
        temperature=0.8,
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
