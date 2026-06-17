import json
import random

with open("/home/n50059067/Vman/student_profile_config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)


def random_grade_and_age():
    grade = random.choice(CONFIG["grade"])
    if grade == "研究生":
        edu = "研究生"
        age = random.randint(CONFIG["age_range"]["研究生"]["min"], CONFIG["age_range"]["研究生"]["max"])
    else:
        edu = "本科"
        idx = CONFIG["grade"].index(grade)  # 大一0 -> 18, 大二1 -> 19 ...
        base = CONFIG["age_range"]["本科"]["min"]
        age = base + idx + random.randint(0, 1)
        age = min(age, CONFIG["age_range"]["本科"]["max"])
    return grade, edu, age

def random_major():
    category = random.choice(list(CONFIG["major"].keys()))
    return random.choice(CONFIG["major"][category])

def random_mbti():
    return random.choices(CONFIG["mbti"], weights=CONFIG["mbti_weight"], k=1)[0]

def random_monthly_budget():
    seg = random.choices(CONFIG["monthly_budget"]["segments"], weights=[s["weight"] for s in CONFIG["monthly_budget"]["segments"]])[0]
    low, high = seg["range"]
    steps = list(range(low, high + 1, 100))
    return random.choice(steps)

def random_phone():
    brands = list(CONFIG["phone_brand_weights"].keys())
    weights = list(CONFIG["phone_brand_weights"].values())
    brand = random.choices(brands, weights=weights, k=1)[0]
    model = random.choice(CONFIG["phones"][brand])
    return f"{brand} {model}"

def random_smart_devices():
    devices = CONFIG["smart_devices"]
    if random.random() < 0.15:
        return ["无"]
    else:
        k = random.randint(1, 3)
        candidates = [d for d in devices if d != "无"]
        return random.sample(candidates, min(k, len(candidates)))

def random_purchase_reasons():
    reasons = CONFIG["purchase_reasons"]
    k = random.randint(2, 5)
    return random.sample(reasons, k)

def random_hobbies(gender):
    # 按类别整理爱好
    categorized = {}
    for cat, items in CONFIG["hobbies"].items():
        filtered = []
        for h in items:
            if gender == "女" and h in CONFIG.get("boys_only", []):
                continue
            if gender == "男" and h in CONFIG.get("girls_only", []):
                continue
            filtered.append(h)
        if filtered:
            categorized[cat] = filtered

    categories = list(categorized.keys())
    # 随机选择 2~3 个不同的类别
    num_cats = random.randint(2, 3)
    selected_cats = random.sample(categories, min(num_cats, len(categories)))

    hobbies = []
    for cat in selected_cats:
        # 每个类别选 1~2 个爱好
        num_from_cat = random.randint(1, 3)
        available = categorized[cat]
        sampled = random.sample(available, min(num_from_cat, len(available)))
        hobbies.extend(sampled)

    # 如果不足 3 个，从所有爱好中补充
    all_hobbies = [h for cat in categorized.values() for h in cat]
    while len(hobbies) < 3:
        extra = random.choice(all_hobbies)
        if extra not in hobbies:
            hobbies.append(extra)

    # 如果超过 5 个，随机保留 5 个
    if len(hobbies) > 5:
        hobbies = random.sample(hobbies, 5)

    return hobbies

def generate_student():
    gender = random.choice(CONFIG["gender"])
    grade, edu, age = random_grade_and_age()
    major = random_major()
    mbti = random_mbti()
    budget = random_monthly_budget()
    phone = random_phone()
    devices = random_smart_devices()
    reasons = random_purchase_reasons()
    hobbies = random_hobbies(gender)
    
    return {
        "name": CONFIG["name"],         
        "gender": gender,
        "age": age,
        "education": edu,
        "grade": grade,
        "major": major,
        "mbti": mbti,
        "monthly_budget": budget,
        "phone": phone,
        "smart_devices": devices,
        "purchase_reasons": reasons,
        "hobbies": hobbies
    }
