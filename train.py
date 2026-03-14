import math
import re

# =====================================================================
# 1. INPUT DATA
# =====================================================================

with open('parameters.csv', 'r', encoding='utf-8') as f:
    parameters_csv = f.read()

with open('records.md', 'r', encoding='utf-8') as f:
    records_md = f.read()

OUTCOME_SCORES = {
    "阵斩/生擒": 10.0, "伤": 8.7, "胜": 5.5, "优势": 2.0, "平": 0.0,
    "劣势": -2.0, "负": -5.5, "被伤": -8.7, "被阵斩/生擒": -10.0
}

# =====================================================================
# 2. PARSING FUNCTIONS
# =====================================================================

def parse_parameters(csv_text):
    C, m, bounds, model_params, train_params = {}, {}, {}, {}, {}
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
        
        if current_section == "武将战力":
            C[key] = val
        elif current_section == "战力修正":
            m[key] = val
        elif current_section == "修正约束":
            if key.startswith("max_"):
                mod_name = key[4:]
                bounds.setdefault(mod_name, [None, None])[1] = val # [min, max]
            elif key.startswith("min_"):
                mod_name = key[4:]
                bounds.setdefault(mod_name, [None, None])[0] = val
        elif current_section == "模型参数":
            model_params[key] = val
        elif current_section == "训练参数":
            train_params[key] = val
            
    return C, m, bounds, model_params, train_params

def expand_generals(general_string):
    """Parses '刘备, 关羽' -> ['刘备', '关羽']. Parses 'UNKNOWN_GENERAL(10)' -> 10 generic entries"""
    generals = []
    for g in general_string.split(','):
        g = g.strip()
        # Check for multipliers like UNKNOWN_GENERAL(10)
        match = re.match(r"(.*)\((\d+)\)", g)
        if match:
            base_name = match.group(1).strip()
            count = int(match.group(2))
            generals.extend([base_name] * count)
        else:
            generals.append(g)
    return generals

def parse_modifiers(mod_string):
    """Parses 'CHAOS(被围攻), SURPRISE_ATTACK(突袭)' -> ['CHAOS', 'SURPRISE_ATTACK']"""
    if mod_string.strip() in ["无", "", "None"]: return []
    mods = []
    for m in mod_string.split(','):
        base_mod = m.split('(')[0].strip() # Strip specific sub-type tags
        mods.append(base_mod)
    return mods

def parse_records(md_text):
    battles = []
    for line in md_text.strip().split('\n'):
        if not line.startswith('|') or '战斗名称' in line or '---' in line:
            continue
        cols = [c.strip() for c in line.split('|')][1:-1]
        if len(cols) < 7: continue
        
        A_list = expand_generals(cols[1])
        B_list = expand_generals(cols[2])
        outcome = cols[3]
        try: turns = int(cols[4])
        except: turns = 5
        A_mods = parse_modifiers(cols[5])
        B_mods = parse_modifiers(cols[6])
        
        battles.append((A_list, B_list, outcome, turns, A_mods, B_mods))
    return battles

# =====================================================================
# 3. INITIALIZATION & ANCHORING
# =====================================================================

C, m, MOD_BOUNDS, MODEL, TRAIN = parse_parameters(parameters_csv)
battles = parse_records(records_md)

# Build Hard Anchors dynamically
HARD_ANCHORS = {"吕布": 100.0} # Absolute ceiling
for b in battles:
    for gen in b[0] + b[1]:
        if gen not in C:
            C[gen] = 60.0  # Default all missing/generics to 60
            HARD_ANCHORS[gen] = 60.0 # Anchor them permanently

# Initialize missing modifiers to 0.0
for b in battles:
    for mod in b[4] + b[5]:
        if mod not in m: m[mod] = 0.0

# =====================================================================
# 4. MATHEMATICAL ENGINE
# =====================================================================

def calc_c_group(generals, p_val):
    sum_cp = sum(math.pow(C[gen], p_val) for gen in generals)
    return math.pow(sum_cp, 1.0 / p_val)

def calc_dp_norm(generals, c_group, p_val):
    if len(generals) <= 1: return 0.0
    sum_cp = sum(math.pow(C[gen], p_val) for gen in generals)
    sum_cp_lnc = sum(math.pow(C[gen], p_val) * math.log(C[gen]) for gen in generals)
    return (c_group / p_val) * ((sum_cp_lnc / sum_cp) - math.log(c_group))

# =====================================================================
# 5. GRADIENT DESCENT TRAINING LOOP
# =====================================================================

print("Starting Training Pipeline...")
prev_loss = float('inf')

for epoch in range(int(TRAIN['EPOCHS'])):
    dJ_dC = {gen: 0.0 for gen in C}
    dJ_dm = {mod: 0.0 for mod in m}
    dJ_dbeta, dJ_dalpha, dJ_dp = 0.0, 0.0, 0.0
    total_loss = 0.0
    
    for A_list, B_list, outcome_str, t, A_mods, B_mods in battles:
        if outcome_str not in OUTCOME_SCORES: continue
        O_obs = OUTCOME_SCORES[outcome_str]
        
        C_group_A = calc_c_group(A_list, MODEL['p'])
        C_group_B = calc_c_group(B_list, MODEL['p'])
        
        E_A = C_group_A + sum(m[mod] for mod in A_mods)
        E_B = C_group_B + sum(m[mod] for mod in B_mods)
        
        Delta = E_A - E_B
        u = MODEL['beta'] * Delta * math.pow(t, MODEL['alpha'])
        O_pred = 10.0 * math.tanh(u)
        
        loss = 0.5 * (O_pred - O_obs)**2
        total_loss += loss
        
        # Chain Rule Term
        derivative_tanh = 1.0 - math.pow(math.tanh(u), 2)
        if abs(O_pred - O_obs) > 5.0:
            derivative_tanh = max(0.05, derivative_tanh) # Added a floor to prevent gradient vanishing
        delta_k = (O_pred - O_obs) * 10.0 * derivative_tanh
        t_alpha = math.pow(t, MODEL['alpha'])
        beta_t_alpha = MODEL['beta'] * t_alpha
        
        # Global Gradients
        dJ_dbeta += delta_k * Delta * t_alpha
        dJ_dalpha += delta_k * MODEL['beta'] * Delta * t_alpha * math.log(max(1.1, t))
        
        # Side A Gradients
        for gen in A_list:
            ratio = C[gen] / max(0.1, C_group_A)
            ratio_deriv = max(0.05, math.pow(ratio, MODEL['p'] - 1))
            dJ_dC[gen] += delta_k * beta_t_alpha * 1.0 * ratio_deriv
        for mod in A_mods:
            dJ_dm[mod] += delta_k * beta_t_alpha * 1.0
        dJ_dp += delta_k * beta_t_alpha * 1.0 * calc_dp_norm(A_list, C_group_A, MODEL['p'])
        
        # Side B Gradients
        for gen in B_list:
            ratio = C[gen] / max(0.1, C_group_B)
            ratio_deriv = max(0.05, math.pow(ratio, MODEL['p'] - 1))
            dJ_dC[gen] += delta_k * beta_t_alpha * (-1.0) * ratio_deriv
        for mod in B_mods:
            dJ_dm[mod] += delta_k * beta_t_alpha * (-1.0)
        dJ_dp += delta_k * beta_t_alpha * (-1.0) * calc_dp_norm(B_list, C_group_B, MODEL['p'])

    # --- ADVANCED TRAINING MECHANICS ---
    loss_diff = abs(prev_loss - total_loss)
    
    # 1. Early Stopping
    if loss_diff < TRAIN['STOPPING_DELTA_LOSS']:
        print(f"Early stopping triggered at Epoch {epoch} (Loss Delta: {loss_diff:.5f})")
        break
        
    # 2. Learning Rate Decay (Simulated Annealing)
    if loss_diff < TRAIN['LEARNING_RATE_DECAY_DELTA_LOSS']:
        TRAIN['LEARNING_RATE_C'] *= 0.95
        TRAIN['LEARNING_RATE_M'] *= 0.95
        print(f"Learning rate decay for general: {TRAIN['LEARNING_RATE_C']}, for modifier: {TRAIN['LEARNING_RATE_C']} \n")
    
    prev_loss = total_loss

    # --- APPLY GRADIENTS ---
    for gen in C:
        if gen not in HARD_ANCHORS:
            C[gen] -= TRAIN['LEARNING_RATE_C'] * dJ_dC[gen]
            C[gen] = max(60.0, C[gen])
            
    for mod in m:
        m[mod] -= TRAIN['LEARNING_RATE_M'] * dJ_dm[mod]
        # Bounding / Clipping
        if mod in MOD_BOUNDS:
            min_val, max_val = MOD_BOUNDS[mod]
            if min_val is not None: m[mod] = max(min_val, m[mod])
            if max_val is not None: m[mod] = min(max_val, m[mod])
    
    dJ_dbeta = max(-100.0, min(100.0, dJ_dbeta))
    MODEL['beta'] -= TRAIN['LEARNING_RATE_GLOBAL'] * dJ_dbeta
    MODEL['alpha'] -= TRAIN['LEARNING_RATE_GLOBAL'] * dJ_dalpha
    MODEL['p'] -= TRAIN['LEARNING_RATE_GLOBAL'] * dJ_dp
    
    MODEL['beta'] = max(0.01, MODEL['beta'])
    MODEL['alpha'] = max(0.1, min(MODEL['alpha'], 0.9))
    MODEL['p'] = max(1.0, min(MODEL['p'], 2.0))
    if epoch%100 == 0:
        leader_board = sorted(C.items(), key=lambda item: item[1], reverse=True)[:10]
        leader_string = "\n".join([f"{name}: {score:.2f}" for name, score in leader_board])
        print(f"Epoch: {epoch}, loss: {total_loss}, leader board: \n{leader_string} \n")

print(f"Final Loss: {total_loss:.4f}\n")

# =====================================================================
# 6. OUTPUT GENERATOR
# =====================================================================

def generate_output_csv():
    lines = []
    lines.append("<!-- 武将战力 -->")
    for gen, score in sorted(C.items(), key=lambda x: x[1], reverse=True):
        if gen not in HARD_ANCHORS or gen == "吕布": # Only print trained/main anchors
            lines.append(f"{gen},{score:.2f}")
            
    lines.append("<!-- 战力修正 -->")
    for mod, val in sorted(m.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"{mod},{val:.2f}")
        
    lines.append("<!-- 修正约束 -->")
    for mod, bounds in MOD_BOUNDS.items():
        if bounds[1] is not None: lines.append(f"max_{mod},{bounds[1]}")
        if bounds[0] is not None: lines.append(f"min_{mod},{bounds[0]}")
        
    lines.append("<!-- 模型参数 -->")
    for param, val in MODEL.items():
        lines.append(f"{param},{val:.3f}")
        
    lines.append("<!-- 训练参数 -->")
    for param, val in TRAIN.items():
        if "LEARNING_RATE" in param:
            lines.append(f"{param},{val:.4f}")
        else:
            lines.append(f"{param},{val}")
            
    return "\n".join(lines)

print("=========== UPDATED PARAMETERS.CSV ===========")
print(generate_output_csv())
