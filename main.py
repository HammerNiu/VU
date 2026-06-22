import re
import pandas as pd
from openai import OpenAI
import json

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

def generate_answers_for_student(student, questions_text):
    """
    为单个学生生成问卷答案
    student: 学生画像字典
    questions_text: 所有问题拼接的字符串（以换行分隔）
    返回答案列表（字符串列表）
    """
    # 构建学生画像描述字符串（用于system_prompt）
    def format_dict(d, indent=0):
        lines = []
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append("  " * indent + f"{k}:")
                lines.extend(format_dict(v, indent+1))
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

    system_prompt = f"""你是一个真实的大学生，以下是你的个人信息：
                    {profile_str}
                    **充分代入角色**，把自己当成一个有血有肉的人。可以适当添加一些人物背景，人物性格。
                    针对问卷问题，给出真实、合理的个人回答，保证一致性。
                    **直接逐题作答**

                    【强制规则】
                    1. 下面有若干道题，你只需输出答案，**不要重复题目**
                    2. 每行一个答案，按题目顺序输出
                    3. 选择题直接写选项字母和选项内容，开放题写你的真实回答
                    4. 不要加序号、不要加解释、不要空行 
                """

    client = OpenAI(
        api_key="token-abc123",
        base_url="http://100.102.218.124:3236/v1"
    )

    response = client.chat.completions.create(
        model="Qwen3-32B",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": questions_text}
        ],
    )

    result = response.choices[0].message.content
    answers = [line.strip() for line in result.strip().split('\n') if line.strip()]
    return answers

def fill_excel_with_students(excel_path, students, questions, row_indices, output_path):
    """
    将每个学生的答案填入对应的列（D列开始）
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
        # 将问题列表拼接成文本（每行一个问题）
        questions_text = '\n'.join(questions)
        answers = generate_answers_for_student(student, questions_text)

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

    # 保存
    df.to_excel(output_path, index=False, header=False)
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
