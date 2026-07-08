import re
import random
import pandas as pd
from openai import OpenAI
import json

from profile_builder import build_profile_xml, build_style_hint

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

MEMORY_PROMPT = """不要写日记体流水账，请为自己整理一份高密度的"个人记忆库"，作为你之后回忆自己经历、习惯和数据的依据。严格按下面四个小标题分块输出，块内按行/按点写，信息密度要高，不要用完整段落把内容连成一段叙事：

【人物经历】
用2-3句话说清楚自己的成长背景、性格是怎么形成的、有没有什么长期影响自己的经历或习惯，不超过80字。

【近期事件】
列6-8条最近一个月内发生的具体事情，每条单独一行，格式为"大致时间+事情经过+涉及的人+结果或感受"。事情要具体到能被后续问卷直接引用，比如具体做了什么、买了什么、和谁发生了什么，不要写"过得很充实"这种空话。

【习惯与规律】
分点列出作息时间、学习/上课规律、手机使用习惯（刷什么、玩什么、大致用量）、周末通常怎么过、消费习惯，每一点尽量给出具体的时间段、频率或数量。

【关键数据】
列8-12项与自己相关、之后回答问卷时可能会用到的具体数字，比如每日屏幕使用时长、每月话费/生活费花销、相册照片数量、每天刷短视频次数或时长、微信好友数、常联系的人数、追的剧/玩的游戏数量等。数字要符合自己的画像和上面写的经历，要有个人特色，不要凑整数、不要和"一般人"给出相似的数字。如果上面的个人信息里已经给出某个具体数值或范围（比如生活费、手机型号），这里要在其基础上给出更精确、不矛盾的数字，不要编出和画像冲突的新版本；画像没提到的再由你自己创造。

每一条都要有实际内容，不要泛泛而谈，不要加多余的总结或结尾语。"""

def generate_personal_memory(persona_prompt):
    """
    让模型基于人设生成一份结构化的"个人记忆库"（人物经历/近期事件/习惯规律/关键数据），
    而不是流水账式的自然语言日记。这份记忆会作为 assistant 历史消息带入下一次请求，
    使问卷答案里的细节、数字有据可依，而不是逐题现场编。
    """
    response = client.chat.completions.create(
        model="Qwen3-32B",
        messages=[
            {"role": "system", "content": persona_prompt},
            {"role": "user", "content": MEMORY_PROMPT},
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
    # 构建学生画像描述字符串（用于system_prompt），用 XML 标签区分人设和具体事实
    profile_str = build_profile_xml(student)

    style_hint = build_style_hint(student)
    style_block = f"\n【说话风格】{style_hint}，回答时让这种性格特点体现在语气和用词上，不要每个人听起来都是一个调调。\n" if style_hint else ""

    persona_prompt = f"""你是一个真实的大学生，以下是你的个人信息：
                    {profile_str}
                    **充分代入角色**，把自己当成一个有血有肉的人。可以适当添加一些人物背景，人物性格。
                    {style_block}
                """

    # 先让模型基于人设生成结构化的"个人记忆库"，再带着这份记忆去答题，
    # 而不是直接甩问题让模型现场编答案
    memory = generate_personal_memory(persona_prompt)

    questions_text = '\n'.join(f"{i + 1}. {q}" for i, q in enumerate(questions))

    answer_prompt = f"""现在请回答下面的问卷。回答时首先要和你的个人信息保持一致，这是你身份的硬事实，不能矛盾；在此基础上，结合上面整理的个人记忆库中的具体细节和数字，让回答更真实、更细节。
        {RULE}
        {questions_text}"""

    response = client.chat.completions.create(
        model="Qwen3-32B",
        messages=[
            {"role": "system", "content": persona_prompt},
            {"role": "user", "content": MEMORY_PROMPT},
            {"role": "assistant", "content": memory},
            {"role": "user", "content": answer_prompt},
        ],
        temperature=0.8,
        top_p=0.9,
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
