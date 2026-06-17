from profile import generate_student
import re
import zipfile
from openai import OpenAI
import pandas as pd

# ---------- 提取 xlsx 文本 ----------
def extract_text_from_excel(excel_path, question_col=2, skip_header=True):
    """
    从 Excel 提取题目文本（默认C列，跳过表头）
    返回格式化后的文本，可直接给大模型
    """
    df = pd.read_excel(excel_path, header=None)
    start = 1 if skip_header else 0
    questions = []
    for i in range(start, df.shape[0]):
        q = str(df.iloc[i, question_col]).strip() if pd.notna(df.iloc[i, question_col]) else ''
        if q:
            questions.append(q)
    return '\n\n'.join(questions)

def parse_answers(text):
    """按顺序解析答案列表（不用匹配题目了）"""
    answers = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        # 去掉可能的题号前缀
        line = re.sub(r'^第\d+[题][：:.\s]*', '', line)
        line = re.sub(r'^\d+[.、．]\s*', '', line)
        answers.append(line)
    return answers


def fill_excel(original_path, answers_list, output_path):
    df = pd.read_excel(original_path, header=None)
    
    # 确保D列存在
    if df.shape[1] < 4:
        df[3] = ''
    
    ans_idx = 0
    # 从第1行开始（跳过表头）
    for i in range(1, df.shape[0]):
        question = str(df.iloc[i, 2]).strip() if pd.notna(df.iloc[i, 2]) else ''
        if not question:
            continue
        if ans_idx < len(answers_list):
            df.iloc[i, 3] = answers_list[ans_idx]
            ans_idx += 1
    
    df.to_excel(output_path, index=False, header=False)
    print(f"成功填充 {ans_idx} 个答案到 D 列（从第2行开始）")
    return df

student = generate_student()

print("【随机生成的学生画像】")
for key, value in student.items():
    if key == "smart_devices" or key == "purchase_reasons" or key == "hobbies":
        print(f"{key}: {', '.join(value)}")
    else:
        print(f"{key}: {value}")
print("=" * 50)

excel_path = "/home/n50059067/Vman/动图.xlsx"
output_path = "/home/n50059067/Vman/问卷答案_已填.xlsx"
text = extract_text_from_excel(excel_path)

system_prompt = f"""你是一个真实的大学生，请严格按照以下个人信息逐题填写问卷：

姓名：{student['name']}
性别：{student['gender']}
年龄：{student['age']}岁
学历：{student['education']}（{student['grade']}）
专业：{student['major']}
MBTI：{student['mbti']}
月生活费预算：{student['monthly_budget']}元
当前使用的手机：{student['phone']}
拥有的智能设备：{', '.join(student['smart_devices'])}
购买手机时最看重的因素（多选）：{', '.join(student['purchase_reasons'])}
兴趣爱好：{', '.join(student['hobbies'])}

基于以上身份给出真实、合理的个人选择。直接逐题作答。

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
        {"role": "user", "content": text}
    ],
)

result = response.choices[0].message.content
print(result)

answers = parse_answers(result)

df_temp = pd.read_excel(excel_path, header=None)
question_rows = [i for i in range(1, df_temp.shape[0]) if pd.notna(df_temp.iloc[i, 2]) and str(df_temp.iloc[i, 2]).strip()]
expected_num = len(question_rows)

# 确保长度一致
if len(answers) != expected_num:
    print(f"警告：答案数量({len(answers)})与问题数量({expected_num})不匹配，将进行截断或补空")
    if len(answers) > expected_num:
        answers = answers[:expected_num]
    else:
        answers += [""] * (expected_num - len(answers))

fill_excel(excel_path, answers, output_path)
print(f"完成！答案已填回：{output_path}")
