import math
import re
import numpy as np
from scipy.stats import norm
# pip install scipy

with open('parameters.csv', 'r', encoding='utf-8') as f:
    parameters_csv = f.read()

with open('records.md', 'r', encoding='utf-8') as f:
    records_md = f.read()

OUTCOME_SCORES = {
    "阵斩/生擒": 10.0, "伤": 8.7, "胜": 5.5, "优势": 2.0, "平": 0.0,
    "劣势": -2.0, "负": -5.5, "被伤": -8.7, "被阵斩/生擒": -10.0
}

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
        
        if current_section == "武将战力": C[key] = val
        elif current_section == "战力修正": m[key] = val
        elif current_section == "修正约束":
            if key.startswith("max_"): bounds.setdefault(key[4:], [None, None])[1] = val 
            elif key.startswith("min_"): bounds.setdefault(key[4:], [None, None])[0] = val
        elif current_section == "模型参数": model_params[key] = val
        elif current_section == "训练参数": train_params[key] = val
    return C, m, bounds, model_params, train_params

def expand_generals(general_string):
    generals = []
    for g in general_string.split(','):
        g = g.strip()
        match = re.match(r"(.*)\((\d+)\)", g)
        if match:
            generals.extend([match.group(1).strip()] * int(match.group(2)))
        else:
            generals.append(g)
    return generals

def parse_modifiers(mod_string):
    if mod_string.strip() in ["无", "", "None"]: return []
    return [m.split('(')[0].strip() for m in mod_string.split(',') if m.split('(')[0].strip()]

def parse_records(md_text):
    battles = []
    for line in md_text.strip().split('\n'):
        if not line.startswith('|') or '战斗名称' in line or '---' in line: continue
        cols = [c.strip() for c in line.split('|')][1:-1]
        if len(cols) < 7: continue
        try: turns = int(cols[4])
        except: turns = 5
        battles.append((expand_generals(cols[1]), expand_generals(cols[2]), cols[3], turns, parse_modifiers(cols[5]), parse_modifiers(cols[6])))
    return battles

C, m, MOD_BOUNDS, MODEL, TRAIN = parse_parameters(parameters_csv)
battles = parse_records(records_md)

HARD_ANCHORS = {}#{"吕布": 100.0}
REFERENCES = ["刘备", "沙摩柯", "曹休", "周仓", "邓忠", "公孙瓒", "徐盛", "刘封"]
for b in battles:
    for gen in b[0] + b[1]:
        if gen not in C:
            C[gen] = 60.0  
            HARD_ANCHORS[gen] = 60.0 

for b in battles:
    for mod in b[4] + b[5]:
        if mod not in m: m[mod] = 0.0

def calc_c_group(generals, p_val):
    return math.pow(sum(math.pow(max(0.1, C[gen]), p_val) for gen in generals), 1.0 / p_val)

def calc_dp_norm(generals, c_group, p_val):
    if len(generals) <= 1: return 0.0
    sum_cp = sum(math.pow(max(0.1, C[gen]), p_val) for gen in generals)
    sum_cp_lnc = sum(math.pow(max(0.1, C[gen]), p_val) * math.log(max(0.1, C[gen])) for gen in generals)
    return (max(0.1, c_group) / p_val) * ((sum_cp_lnc / sum_cp) - math.log(max(0.1, c_group)))

N_POP = 436.0
K_TOP = 62.0
MU_C = 60.0
SIGMA_C = 11.47
SIGMA_C_SQ = SIGMA_C**2 
PROB_FLOOR = 1e-5 

def calc_soft_floor_gradient(C_i):
    p_i = 1.0 - norm.cdf(C_i, loc=MU_C, scale=SIGMA_C)
    p_i = max(1e-10, min(p_i, 1.0 - 1e-10)) 
    bin_mu = N_POP * p_i
    bin_std = np.sqrt(N_POP * p_i * (1.0 - p_i))
    Z = (K_TOP - bin_mu) / bin_std
    prob_S = max(PROB_FLOOR, norm.cdf(Z))
    
    dp_dC = -norm.pdf(C_i, loc=MU_C, scale=SIGMA_C)
    u_z = K_TOP - N_POP * p_i
    du_dp = -N_POP
    v_z = bin_std
    dv_dp = (N_POP - 2*N_POP*p_i) / (2 * bin_std)
    dZ_dp = (du_dp * v_z - u_z * dv_dp) / (v_z**2)
    
    grad_floor = - (norm.pdf(Z) / prob_S) * dZ_dp * dp_dC
    return max(-5.0, min(grad_floor, 5.0))

prev_loss = float('inf')

for epoch in range(int(TRAIN['EPOCHS'])):
    dJ_dC = {gen: 0.0 for gen in C}
    dJ_dm = {mod: 0.0 for mod in m}
    dJ_dbeta, dJ_dalpha, dJ_dp = 0.0, 0.0, 0.0
    total_data_loss = 0.0
    
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
        total_data_loss += loss
        
        derivative_tanh = 1.0 - math.pow(math.tanh(u), 2)
        if abs(O_pred - O_obs) > 5.0:
            derivative_tanh = max(0.05, derivative_tanh) 
        delta_k = (O_pred - O_obs) * 10.0 * derivative_tanh
        t_alpha = math.pow(t, MODEL['alpha'])
        beta_t_alpha = MODEL['beta'] * t_alpha
        
        dJ_dbeta += delta_k * Delta * t_alpha
        dJ_dalpha += delta_k * MODEL['beta'] * Delta * t_alpha * math.log(max(1.1, t))
        
        for gen in A_list:
            ratio = C[gen] / max(0.1, C_group_A)
            ratio_deriv = max(0.05, math.pow(ratio, MODEL['p'] - 1))
            dJ_dC[gen] += delta_k * beta_t_alpha * 1.0 * ratio_deriv
        for mod in A_mods:
            dJ_dm[mod] += delta_k * beta_t_alpha * 1.0
        dJ_dp += delta_k * beta_t_alpha * 1.0 * calc_dp_norm(A_list, C_group_A, MODEL['p'])
        
        for gen in B_list:
            ratio = C[gen] / max(0.1, C_group_B)
            ratio_deriv = max(0.05, math.pow(ratio, MODEL['p'] - 1))
            dJ_dC[gen] += delta_k * beta_t_alpha * (-1.0) * ratio_deriv
        for mod in B_mods:
            dJ_dm[mod] += delta_k * beta_t_alpha * (-1.0)
        dJ_dp += delta_k * beta_t_alpha * (-1.0) * calc_dp_norm(B_list, C_group_B, MODEL['p'])

    sigma_o_sq = max(1.0, total_data_loss / max(1, len(battles))) 
    gamma = sigma_o_sq / SIGMA_C_SQ

    total_loss = total_data_loss
    loss_diff = abs(prev_loss - total_loss)
    
    if loss_diff < TRAIN['STOPPING_DELTA_LOSS'] and epoch > 100:
        break
        
    if loss_diff < TRAIN['LEARNING_RATE_DECAY_DELTA_LOSS']:
        TRAIN['LEARNING_RATE_C'] *= 0.99
        TRAIN['LEARNING_RATE_M'] *= 0.99
    
    prev_loss = total_loss

    for gen in C:
        if gen not in HARD_ANCHORS:
            grad_data = dJ_dC[gen]
            grad_gravity = 2.0 * gamma * (C[gen] - MU_C)
            LAMBDA_S = 2.0 * sigma_o_sq 
            grad_buoyancy = LAMBDA_S * calc_soft_floor_gradient(C[gen])
            
            total_grad = grad_data + grad_gravity 
            if gen not in REFERENCES:
                total_grad = total_grad + grad_buoyancy
            C[gen] -= TRAIN['LEARNING_RATE_C'] * total_grad
            C[gen] = max(0.1, C[gen])
            
    for mod in m:
        m[mod] -= TRAIN['LEARNING_RATE_M'] * dJ_dm[mod]
        if mod in MOD_BOUNDS:
            min_val, max_val = MOD_BOUNDS[mod]
            if min_val is not None: m[mod] = max(min_val, m[mod])
            if max_val is not None: m[mod] = min(max_val, m[mod])
    
    dJ_dbeta = max(-100.0, min(100.0, dJ_dbeta))
    MODEL['beta'] -= TRAIN['LEARNING_RATE_GLOBAL'] * dJ_dbeta
    MODEL['alpha'] -= TRAIN['LEARNING_RATE_GLOBAL'] * dJ_dalpha
    MODEL['p'] -= TRAIN['LEARNING_RATE_GLOBAL'] * dJ_dp
    
    # Locking beta exactly to 0.01 to force the spread
    # MODEL['beta'] = 0.01
    MODEL['alpha'] = max(0.1, min(MODEL['alpha'], 0.9))
    MODEL['p'] = max(1.0, min(MODEL['p'], 2.0))
    if epoch%100 == 0:
        leader_board = sorted(C.items(), key=lambda item: item[1], reverse=True)[:10]
        leader_string = "\n".join([f"{name}: {score:.2f}" for name, score in leader_board])
        print(f"Epoch: {epoch}, loss: {total_loss}, leader board: \n{leader_string} \n")


print(f"Final Loss: {total_loss:.4f} | Gamma: {gamma:.4f}\n")


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
