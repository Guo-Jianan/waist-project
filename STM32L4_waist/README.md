# STM32L4 四推杆控制节点

## 1. 项目概述

基于 **STM32L4 + FreeRTOS** 的四推杆控制项目。通过 ESP01S（AT固件）连接 WiFi，经 MQTT Broker 接收上位机 JSON 控制指令，PID 闭环控制四路推杆。

| 推杆 | PWM通道 | ADC通道 | 状态 |
|------|---------|---------|------|
| RB（右后） | TIM4 CH1/CH2 (PD15/PD14) | ADC1 IN8 (PA3) | ✅ 闭环控制 |
| RF（右前） | TIM4 CH3/CH4 (PD12/PD13) | ADC1 IN7 (PA2) | ✅ 闭环控制 |
| LF（左前） | TIM5 CH1/CH2 (PF6/PF7) | ADC1 IN2 (PC1) | ✅ 闭环控制 |
| LB（左后） | TIM5 CH3/CH4 (PF8/PF9) | ADC1 IN3 (PC2) | ✅ 闭环控制 |

---

## 2. 硬件接口

### TIM PWM（推杆驱动）
| 推杆 | 定时器 | 通道 | IO |
|------|--------|------|-----|
| RB | TIM4 | CH1/CH2 | PD15/PD14 |
| RF | TIM4 | CH3/CH4 | PD12/PD13 |
| LF | TIM5 | CH1/CH2 | PF6/PF7 |
| LB | TIM5 | CH3/CH4 | PF8/PF9 |

### ADC1 DMA（位置反馈）
| 推杆 | 通道 | IO |
|------|------|-----|
| RF | IN7 | PA2 |
| RB | IN8 | PA3 |
| LB | IN3 | PC2 |
| LF | IN2 | PC1 |

### 串口
| 功能 | 外设 | IO | 波特率 |
|------|------|-----|--------|
| Shell/Log | LPUART1 | PG7/PG8 | 209700 |
| ESP01S | USART1 | PG9/PG10 | 115200 |

---

## 3. 软件架构

### 核心文件
| 文件 | 作用 |
|------|------|
| `freertos.c` | 任务创建、WiFi/MQTT初始化、主循环轮询MQTT消息 |
| `driver_actuator.c` | 推杆抽象、PWM控制、ADC反馈 |
| `driver_frame.c` | 二进制协议解析（兼容旧版TCP帧）、frame队列 |
| `driver_shell.c` | 本地Shell命令 |
| `driver_ESP01s.c` | ESP01S AT指令驱动、MQTT连接/订阅/消息解析 |
| `driver_log.h` | 分级调试日志 (ERROR/WARNING/INFO) |
| `driver_irq.c` | HAL回调分发 |

### 任务
| 任务 | 优先级 | 栈大小 | 功能 |
|------|--------|--------|------|
| defaultTask | Normal | 512×4 | ESP01S初始化→WiFi连接→MQTT连接→订阅主题→轮询MQTT消息→LED闪烁 |
| pidControlTask | Realtime | 128×4 | 队列集读取目标 → 4路PID计算 → PWM输出 |
| printTask | BelowNormal | — | 调试日志异步输出 |
| shellTask | Normal | — | Shell命令解析 |
| frameTask | Normal | — | 二进制帧解析（兼容模式） |

---

## 4. 控制链路

### MQTT控制（主要通道）
```
MQTTX/上位机 → MQTT Broker → ESP01S → UART AT响应
    → ESP8266_UART_IDLE_Handler → mqtt_line_buf
    → defaultTask轮询 → JSON解析 → ActuatorTarget
    → frame队列 → pidControlTask → 4路PID → PWM
```

### MQTT 指令格式 (JSON)
**Topic**: `waist/device001/cmd` (QoS 1)

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

### Shell控制（本地调试）
```
LPUART1 DMA → Shell解析 → shell队列 → pidControlTask → 4路PID → PWM
```

### 反馈链路
```
ADC1 DMA (4通道) → Actuator_UpdateFeedback → current_pos_mm → PID
```

---

## 5. MQTT 配置

| 参数 | 值 | 说明 |
|------|-----|------|
| WiFi SSID | `rickWiFi` | 2.4G WiFi |
| WiFi 密码 | `12345678` | — |
| Broker | `broker.emqx.io` | EMQX Public Broker |
| 端口 | `1883` | TCP（非TLS） |
| 连接方式 | scheme=1 | MQTT over TCP |
| 客户端ID | `ESP-01S` | — |
| 用户名 | `ESP-01S` | — |
| 密码 | `admin` | — |
| 订阅Topic | `waist/device001/cmd` | — |
| QoS | 1 | 至少一次送达 |

> 修改WiFi/MQTT配置：编辑 `freertos.c` 中 `StartDefaultTask` 函数的 `ESP8266_ConnectAP` 和 `ESP8266_ConnectMQTT` 调用参数。

---

## 6. AT指令序列

ESP01S初始化时依次执行以下AT指令（带超时重试）：

```
AT+RST                         → 复位模块 (等待 "ready")
AT                             → 测试通信 (等待 "OK")
ATE0                           → 关闭回显 (等待 "OK")
AT+CWMODE=1                    → 设为STA模式 (等待 "OK")
AT+CWJAP="SSID","PWD"         → 连接WiFi (等待 "OK", 10s超时)
AT+MQTTUSERCFG=0,1,...        → 配置MQTT用户 (等待 "OK", 5s超时, 3次重试)
AT+MQTTCONN=0,"broker",1883,0 → 连接MQTT Broker (等待 "OK", 10s超时, 3次重试)
AT+MQTTSUB=0,"topic",1        → 订阅主题 (等待 "OK", 5s超时)
```

WiFi连接后等待5秒确保DHCP获取IP，MQTT两个步骤各支持3次重试（间隔2秒）。

---

## 7. 二进制协议（兼容保留）

旧版TCP直连模式的控制帧格式：
```
[0]   head   = 0xA5
[1]   func   = 0xCC
[2]   len    = 0x10
[3:6] rb     = float
[7:10] rf    = float
[11:14] lb   = float
[15:18] lf   = float
[19]  check  = ~(head + func + data)
[20]  tail   = 0x5A
```

### Shell命令（本地调试）
```
RB <float>   // 设置RB目标值
RF <float>   // 设置RF目标值
LF <float>   // 设置LF目标值
LB <float>   // 设置LB目标值
```

---

## 8. 调试

### 开启调试输出
- `driver_ESP01s.h`: 取消注释 `#define ESP8266_DEBUG` 查看AT指令收发
- `driver_log.h`: 定义 `DEBUG_PRINT_ENABLED` 启用分级日志

### 串口连接
- Shell/Log输出: LPUART1, 209700bps
- 使用串口工具连接后可直接输入Shell命令（RB/RF/LB/LF）控制推杆

---

## 9. 待完成

- [ ] MQTT数据上报（推杆位置/力传感器状态）
- [ ] 异常保护/急停
- [ ] WiFi断线自动重连
- [ ] MQTT断线自动重连

---

## 10. 快速开始

1. 连接 LPUART1（Shell/Log, 209700bps）查看启动日志
2. 设备自动连接WiFi → MQTT Broker → 订阅 `waist/device001/cmd`
3. 使用 MQTTX 或上位机向该Topic发布JSON指令
4. 或直接通过Shell发送 `RB 50` 等命令本地控制
