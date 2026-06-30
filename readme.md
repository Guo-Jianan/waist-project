# 腰部康复训练机器人系统 (Waist Rehabilitation Robot System)

基于四自由度并联机构（Stewart 平台衍生构型）的腰部康复训练设备，集成表面肌电（sEMG）生物反馈与本地大语言模型（LLM）智能分析，实现康复训练闭环控制。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         上位机 (PC Waist UI)                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐     │
│  │DataMonitor│ │RehabTrain│ │AiAnalysis│ │RehabRecrd│ │ LogInterf.   │     │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘     │
│       └─────────────┴────────────┴────────────┴──────────────┘             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  Communication Layer:  MQTTClient (paho-mqtt) / TCPClient         │    │
│  │  Signal Processing:    SemgSignalProcessor (notch+bandpass+envel) │    │
│  │  AI Analysis:          AiAnalyzer (Ollama REST API)               │    │
│  │  Kinematics:           Stewart IK (4-DOF)                         │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │ MQTT / TLS :8883
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EMQX Public Broker (broker.emqx.io)                     │
│  Topics: waist/{device_id}/{telemetry,cmd,status,ack,sEMG}                  │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │ MQTT / TCP :1883
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        下位机 (STM32L4R5ZI)                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐ ┌──────────────┐    │
│  │ defaultTask │ │pidControlTask│ │ sEMG Task (1kHz) │ │ sEMG Pub     │    │
│  │ (WiFi/MQTT) │ │ (100Hz PID)  │ │ + Ping-pong buf  │ │ (1s publish) │    │
│  └──────┬──────┘ └──────┬──────┘ └──────────────────┘ └──────────────┘    │
│         │               │                                                    │
│  ┌──────┴──────┐  ┌─────┴──────────────────────────────────────────────┐   │
│  │ ESP01S AT   │  │  4× Push-rod Actuators (PWM + ADC position fb)    │   │
│  │ USART1      │  │  sEMG ADC1 IN4 (1kHz, moving-average filter)      │   │
│  └─────────────┘  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 子系统

| 子系统 | 目录 | 平台 | 技术栈 | 职责 |
|--------|------|------|--------|------|
| **上位机** | `上位机/waist_ui/` | Windows PC | Python 3.10+, PySide6, QFluentWidgets, paho-mqtt, pyqtgraph, scipy, Ollama | 人机交互界面、数据可视化、sEMG 信号处理、AI 分析、运动学解算 |
| **下位机** | `STM32L4_waist/` | STM32L4R5ZIT6 | C, FreeRTOS, STM32 HAL, Keil MDK | 实时 PID 控制、sEMG 数据采集、MQTT 通信桥接 |
| **WiFi 模块** | `ESP8266CODE/` | ESP-01S / ESP-12E | AT 固件 / Arduino | WiFi 网关、MQTT 协议转换（已过渡到 AT 模式） |

---

## 技术栈

### 上位机

| 类别 | 技术 | 版本 |
|------|------|------|
| 编程语言 | Python | ≥ 3.10 |
| GUI 框架 | PySide6 (Qt for Python) | ≥ 6.6 |
| UI 组件库 | QFluentWidgets (PyQt-Fluent-Widgets) | - |
| 实时图表 | pyqtgraph | - |
| MQTT 通信 | paho-mqtt | TLS v3.1.1 |
| 信号处理 | NumPy, SciPy | 滤波、包络提取 |
| AI 推理 | Ollama REST API | llama3.2 / deepseek-r1:1.5b |
| 运动学 | 自定义 Stewart 逆解 | 4-DOF |
| 配置管理 | python-dotenv | - |

### 下位机

| 类别 | 技术 | 规格 |
|------|------|------|
| MCU | STM32L4R5ZIT6 | Cortex-M4F @ 120MHz |
| RTOS | FreeRTOS (CMSIS-RTOS v2) | 多任务抢占式调度 |
| HAL | STM32L4xx HAL | CubeMX 生成 |
| IDE | Keil MDK-ARM | .uvprojx |
| WiFi | ESP-01S (ESP8266) | AT v2.3.0, USART1 @ 115200 |
| 串口 Shell | LPUART1 | 209700 baud |
| 控制算法 | 位置式 PID | 死区 + 抗积分饱和 |

---

## 通信协议

### MQTT 主题

| 主题 | 方向 | QoS | 说明 |
|------|------|-----|------|
| `waist/{id}/telemetry` | 上位机发布 | 1 | 上位机下发的推杆目标值 JSON |
| `waist/{id}/cmd` | 上位机发布 | 1 | 控制指令（含手动文本命令） |
| `waist/{id}/status` | 下位机发布 | 1 | 设备状态上报 |
| `waist/{id}/ack` | 下位机发布 | 1 | 指令应答 |
| `waist/{id}/sEMG` | 下位机发布 | 0 | sEMG 采样数据（格式：空格分隔数值） |

### TCP 协议（已废弃，仅用于兼容）

二进制帧格式：`[0xA5][0xCC][0x10][RB:4B][RF:4B][LB:4B][LF:4B][checksum][0x5A]`

---

## 性能指标

### 控制性能

| 指标 | 值 | 说明 |
|------|-----|------|
| PID 控制周期 | 10 ms | 100 Hz, Realtime FreeRTOS task |
| sEMG 采样率 | 1 kHz | 1 ms 任务周期 |
| sEMG 批量发布 | 1000 ms | 约 200 个采样点/批 |
| PWM 频率 | 1 kHz | TIM4/TIM5 |
| ADC 分辨率 | 12-bit | 0–4095, 0–3.3V |
| ADC 通道数 | 5 | 4 路推杆反馈 + 1 路 sEMG |
| 推杆行程 | 0–100 mm | 软件限位 5–80 mm |
| 推杆反馈精度 | ~0.024 mm/LSB | 100 mm / 4096 |

### 信号处理

| 指标 | 值 |
|------|-----|
| 工频陷波 | 50 Hz, Q=30 |
| 带通滤波 | 20–150 Hz, 4 阶 Butterworth |
| 包络提取 | 5 Hz 低通, 2 阶 |
| 基线自适应 | α=0.002 |
| sEMG 采样率 | 1 kHz |

### UI 性能

| 指标 | 值 |
|------|-----|
| GUI 刷新率 | ~60 FPS |
| sEMG 图表曲线 | 3 条（原始/整流/包络） |
| AI 分析超时 | 120 s |

---

## 快速开始

### 上位机

```bash
cd 上位机/waist_ui
pip install -r requirements.txt
# 编辑 .env 配置文件（MQTT broker 地址、端口等）
python main.py
```

### 下位机

使用 Keil MDK 打开 `STM32L4_waist/MDK-ARM/NEW_Waist.uvprojx`，编译并下载至 STM32L4R5ZIT6 开发板。

### MQTT 测试

```bash
cd 上位机/waist_ui
python tools/test_emqx_connection.py
```

---

## 已知问题

- 阻抗控制尚未实现（`Alg_impedance.c` 为 PID 占位）
- GY85 IMU 驱动已编写但未集成到控制回路
- 下位机 MQTT 端不支持 TLS（ESP01S AT 固件限制）
- WiFi/MQTT 断线自动重连未实现
- 未实现急停/过流保护

---

*文档版本: 2026-06*
