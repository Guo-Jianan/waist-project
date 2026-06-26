# 上位机软件 — Waist UI (腰部康复训练监控系统)

基于 PySide6 的桌面应用程序，用于腰部康复训练机器人的实时监控、数据可视化和 AI 辅助分析。

---

## 技术栈

| 类别 | 技术 | 版本/备注 |
|------|------|-----------|
| 编程语言 | Python | ≥ 3.10 |
| GUI 框架 | PySide6 | Qt for Python ≥ 6.6 |
| UI 组件 | QFluentWidgets (PyQt-Fluent-Widgets) | Fluent Design 风格 |
| 实时图表 | pyqtgraph | OpenGL 加速 |
| MQTT | paho-mqtt | TLS v3.1.1 |
| 信号处理 | NumPy, SciPy | 陷波、带通、包络提取 |
| AI | Ollama REST API | llama3.2, deepseek-r1:1.5b |
| 运动学 | 自定义 Stewart 逆解 | 4-DOF |
| 配置 | python-dotenv | .env 文件 |

---

## 项目结构

```
waist_ui/
├── main.py                          # 程序入口：QApplication 初始化、QSS 样式加载
├── requirements.txt                 # 依赖清单
├── .env                             # MQTT/AI 配置（gitignored）
├── config/
│   ├── settings.py                  # 配置加载类（.env 读取）
│   └── semg_analysis_prompt.md      # sEMG AI 分析提示词模板
├── ui/
│   ├── main_window.py               # 主窗口（FluentWindow，5 个导航子页）
│   ├── data_monitor.py              # 数据监控页：状态卡片 + 体感图 + 滑块 + 肌电图
│   ├── log_interface.py             # 通信控制页：连接管理、日志、指令输入
│   ├── rehab_training.py            # 康复训练页：预设动作序列编排与执行
│   ├── fun_game.py                  # 预留：游戏交互
│   └── user_custom.py               # 预留：用户自定义
├── communication/
│   ├── mqtt_client.py               # MQTT 客户端（paho-mqtt, 自动重连, 信号槽）
│   ├── tcp_client.py                # TCP 客户端（二进制帧协议，线程式接收）
│   ├── semg_filter.py               # sEMG 实时信号处理器（陷波 + 带通 + 包络）
│   └── semg_resampler.py            # sEMG 重采样器（UI 显示插值）
├── backend/
│   ├── ai_analyzer.py               # AI 分析模块（Ollama REST 后台线程）
│   ├── kinematics.py                # Stewart 平台逆运动学解算
│   └── sensor_manager.py            # 传感器数据管理器（4 通道统一管理）
├── data/
│   └── sensor_data.py               # SensorData 数据类
├── tools/
│   └── test_emqx_connection.py      # MQTT 连接独立测试脚本
├── resource/
│   ├── light/demo.qss               # 浅色主题样式表
│   └── body.png                     # 人体轮廓示意图
├── certs/                           # MQTT TLS CA 证书
└── docs/
    └── mqtt_integration.md          # MQTT 集成文档
```

---

## 功能模块

### 1. 数据监控 (Data Monitor)

主界面，采用 **50:50 双栏布局**：

- **左栏**: 人体示意图 + 4 个状态卡片（左前 LF、左后 LB、右前 RF、右后 RB）
- **右栏**: 连接状态卡 + 训练强度调节（4 个滑块 + DoubleSpinBox）+ sEMG 实时波形图

两种控制模式：
- **即时模式**: 滑块变化实时发送
- **批量模式**: 4 个通道统一调整后一键发送（100ms 防抖）

sEMG 波形图叠加三条曲线：
- 原始波形（蓝色）
- 全波整流（蓝色）
- 包络线（红色）

### 2. 通信日志 (Log Interface)

- TCP / MQTT 连接管理与状态显示
- 彩色日志输出（按级别着色）
- 手动指令输入与发送

### 3. 康复训练 (Rehab Training)

- **预设动作**: 前向弯腰、侧向弯腰、转身
- 每个动作配置角度值
- 运动序列编排（按序执行，可调间隔）
- **运动学解算**: 欧拉角 (α, β, γ) → 4 路推杆长度 → 发送至下位机
- 训练结束后自动触发 **AI 分析**

### 4. AI 分析

通过 Ollama 本地大模型分析 sEMG 信号：

| 功能 | 说明 |
|------|------|
| 模型 | 支持任意 Ollama 模型（默认 deepseek-r1:1.5b） |
| 数据缓存 | 最近 200 个采样点 |
| 分析维度 | 信号质量、肌电强度、疲劳判断、动作执行质量 |
| 触发方式 | 训练结束后自动触发 或 手动触发 |
| 超时 | 120 秒 |

输出内容包括：总体评估、动作执行分析表格、肌肉疲劳状态、腰部状况评估、康复建议。

### 5. 运动学解算

四自由度 Stewart 并联机构逆解：

| 参数 | 值 |
|------|-----|
| 基座长度 (Bl) | 30 cm |
| 基座宽度 (Bw) | 10 cm |
| 平台长度 (Pl) | 31.5 cm = 1.05 × Bl |
| 平台宽度 (Pw) | 15 cm |
| 推杆行程 | 16.5–25.5 cm |

输入：α（绕X轴旋转）、β（绕Y轴旋转）、γ（绕Z轴旋转）
输出：LF、LB、RF、RB 四路推杆长度百分比 (0–100%)

---

## sEMG 信号处理流水线

```
原始 ADC 值 (0–4095)
    → 自适应基线去除 (DC removal, α=0.002)
    → 50Hz IIR 陷波 (Notch, Q=30)
    → 20–150Hz Butterworth 带通 (4 阶)
    → 全波整流 (Rectification)
    → 5Hz Butterworth 低通包络提取 (2 阶)
    → 重采样/插值 → UI 波形显示
```

---

## 配置

通过 `.env` 文件（位于项目根目录）配置：

```env
COMM_MODE=mqtt                          # 通信模式: mqtt / tcp
MQTT_BROKER_HOST=broker.emqx.io        # MQTT 服务器地址
MQTT_BROKER_PORT=8883                   # MQTT 端口 (TLS)
MQTT_USERNAME=waist-ui                  # MQTT 用户名
MQTT_PASSWORD=admin                     # MQTT 密码
MQTT_CLIENT_ID=waist-ui-device001       # 客户端 ID
MQTT_DEVICE_ID=device001                # 设备 ID
MQTT_TOPIC_PREFIX=waist                 # 主题前缀
MQTT_TLS_ENABLE=true                    # 启用 TLS
MQTT_CA_CERT_PATH=certs/emqxsl-ca.crt  # CA 证书路径
AI_MODEL=deepseek-r1:1.5b              # Ollama 模型名称
```

---

## 性能指标

| 指标 | 值 |
|------|-----|
| GUI 刷新率 | ~60 FPS |
| sEMG 数据缓冲 | 200 点 |
| sEMG 图表曲线 | 3 条（原始/整流/包络） |
| AI 分析超时 | 120 秒 |
| MQTT QoS | 1 (at-least-once) |
| TCP 帧校验 | 累加和取反 |
| 批量发送防抖 | 100 ms |

---

## 安装与运行

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 配置 MQTT
# 编辑 .env 中的配置项

# 3. 启动应用
python main.py

# 4. （可选）启动 Ollama 本地 AI 服务
ollama serve
ollama pull deepseek-r1:1.5b
```

---

## 依赖

```
PySide6
PyQt-Fluent-Widgets (QFluentWidgets)
paho-mqtt
python-dotenv
numpy
scipy
requests
```
