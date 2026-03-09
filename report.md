
### 0. Objective & Methodology Rationale
---

**Objective:**
There have been perpetual community debates on 三国演义武将战力排名 (General Combat Skill Rankings). Given the extensive and detailed combat records described in the 原著 (original text), ranking generals is fundamentally an easy optimization problem using mathematical models.

**Rejected Methodology: Graph Topological Sort**
Traditional ranking algorithms like topological sorting fail on this dataset due to the nature of literary combat:
*   **Not Directed/Acyclic:** The combat network contains non-transitive loops (A > B, B > C, C > A).
*   **Isolated Nodes:** Many generals fight in isolated regional clusters and never cross swords with the central network.
*   **Non-Deterministic Outcomes:** Battle results are highly contextual, involving draws, varying round counts (回合数), and situational modifiers, rather than binary win/loss edges.

**Core Methodology: Maximum Total Probability Estimation**
To account for the non-deterministic nature of the data, we reframe the ranking system as a probability optimization problem. By treating a general's Base Combat Skill ($C$) and tactical modifiers ($m$) as hidden variables, we calculate the probability of a specific combat outcome occurring. 

The objective is to find the exact configuration of all generals' $C$ values that yields the **Maximum Total Probability** of producing the exact combat dataset observed in the 原著.


### 1. Data Collection
---
Since we are only interested in top ranking generals, the following generals are picked for ranking according to “《三国演义》160员武将排名：华雄第四档，五虎第二档”(https://zhuanlan.zhihu.com/p/1899763014980310730).
```
第一档：吕布、兀突骨（2人）
第二档：关羽、张飞、赵云、马超、黄忠、典韦、许褚、颜良、文丑、曲阿小将（10人）
第三档：庞德、魏延、徐晃、孙策、太史慈、夏侯惇、夏侯渊、张辽、张郃、甘宁、曹彰、曹洪、乐进、臧霸、文聘、凌统、周泰、程普、李严、高览、关平、文鸯、管亥（23人）
第四档：华雄、高顺、杨任、何曼、泠苞、王平、马岱、陈武、曹仁、张任、姜维、邓艾、诸葛尚、关兴、张苞、王双、徐质、李典、鄂焕、纪灵、武安国（21人）
```
*copied from "《三国演义》160员武将排名：华雄第四档，五虎第二档"*

### 1.1 Data Extraction

Used Gemini + Search to collect all combat records for the selected generals.

**Problem:** AI LLMs suffer from poor recall when asked for bulk data extraction. A single prompt asking for all battles results in severe omissions.
**Solution:** Programatically iterate through the generals individually. Ask the AI to search for battles of specific generals, format the output, and then use code to dedupe and merge the results. To avoid API fees, this was executed manually in small batches using the following prompt:

```text
Search online for 《三国演义》 武将交战记录 for the following major characters. Generate a markdown table with these exact columns:
1. 战斗名称 (String)
2. 交战方A (List[String]: comma separated, e.g., 刘备, 关羽, 张飞)
3. 交战方B (List[String])
4. 交战结果 (Enum)
5. 回合数 (Integer: infer and note if unspecified)
6. A方修正 (List[String])
7. B方修正 (List[Enum])
8. 原著描述 (String: exact novel quote)
9. 特殊情况注释 (String)

Allowed Enums for 交战结果:
["阵斩/生擒", "被阵斩/生擒", "伤", "被伤", "胜", "负", "优势", "劣势", "平"]

Allowed Enums for 标准修正 (Modifiers affecting base skill AT THE START of round 1. Equipment is base skill, not a modifier):
- SURPRISE_ATTACK (突袭/偷袭/暗器/拖刀计)
- ARCHERY (射箭)
- BERSERKER (舍命/卸甲)
- RELUCTANT (诱敌/战意不足)
- EXHAUSTED (疲惫/力穷)
- CHAOS (被包围/军队被伏击/撤退/军乱)
- IMPAIRED (负伤/带病/大醉)
- AGE (年老/初出茅庐)
- LETHAL_RNG (无兵器/马失前蹄/溺水)

If a battle is a macro-army clash and not direct general combat, leave all blank except 战斗名称, 交战方A, 交战方B, and 原著描述.

Execute the following workflow to maximize recall:
1. Iterate each character in the provided list.
2. Search specifically for that character's 1v1 and 1vMany engagements.
3. Append results to the final table.

Do this for characters: [Insert Batch Here, e.g., 吕布, 兀突骨]
```

### 1.2 Data Standardization

Raw extraction yields dozens of inconsistent literary terms:
```
激愤, 舍命, 奋勇, 战意十足, 突袭, 偷袭, 射箭, 暗器, 拖刀计, 反击, 以逸待劳, 智斗, 严阵以待, 占优地形, 登城, 威压, 气势惊人, 卸甲, 连战, 年少。
疲惫, 力穷, 气力不加, 战意不足, 撤退中, 败军之际, 败退中, 军乱, 阵乱, 乱阵, 兵败, 惊恐, 惊骇, 胆裂, 胆怯, 震慑, 慌乱, 措手不及, 无防备, 毫无防备, 偷袭失败, 负伤, 被伤, 带病, 溺水, 大醉, 年老, 围攻, 孤立无援, 被包围, 马失前蹄, 袍袖钩挂, 无兵器, 弃兵器步战, 武力差距大。
诱敌, 疑兵, 谨慎, 慎重。
```

To prevent mathematical overfitting, unique literary scenarios are compressed into 9 core mechanics. Modifiers must fit the following criteria:
*   **Pre-Combat State:** Must affect effective battle skill at the start of Round 1. States caused *by* the current battle do not count.
*   **External/Physical Limits:** Inherent traits and signature equipment are intrinsic to Base Combat Skill ($C$). Psychological effects like fear or intimidation are a general's own failure and do not warrant a modifier.
*   **Categorize by nature:** Modifiers in the same category do not stack (e.g., 疲惫 and 力穷 map to one `EXHAUSTED` debuff). Different categories can stack.

Below are the 9 categories:

```
🟢 1. Surprise Attack (突袭)
Collapses all forms of catching the enemy off-guard or using concealed melee tactics into a single positive buff for the attacker. (Removes the need for a "caught off-guard" debuff for the defender).
Modifiers Included: Surprise Attack (突袭), Sneak Attack (偷袭), Hidden Weapon (暗器), Drag-Blade Feint/Return Thrust (拖刀计 / 回马枪).

🟢 2. Archery / Ranged (弓箭)
Separated from melee surprise attacks, as archery relies on a completely different skill set and range vector.
Modifiers Included: Archery (射箭).

🟢 3. Berserker / Adrenaline (搏命状态)
Temporary physical and mental limit-breaking due to rage or facing certain death.
Modifiers Included: To the death (舍命), Enraged (激愤), Shedding Armor (卸甲).

🔴 4. Reluctance & Luring (战意不足 / 诱敌)
Collapses all situations where a general has no intention of winning the current melee clash (either because they are distracted, trying to escape, or deliberately faking a loss).
Modifiers Included: Lack of Will (战意不足), Reluctant/Distracted (无心恋战), Feigning Defeat/Luring (诱敌 / 诈败).
(Note: If "Luring/诈败" is used, the battle result must NOT be recorded as "Defeat/败", but rather as "Tactical Withdrawal" or "Advantage/优势" for the broader battle).

🔴 5. Stamina Exhaustion (体力透支)
"Fresh" is considered the baseline 0 modifier, we only apply a debuff to those who are explicitly drained.
Modifiers Included: Exhausted (疲惫), Force Spent (力穷 / 气力不加).

🔴 6. Battlefield Chaos & Outnumbered (局势劣势)
External macro-level factors surrounding the fighters.
Modifiers Included: Besieged/Outnumbered (围攻 / 孤立无援), Army Routed/Retreating (军乱 / 阵乱 / 败军之际).

🔴 7. Physical Health Impairment (机能受损)
Current biological debuffs on the general's body (excluding natural aging).
Modifiers Included: Injured (负伤 / 被伤), Sick (带病), Drunk (大醉).

🔴 8. Age & Experience (生理周期)
Permanent or semi-permanent limiters on peak output.
Modifiers Included: Elderly (年老), Inexperienced/Rookie (初出茅庐).

🔴 9. Lethal RNG & Freak Accidents (极端意外)
Purely circumstantial disasters that bypass standard combat math and generally guarantee a loss or death.
Modifiers Included: Disarmed (无兵器), Sleeve Caught (袍袖钩挂), Horse Stumbled (马失前蹄), Drowning (溺水).
```

To enforce this standardization across the dataset, the raw tables were passed back through the AI in batches using the following strict mapping instruction set.

```text
You are an expert data analyst specializing in the classical Chinese novel "Romance of the Three Kingdoms" (三国演义). Your task is to clean, standardize, and convert the combat modifiers (战力修正) and combat results (交战结果) for a single row of a general's dueling record.

Apply the following strict "9-Category Modifier System" and conversion rules to the input data. A general can only have a maximum of ONE modifier from each category. Do NOT invent new modifiers.

### MODIFIER CATEGORIES & MAPPING RULES:
1. **SURPRISE_ATTACK (突袭)**: 
   - *Map from:* 突袭, 偷袭, 暗器, 拖刀计, 回马枪.
   - *Opponent Transfer Rule:* If the victim has "措手不及" (Caught off-guard), "无防备", or "毫无防备", REMOVE it from the victim and give the attacker "突袭".
2. **ARCHERY (射箭)**:
   - *Map from:* 射箭, 放冷箭.
3. **BERSERKER (搏命)**: 
   - *Map from:* 舍命, 激愤, 卸甲, 奋勇. (Only use for actions that explicitly lower defense. Regular emotion changes do not count).
4. **RELUCTANT (战意不足)**:
   - *Map from:* 战意不足, 无心恋战, 诱敌, 诈败, 疑兵, 谨慎. (Do not overuse; strictly for intentionally hiding full strength).
   - *Result Modification Rule:* If mapped from "诈败" (Feigned defeat) or "诱敌" (Luring), the general did NOT lose martial-wise. You MUST change the "交战结果" to "战术撤退" or "平" (Draw).
5. **EXHAUSTED (疲惫)**:
   - *Map from:* 疲惫, 力穷, 气力不加.
   - *Removal Rule:* REMOVE "以逸待劳" (Fresh/Waiting at ease) from the opponent, as "Fresh" is the 0-baseline.
6. **CHAOS (局势劣势)**:
   - *Map from:* 包围, 孤立无援, 军乱, 阵乱, 败军之际, 撤退中. (Do not overuse; requires clear context of being outnumbered or army routing. Only battles happening *during* retreat incur CHAOS, retreats caused *by* the battle do not).
   - *Removal Rule:* Psychological states triggered by opponent skill (e.g., 气势惊人, 威压, 惊恐, 胆怯, 慌乱) are NOT modifiers. REMOVE them.
   - *Opponent Transfer Rule:* "包围" maps to the opponent's "被包围".
7. **IMPAIRED (机能受损)**:
   - *Map from:* 负伤, 被伤, 带病, 大醉.
8. **AGE (生理周期)**:
   - *Map from:* 年老, 初出茅庐, 年少.
9. **LETHAL_RNG (极端意外)**:
   - *Map from:* 无兵器, 袍袖钩挂, 马失前蹄, 溺水.

### GLOBAL RULES:
- 交战方 must be strictly a list of generals. Disallow: "...等六将", "...军". Use "KNOWN_GENERAL_1, ..., UNKNOWN_GENERAL(count)", or "SOLDIERS".
- Identify if each modifier is: caused by battle, happened after battle, or does not affect battle outcome. If any apply, REMOVE the modifier.
- Allowed 交战结果: 生擒/阵斩, 伤, 胜, 优势, 平, 劣势, 负, 被伤, 被生擒/阵斩.
- Your updated table should use modifiers formatted as: "STANDARD_MODIFIER(optional_very_brief_description_if_ambiguous)".
```

Again, to solve recall problem, sent to AI by small batches and did manual verification.


### 1.3 Final Standardized Dueling Records 

| 战斗名称 | 交战方A | 交战方B | 交战结果 | 回合数 | A方标准修正 | B方标准修正 | 原著描述 | 特殊情况注释 |
|------|------|------|------|-----|--------|--------|------|--------|
| 虎牢关之战 | 吕布 | 武安国 | 伤 | 10 | 无 | 无 | 战到十余合，一戟砍断安国手腕……弃锤于地而走。 | 吕布致残对方获胜 |
| 虎牢关之战 | 吕布 | 公孙瓒 | 胜 | 5 | 无 | 无 | 战不数合，瓒败走。吕布纵赤兔马赶来。 | 推测约5合 |
| 虎牢关之战 | 吕布 | 张飞 | 平 | 50 | 无 | 无 | 连斗五十余合，不分胜负。 |  |
| 三英战吕布 | 吕布 | 刘备, 关羽, 张飞 | 负 | 30 | CHAOS(被围攻) | 无 | 吕布架隔遮拦不定……荡开阵角，倒拖画戟，飞马便回。 | 关张合攻30合，刘备随后加入 |
| 长安之战 | 吕布 | 郭汜 | 伤 | 5 | 无 | 无 | 布举画戟直刺郭汜。汜后心处中戟，郭汜部将救回。 |  |
| 定陶之战 | 吕布 | 许褚 | 平 | 5 | 无 | 无 | 吕布出马，横戟大骂。许褚出马。战不数合，因布军乱，褚退回。 | 因吕布阵型混乱而止战 |
| 荥阳之战 | 吕布 | 夏侯惇 | 胜 | 10 | 无 | 无 | 惇挺枪出马，直取吕布。性急且战且走。布引铁骑掩杀，操军大乱。 |  |
| 濮阳之战 | 吕布 | 夏侯惇 | 平 | 30 | 无 | 无 | 夏侯惇截住吕布大战。斗到黄昏，大雨如注，各自引军分散。 | 战至黄昏因暴雨收兵 |
| 濮阳之战 | 吕布 | 许褚 | 平 | 20 | 无 | 无 | 斗二十合，不分胜负。操曰：‘吕布非一人可胜。’ | 已合并原表重复项 |
| 濮阳之战 | 吕布 | 许褚, 典韦, 夏侯惇, 夏侯渊, 李典, 乐进 | 负 | 10 | CHAOS(被包围) | 无 | 吕布遮拦不住，拨马回城。 | 曹操派六员大将夹攻吕布 |
| 小沛之战 | 吕布 | 张飞 | 平 | 100 | 无 | 无 | 两个好生厮杀。酣战一百余合，未见胜负。 |  |
| 下邳之战 | 吕布 | 关羽, 张飞 | 负 | 30 | RELUCTANT(战意不足), CHAOS(被围攻) | 无 | 布与关、张二将大战……布见势头不好，拨马便回。 | 吕布陷入埋伏且心恋妻妾战意不足 |
| 乌戈国之战 | 兀突骨 | 魏延 | 平 | 5 | 无 | RELUCTANT(诱敌) | 魏延与兀突骨交锋，不数合，延拨马便走。 | 魏延按诸葛亮之计诈败诱敌 |
| 汜水关之战 | 关羽 | 华雄 | 阵斩/生擒 | 1 | 无 | 无 | 众诸侯听得关外鼓声大振……云长提华雄之头，掷于地上。其酒尚温。 | 温酒斩华雄 |
| 下邳之战 | 关羽 | 夏侯惇 | 平 | 10 | 无 | RELUCTANT(诱敌) | 夏侯惇约战十余合，佯败而走……关公赶二十里，恐下邳有失，急回军。 | 夏侯惇受命引诱关羽出城 |
| 白马之战 | 关羽 | 颜良 | 阵斩/生擒 | 1 | SURPRISE_ATTACK(突袭) | 无 | 公奋然上马，倒提青龙刀……颜良措手不及，被云长手起一刀，刺于马下。 | 关羽借马快突袭 |
| 延津之战 | 关羽 | 文丑 | 阵斩/生擒 | 3 | 无 | 无 | 战不三合，文丑心怯……云长马快，脑后一刀，将文丑斩下马来。 | 文丑因怯战欲逃 |
| 土山之战 | 关羽 | 许褚, 徐晃 | 胜 | 10 | CHAOS(围攻) | 无 | 关公夺路而走。许褚、徐晃接住交战。关公奋然挥刀，二将料敌不过，拨马而走。 | 关羽突围，面对二将围攻 |
| 滑州拦截 | 关羽 | 夏侯惇 | 平 | 10 | 无 | 无 | 惇挺枪纵马，直取关羽。……关公大怒，舞刀迎之。两个战不十余合。 |  |
| 滑州拦截 | 关羽 | 夏侯惇 | 平 | 10 | 无 | 无 | 夏侯惇纵马大叫：“关某休走！”……张辽纵马而至，大叫：“二公罢战！” | 被使者张辽打断 |
| 南郡之战 | 关羽 | 张郃 | 胜 | 5 | 无 | 无 | 操教张郃抵敌。郃战不数合，拨马便走。云长随后赶来。 | 张郃奉命断后掩护撤退 |
| 长沙之战 | 关羽 | 黄忠 | 平 | 100 | 无 | AGE(年老) | 斗一百余合，不分胜负……云长暗忖：‘老将名不虚传。’ |  |
| 长沙之战 | 关羽 | 黄忠 | 劣势 | 10 | 无 | AGE(年老), ARCHERY(射箭) | 忠搭箭开弓，弦响箭到，正射在云长盔缨根上。云长吃惊，带箭回营。 | 黄忠为报不杀之恩 |
| 樊城之战 | 关羽 | 庞德 | 平 | 100 | AGE(年老) | BERSERKER(舍命) | 二将更不打话，纵马舞刀，长驱大战。斗至百余合，精神倍加。两军各看得痴了。 | 庞德抬榇决死 |
| 樊城之战 | 关羽 | 庞德 | 被伤 | 50 | AGE(年老) | BERSERKER(舍命), ARCHERY(射箭), SURPRISE_ATTACK(偷袭) | 德虚晃一刀，诈败而走。羽随后追赶。……德……拨箭搭弓，暗射一箭。……正中关羽左臂。 | 庞德诈败并放暗箭 |
| 樊城之战 | 关羽 | 徐晃 | 负 | 80 | AGE(年老), IMPAIRED(负伤) | 无 | 晃大怒，轮大斧径取关羽。羽抡刀迎之。战至八十余合，羽虽武艺极高，右臂少力，终不支。 | 关羽右臂负伤 |
| 古城之战 | 关羽 | 蔡阳 | 阵斩/生擒 | 1 | 无 | 无 | 曹军至，为首一将，乃是蔡阳...关公更不答话，举刀便砍。只见一通鼓未尽，关公刀起处，蔡阳头已落地。 | 关羽向张飞证清白 |
| 下邳之战 | 张飞 | 曹豹 | 胜 | 3 | IMPAIRED(大醉) | 无 | 曹豹挺枪来迎……战到三合，曹豹拨马便走。 | 张飞醉酒仍胜出 |
| 赤壁追击战 | 张飞 | 许褚 | 胜 | 10 | 无 | CHAOS(撤退) | 许褚骑无鞍马，凑架张飞……曹操各自夺路而走。 | 许褚骑无鞍马 |
| 益州之战 | 张飞 | 严颜 | 阵斩/生擒 | 10 | 无 | AGE(年老) | 战不十合，张飞卖个破绽……生擒严颜上马。 |  |
| 葭萌关之战 | 张飞 | 马超 | 平 | 220 | 无 | 无 | 两马交锋，斗一百余合，不分胜负……点起火把，换马再战。 | 此战从白昼斗至掌灯 |
| 宕渠之战 | 张飞 | 张郃 | 胜 | 40 | 无 | 无 | 二将交锋，三五十合。郃见后军乱，拨马而走。 | 张飞智斗劫营 |
... More rows.

## 2. Mathematical Model
---
### 2.1. Variable Definitions

*   **Combat Skill $C$ (武力值)**: Core hidden variable. Peak martial capability.
*   **Modifier $m$ (修正项)**: External variables altering real-time performance.
    *   Negative: e.g., $m_{old}$ (年老), $m_{injury}$ (带病/负伤).
    *   Positive: e.g., $m_{sneak}$ (突袭).
*   **Rounds $t$ (回合数)**: Duration of duel. Amplifies true skill gap over time.
*   **Effective Strength $E$ (有效战力)**: Actual combat output for a side in a specific clash.

$$E = C_{group} + \sum m$$

Where group strength uses the Minkowski $p$-norm:
$$C_{group}=\left( \sum_{i=1}^{N} C_i^p \right)^{\frac{1}{p}}$$
Multiple generals fighting together do not scale linearly. Higher $p$ limits the efficiency of outnumbering.

*   **Strength Differential $\Delta$ (战力差)**: Net difference in real-time strength.
$$\Delta = E_{A} - E_{B}$$

*   **Outcome $O$**: Quantified battle result from the text.
Mapping: 阵斩/生擒=10, 伤=7, 胜=5, 优势=2, 平=0, 劣势=-2, 负=-5, 被伤=-7, 被阵斩/生擒=-10.

### 2.2. Outcome Prediction Function $O(\Delta, t)$

To model the expected outcome where true skill gaps become more apparent over time, we use a scaled hyperbolic tangent ($\tanh$) function. The domain of $O$ is $[-10, 10]$ (positive for advantage, negative for disadvantage).

$$O_{pred} = 10 \cdot \tanh(\beta \cdot \Delta \cdot t^{\alpha})$$

*   **Cumulative Strength $\Delta \cdot t^{\alpha}$**: Amplifies the impact of the strength differential $\Delta$ as rounds $t$ increase.
*   **Sensitivity $\beta$**: Determines how much 1 point of $\Delta$ translates to outcome score over $t$ rounds.
*   **Scaling Factor $10$**: Maps the continuous output to the bounded $O$ interval (e.g., Kill = 10, Draw = 0).

**Why $\tanh$:**

The hyperbolic tangent function naturally bounds any infinite cumulative strength/time inputs into a strict $[-1, 1]$ range (scaled to $[-10, 10]$). This mirrors the physical limits of combat: an outcome cannot logically exceed a definitive kill ($10$). It also provides a smooth, continuous, non-linear gradient essential for backpropagation.

Since we are using $\tanh$, we curve the linear -10 to 10 outcome (阵斩/生擒=10, 伤=7, 胜=5, 优势=2, 平=0, 劣势=-2, 负=-5, 被伤=-7, 被阵斩/生擒=-10) to (阵斩/生擒=10.0, 伤=8.7, 胜=5.5, 优势=2.0, 平=0, 劣势=-2, 负=-5.5, 被伤=-8.7, 被阵斩/生擒=-10.0) to fit the $\tanh$ function.

**Why $t^{\alpha}$ instead of linear $t$:**

Diminishing marginal returns: Early rounds provide maximum information regarding the skill gap. If fighters draw for 100 rounds, the probability of drawing for another 10 rounds is extremely high. 

Using linear $t$ creates massive gradient pressure during training. 
*   *Example:* 马超 vs. 张飞 for 200 rounds ($O=0$). To neutralize the massive $t=200$ multiplier and achieve an outcome of $0$, linear $t$ forces the model to crush $\Delta$ infinitely close to $0$. 
*   This causes the $C$ values of all top-tier generals to rapidly collapse into a single point, destroying tier separation. Using the power function $t^{\alpha}$ (e.g., $200^{0.4} \approx 8.3$) compresses this time pressure into a manageable magnitude, preserving the tier list hierarchy.

### 2.3. Probability Distribution Function $P$

In combat, raw strength does not deterministically dictate the outcome. Massive randomness exists on the battlefield. Therefore, the observed outcome $O_{obs}$ fluctuates around our predicted theoretical outcome $O(\Delta, t)$.

We model this fluctuation using a **Normal Distribution**:

$$P(O_{obs} \mid \Delta, t) = \frac{1}{\sigma \sqrt{2\pi}} \exp\left( -\frac{(O_{obs} - O(\Delta, t))^2}{2\sigma^2} \right)$$

*   **Logic of Normal Distribution**: The highest probability outcome occurs at the theoretical prediction (e.g., equal strength most likely yields a draw). Extreme deviations (e.g., an instant kill between equal fighters) have exponentially lower probabilities.
*   **Variance $\sigma$**: Represents randomness. A larger $\sigma$ implies a higher reliance on luck over raw skill.
*   **Physical Meaning**: $P$ represents the probability of a specific outcome given the underlying combat variables. For example, $P(10 \mid 10, 2)$ represents the probability that 关羽 kills 华雄 in 2 rounds, given a true strength differential of 10.

### 2.4. Objective: Maximize Total Probability (Minimizing Loss)

Our ultimate goal is to find the precise configuration of all Base Combat Skills $C$ and global parameters ($\beta, \alpha$) that yields the **Maximum Total Probability** of the entire historical dataset occurring exactly as recorded:

$$\text{Maximize } \prod_{k=1}^{n} P_k$$

To optimize this computationally via gradient descent, we take the negative natural logarithm of the product. This transforms the probability maximization problem into a standard **Least Squares Error Minimization** problem:

$$\text{Minimize } J = \sum_{k=1}^{n} (O_{obs, k} - O(\Delta_k, t_k))^2$$

### 2.5. Gradient Descent

**Algorithm:**
1. Initialize all generals' Base Combat Skills ($C$) using common sense estimates.
2. Calculate the total error $J$ (the negative log-probability of the historical dataset).
3. Update $C$ values by stepping in the direction of the negative gradient (the partial derivatives of the loss function).
4. Repeat the iteration loop until the parameters converge.

#### a. Deriving the Gradient for General A's Combat Skill $C_A$:

To simplify the derivative, we multiply the minimization objective $J$ by a constant $\frac{1}{2}$ (which cancels the exponent $2$ during derivation without shifting the optimal solution):

$$J = \frac{1}{2} \sum_{k=1}^{n} (O_{pred,k} - O_{obs,k})^2$$

Where $O_{pred,k} = 10 \cdot \tanh(u_k)$ and the core transmission term is $u_k = \beta \cdot \Delta_k \cdot t_k^\alpha$.

For a single battle $k$, the error $J_k$ is:
$$J_k = \frac{1}{2}(O_{pred,k} - O_{obs,k})^2$$

Applying the Chain Rule:

**1. Derivative with respect to $u_k$ (Common Error Term $\delta_k$):**
$$\delta_k = \frac{\partial J_k}{\partial u_k} = (O_{pred,k} - O_{obs,k}) \cdot 10(1 - \tanh^2(u_k))$$

**2. Derivative with respect to $\Delta_k$:**
$$\frac{\partial u_k}{\partial \Delta_k} = \beta \cdot t_k^\alpha$$

**3. Derivative with respect to Effective Strength $E$:**
Since $\Delta_k = E_{Side A} - E_{Side B}$, we define $S_{A,k}$ as a directional indicator for General A in battle $k$:
*   $1$ if General A is on Side A.
*   $-1$ if General A is on Side B.

$$\frac{\partial \Delta_k}{\partial C_A} = S_{A,k}\frac{\partial E_{Group}}{\partial C_A}$$

**4. Derivative of the Minkowski $p$-norm:**
$$S_{A,k}\frac{\partial}{\partial C_A} \left[ \left( \sum_{i=1}^{N} C_i^p \right)^{\frac{1}{p}} + \sum m \right] = S_{A,k}\frac{\partial}{\partial C_A} \left[ \left( \sum_{i=1}^{N} C_i^p \right)^{\frac{1}{p}} \right]$$

Expanding the partial derivative:
$$\frac{\partial}{\partial C_A} \left[ \left( \sum_{i=1}^{N} C_i^p \right)^{\frac{1}{p}} \right] = \frac{1}{p} \left( \sum C_i^p \right)^{\frac{1}{p} - 1} \cdot \frac{\partial}{\partial C_A} \left( \sum C_i^p \right)$$

Substituting the definition $C_{group} = \left( \sum_{i=1}^{N} C_i^p \right)^{\frac{1}{p}}$:
$$= \frac{1}{p} \left( C_{group}^p \right)^{\frac{1-p}{p}} \cdot \left( p \cdot C_A^{p-1} \right)$$
$$= C_{group}^{1-p} \cdot C_A^{p-1} = \frac{C_A^{p-1}}{C_{group}^{p-1}} = \left( \frac{C_A}{C_{group}} \right)^{p-1}$$

**Final Gradient Assembly:**
Multiplying the chain components yields the gradient for a single battle $k$:
$$ \frac{\partial J_k}{\partial C_A} = \delta_k \cdot \beta \cdot t_k^\alpha \cdot S_{A,k} \cdot \left( \frac{C_A}{C_{group, k}} \right)^{p-1} $$

Summing across the entire dataset yields the global gradient for General A's skill:
$$ \frac{\partial J}{\partial C_A} = \sum_{k} \delta_k \cdot \beta \cdot t_k^\alpha \cdot S_{A,k} \cdot \left( \frac{C_A}{C_{group, k}} \right)^{p-1} $$

#### b. Gradient for Sensitivity $\beta$

Controls the probability of extreme combat outcomes.

$$ \frac{\partial J}{\partial \beta} = \sum_{k=1}^{n} \delta_k \cdot \Delta_k \cdot t_k^\alpha $$

#### c. Gradient for Modifiers $m_x$

Represents the linear offset to Effective Strength $E$. 

$$ \frac{\partial J}{\partial m_x} = \sum_{k \in \text{battles with } m_x} \delta_k \cdot \beta \cdot t_k^\alpha \cdot S_{m_x, k} $$

Where $S_{m_x,k} = 1$ if the modifier applies to Side A, and $-1$ if it applies to Side B.

#### d. Gradient for Time Decay $\alpha$

Controls the diminishing marginal returns of extended round counts.

$$ \frac{\partial J}{\partial \alpha} = \sum_{k=1}^{n} \delta_k \cdot \beta \cdot \Delta_k \cdot t_k^\alpha \cdot \ln(t_k) $$

#### e. Gradient for Variance $\sigma$

Represents baseline combat randomness. Because it does not shift the optimal relative calculations of Combat Skill $C$, it is fixed as a constant ($1$).

$$ \frac{\partial J}{\partial \sigma} = 0$$

#### f. Gradient for Group Strength $p$

Controls the scaling efficiency of multiple generals fighting together. A lower $p$ increases combined output. Computed only during 1vMany engagements.

$$ \frac{\partial J}{\partial p} = \sum_{k \in 1vN} \delta_k \cdot \beta \cdot t_k^\alpha \cdot S_{group, k} \cdot \frac{\partial E}{\partial p} $$

### 3. Computation
---

### 3.1. Data Initialization

**Initial Base Combat Skill ($C$) Values:**
To begin gradient descent, initial values must be assigned to the baseline roster. These values will be iteratively updated, but starting close to expected historical tiers accelerates convergence and prevents getting trapped in local minima.

*   **Tier 1 (第一档):** $100.0$
*   **Tier 2 (第二档):** $95.0$
*   **Tier 3 (第三档):** $90.0$
*   **References:** $60.0$
*   **All Unlisted Generals:** $60.0$

吕布 is the universally recognized apex of 三国演义. His Combat Skill is hard-anchored at 100 as the full score, defining the absolute ceiling of the universe.

Though not listed among the top tiers, 刘备, 沙摩柯, 曹休, 周仓, 邓忠, 公孙瓒 occurred multiple times in the dataset,they can be used as Reference Points. They are initialized at 60 and will update dynamically during training.

We assume the average baseline for any qualified general is 60. Unlisted background generals are hard-anchored at 60. Since most exist solely to be one-hit killed to hype a top-tier warrior's debut, calculating their individual variance is mathematically meaningless.

**Initial Modifiers:**

Apart from values, modifiers are assigned constraints to prevent drifting to unrealistic values caused by overfitting.

Based on the initialization in Section 3.1, a single tier gap equates to $5.0$ points of Combat Skill ($C$).

Positive Modifiers (Buffs):

*   **`SURPRISE_ATTACK` (突袭)**
    *   **Initial:** $+15.0$ | **Constraint:** $[+10.0, +25.0]$
    *   *Logic:* Allowed 关羽 (Tier 2) to 1-round 颜良 (Tier 2), and 黄忠 (Tier 2) to 1-round 夏侯渊 (Tier 3). It effectively gives the attacker a temporary 3-tier advantage to force a 1-round kill.
*   **`ARCHERY` (射箭)**
    *   **Initial:** $+10.0$ | **Constraint:** $[+5.0, +15.0]$
    *   *Logic:* Bypasses standard melee checks. Allowed 甘宁 to instantly wound 乐进, and 丁奉 to fatally wound 张辽. Grants a reliable 2-tier advantage.
*   **`BERSERKER` (搏命)**
    *   **Initial:** $+5.0$ | **Constraint:** $[+2.0, +10.0]$
    *   *Logic:* Bridges exactly 1 tier. Allowed 庞德 (Tier 3) to stall 关羽 (Tier 2) for 100 rounds without losing.

Negative Modifiers (Debuffs):

*   **`RELUCTANT` (战意不足/诱敌)**
    *   **Initial:** $-3.0$ | **Constraint:** $[-8.0, 0.0]$
    *   *Logic:* Rarely causes fatal outcomes. A general faking defeat or distracted is merely suppressing peak output, not losing their baseline skill. They can still easily draw or block attacks.
*   **`IMPAIRED` (机能受损)**
    *   **Initial:** $-10.0$ | **Constraint:** $[-10.0, -5.0]$
    *   *Logic:* Severe biological detriment (drunkenness, heavy wounds, sickness). Drops a combatant roughly 2 tiers. Forced 许褚 (Tier 2, 大醉) to be instantly speared by 张飞 (Tier 2).
*   **`AGE` (生理周期)**
    *   **Initial:** $-5.0$ | **Constraint:** $[-10.0, -1.0]$
    *   *Logic:* Drops a general $\approx 1$ tier. Accounts for why an elderly 关羽 draw with 庞德.
*   **`EXHAUSTED` (疲惫)**
    *   **Initial:** $-5.0$ | **Constraint:** $[-10.0, -2.0]$
    *   *Logic:* A standard 1-tier stamina penalty.
*   **`CHAOS` (局势劣势)**
    *   **Initial:** $-3.0$ | **Constraint:** $[-8.0, -1.0]$
    *   *Logic:* Represents unfavorable macro conditions (being surrounded, army routing). It does not obliterate raw combat skill if the general chooses to fight, but it mathematically pressures them to withdraw sooner than in a fair 1v1.
*   **`LETHAL_RNG` (极端意外)**
    *   **Initial:** $-30.0$ | **Constraint:** $[-50.0, -20.0]$
    *   *Logic:* Fatal accidents that bypass combat math. Allowed 周仓 (Reference $C \approx 60$) to easily capture 庞德 (Tier 3, 溺水). Must completely cripple the victim's output.


**Initial Model Parameters:**
*   $\alpha$ (Time Decay): initialized at $0.3$
    *  许褚 vs. 马超 fought for 230 rounds (渭水之战) to a dead draw ($O=0$). 
    *  They are both Tier 2 legends, meaning their expected true skill gap is $\Delta < 5.0$.
    *  With $\alpha = 0.4$, $230^{0.3} \approx 5$. Making it equally effective as $\Delta$.
*   $\beta$ (Sensitivity): initialized at $0.035$
    *  乐进 (Tier 3, $C=90$) vs. 吕布 (Tier 1, $C=100$). 乐进 loses and flees in 5 rounds ($t=5, O=-5$). 
    *  $O = 10 \cdot \tanh(\beta \cdot \Delta \cdot t^\alpha)$ -> \text{arctanh}(-0.5) = -16.2\beta$ -> $\beta \approx 0.034$
*   $p$ (Group Strength Norm): initialized at $1.5$
    *  吕布 ($100$) vs. 关羽 ($95$) + 张飞 ($95$) + 刘备 ($60$) lose.
    *  $p=1.5$ yields $(95^{1.5} + 95^{1.5} + 60^{1.5})^{\frac{1}{1.5}} \approx 133$. Explains 吕布's quick defeat, not wounded or killed.

### 3.3. Implementation

parameters.csv:
```csv
<!-- 武将战力 -->
吕布,100.00
兀突骨,100.00
关羽,95.00
...
公孙瓒,60.00
<!-- 战力修正 -->
CHAOS,-3.00
SURPRISE_ATTACK,15.00
ARCHERY,10.00
...
LETHAL_RNG,-30.00
<!-- 修正约束 -->
max_CHAOS,-1.00
min_CHAOS,-8.00
max_SURPRISE_ATTACK,25.00
...
min_LETHAL_RNG,-50.00
<!-- 模型参数 -->
alpha,0.300
beta,0.035
p,1.500
<!-- 训练参数 -->
LEARNING_RATE_C,0.050000
LEARNING_RATE_M,0.020000
LEARNING_RATE_GLOBAL,0.000500
EPOCHS,10000
STOPPING_DELTA_LOSS,0.000010
LEARNING_RATE_DECAY_DELTA_LOSS,0.500000
```

train.py
```python
...
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
```

**Adjustment in the implementation:**
 * Applied floor / ceiling to prevent gradient vanishing / explosion caused ny float computation.
 * Model parameters are also bounded to prevent unrealistic outcomes.

### 4. Result
---

After 20000 epochs,  we achieved a final loss of 2889.2272 with final values:

```csv
<!-- 武将战力 -->
曲阿小将,224.89
曹彰,155.74
鄂焕,112.17
文鸯,102.33
颜良,101.39
马超,101.32
张飞,101.18
关羽,100.59
赵云,100.58
典韦,100.53
许褚,100.24
吕布,100.00
夏侯惇,99.96
邓艾,99.51
纪灵,99.48
张任,99.26
臧霸,99.24
高览,99.07
姜维,98.91
徐晃,98.87
杨任,98.77
文丑,98.74
孙策,98.63
高顺,98.48
太史慈,98.46
黄忠,98.44
张苞,98.43
甘宁,98.38
张辽,98.29
王平,98.21
程普,98.15
乐进,98.15
李严,98.05
刘封,98.01
曹洪,97.99
夏侯渊,97.94
周泰,97.71
凌统,97.68
张郃,97.43
李典,97.07
陈武,97.00
曹仁,96.83
庞德,96.82
关平,96.74
马岱,96.41
徐盛,95.85
魏延,94.50
关兴,94.30
文聘,94.26
泠苞,93.72
兀突骨,93.23
曹休,92.88
华雄,89.35
沙摩柯,88.34
王双,87.93
诸葛尚,85.00
徐质,84.97
管亥,77.96
周仓,77.84
何曼,60.00
武安国,60.00
刘备,60.00
邓忠,60.00
公孙瓒,60.00
<!-- 战力修正 -->
SURPRISE_ATTACK,25.00
ARCHERY,15.00
BERSERKER,2.13
RELUCTANT,-0.63
AGE,-1.01
EXHAUSTED,-2.42
CHAOS,-3.18
IMPAIRED,-10.00
LETHAL_RNG,-50.00
<!-- 修正约束 -->
max_CHAOS,-1.0
min_CHAOS,-8.0
max_SURPRISE_ATTACK,25.0
min_SURPRISE_ATTACK,10.0
max_ARCHERY,15.0
min_ARCHERY,5.0
max_BERSERKER,10.0
min_BERSERKER,2.0
max_RELUCTANT,0.0
min_RELUCTANT,-8.0
max_EXHAUSTED,-2.0
min_EXHAUSTED,-10.0
max_IMPAIRED,-5.0
min_IMPAIRED,-10.0
max_AGE,-1.0
min_AGE,-10.0
max_LETHAL_RNG,-20.0
min_LETHAL_RNG,-50.0
<!-- 模型参数 -->
alpha,0.645
beta,0.060
p,2.000
<!-- 训练参数 -->
LEARNING_RATE_C,0.0332
LEARNING_RATE_M,0.0133
LEARNING_RATE_GLOBAL,0.0005
EPOCHS,10000.0
STOPPING_DELTA_LOSS,1e-05
LEARNING_RATE_DECAY_DELTA_LOSS,0.5000
```

### 4.1. Ranking
### 📢 全网最权威，纯数据说话，谁才是三国演义第一战神，终结一切讨论！

**260条交战记录，转化为 Maximum Likelihood Estimation 问题，覆盖胜负关系，回合数，战力修正（突袭、放冷箭、年老、群殴等）**

**经历10,000 轮的梯度下降，真正的10大战神，呼之而出：**

---

#### Rank 10: 典韦 (战力：100.53) -- “超越吕布的传奇”
**上榜理由：** 濮阳之战，平“满分标杆”吕布直接将其战力定为100。然而典韦一人杀退高顺, 侯成两员大将；吕布却多次速败于一对多：刘关张，曹营六将，下邳再战关张，皆落荒而逃。吕布败退，典韦冲锋，高下立判！

#### Rank 9: 赵云 (战力：100.58) —— “死神”
**上榜理由：** 高览，麴义，夏侯恩，邢道荣，裴元绍，淳于导，晏明，钟缙, 钟绅...赵云的战绩表简直就是一张死神点名册.一人包揽全数据库6.5%的交战记录，却未无一败绩，不愧为“常胜将军”！

#### Rank 8: 关羽 (战力：100.59) —— “名将收割机”
**上榜理由：** 虽然有大量平局拖累（夏侯惇、黄忠、庞德、高顺），但关羽的斩杀极有含金量：1合斩颜良、3合斩文丑、温酒斩华雄。此三人皆战绩爆表：颜良连斩宋宪、魏续，速胜徐晃；文丑胜臧霸，刺史涣，追击公孙瓒一挑四达成一死三逃；华雄连斩鲍忠、俞涉、潘凤、祖茂。三大精英怪被关羽直接收割，武圣之威名不虚传！

#### Rank 7: 张飞 (战力：101.18) —— “终极质检员”
**上榜理由：** 超越赵云的超级劳模，23条交战记录占全库8.8%。竟交出了“7平、9胜、1伤敌、6斩擒”的恐怖答卷，其中包含多次胜(联手)/平吕布，刺伤许褚，胜张郃，高顺，曹仁，刺纪灵等高质量对决。实至名归！

#### Rank 6: 马超 (101.32) —— “常胜将军升级版”
**上榜理由：** 平张飞，战许褚，压曹洪，胜张郃，退于禁，败曹仁，刺王方，擒李蒙，和赵云同样的不败金身。但同样是平许褚，许褚开启裸衣`BERSERKER`状态才能抹平数值差打成平手。而胜张郃仅用20回合（赵云用了30回合）。由此系统精准判定马超更胜一筹，合情合理！

#### Rank 5: 颜良 (101.39) —— “千古奇冤”
**上榜理由：** 3合斩宋宪、1合劈魏续、20合退徐晃，全部速胜！至于败于关羽，算法终于还他公道！经过迭代演算，系统认定关羽那一刀的 `SURPRISE_ATTACK`加成，足有约束极值`+25`点，这一数值极其合理，纵观全数据库，带有此 buff 的交锋几乎全以秒杀结束。颜良判定为死于开挂，千古奇冤得雪！

#### 🥉 Rank 4: 文鸯 (102.33) —— “乐嘉一战封神”
**上榜理由：** 乐嘉之战, 连杀一整夜顶着`EXHAUSTED(-2.42)`的 debuff 仍能与邓艾(`99.51`)大战了五十回合不分胜负，而后更有百员魏将在其面前纷纷落马。一战定格后三国时期的武力天花板！

#### 🥈 Rank 3: 鄂焕 (112.17) —— “一击毙命”
**上榜理由：** 1合刺雍闿，1合刺朱褒，两场极致的“一击必杀”，足以奠定其杀神地位。被魏延, 王平, 张翼围殴生擒的唯一污点，使其未能更进一步，实属遗憾！

#### 🏅 Rank 2: 曹彰 (155.74) —— “全胜将军”
**上榜理由：** 3合胜刘封，斩吴兰。100%胜率，全在极短回合达成，没有一场平局拖累，全书可有第二人？实至名归！

#### 👑 Rank 1: 曲阿小将 (224.89) —— “神亭岭高达、宇宙的尽头”
**上榜理由：** 惊天地泣鬼神的 **224.89** 分,足是满分吕布的两倍多！神亭岭阻击战，一人阻挡程普、黄盖等十二位江东虎臣，并且拖了至少100回合！（太史慈孙策交战100回合以上，加上跑图时间）1v12打出如此战绩，吕布自惭形秽！（1v6都打不过）可别说群殴的算法有问题，叠力公式 $C_{group}=\left( \sum_{i=1}^{N} C_i^p \right)^{\frac{1}{p}}$ 中的变量p值可是系统根据全部战绩 Maximize Likelihood 算出的。在冷酷的数学公式面前，曲阿小将强出天际，飞升高达！
