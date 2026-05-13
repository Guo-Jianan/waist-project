# 康复医疗仪表盘

基于PySide6和QFluentWidgets的康复医疗设备监控上位机系统，通过MQTT与下位机（STM32+ESP01S）通信，支持实时数据监测和力控指令下发。

## 项目简介

本项目是一个现代化的康复医疗仪表盘系统，用于实时监测和控制康复设备。系统采用模块化设计，界面美观易用，通过MQTT Broker与STM32+ESP01S设备节点通信，实现力控参数调节、电机推杆控制等功能。

### 主要功能

- **数据监测界面**：实时显示四个电机通道（左前LF、右前RF、左后LB、右后RB）的推杆长度数据
- **力控参数调节**：通过滑动条和数字框精确控制各通道的参数（0-100）
- **系统状态监控**：实时显示设备连接状态和通讯状态
- **快捷指令**：支持参数自动辨识和系统复位功能
- **通信日志**：独立的通信日志界面，支持命令发送
- **多界面支持**：包含康复训练、趣味游戏、用户自定义等扩展界面

### 技术栈

- **GUI框架**：PySide6 (Qt for Python)
- **UI组件库**：QFluentWidgets
- **通信协议**：MQTT (JSON)，通过EMQX公共Broker中转
- **编程语言**：Python 3.10+
- **下位机**：STM32L4 + ESP01S (AT固件) + 四路推杆

## 项目结构

```
waist_ui/
├── main.py                          # 主程序入口
├── README.md                       # 项目说明文档
├── config/                         # 配置模块
│   ├── __init__.py
│   └── settings.py                 # 配置管理
├── ui/                            # UI模块
│   ├── __init__.py
│   ├── main_window.py              # MainWindow类（主窗口，5个Tab）
│   ├── data_monitor.py             # DataMonitorInterface和StatusCard类
│   ├── log_interface.py            # LogInterface（通信日志界面）
│   ├── rehab_training.py           # RehabTrainingInterface（康复训练界面）
│   ├── fun_game.py                # FunGameInterface（趣味游戏界面）
│   └── user_custom.py             # UserCustomInterface（用户自定义界面）
├── communication/                  # 通信模块
│   ├── __init__.py
│   ├── mqtt_client.py              # MQTT客户端（连接Broker）
│   ├── protocol.py                # 通信协议定义
│   ├── communication_manager.py    # 通信管理器
│   └── tcp_server.py              # TCP服务器（已废弃，保留兼容）
├── data/                          # 数据处理模块
│   ├── __init__.py
│   └── sensor_data.py             # 传感器数据处理
└── resource/                      # 资源文件
    ├── light/                     # 浅色主题
    │   └── demo.qss
    ├── dark/                      # 深色主题
    │   └── demo.qss
    └── body.png                   # 人体图片
```

## 快速开始

### 环境要求

- Python 3.10 或更高版本
- Windows 操作系统（推荐）
- 网络连接（用于MQTT通信）

### 安装依赖

```bash
pip install PySide6 qfluentwidgets paho-mqtt
```

### 运行程序

```bash
cd waist_ui
python main.py
```

## 界面说明

### 界面1：数据监测（主页）

采用**非对称双栏布局 (70% 可视化 : 30% 控制区)**：

**左侧区域 - 患者数字孪生区**
- 使用 `ElevatedCardWidget` 作为容器（白色背景、带阴影）
- 中央放置人体剪影图
- 四个悬浮状态卡片分布在人体图周围：
  - 左前(LF)、右前(RF)、左后(LB)、右后(RB)
- 每个卡片包含：部位名称、数值、进度条、状态徽章

**右侧区域 - 指挥控制中心**

1. **连接状态**
   - 显示MQTT连接状态（已连接/未连接）
   - 显示Broker地址

2. **力控参数调节**
   - 四个滑动条分别控制LF、LB、RF、RB四个通道
   - 每个滑动条旁边有数字框，可精确输入数值
   - 滑动条和数字框双向绑定，实时同步

3. **快捷指令**
   - **参数自动辨识**：点击后自动识别设备参数
   - **系统复位**：将所有滑动条和状态卡片重置为0

### 界面2：通信日志

- 日志显示区域（彩色分级：INFO/WARNING/ERROR/DEBUG）
- 命令输入框（可发送自定义命令）
- 清空日志按钮

### 界面3-5

康复训练、趣味游戏、用户自定义界面（预留）

## 通信协议

### MQTT 控制指令（JSON）

**Topic**: `waist/device001/cmd`（QoS 1）

**JSON格式**:
```json
{
    "cmd": "set_force",
    "device_id": "device001",
    "RB": 0.0,
    "RF": 0.0,
    "LB": 61.0,
    "LF": 42.0
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| cmd | string | 指令类型，当前仅支持 `set_force` |
| device_id | string | 目标设备ID |
| RB | float | 右后推杆目标值 (0-100) |
| RF | float | 右前推杆目标值 (0-100) |
| LB | float | 左后推杆目标值 (0-100) |
| LF | float | 左前推杆目标值 (0-100) |

### 通信流程

```
UI → MQTT Broker (broker.emqx.io:1883) → ESP01S → STM32 → PID控制 → 四路推杆
```

### 旧版二进制协议（已废弃，保留兼容）

数据包格式（仅用于旧版TCP直连模式）：
```
[起始符][功能][长度][4×float数据][校验][结束符]
  0xA5   0xCC  0x10  16字节     ~校验  0x5A
```

## MQTT Broker 配置

| 参数 | 值 |
|------|-----|
| Broker地址 | broker.emqx.io |
| 端口 | 1883 |
| 客户端ID | waist_ui_xxx（自动生成） |
| 发布Topic | waist/device001/cmd |
| 订阅Topic | 待定（数据上报） |
| QoS | 1 |

## 下位机配置

下位机为STM32L4 + ESP01S（AT固件 v2.3.0），详见 `STM32L4_waist/README.md`。

- STM32通过USART1发送AT指令控制ESP01S
- ESP01S连接WiFi后，通过MQTT订阅 `waist/device001/cmd` 接收控制指令
- STM32解析JSON后通过PID闭环控制四路推杆

## 开发规范

### 组件使用规范

- 所有文本使用QFluentWidgets字体规范 (`TitleLabel`, `BodyLabel`, `CaptionLabel`)
- 所有图标使用 `FluentIcon`
- 所有按钮使用 `PushButton` / `PrimaryPushButton`
- 所有滑动条使用 `Slider`
- 滑动条和数字框使用 `blockSignals()` 避免循环触发

### 沟通规范

- 修改代码前必须先提问确认需求
- 需求不明确时必须停止，直到完全理解
- 修改完成后必须告知如何验证

## 待开发功能

- [ ] 压力传感器数据支持
- [ ] 康复训练模式
- [ ] 趣味游戏功能
- [ ] 用户自定义功能
- [ ] 数据记录和导出
- [ ] MQTT自动重连机制
- [ ] 下位机状态上报订阅

## 更新日志

### v2.0.0 (2026-05-13)

**重大架构变更：**
- 通信方式从 TCP直连 改为 MQTT（Broker中转）
- 下位机从 ESP8266 Arduino固件 改为 STM32L4+ESP01S AT固件
- 指令格式从 二进制协议 改为 JSON over MQTT
- 引入 EMQX Public Broker (broker.emqx.io:1883)

### v1.1.0 (2026-03-05)

**新增功能：**
- 实现与ESP8266的TCP通信
- 添加通信日志界面
- 添加命令发送功能
- 完善协议解析

### v1.0.0 (2026-02-05)

**新增功能：**
- 初始版本发布
- 实现数据监测界面
- 实现力控参数调节功能
- 实现系统状态监控
- 实现快捷指令功能
