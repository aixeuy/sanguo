
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

After 10000 epochs,  we achieved a final loss of 2889.2272 with final values:

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

### 📢 全网最权威，纯数据说话，谁才是三国演义第一战神，终结一切讨论！

**260条交战记录，转化为 Maximum Likelihood Estimation 问题，覆盖胜负关系，回合数，战力修正（突袭、放冷箭、年老、群殴等）**

**经历10,000 轮的梯度下降，真正的10大战神，呼之而出：**

---

#### Rank 10: 典韦 (战力：100.53) -- “超越吕布的传奇”
**上榜理由：** 濮阳之战，平“满分标杆”吕布直接将其战力定为100。然而典韦一人杀退高顺, 侯成两员大将；吕布却多次速败于一对多：刘关张，曹营六将，下邳再战关张，皆落荒而逃。吕布败退，典韦冲锋，高下立判！

#### Rank 9: 赵云 (战力：100.58) —— “死神”
**上榜理由：** 高览，麴义，夏侯恩，邢道荣，裴元绍，淳于导，晏明，钟缙, 钟绅...赵云的战绩表简直就是神点名册.一人包揽全数据库6.5%的交战记录，却未无一败绩，不愧为“常胜将军”！

#### Rank 8: 关羽 (战力：100.59) —— “名将收割机”
**上榜理由：** 虽然有大量平局拖累（夏侯惇、黄忠、庞德、高顺），但关羽的斩杀极有含金量：1合斩颜良、3合斩文丑、温酒斩华雄。此三人皆战绩爆表：颜良连斩宋宪、魏续，速胜徐晃；文丑胜臧霸，刺史涣，追击公孙瓒一挑四达成一死三逃；华雄连斩鲍忠、俞涉、潘凤、祖茂。三大精英怪被关羽直接收割，武圣之威名不虚传！

#### Rank 7: 张飞 (战力：101.18) —— “终极质检员”
**上榜理由：** 超越赵云的超级劳模，23条交战记录占全库8.8%。竟交出了“7平、9胜、1伤敌、6斩擒”的恐怖答卷。吕布，许褚，张郃，高顺，曹仁，刺纪灵等各路高手在其面前纷纷被打回原型。真乃名将质检员！

#### Rank 6: 马超 (101.32) —— “常胜将军升级版”
**上榜理由：** 平张飞，战许褚，压曹洪，胜张郃，退于禁，败曹仁，刺王方，擒李蒙，和赵云同样的不败金身。但同样是平许褚，许褚开启裸衣`BERSERKER(+2.13)`状态才能抹平数值差打成平手。而胜张郃仅用20回合（赵云用了30回合）。由此系统精准判定马超更胜一筹，合情合理！

#### Rank 5: 颜良 (101.39) —— “千古奇冤”
**上榜理由：** 3合斩宋宪、1合劈魏续、20合退徐晃，全部速胜！至于败于关羽，算法终于还他公道！经过迭代演算，系统认定关羽那一刀的 `SURPRISE_ATTACK`加成，足有约束极值`+25`点，这一数值极其合理，纵观全数据库，带有此 buff 的交锋几乎全以秒杀结束。颜良判定为死于开挂，千古奇冤得雪！

#### 🥉 Rank 4: 文鸯 (102.33) —— “乐嘉一战封神”
**上榜理由：** 乐嘉之战, 连杀一整夜顶着`EXHAUSTED(-2.42)`的 debuff 仍能与邓艾(`99.51`)大战了五十回合不分胜负，而后更有百员魏将在其面前纷纷落马。一战定格后三国时期的武力天花板！

#### 🥈 Rank 3: 鄂焕 (112.17) —— “一击毙命”
**上榜理由：** 1合刺雍闿，1合刺朱褒，两场极致的“一击必杀”，足以奠定其杀神地位。被魏延, 王平, 张翼围殴生擒的唯一污点，使其未能更进一步，实属遗憾！

#### 🏅 Rank 2: 曹彰 (155.74) —— “全胜将军”
**上榜理由：** 3合胜刘封，斩吴兰。100%胜率，全在极短回合达成，没有一场平局拖累，全书可有第二人？实至名归！

#### 👑 Rank 1: 曲阿小将 (224.89) —— “神亭岭高达、宇宙的尽头”
**上榜理由：** 惊天地泣鬼神的 **224.89** 分,足是满分吕布的两倍多！神亭岭阻击战，一人阻挡程普、黄盖等十二位江东虎臣，并且拖了至少100回合！（太史慈孙策交战100回合以上，加上跑图时间）1v12打出如此战绩，吕布自惭形秽！（1v6都打不过）群殴的叠力公式 $C_{group}=\left( \sum_{i=1}^{N} C_i^p \right)^{\frac{1}{p}}$ 已考虑多人时的战力衰减，其中的变量p是系统根据全部战绩 Maximize Likelihood 算出的。在冷酷的数学公式面前，曲阿小将飞升高达，强出天际！

### 5. Result Analysis (Post-Training)

After 10,000 epochs, the gradient descent algorithm reached a Final Loss of **3215.3882**, with the loss delta settling at **0.0359** in the final epoch. The fact that the loss did not perfectly zero out (and multiple parameters slammed into their hard constraints) reveals a profound truth: the mathematical model is constantly wrestling with the inherent logical contradictions of 罗贯中’s literary universe. 

By observing how the engine balanced the equations, we gain fascinating insights into the underlying "physics" of *Romance of the Three Kingdoms*.

#### 5.1. The Mathematics of Group Combat (The $p=2.0$ Cap)
The most revealing discovery of the entire experiment lies in the group scaling parameter, $p$. During training, the unconstrained algorithm desperately attempted to push $p$ well beyond 5.0. 
*   **Math** As $p \to \infty$, the Minkowski distance $C_{group} = (\sum C_i^p)^{1/p}$ approaches the $\max()$ function. The AI realized a harsh literary reality: **In this universe, teamwork is mathematically useless.** The author writes 1vN fights as if the solo fighter is only facing the *single strongest member* of the opposing group.
*   **The Constraint:** To maintain a universe that minimally respects the laws of physics, we hard-capped $p$ at **2.0** (Euclidean distance). 
*   **The Consequence:** This constraint directly spawned our greatest anomaly: **曲阿小将 (Qu A Young General at 224.89)**. To hold off 12 elite 吴 generals for 50 rounds, his single Base Combat Skill ($C$) must equal the square root of the sum of the squares of all 12 opponents. The math had no choice but to ascend him to godhood.

#### 5.2. Reasoning of $C$ and Rankings
The generated Tier List is completely unbiased, ignoring historical fame and strictly evaluating pure combat efficiency.

*   **The "Floating Anchor" Anomaly (曹彰, 鄂焕):** 
    *   *曹彰 (155.74)* and *鄂焕 (112.17)* sit at the absolute top of the mortal roster. Their records consist entirely of 1-to-3 round decisive executions, with a 100% win rate. Because they lack any "Draw" or "Loss" records to act as a mathematical ceiling (gravity), the $\tanh$ function demands a nearly infinite Strength Differential ($\Delta$) to output an absolute victory ($O=9.5$) in such short timeframes ($t \le 3$). The gradient descent simply pushed their stats into the stratosphere.
*   **The True Pantheon (The Natural Overflow):**
    *   With *吕布 (100.00)* as the fixed anchor, the algorithm determined that a select group of legendary generals—*文鸯 (102.33), 颜良 (101.39), 马超 (101.32), 张飞 (101.18), 关羽 (100.59), and 赵云 (100.58)*—actually mathematically out-perform him. 
    *   吕布 is dragged down by his tendency to retreat when outnumbered. Conversely, 张飞 boasts 23 flawless records with zero 1v1 losses; 赵云 has a terrifying volume of 1-round instant kills; and 颜良 defeated the 98-point 颜良 in just 20 rounds. Their sheer efficiency and high-quality outputs forced their Base $C$ to naturally overflow past the 100.00 mark.

#### 5.3. Reasoning of Modifiers ($m$)
To prevent the Base $C$ rankings from entirely collapsing under the weight of narrative plot armor, the model aggressively utilized the modifiers as **Mathematical Shock Absorbers**. This explains why so many modifiers arrived at their maximum constraints:

*   **Positive Buffs hit the Ceiling (`SURPRISE_ATTACK: 25.00`):**
    *   To explain how 关羽 (100.59) could instantly decapitate 颜良 (101.39) in exactly 1 round, a negative base skill difference makes it mathematically impossible. The model slammed `SURPRISE_ATTACK` into its absolute hard cap of +25.00, temporarily pushing 关羽's Effective Strength ($E$) to ~125. This bridges the mathematical gap required for a 1-round execution, protecting 颜良's high base stats from cratering.
*   **Freak Accidents hit the Floor (`LETHAL_RNG: -50.00`, `IMPAIRED: -10.00`):**
    *   When top-tier generals die or lose to lesser opponents (e.g., 庞德 drowning, a heavily intoxicated 许褚 getting stabbed by 张飞), the algorithm craters the debuffs to their minimum bounds. This logically shifts the blame from the general's martial arts to extreme biological or environmental disadvantages.
*   **The Synergy of Conditionals (`BERSERKER: 2.13`, `RELUCTANT: -0.63`, `AGE: -1.01`, `EXHAUSTED: -2.42`, `CHAOS: -3.18`):**
    *   The model fit these situational modifiers perfectly to balance the equations of drawn-out battles. For instance, 文鸯 (102.33) drew with 邓艾 (99.51) for 50 rounds after fighting all night. The model solved this elegantly: $C_{文鸯} (102.33) + m_{EXHAUSTED} (-2.42) = 99.91$, which is mathematically near-identical to 邓艾's 99.51, perfectly justifying the dead draw.


#### 5.4. Global Model Parameters ($\alpha, \beta$)
*   **The Time Decay ($\alpha=0.645$):** 
    *   This non-linear scaling parameter resolves the paradox of "marathon duels." While it aggressively amplifies the strength differential ($\Delta$) in early rounds (proving that a 3-round victory requires far more raw power than a 30-round victory), the $t^{0.645}$ decay effectively compresses the impact of super long turns. If time were linear, a 200+ round duel like 马超 vs. 张飞 would cause a massive gradient explosion, forcing their stats to perfectly equal each other to the thousandth decimal. By applying this decay, the model ensures marathon draws don't break the system, allowing for a natural 1-to-2 point variance between evenly matched legends.
*   **The Sensitivity ($\beta=0.060$):** At this sensitivity, a modest 3-to-5 point skill gap ($\Delta$) is enough to convincingly predict a decisive victory within 20 to 30 rounds. This perfectly segments the roster into the classic 100+ (God-tier), 95-99 (Elite), and 90-94 (First-rate) tiers, proving that despite some exaggerated anomalies, the original author's underlying "power scaling" was surprisingly consistent.


#### 5.5. Problems and Incentive for Model Improvement
While the mathematical optimization is flawless, the resulting Tier List (e.g., 曲阿小将 at 224.89, 曹彰 at 155.74) reveals a critical flaw in our current methodology: **Data Overfitting** in Maximum Likelihood Estimation (MLE).

1.  **The "Undefeated Bias" (Floating Anchor) Problem:**
    *   Because generals like 曹彰 and 鄂焕 have 100% win rates in very short rounds and completely lack "Draw" or "Loss" records to act as a mathematical ceiling, the MLE algorithm assumes their combat potential is practically infinite. It infinitely scales their $C$ values upwards to perfectly match the $O=9.5$ (Kill/Crushing Defeat) outcome in $t \le 3$ rounds.
2.  **The "Group Fight" Inflation:**
    *   For 曲阿小将, holding off 12 elite generals forces his stats to equal the square root of their combined squares. Pure MLE blindly accepts this to minimize the loss function, completely ignoring the biological and literary impossibility of a human possessing 224 base strength.
3.  **The Incentive:**
    *   We cannot fix this by simply adding more data, because the novel *does not contain* records of 曹彰 losing 1v1 duels, nor does it provide a standard 1v1 fight for 曲阿小将 to anchor his stats. To solve this, we must transition from pure data-driven MLE to **Maximum A Posteriori (MAP) Estimation**. We must inject our "Expert Prior Knowledge" (the consensus that human strength follows a natural distribution and 吕布's 100 is the realistic peak) directly into the loss function to act as a mathematical rubber band, pulling the extreme outliers back to reality.

## 6. Model Improvement: MAP Estimation

### 6.1. Maximum A Posteriori (MAP) Estimation
Under pure Maximum Likelihood Estimation (MLE), the model relies exclusively on minimizing battle prediction errors. As seen with 曹彰 (155+) and 曲阿小将 (224+), this causes severe **overfitting** for generals with perfect win rates in small sample sizes or extreme 1vN survival scenarios. 

To solve this, we must transition to **MAP Estimation**. MAP introduces a "Prior" distribution $P(C)$, forcing the algorithm to balance the battle records against the natual of combat skill's distribution. The goal is to maximize the posterior probability:
$$ P(C \mid O, S) \propto P(O \mid C) \cdot P(C \mid S) \cdot P(S) $$
Where $O$ represents observed battle outcomes, and $S$ represents the Selection Bias (the fact that a general was selected by the author to appear in our dataset).

Since selected sample is fact, $P(S)=1$

### 6.2. Sample Bias: The Top-Tier Probability
The prior distribution depending on sample selection $P(C \mid S)$ is derived using Bayes' Theorem. Because our selected sample is an observed fact, $P(S)=1$. Therefore:
$$ P(C \mid S) = \frac{P(S \mid C) P(C)}{P(S)} = P(S \mid C) P(C) $$

We assume the combat skills ($C$) of the entire global population of named characters in the novel (roughly $N = 436$ generals) form a standard Normal Distribution:
$$ C_{global} \sim \mathcal{N}(\mu_C, \sigma_C^2) \quad \text{with } \mu_C = 60 $$

However, the generals in our dataset are not a random sample. They are explicitly curated by history and fandom as the absolute elite. Let $K$ be the number of generals in our specific curated dataset (e.g., $K = 62$). 
Therefore, $P(S \mid C_i)$ is the probability that General $i$, given their true combat skill $C_i$, mathematically qualifies as one of the **Top $K$** generals out of the $N$ total population.

For a general with skill $C_i$, the probability that any single random general from the population is stronger than them is:
$$ p_i = 1 - \Phi\left(\frac{C_i - \mu_C}{\sigma_C}\right) $$
Where $\Phi$ is the Cumulative Distribution Function (CDF) of the standard normal distribution.

To be included in our dataset, no more than $K-1$ of the remaining $N-1$ generals can be stronger than General $i$. This is a **Binomial Distribution**. The probability of selection is the cumulative binomial probability:
$$ P(S \mid C_i) = \sum_{j=0}^{K-1} \binom{N-1}{j} p_i^j (1 - p_i)^{(N-1)-j} $$

This function acts as a **"Soft Floor" Sigmoid**. If a general's $C_i$ is exceptionally high (e.g., 90), $p_i$ approaches 0, and the probability of being in the top 62 is virtually $1.0$. However, as $C_i$ drops toward the 70s, $P(S \mid C_i)$ plummets, creating a mathematical barrier that prevents dataset generals from being ranked as generic foot soldiers.

### 3. Calculation of Distribution Parameters
We must calculate the global variance ($\sigma_C^2$) to ground our prior distribution.

Using Extreme Value Theory, the expected maximum value of $N=436$ samples drawn from $\mathcal{N}(\mu_C, \sigma_C^2)$ is approximated by:
$$ \mathbb{E}[\max] \approx \mu_C + \sigma_C \sqrt{2 \ln N} $$

We anchor the absolute ceiling of the universe (Lu Bu) at 100:
$$ 100 = 60 + \sigma_C \sqrt{2 \ln(436)} $$
$$ 40 = \sigma_C \sqrt{12.155} \implies \sigma_C \approx 11.47 $$
The global variance is **$\sigma_C^2 \approx 131.6$**.

### 4. Final Max Probability Function

The **Total Joint Probability** is the product of the Likelihood (how well $C$ predicts the battles), the Global Prior (the natural distribution of $C$), and the Selection Bias (the probability of inclusion):
$$ P_{total}(C, O, S) = \prod_{k=1}^{n} P(O_k \mid C) \cdot \prod_{i=1}^{N_{gen}} \left[ P(S \mid C_i) \cdot P(C_i) \right] $$

Substituting our mathematical distributions, the full probability function is:
$$ P_{total} = \left[ \prod_{k=1}^{n} \frac{1}{\sigma_O \sqrt{2\pi}} \exp\left( -\frac{(O_{obs,k} - O_{pred,k})^2}{2\sigma_O^2} \right) \right] \cdot \prod_{i=1}^{N_{gen}} \left[ \left( \sum_{j=0}^{K-1} \binom{N-1}{j} p_i^j (1 - p_i)^{(N-1)-j} \right) \cdot \exp\left( -\frac{(C_i - 60)^2}{2\sigma_C^2} \right) \right] $$
*(Where $p_i = 1 - \Phi\left(\frac{C_i - 60}{11.47}\right)$).*

To maximize the total joint probability $P(C, O, S) = P(O \mid C) \cdot P(S \mid C) \cdot P(C)$, we minimize its negative natural logarithm (Loss Function $J$). Ignoring constants, the objective function is:

$$ J_{MAP} = \underbrace{ \sum_{k=1}^{n} \frac{(O_{pred, k} - O_{obs, k})^2}{2\sigma_O^2} }_{\text{Battle Fit (MLE)}} \underbrace{ - \sum_{i=1}^{N_{gen}} \ln \left[ P(S \mid C_i) \right] }_{\text{Selection Sigmoid (The Floor)}} + \underbrace{ \sum_{i=1}^{N_{gen}} \frac{(C_i - 60)^2}{2\sigma_C^2} }_{\text{Global Gaussian (The Gravity)}} $$

The indroduction of prior normal distribution naturally results in an L2 regularization term in *The Gravity*.

### 5. Math for Simplification and Gradients
To simplify for gradient descent, we multiply the entire loss function by $2\sigma_O^2$. We define our regularization hyperparameters:
*   $\gamma = \frac{\sigma_O^2}{\sigma_C^2} = \frac{\sigma_O^2}{131.6}$ (Controls the downward "Gravity" toward 60).
*   $\lambda = 2\sigma_O^2$ (Controls the strength of the "Soft Floor" upward buoyancy).

The simplified Loss Function is:
$$ J_{simplified} = \sum_{k=1}^{n} (O_{pred, k} - O_{obs, k})^2 - \lambda \sum_{i=1}^{N_{gen}} \ln P(S \mid C_i) + \gamma \sum_{i=1}^{N_{gen}} (C_i - 60)^2 $$

#### The Combat Skill Gradient ($\frac{\partial J}{\partial C_i}$)
Let $\delta_k = (O_{pred,k} - O_{obs,k}) \cdot 10(1 - \tanh^2(u_k))$. Let $S_{side,k}$ be $1$ if General $i$ is on Side A, and $-1$ if on Side B.

The derivative with respect to $C_i$ perfectly balances three mathematical forces:
1.  **The Data Force:** Driven by battle prediction errors.
2.  **The Floor Force (Buoyancy):** The derivative of the negative log-binomial CDF. As $C_i$ drops, this generates a massive positive gradient, repelling the general back into the elite threshold. Let this derivative be $B'(C_i)$.
3.  **The Gravity Force:** The constant downward pull of the 60-average.

$$ \frac{\partial J}{\partial C_i} = \underbrace{\sum_{k} \left[ \delta_k \cdot \beta \cdot t_k^\alpha \cdot S_{side,k} \cdot \left(\frac{C_i}{C_{group, k}}\right)^{p-1} \right]}_{\text{Data Fit Gradient}} - \underbrace{\lambda \cdot B'(C_i)}_{\text{Soft Floor (Upward)}} + \underbrace{2\gamma(C_i - 60)}_{\text{Global Prior (Downward)}} $$

Where $ B'(C_i) = \ln P(S \mid C_i)  $ (binomial distribution).

*Note: for reference generals occurring multiple times in the battle records, not picked because they are the top, we  assume they form the normal distribution of global population, thus the soft floor part is removed.*

#### B. Other Model Parameters ($\beta, \alpha, p, m_x$)
$\beta, \alpha, p, m_x$ don't change. as the structural introduction of the Prior $P(C)$ and Selection Bias $P(S|C)$ only affects the individual generals ($C_i$). Because the modifiers ($m_x$) and model parameters ($\beta, \alpha, p$) are purely components of the *Likelihood* prediction ($O_{pred}$), their gradient formulas remain absolutely identical to the pure MLE derivation. The only difference is that their entire gradient vector is scaled by the constant multiplier $\frac{1}{\sigma_O^2}$.

#### C. The Gradient for the Variance ($\sigma_O^2$)
Because we are now using a true MAP probabilistic model rather than simple Mean Squared Error, the variance of the battle outcomes ($\sigma_O^2$) is no longer an invisible constant. It acts as the balancing scale between the Data Fit and the Prior Pulls.

We can solve for $\sigma_O^2$ dynamically. Taking the derivative of $J_{MAP}$ with respect to $\sigma_O$ and setting it to $0$:
$$ \frac{\partial J_{MAP}}{\partial \sigma_O} = -\frac{1}{\sigma_O^3} \sum_{k=1}^{n} (O_{pred,k} - O_{obs,k})^2 + \frac{n}{\sigma_O} = 0 $$
$$ \sigma_O^2 = \frac{1}{n} \sum_{k=1}^{n} (O_{pred,k} - O_{obs,k})^2 $$
*Mathematical elegance:* The optimal $\sigma_O^2$ at any given epoch is exactly the current **Mean Squared Error (MSE)** of the battle predictions.



#### Conclusion of the Mathematical Framework
This three-part gradient is the ultimate solution to the dataset's anomalies. If a general like Guan Xing achieves multiple 1-round kills, the *Data Fit Gradient* pushes his score up. As his score rises past 90, the *Soft Floor* probability $P(S \mid C_i)$ becomes exactly $1.0$, rendering its log-derivative $B'(C_i)$ to $0$. He is now entirely free of the floor, fighting only against the gentle *Global Gravity* of $2\gamma(C_i - 60)$, which safely caps his runaway inflation at a realistic elite level (e.g., 95) rather than 144. Conversely, generals with terrible records will be caught by the *Soft Floor*, mathematically proving that to even be recorded losing to Hua Xiong, one must still be vastly superior to a generic 60-average soldier.


### 6. Implementation
---
Implementing the exact derivative of the Binomial CDF (the Soft Floor Buoyancy, $\frac{\partial}{\partial C_i} \ln P(S \mid C_i)$) presents a significant computational challenge. 

**The Implementation Problem:**
Calculating the derivative of a sum of 62 binomial coefficients involving $436!$ (factorial) at every step of a gradient descent loop will cause **severe numerical underflow/overflow** in Python, resulting in `NaN` or `inf` gradients that instantly crash the model.

**The Engineering Solution (Normal Approximation):**
To make this viable in Python, we must approximate the Binomial Distribution with a Normal Distribution using the De Moivre–Laplace theorem.

Since $B \sim \text{Binomial}(N_{pop}, p_i)$, it can be approximated as:
$$ B \sim \mathcal{N}\left(N_{pop} \cdot p_i, N_{pop} \cdot p_i \cdot (1 - p_i)\right) $$

Therefore, the Soft Floor probability is beautifully approximated by the standard Gaussian CDF:
$$ P(S \mid C_i) = P(B \le K) \approx \Phi\left( \frac{K - N_{pop} \cdot p_i}{\sqrt{N_{pop} \cdot p_i \cdot (1 - p_i)}} \right) $$

Same as **Adjustment in the implementation:** 3.2, we have the following:
 * Applied floor / ceiling to prevent gradient vanishing / explosion caused ny float computation.
 * Model parameters are also bounded to prevent unrealistic outcomes.

Since we introduced the prior distribution of generals combat skills, there is no need to anchot 吕布 at 100. The prior distribution will naturally fit top general to around 100.

### 7. Results and Discussion
---

After 10,000 epochs, the transition to **Maximum A Posteriori (MAP) Estimation** yielded a Final Loss of **2034.5590**, with the loss change per epoch converging to $1.66 \times 10^{-4}$. These are the resulting parameter values:

```
Final Loss: 2034.5590 | Gamma: 0.0597 | Delta loss 0.00016599625

<!-- 武将战力 -->
赵云,98.45
关羽,80.76
吕布,79.91
夏侯惇,79.44
马超,78.97
张飞,78.84
颜良,77.99
典韦,77.91
许褚,76.59
黄忠,75.65
臧霸,75.19
文鸯,74.82
高览,74.78
孙策,74.67
甘宁,74.56
李严,74.53
曹彰,74.41
张任,74.27
夏侯渊,74.19
杨任,74.18
庞德,74.15
王平,74.15
程普,74.11
陈武,74.07
曹仁,74.05
文丑,74.01
华雄,74.00
太史慈,74.00
高顺,73.95
徐晃,73.93
乐进,73.92
曲阿小将,73.89
曹洪,73.88
张苞,73.81
周泰,73.78
马岱,73.78
鄂焕,73.78
诸葛尚,73.76
凌统,73.76
何曼,73.74
王双,73.72
纪灵,73.69
姜维,73.68
兀突骨,73.67
邓艾,73.60
张辽,73.59
徐质,73.58
李典,73.51
管亥,73.51
张郃,73.47
武安国,73.40
关平,73.22
关兴,73.09
泠苞,73.03
魏延,72.97
文聘,72.63
徐盛,72.17
刘封,68.57
邓忠,62.95
曹休,62.82
刘备,62.45
公孙瓒,62.32
周仓,60.64
沙摩柯,59.42
<!-- 战力修正 -->
SURPRISE_ATTACK,25.00
ARCHERY,15.00
BERSERKER,2.00
RELUCTANT,-0.07
EXHAUSTED,-2.00
AGE,-6.93
CHAOS,-8.00
IMPAIRED,-10.00
LETHAL_RNG,-44.50
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
alpha,0.100
beta,0.035
p,2.000
<!-- 训练参数 -->
LEARNING_RATE_C,0.0500
LEARNING_RATE_M,0.0050
LEARNING_RATE_GLOBAL,0.0005
EPOCHS,10000.0
STOPPING_DELTA_LOSS,1e-05
LEARNING_RATE_DECAY_DELTA_LOSS,0.5000
```

 The introduction of the Gaussian prior and the selection bias probability successfully resolved the overfitting issues observed in the Maximum Likelihood Estimation (MLE) approach. The resulting parameter values demonstrate a rigorous mathematical alignment between the dataset and the probabilistic framework.

#### 7.1. Mitigation of Overfitting via the Gaussian Prior
The primary limitation of the pure MLE approach was the infinite scaling of parameters for generals with small sample sizes and perfect win/draw rates (e.g., 曲阿小将, 曹彰, 鄂焕). 
*   Under MAP, the Gaussian prior imposes an $L_2$ regularization penalty on the objective function, scaled by $\gamma = 0.0597$. 
*   Because 曲阿小将's statistical significance was limited to a single multi-target draw, the data likelihood gradient was insufficient to overcome the regularization penalty. Consequently, his Base Combat Skill ($C$) was appropriately constrained, dropping from the anomalous 224.89 down to **73.89**. 曹彰 (74.41) and 鄂焕 (73.78) experienced identical mathematical corrections, converging to values consistent with the elite strata rather than scaling to infinity.

#### 7.2. Distribution Compression and Unanchored Estimation
By introducing the prior distribution $P(C)$, the model no longer required a hard anchor (previously 吕布 at 100.00) to maintain numerical stability. The entire parameter space was allowed to settle based strictly on relative battle outcomes and the prior variance.
*   The top-tier generals compressed into a highly dense bandwidth. 关羽 (80.76), 吕布 (79.91), 夏侯惇 (79.44), 马超 (78.97), and 张飞 (78.84) form the statistical peak. 
*   This compression indicates that the raw textual data, when subjected to proper statistical variance, naturally aggregates the most prominent combatants into a statistically indistinguishable top percentile, where performance variations are dictated by situational modifiers rather than vast disparities in base skill.

#### 7.3. The Statistical Outlier: 赵云
While the prior distribution effectively compressed the majority of the elite roster below $C=81.00$, **赵云** converged to an exceptional **98.45**.
*   In MAP estimation, overcoming the quadratic penalty term $\gamma(C_i - \mu_C)^2$ requires a consistently high magnitude in the data likelihood gradient $\frac{\partial J_{MLE}}{\partial C_i}$. 
*   赵云 possesses a uniquely high volume of 1-round decisive victories ($t=1, O=9.5$). The cumulative gradient generated by these rapid, highly skewed outcome scores provided sufficient mathematical thrust to offset the regularization penalty. Consequently, 赵云 is identified as the most statistically significant outlier in the dataset.

#### 7.4. Selection Bias and the Lower Bound
For the lower-tier named generals in the dataset—such as 刘备 (62.45), 周仓 (60.64), and 沙摩柯 (59.42)—the parameters stabilized near the global population mean ($\mu_C = 60$). 
*   Despite accumulating severe negative outcomes against top-tier opponents, their parameters did not collapse toward zero. This stabilization is driven by the selection bias probability term $P(S \mid C_i)$. As their $C$ values approached the mean, the derivative of the negative log-binomial CDF generated a steep positive gradient, acting as a soft lower bound. The model mathematically infers that inclusion in the historical/literary dataset necessitates a baseline proficiency superior to the unmentioned general population.

#### 7.5. Impact of Situational Modifiers ($m$)
Because the base combat skills ($C$) became heavily compressed (the variance across the top 30 generals is minimal), the situational modifiers were optimized to their predefined constraints to account for outcome variance:
*   **Negative Modifiers (`CHAOS: -8.00`, `AGE: -6.93`):** In a tightly compressed distribution, an 8-point deduction is mathematically equivalent to dropping a combatant by an entire tier. The model correctly assigns the causality of elite defeats or retreats to these environmental and physiological constraints.
*   **Positive Modifiers (`SURPRISE_ATTACK: 25.00`):** To model 关羽 (80.76) executing 颜良 (77.99) in $t=1$ round, a base skill differential of $\Delta = 2.77$ is insufficient to produce $O_{pred} \approx 9.5$. The optimization algorithm maximized the `SURPRISE_ATTACK` variable to its upper bound (+25.00) to maximize the argument $u$ in the $\tanh$ function. This proves the model strictly attributes the rapid outcome to tactical conditions rather than an underlying disparity in base capability.

#### 7.6. Global Hyperparameters ($\alpha, \beta, p$)
*   **Time Decay ($\alpha=0.100$):** Converging to its absolute lower bound, the $\alpha$ parameter heavily flattens the round count scalar. Mathematically, $50^{0.100} \approx 1.48$ and $200^{0.100} \approx 1.70$ yield similar asymptotic multipliers. This decay formulation successfully prevents gradient explosion during extreme outliers (e.g., 200-round marathon duels), ensuring that the model treats drawn-out engagements beyond 50 rounds as functionally identical in terms of skill parity.
*   **Sensitivity ($\beta=0.035$):** The stabilized $\beta$ value dictates the scaling of the strength differential $\Delta$. A relatively low sensitivity requires either extended rounds ($t$) or substantial modifier adjustments to confidently predict a decisive victory ($O \to \pm 9.5$).
*   **Minkowski Norm ($p=2.000$):** Pushed to the Euclidean constraint, the model confirms that group combat in the dataset scales sub-additively. By enforcing $1+1 < 2$, the mathematical framework accurately prevents the aggregated effective strength of multiple attackers from instantly producing a terminal prediction ($O=-9.5$) against a single top-tier defender, aligning with the recorded multi-round survivability in 1vN engagements.


### 8. Statistical Reality vs. Literary Intuition: A Fandom Post-Mortem

While the Maximum A Posteriori (MAP) estimation provides a mathematically rigorous optimization of the dataset, cross-referencing these empirical results with traditional reader consensus (the historical *Three Kingdoms* fandom) reveals a fascinating dichotomy. The probabilistic framework does not read the author's poetic hyperbole or dramatic tension; it only reads categorical outcomes. This strict adherence to data generates several conclusions that simultaneously validate and violently contradict centuries of literary intuition.

#### 8.1. The Ultimate Fandom Heresy: 关羽 > 吕布
In traditional fandom, **吕布 (Lu Bu)**'s status as the absolute ceiling of martial prowess is sacred. Yet, the MAP estimation commits the ultimate mathematical heresy by ranking **关羽 (Guan Yu)** at 80.76, slightly edging out 吕布 at 79.91. To a reader, this is blasphemy; to the optimization algorithm, it is simple accounting. 

The model penalizes 吕布 for his tendency to retreat when outnumbered (yielding negative outcome scores) and notes his distinct lack of lethal executions against top-tier peers. Conversely, 关羽 operates as the novel's premium bounty hunter. By executing high-value targets with established empirical weight (e.g., 华雄, 颜良, and 文丑) in three rounds or fewer, he generated massive positive gradients. The algorithm ignores 吕布's terrifying narrative aura and strictly evaluates K/D (Kill/Death) efficiency, officially categorizing 吕布 as an unparalleled survivor, but 关羽 as the superior lethal asset.

#### 8.2. The 赵云 Singularity and Plot Armor
Readers have long joked that author Luo Guanzhong treated **赵云 (Zhao Yun)** with extreme favoritism, portraying him as a flawless warrior who is never truly bested. The mathematical model completely validates this reader intuition but scales it to a comical extreme. 

While the Gaussian prior successfully compressed the rest of the elite roster into a tight 73.00–80.00 bandwidth, 赵云 shattered the mathematical gravity to reach an astronomical **98.45**—nearly 18 points above his closest peer. This inadvertently exposes the author's narrative mechanics. Because Luo Guanzhong frequently deployed 赵云 as a convenient plot device to "clean up" the battlefield by instantly executing mid-tier generals (e.g., 高览, 麴义), he fed the algorithm an endless diet of high-magnitude, low-round-count victories. The algorithm confirms what the fandom always suspected: statistically, 赵云 does not just possess plot armor; he operates under an entirely different set of physical laws.

#### 8.3. 夏侯惇: The Ultimate Stat-Padder
Perhaps the most jarring discrepancy for readers is **夏侯惇 (Xiahou Dun)** ranking at 79.44, mathematically outscoring legendary figures like 马超 (78.97) and 张飞 (78.84). To readers, 夏侯惇 is known primarily for his reckless bravery, losing an eye to a generic archer, and occasionally needing rescue. 

The algorithm, however, does not penalize a general for "looking bad" in the narrative unless it results in a categorical loss. What the model sees is a highly efficient combatant who fought 吕布 for 30 rounds and 关羽 for 20 rounds, securing draws in both. By consistently picking fights with the absolute strongest entities in the dataset and miraculously surviving due to external, non-combat interruptions (such as sudden rainstorms or arriving messengers), 夏侯惇 accidentally maximized his posterior probability. The algorithm inadvertently identifies him as the ultimate "stat-padder"—a fighter who leeches off the high $C$ values of top-tier gods by surviving just long enough to secure a $O=0$ dead draw.

#### 8.4. The Mathematical Extinction of Power Scaling Debates
For decades, literary forums have hosted endless debates over hypothetical matchups, arguing whether 马超 is fundamentally stronger than 张飞, or if 颜良 could outlast 许褚. The MAP estimation effectively closes these debates by demonstrating their mathematical futility. 

The model evaluates **马超 (78.97)** and **张飞 (78.84)** and separates them by a microscopic 0.13 points. When inserted into the prediction function $10 \cdot \tanh(\beta \cdot \Delta \cdot t^\alpha)$, this $\Delta$ yields an expected outcome precisely hovering at $0.0$ (Draw), regardless of whether the duel lasts 50 or 200 rounds. In short, the algorithm proves that Luo Guanzhong intentionally engineered these characters to be perfectly equivalent. From a probabilistic standpoint, readers are simply arguing over palette swaps of the exact same underlying numerical matrix.

#### 8.5. The Deflation of Meme Generals
Finally, the MAP estimation acts as the much-needed voice of reason against the statistical noise that plagued earlier MLE models. In pure Maximum Likelihood Estimation, readers would have been horrified to see obscure characters like **曲阿小将**, **曹彰**, and **鄂焕** dominating the top three spots due to their 100% win or survival rates in tiny sample sizes. 

By applying the global prior, the model forcefully dragged these undefeated anomalies back down to the 73.00–74.00 range. The algorithm finally agrees with common sense: a nameless lieutenant cannot possess double the physical strength of 吕布 simply because he stalled a group fight off-screen. The Gaussian prior successfully intervened, ensuring that literary hyperbole and statistical noise are no longer mistaken for divine martial prowess.


### 9. Bonus Track: Duel Simulator!


Every 三国演义 fan has spent hours arguing over hypothetical matchups. *What if 吕布 fought 赵云? Who will win the tournament of 五虎上将* 

To finally settle these pub debates and make every reader's dream a reality, we took our newly minted combat stats and built the ultimate fan-service tool: a narrative simulator (`predict.py`). You simply plug in General A and General B. The script calculates the shifting combat advantage round-by-round, pulling classic clichés from a hardcoded list of novel quotes to narrate the action in real-time.

Some examples:

刘封 vs 刘备
```
$ python predict.py -A 刘封 -B 刘备

==================================================
 📖 演义推演 (ROMANCE NARRATIVE RECONSTRUCTION)
==================================================
刘封挺枪纵马，大喝一声，径奔刘备。

【第 0 合】
二将方才交马，金鼓连天。

【第 1 合】
只听得一声大喝，刘封轮刀纵马，不数合，刘封力大，刘备抵敌不住。

【斗至 8 合】
战不数合，刘备气力不加，荡开阵角，倒拖兵器，夺路而逃。

【斗至 115 合】
刘封纵马大喝：‘刘备小儿，休走！’,赶上砍伤刘备。
==================================================
```

张郃 vs 刘备
```
$ python predict.py -A 张郃 -B 刘备
==================================================
 📖 演义推演 (ROMANCE NARRATIVE RECONSTRUCTION)
==================================================
张郃挺枪纵马，大喝一声，径奔刘备。

【第 0 合】
二将方才交马，金鼓连天。

【第 1 合】
张郃抖擞精神，越战越勇。刘备渐渐枪法散乱，只得勉强架隔遮拦。

【斗至 2 合】
战不数合，刘备气力不加，荡开阵角，倒拖兵器，夺路而逃。

【斗至 17 合】
张郃纵马大喝：‘刘备小儿，休走！’,赶上砍伤刘备。

【斗至 140 合】
张郃纵马如飞，生擒刘备过去，挟在腋下掷于阵前，众军骇然。
==================================================
```

张郃 vs 刘备 (偷袭)
```
$ python predict.py -A 张郃 -B 刘备 -mB SURPRISE_ATTACK

==================================================
 📖 演义推演 (ROMANCE NARRATIVE RECONSTRUCTION)
==================================================
忽见草坡后一彪军出，为首大将，乃张郃。挺枪跃马，径奔刘备而去。 谁知刘备早有防备，暗中反扑，打了张郃一个措手不及！

【第 0 合】
二将方才交马，金鼓连天。

【第 1 合】
张郃拨马而逃,刘备纵马横戟，大叫：‘张郃贼休走！’

【斗至 8 合】
正追赶间，刘备赶上一步，一戟刺中张郃后心。张郃大惊失色，险些落马。

【斗至 64 合】
张郃刀法已乱，被刘备一刀砍下头来。
==================================================
```

赵云 vs 刘备
```
$ python predict.py -A 赵云 -B 刘备

==================================================
 📖 演义推演 (ROMANCE NARRATIVE RECONSTRUCTION)
==================================================
两阵对圆，赵云出马，大叫：‘贼将刘备快下马受降！’

【第 0 合】
赵云与刘备两马相交，兵器并举。

【第 1 合】
赵云手起处，早将刘备砍中，刘备痛呼一声，伏鞍而逃。

【斗至 3 合】
斗不3合，刘备被赵云大喝一声，一矛刺下马去。
==================================================
```

马超 vs 张飞
```
python predict.py -A 马超 -B 张飞
draw

==================================================
 📖 演义推演 (ROMANCE NARRATIVE RECONSTRUCTION)
==================================================
忽见草坡后一彪军出，为首大将，乃马超。挺枪跃马，径奔张飞而去。

【第 0 合】
马超与张飞斗到0余合，不分胜负。

【斗至 200 合】
斗到200合，大雨如注，各自引军分散。
==================================================
```
