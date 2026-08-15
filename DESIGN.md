---
name: ServiceLoop
description: 可信、克制、可追踪的智能客服工作界面
colors:
  pine-deep: "#0d2823"
  pine: "#14352f"
  agent-pine: "#0d2a25"
  pine-soft: "#153a33"
  canvas: "#f2f0e9"
  canvas-muted: "#eeece5"
  paper: "#fbfaf6"
  white: "#ffffff"
  ink: "#17231f"
  ink-soft: "#68736e"
  muted-strong: "#58665f"
  line: "#d9ddd5"
  amber: "#d6a64a"
  sage: "#aac2b5"
  danger: "#a34c3e"
typography:
  display:
    fontFamily: '"Manrope", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "clamp(38px, 4.25vw, 59px)"
    fontWeight: 600
    lineHeight: 1.13
    letterSpacing: "-0.038em"
  headline:
    fontFamily: '"Manrope", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "20px"
    fontWeight: 650
    letterSpacing: "-0.025em"
  title:
    fontFamily: '"Manrope", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "14px"
    fontWeight: 700
    letterSpacing: "-0.01em"
  body:
    fontFamily: '"Manrope", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.75
  label:
    fontFamily: '"Manrope", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "10px"
    fontWeight: 700
    letterSpacing: "0.13em"
rounded:
  xs: "3px"
  sm: "5px"
  md: "6px"
  lg: "8px"
  message: "10px"
  full: "50%"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  3xl: "48px"
  4xl: "64px"
components:
  button-primary:
    backgroundColor: "{colors.pine}"
    textColor: "{colors.white}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.pine-deep}"
    textColor: "{colors.white}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    height: "40px"
  field-search:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "42px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.sage}"
    size: "46px"
  queue-item:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    padding: "16px 13px 14px 16px"
  message-customer:
    backgroundColor: "{colors.pine}"
    textColor: "{colors.white}"
    rounded: "{rounded.message}"
    padding: "11px 15px"
    typography: "{typography.body}"
  message-service:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    padding: "3px 0 4px 14px"
    typography: "{typography.body}"
  composer:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "11px 10px 8px 14px"
  handoff-status:
    backgroundColor: "#fff8ee"
    textColor: "#7a4e36"
    rounded: "{rounded.md}"
    padding: "14px 15px"
---

# Design System: ServiceLoop

## Overview

**Creative North Star: "The Service Ledger / 服务账本"**

ServiceLoop 像一本持续更新的服务账本：松针绿建立稳定的操作边界，纸白承载可阅读的工作内容，暖琥珀只在等待与需注意时出现。视觉不强调“AI 的神奇”，而是让每次查询、转接、回复和处理结论都有清楚来源与顺序。

整体气质可信、克制、可追踪。密度服务于高频扫描，但通过留白、细分隔线和编辑式排版保持安静；阴影只说明真正离开页面平面的元素。客户咨询端与人工工作台共享材料、颜色和状态语义，但可以使用适合各自任务的布局，人工工作台的多栏操作面不是所有页面的强制模板。

**Key Characteristics:**

- 松针绿操作面与纸白工作区形成稳定的明暗骨架。
- 暖琥珀表达等待、接管与键盘焦点，不作无意义装饰。
- 信息主要靠排版、留白、状态线和细分隔线组织。
- Agent、业务 Service、人工客服的来源和轨迹始终可辨。
- 紧凑、小圆角、低阴影，并为移动端重排真实任务顺序。

## Colors

色板以冷静的松针绿和暖纸色为主体，琥珀与危险红只承担明确状态语义；frontmatter 中的颜色值是规范来源。

### Primary

- **深松针（pine-deep）**：客户侧主导航与最深品牌面，提供可靠的操作边界。
- **操作松针（pine）**：主要操作、发送按钮和客户消息，代表可执行动作。
- **工作台松针（agent-pine）**：人工工作台轨道的局部深色变体，不应扩散成新的全局主题。
- **柔松针（pine-soft）**：工作台导航激活面，用于在深色轨道中建立层级。

### Secondary

- **等待琥珀（amber）**：等待人工、排队状态、当前项状态线和键盘焦点。
- **追踪鼠尾草（sage）**：低优先级图标、辅助品牌细节和柔和的追踪提示。

### Neutral

- **纸张墨色（ink）**：正文、标题和关键业务信息。
- **柔墨（ink-soft）**：说明、时间和次级元数据。
- **强次级墨（muted-strong）**：人工工作台中需要稳定可读、但不与标题争抢的元数据。
- **应用画布（canvas）**：客户侧应用背景，和纸白内容面形成轻微层次。
- **静音画布（canvas-muted）**：人工工作台外围与队列区域的冷暖中性底色。
- **工作纸（paper）**：对话、表单和主工作区的默认表面。
- **纯白（white）**：输入框和需要最高局部清晰度的小面积控件。
- **账页分隔线（line）**：列表、栏目、页头和上下文区的细边界。

### Tertiary

- **风险赤陶（danger）**：错误与失败状态，仅在需要纠正或警示时使用。

### Named Rules

**The Status Has Meaning Rule.** 绿色、琥珀和危险色必须对应业务状态；若颜色消失，文字或形状仍要让状态可辨。

**The Paper Before Decoration Rule.** 先用纸色层次、细线和留白分组，再考虑增加色块；禁止渐变、荧光与装饰性玻璃。

## Typography

**Display Font:** Manrope（中文回退为 Noto Sans SC、PingFang/系统无衬线）  
**Body Font:** Manrope（中文回退为 Noto Sans SC、PingFang/系统无衬线）  
**Label Font:** Manrope（中文回退为 Noto Sans SC、PingFang/系统无衬线）

**Character:** 同一套人文无衬线承担中英文与数字，让业务信息连续而不炫技。大标题使用紧字距和有限字重形成编辑感，小标签只用于稳定分组与状态扫描。

### Hierarchy

- **Display**（600，流体字号，1.13 行高）：仅用于客户侧服务入口的主标题，左对齐并控制为两行内的清晰承诺。
- **Headline**（650，20px）：用于队列等高层级工作标题，紧凑但不做营销式放大。
- **Title**（700，14px）：用于客户、服务主题和列表主信息。
- **Body**（400，13px，1.75 行高）：用于对话与说明；长段落保持约 68–70ch 的阅读宽度。
- **Label**（700，10px，0.13em 字距）：用于短分组标题和少量大写英文辅助标签，不替代中文业务名称。

### Named Rules

**The Readable Trace Rule.** 查询轨迹、转接判断和处理结论可以紧凑，但正文行高不得被压缩成日志噪声。

## Layout

系统共享“稳定操作边界 + 左对齐工作内容”的空间语法，而不是共享一张固定页面模板。客户侧桌面使用 278px 服务导航与弹性纸白对话区，内容宽度分别收敛在 980px 的入口区与 820px 的对话/输入区；人工工作台桌面采用 72px 操作轨、348px 队列和弹性工作区，工作区内的 316px 上下文栏只属于高频接管场景。

间距从 4px 基线递增到 64px，控件内部以 8–16px 为主，栏目与大区块使用 24–64px。同行操作保持紧凑，同级信息以列表、工具栏、分隔线和状态线组织，避免等宽 KPI 卡片墙。

客户侧在 780px 以下把导航变为抽屉，在 430px 以下进一步压缩标题与辅助信息；人工工作台在 920px 以下把上下文变为右侧抽屉，在 720px 以下先展示队列、进入会话后以返回按钮切换。新增页面应选择符合任务的布局，只继承空间语法与响应式原则，不复制人工工作台的多栏尺寸。

**The Task Order Rule.** 移动端重排必须服从业务顺序：先发现任务，再进入会话，再按需查看上下文；不得仅把桌面列机械堆叠。

## Elevation & Depth

系统默认是平的，以纸张色差、1px 分隔线和局部背景变化表达层级。阴影只用于移动抽屉、遮罩上的侧栏和悬浮错误提示等真正离开页面平面的元素；普通卡片、按钮、列表项在静止状态不使用阴影。

### Shadow Vocabulary

- **移动导航抽屉**（`20px 0 50px rgba(9, 29, 25, 0.22)`）：客户侧移动导航覆盖内容时使用。
- **上下文抽屉**（`-18px 0 38px rgba(20, 38, 31, 0.15)`）：人工工作台窄屏上下文从右侧进入时使用。
- **错误提示浮层**（`0 10px 28px rgba(60, 35, 29, 0.12)`）：需要覆盖当前工作面的错误提示使用。

### Named Rules

**The Flat Ledger Rule.** 静态业务内容保持平面；只有空间关系真实改变时才允许阴影出现。

## Shapes

组件以轻微方正、克制圆角为主：标签和细小状态使用 3px，主按钮通常为 5px，状态块与搜索框为 6px，输入容器为 7–8px，消息容器最大约 10px。头像与状态点可以为圆形；品牌字标、Agent 头像和服务回复标记保留方形轮廓，以避免所有元素都变成胶囊。

边界通常是 1px 实线，活动项通过左侧 1–2px 状态线或底部 2px 指示线表达，不依靠大面积填色。客户消息使用一个更小的角形成方向性，AI 与人工回复则以左侧细线和身份标记保持正文式阅读。

**The Reserved Radius Rule.** 圆角服务于触控、消息方向或状态分组；不要把导航、列表和所有容器统一改成大圆角卡片。

## Components

### Buttons

- **Shape:** 主操作使用紧凑的小圆角和至少 40px 高度；图标按钮维持 40×40px 点击区。
- **Primary:** 深松针底、浅色文字，标签紧凑而明确；“接入会话”在待接管状态中是唯一主操作。
- **Hover / Focus:** hover 只加深背景或轻微改变边界；键盘焦点使用 2px 琥珀轮廓和 2–3px 偏移。常规状态过渡约 180ms。
- **Secondary / Ghost:** “完成服务”等次操作使用透明底与细边框；导航和关闭按钮使用无边框 ghost 形态。
- **Disabled:** 用浅中性色面和低对比文字明确不可操作，保留按钮轮廓和业务文案。

### Chips

- **Style:** 队列原因标签使用紧凑的 3px 圆角暖中性色块；状态筛选使用文字与底部指示线，而不是一排胶囊。
- **State:** 选中状态同时依靠文字对比和 2px 指示线；排队状态同时显示琥珀点与等待文案。

### Cards / Containers

- **Corner Style:** 普通工作容器约 6–8px；列表与上下文段落多数不加外框圆角。
- **Background:** 主内容使用工作纸，输入使用纯白，等待转接使用暖纸色状态面。
- **Shadow Strategy:** 静态容器无阴影，遵循 Flat Ledger Rule。
- **Border:** 使用 1px 账页分隔线；当前项用左侧状态线补强。
- **Internal Padding:** 紧凑容器通常为 12–16px，较大上下文区块约 20–24px。

### Inputs / Fields

- **Style:** 纯白或纸白底、1px 中性描边、5–8px 圆角；输入始终靠近当前会话或任务。
- **Focus:** 边框转为柔松针，并使用琥珀 2px 焦点轮廓；组合输入由外层容器承接焦点状态。
- **Error / Disabled:** 错误使用浅暖红表面、风险赤陶文字和细边框；禁用输入保留可读占位与不可用光标。

### Navigation

客户侧导航是 278px 的深松针服务历史栏，当前项用琥珀左线和轻微背景区别；移动端变为可关闭抽屉。人工工作台使用 72px 图标操作轨，活动项使用松针柔色面与琥珀左线。两者都把身份与低优先级信息放在底部，且图标操作必须有 `aria-label`。

### Service Messages & Trace

客户消息可使用紧凑松针色块；AI 与人工回复优先使用正文排版、左侧细线和不同身份标记。系统查询记录默认收起，以有序步骤、成功/失败状态和问题改写记录展开；不得把所有来源隐藏进对称聊天气泡。

### Handoff Queue & Context

转人工状态块说明上下文是否已携带；队列行同时呈现主题、摘要、原因、等待时间和状态。接管上下文按 Agent 摘要、转接判断、业务线索与查询轨迹分段，使用连续细线和时间顺序，而不是独立 KPI 卡片。

## Do's and Don'ts

### Do:

- **Do** 用松针绿明确操作边界，用纸白承载持续阅读与输入。
- **Do** 用文字、身份标记、状态点或状态线共同表达等待、处理中、已解决和失败。
- **Do** 保留 Agent 判断、业务 Service 来源、知识检索和人工接管的可追踪顺序。
- **Do** 在桌面与移动端分别验证任务优先级、无横向滚动、键盘焦点和至少约 40×40px 的图标点击区。
- **Do** 让新页面选择适合自身任务的内容宽度与列结构，同时沿用 4–64px 间距节奏和克制材料语言。

### Don't:

- **Don't** 使用紫蓝渐变、荧光、装饰性玻璃、漂浮光斑或泛用 AI 图标来制造科技感。
- **Don't** 把人工工作台的操作轨—队列—会话—上下文四段布局强制复制到客户侧或未来运营页面。
- **Don't** 创建同尺寸 KPI 卡片墙、虚构实时率/满意度/节省时间，或用装饰替代真实业务状态。
- **Don't** 把所有回复做成对称聊天气泡，隐藏 AI、人工与业务 Service 的来源差异。
- **Don't** 给每个容器添加大圆角、强阴影、渐变或无信息价值的悬浮动效。
