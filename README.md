# 项目结构说明

## 账号插件架构

本项目采用“公共视频生成框架 + 账号插件配置”的架构。公共代码只负责读取配置、调度工作流、生成片段、调用 TTS / 图片 / 剪映草稿；具体账号的人设、赛道、脚本模板、产品池、质量规则、标题文案等都应放在 `accounts/<account_id>/` 下。

当前账号示例：

```text
accounts/
  xiaowanzi_english/
    account.json
    modes.json
    prompts.json
    visual.json
    voices.json
    quality_rules.json
    publish.json
    output.json
    painpoint_presets.json
    scene_collection_presets.json
```

以后新增玄学、好物种草、职场知识等赛道时，应新增独立账号目录，例如：

```text
accounts/
  metaphysics/
    account.json
    modes.json
    prompts.json
    visual.json
    voices.json
    publish.json
    output.json
    product_catalog.json
    script_templates.json
    safety_rules.json
```

运行时通过 `CONTENT_ACCOUNT_ID` 选择账号：

```bash
CONTENT_ACCOUNT_ID=xiaowanzi_english bash scripts/local_run.sh -m flow
CONTENT_ACCOUNT_ID=metaphysics bash scripts/local_run.sh -m flow
```

如果未指定，默认使用 `xiaowanzi_english`。

## 编码规范

### 1. 赛道规则必须账号级配置化

账号相关内容不要写进公共 Python 代码，包括但不限于：

```text
人设
专题方向
脚本模式
标题模板
互动话术
质量规则
图片风格
音色映射
产品池
玄学安全边界
英语预设句库
```

正确做法：

```text
英语规则 -> accounts/xiaowanzi_english/
玄学规则 -> accounts/metaphysics/
公共逻辑 -> src/
```

公共代码只读取配置并执行通用流程，不应出现类似下面的赛道硬编码：

```python
# 不推荐
if "玄关" in topic:
    ...

if "机场值机" in topic:
    ...
```

如果确实需要特殊规则，应放入账号配置，例如 `modes.json`、`quality_rules.json`、`script_templates.json` 或对应 preset 文件。

### 2. 公共节点只处理通用字段

工作流节点应围绕通用结构工作：

```text
raw_topic
content_mode
topic
scene
segments
content_meta
publish_pack
review_card
voice_profile
caption_highlight
animation
output_dir
```

新增账号时，优先复用这些字段。只有当多个账号都需要同一种能力时，才扩展公共字段。

### 3. 模式由账号定义，框架只调度

内容模式可以因账号不同而不同。

小丸子英语常用：

```text
scene_collection
painpoint_contrast
checkin_challenge
```

玄学可以定义：

```text
painpoint_conversion
scene_product_seed
product_list
zodiac_interaction
ritual_checkin
```

公共代码不应假设所有账号都只有英语模式。模式别名、模式路由、脚本模板应由账号配置提供。

### 4. 图片、字幕、音色都从账号配置读取

图片约束放在 `visual.json`，例如：

```text
是否禁止图中文字
是否禁止气泡
字幕关键词高亮样式
默认动画
账号视觉风格
```

脚本提示词放在 `prompts.json`，例如：

```text
账号 system role
账号定位
不同 content_mode 的脚本生成规则
输出 JSON schema
禁止跑偏的内容边界
动态生成时的质量要求
```

音色放在 `voices.json`，例如：

```text
voice key -> TTS speaker code
中文别名
语速范围
不同模式默认音色
```

发布信息放在 `publish.json`，例如：

```text
标题模板
简介模板
话题标签
封面文字长度
```

输出路径放在 `output.json`，例如：

```text
默认输出目录
result.json
segments.json
publish.json
review_card.json
timeline_segments.json
draft_url.txt
```

### 5. 新增账号的推荐步骤

1. 新建 `accounts/<account_id>/`。
2. 添加 `account.json`，定义账号定位、受众、边界。
3. 添加 `modes.json`，定义模式别名、场景识别、默认音色。
4. 添加 `prompts.json`，定义该账号独立的脚本提示词和输出结构。
5. 添加 `visual.json`，定义该账号独立的图片风格、角色形象、字幕规范。
6. 添加 `voices.json`，定义可用音色和语速范围。
7. 添加 `publish.json`，定义标题、简介、标签模板。
8. 添加 `output.json`，定义生成结果落盘路径。
9. 如果账号依赖产品或知识库，添加 `product_catalog.json`、`script_templates.json`、`safety_rules.json`。
10. 补充 tests，验证账号配置能被加载，且不会影响已有账号。

### 6. 账号提示词和视觉必须隔离

不同账号必须拥有独立的 `prompts.json` 和 `visual.json`。公共代码不得复用某个账号的提示词、角色形象、图片风格作为默认规则。

这样可以避免不同赛道互相污染：

```text
英语账号不应生成玄学摆件、水晶、貔貅等画面。
玄学账号不应生成小丸子英语学习搭子形象。
英语账号不应套用玄学开运话术。
玄学账号不应输出英语跟读句型。
```

正确分工：

```text
prompts.json -> 决定这个账号怎么写脚本
visual.json -> 决定这个账号怎么生成图片和字幕
voices.json -> 决定这个账号怎么配音
publish.json -> 决定这个账号怎么生成标题、简介、标签
公共代码 -> 只负责读取当前账号配置并执行工作流
```

### 7. 玄学账号的特别边界

玄学类账号可以围绕开运摆件、转运小物、空间调整、仪式感好物做内容和转化，但需要避免绝对化承诺。

允许表达：

```text
传统说法里
寓意是
提升仪式感
作为积极暗示
给自己一个稳定提醒
从空间感受上看
```

避免表达：

```text
保证发财
必定转运
改命
治病
保证复合
保证升职
化解所有灾
```

玄学互动建议使用自然问句，不使用“评论区打 XXX”：

```text
你最近更想稳事业、招财，还是提升贵人运？
你买转运摆件时，更看重寓意还是颜值？
你家玄关现在是清爽的，还是容易堆东西？
```

# 本地运行
## 运行流程
bash scripts/local_run.sh -m flow

## 运行节点
bash scripts/local_run.sh -m node -n node_name

# 启动HTTP服务
bash scripts/http_run.sh -m http -p 5000
