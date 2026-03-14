import argparse
import math
import random
import sys
import re

# python predict.py -A 颜良,文丑 -B 关羽 -mA SURPRISE_ATTACK
# python predict.py -A 吕布 -B 刘备

# =====================================================================
# 1. PARSE TRAINED PARAMETERS
# =====================================================================
def load_parameters(filepath):
    C, m, MODEL = {}, {}, {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            csv_text = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {filepath}. Please place it in the same directory.")
        sys.exit(1)
        
    current_section = None
    for line in csv_text.strip().split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith("<!--"):
            current_section = line.replace("<!--", "").replace("-->", "").strip()
            continue
            
        parts = line.replace(':', ',').split(',')
        if len(parts) < 2: continue
        key, val = parts[0].strip(), float(parts[1].strip())
        
        if current_section == "武将战力": C[key] = val
        elif current_section == "战力修正": m[key] = val
        elif current_section == "模型参数": MODEL[key] = val
            
    # Safety check: Ensure essential parameters exist
    required_keys = ['alpha', 'beta', 'p']
    for k in required_keys:
        if k not in MODEL:
            print(f"Warning: {k} missing from parameters.csv. Falling back to default.")
            if k == 'alpha': MODEL['alpha'] = 0.4
            if k == 'beta': MODEL['beta'] = 0.02
            if k == 'p': MODEL['p'] = 2.0
            
    return C, m, MODEL

def expand_generals(general_string):
    generals = []
    for g in general_string.split(','):
        g = g.strip()
        match = re.match(r"(.*)\((\d+)\)", g)
        if match: generals.extend([match.group(1).strip()] * int(match.group(2)))
        else: generals.append(g)
    return generals

# =====================================================================
# 2. BATTLE MATH ENGINE (PROGRESSIVE TIMELINE)
# =====================================================================
def calc_c_group(generals_list, C_dict, p_val):
    if not generals_list: return 0.0
    scores = [C_dict.get(gen, 60.0) for gen in generals_list]
    sum_cp = sum(math.pow(max(0.1, s), p_val) for s in scores)
    return math.pow(sum_cp, 1.0 / p_val)

def simulate_timeline(A_names, B_names, A_mods, B_mods, C, m, MODEL):
    C_group_A = calc_c_group(A_names, C, MODEL['p'])
    C_group_B = calc_c_group(B_names, C, MODEL['p'])
    
    E_A = C_group_A + sum(m.get(mod, 0.0) for mod in A_mods)
    E_B = C_group_B + sum(m.get(mod, 0.0) for mod in B_mods)
    
    Delta = E_A - E_B
    beta = MODEL['beta']
    alpha = MODEL['alpha']
    
    if abs(Delta) < 0.001:
        return [{"round": 0, "event": "交战", "winner": "None"},
                {"round": 200, "event": "平", "winner": "None"}]

    winner = "A" if Delta > 0 else "B"
    abs_Delta = abs(Delta)
    
    # Adjusted thresholds specifically tuned for a low-beta (e.g. 0.01~0.05) environment
    states = [
        ("优势", 1.0), 
        ("败退", 3.75), 
        ("伤", 7.1), 
        ("阵斩/生擒", 9.35)
    ] #"阵斩/生擒": 10.0, "伤": 8.7, "胜": 5.5, "优势": 2.0, "平": 0.0,
    
    timeline = [{"round": 0, "event": "交战", "winner": "None"}]
    
    for event_name, threshold in states:
        target_tanh = threshold / 10.0
        if target_tanh >= 1.0: target_tanh = 0.9999
            
        u_required = math.atanh(target_tanh)
        t_required = math.pow(u_required / (beta * abs_Delta), 1.0 / alpha)
        t_rounded = max(1, int(math.ceil(t_required)))
        
        if t_rounded <= 200:
            if timeline[-1]["round"] == t_rounded:
                # Overwrite lower rank event happening at the exact same mathematical moment
                timeline[-1] = {
                    "round": t_rounded,
                    "event": event_name,
                    "winner": winner
                }
            else:
                timeline.append({
                    "round": t_rounded,
                    "event": event_name,
                    "winner": winner
                })
                
            # if event_name == "阵斩/生擒":
            #     break
        else:
            print('draw')
            break

    highest_event = timeline[-1]["event"]
    if highest_event not in ["败退", "伤", "阵斩/生擒"]:
        timeline.append({"round": 200, "event": "平", "winner": "None"})

    return timeline

# =====================================================================
# 3. LITERARY GENERATOR
# =====================================================================
def get_name_str(names):
    if len(names) == 1: return names[0]
    return "、".join(names[:-1]) + "与" + names[-1]

def generate_narrative(timeline, A_str, B_str, A_mods, B_mods):
    narrative = []
    
    # --- INTRO ---
    intro = random.choice([
        f"两阵对圆，{A_str}出马，大叫：‘贼将{B_str}快下马受降！’",
        f"阵上鼓声大震，{A_str}飞马出阵，直取{B_str}。",
        f"{A_str}挺枪纵马，大喝一声，径奔{B_str}。",
        f"忽见草坡后一彪军出，为首大将，乃{A_str}。挺枪跃马，径奔{B_str}而去。",
        f"{A_str}大怒，挥刀纵马来战。{B_str}挺枪出马。"
    ])
    if "SURPRISE_ATTACK" in A_mods: intro += f" {A_str}出其不意，骤马突袭，势如破竹！"
    elif "SURPRISE_ATTACK" in B_mods: intro += f" 谁知{B_str}早有防备，暗中反扑，打了{A_str}一个措手不及！"
    if "CHAOS" in A_mods: intro += f" 然{A_str}身陷重围，形势危急。"
    elif "CHAOS" in B_mods: intro += f" 此时{B_str}孤军深入，阵脚已乱。"
    narrative.append(intro)
    
    # --- CHRONOLOGICAL TIMELINE ---
    for i, step in enumerate(timeline):
        r = step["round"]
        event = step["event"]
        
        if event in ["平", "交战"]:
            v, l = A_str, B_str 
        else:
            v = A_str if step["winner"] == "A" else B_str
            l = B_str if step["winner"] == "A" else A_str
        
        # Round Header
        narrative.append(f"\n【第 {r} 合】" if r <= 1 else f"\n【斗至 {r} 合】")

        # Event Description
        if event == "交战":
            if len(timeline) > 1 and timeline[1]["round"] == 1:
                desc = random.choice([
                    f"{A_str}与{B_str}两马相交，兵器并举。",
                    f"二将方才交马，金鼓连天。"
                ])
            else:
                desc = random.choice([
                    f"{A_str}与{B_str}各不相让，金鼓齐鸣，喊声大震，震动天地。",
                    f"{A_str}与{B_str}二将奋力交锋，各展生平所学。但见：枪来剑去，似走龙蛇；马往人翻，如惊雷电。",
                    f"{A_str}与{B_str}斗到{timeline[i]["round"]}余合，不分胜负。"
                ])
            narrative.append(desc)
            
        elif event == "优势":
            desc = random.choice([
                f"{v}抖擞精神，越战越勇。{l}渐渐枪法散乱，只得勉强架隔遮拦。",
                f"只听得一声大喝，{v}轮刀纵马，不数合，{v}力大，{l}抵敌不住。",
                f"{l}惊得魂飞魄散,只有架隔之功，并无还手之力。"
            ])
            narrative.append(desc)
            
        elif event == "败退":
            desc = random.choice([
                f"{l}自知抵敌不住，虚晃一枪，拨马败走。",
                f"战不数合，{l}气力不加，荡开阵角，倒拖兵器，夺路而逃。",
                f"{l}隔遮拦不住，拨转马头，望大阵里乱走。",
                f"{l}大叫：‘少歇！’拨马入阵。",
                f"{l}拨马而逃,{v}纵马横戟，大叫：‘{l}贼休走！’",
                f"{l}料敌不过，拨马便走."
            ])
            narrative.append(desc)
            
        elif event == "伤":
            if i > 0 and timeline[i-1]["event"] not in ["败退", "优势"]:
                desc = random.choice([
                    f"{l}躲闪不及，被{v}兵刃伤了躯体，鲜血迸流，坠下马来！",
                    f"{v}手起处，早将{l}砍中，{l}痛呼一声，伏鞍而逃。"
                ])
            else:
                desc = random.choice([
                    f"正追赶间，{v}赶上一步，一戟刺中{l}后心。{l}大惊失色，险些落马。",
                    f"{l}正欲脱身，却被{v}赶上伤了肩臂。",
                    f"{v}纵马大喝：‘{l}小儿，休走！’,赶上砍伤{l}。"
                ])
            narrative.append(desc)
            
        elif event == "阵斩/生擒":
            if r <= 3:
                desc = random.choice([
                    f"交马不及数合，{v}大喝一声，犹如巨雷，手起刀落，将{l}斩于马下！",
                    f"{l}措手不及，被{v}一枪刺中咽喉，死于非命。",
                    f"斗不{timeline[i]["round"]}合，{l}被{v}大喝一声，一矛刺下马去。"
                ])
            else:
                desc = random.choice([
                    f"{v}大呼：‘休走！’随后赶来！{l}伤重无力，躲闪不及，被{v}赶上手起一刀，劈为两段！",
                    f"{v}纵马如飞，生擒{l}过去，挟在腋下掷于阵前，众军骇然。",
                    f"{l}刀法已乱，被{v}一刀砍下头来。"
                ])
            narrative.append(desc)
            
        elif event == "平":
            desc = random.choice([
                f"两军恐己方有失，各自鸣金收兵。{A_str}与{B_str}各自拨马回阵。",
                f"天色已晚，双方人困马乏，各自退军，未分胜负。",
                f"斗到{timeline[i]["round"]}合，大雨如注，各自引军分散。"
            ])
            narrative.append(desc)

    return "\n".join(narrative)

# =====================================================================
# 4. MAIN EXECUTION
# =====================================================================
def main():
    parser = argparse.ArgumentParser(description="Predict RotTK battles progressively.")
    parser.add_argument("-A", "--side_A", type=str, required=True, help="Side A (e.g. '吕布')")
    parser.add_argument("-B", "--side_B", type=str, required=True, help="Side B (e.g. '刘备,关羽')")
    parser.add_argument("-mA", "--mods_A", type=str, default="", help="Modifiers for Side A")
    parser.add_argument("-mB", "--mods_B", type=str, default="", help="Modifiers for Side B")
    
    args = parser.parse_args()
    A_names = expand_generals(args.side_A)
    B_names = expand_generals(args.side_B)
    
    A_mods = [mod.strip() for mod in args.mods_A.split(",") if mod.strip()]
    B_mods = [mod.strip() for mod in args.mods_B.split(",") if mod.strip()]
    
    C, m, MODEL = load_parameters("parameters.csv")
    A_str = get_name_str(A_names)
    B_str = get_name_str(B_names)
    
    timeline = simulate_timeline(A_names, B_names, A_mods, B_mods, C, m, MODEL)
    
    print("\n" + "="*50)
    print(" 📖 演义推演 (ROMANCE NARRATIVE RECONSTRUCTION)")
    print("="*50)
    print(generate_narrative(timeline, A_str, B_str, A_mods, B_mods))
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
