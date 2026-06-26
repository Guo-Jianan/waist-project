# 下位机固件 — STM32L4 腰部康复机器人控制器

基于 STM32L4R5ZIT6 的实时嵌入式控制系统，负责四路推杆伺服控制、sEMG 信号采集与 MQTT 通信桥接。

---

## 硬件平台

| 组件 | 型号 | 规格 |
|------|------|------|
| MCU | STM32L4R5ZIT6 | Cortex-M4F @ 120MHz, 2MB Flash, 640KB SRAM |
| WiFi 模块 | ESP-01S (ESP8266) | AT 固件 v2.3.0, USART1 @ 115200 baud |
| 推杆电机 | 4× 直流推杆 | PWM 驱动 + ADC 位置反馈 (电位计) |
| sEMG 传感器 | 表面肌电电极 | ADC1 IN4, 12-bit, 0–3.3V |
| IMU | GY85 (预留) | I2C 接口，未集成 |
| 调试串口 | LPUART1 | 209700 baud |

---

## 技术栈

| 类别 | 技术 | 备注 |
|------|------|------|
| MCU | STM32L4R5ZIT6 | L4 系列超低功耗 |
| RTOS | FreeRTOS (CMSIS-RTOS v2) | 任务调度、队列通信 |
| HAL | STM32L4xx HAL | CubeMX 生成代码框架 |
| 工具链 | Keil MDK-ARM v5 | .uvprojx 工程文件 |
| 通信 | ESP-01S AT 固件 | MQTT over TCP, JSON 协议 |
| 控制 | 位置式 PID | 死区处理 + 抗积分饱和 |

---

## 项目结构

```
STM32L4_waist/
├── NEW_Waist.ioc                  # STM32CubeMX 工程配置（可重新生成）
├── .mxproject                     # CubeMX 元数据
├── Algorithm/
│   ├── Alg_pid.c / .h            # PID 控制器（位置式）
│   └── Alg_impedance.c / .h      # 阻抗控制（占位，内容同 PID）
├── Core/
│   ├── Inc/                      # HAL 头文件
│   │   ├── main.h                # 引脚定义、时钟配置
│   │   ├── FreeRTOSConfig.h      # RTOS 配置（定时器周期、堆大小）
│   │   ├── adc.h, dma.h, ...     # 外设头文件
│   │   └── stm32l4xx_it.h        # 中断声明
│   └── Src/
│       ├── main.c                # 入口：HAL 初始化、外设初始化、启动内核
│       ├── freertos.c            # FreeRTOS 任务创建、外设初始化
│       ├── stm32l4xx_it.c        # 中断服务函数
│       └── adc.c, dma.c, ...     # 外设驱动
├── Drivers/Bsp_Drivers/          # 板级驱动（自定义）
│   ├── driver_actuator.c / .h   # 推杆抽象层（PWM + ADC 反馈）
│   ├── driver_ESP01s.c / .h     # ESP-01S AT 指令驱动
│   ├── driver_frame.c / .h      # 二进制帧协议解析器
│   ├── driver_shell.c / .h      # 串口命令行解析
│   ├── driver_irq.c             # HAL 回调分发
│   ├── driver_log.c / .h        # 异步日志子系统
│   ├── driver_gy85.c / .h       # GY85 IMU 驱动（预留）
│   └── sEMG.c / .h              # sEMG 采集 + 移动平均滤波 + 乒乓缓冲
├── MDK-ARM/
│   ├── NEW_Waist.uvprojx         # Keil MDK 工程文件
│   ├── NEW_Waist.uvoptx         # Keil 选项配置
│   └── startup_stm32l4r5xx.s    # 启动文件
└── Middlewares/Third_Party/
    └── FreeRTOS/                 # FreeRTOS 内核源码
```

---

## RTOS 任务设计

| 任务 | 优先级 | 栈大小 | 周期 | 功能 |
|------|--------|--------|------|------|
| `defaultTask` | Normal | 1024 B | 500 ms | ESP-01S 初始化 → WiFi 连接 → MQTT 连接/订阅 → 轮询 MQTT 消息 → LED 翻转 |
| `pidControlTask` | **Realtime** | 2048 B | **10 ms** | QueueSet 多路选择（Shell/Frame 队列）→ 4 路 PID 计算 → 4 路 PWM 输出 |
| `sEMG Task` | Low | 1024 B | **1 ms** | 读取 ADC1 IN4 → 移动平均滤波 → 乒乓缓冲写入 |
| `sEMG Pub` | Low | 1024 B | **1000 ms** | 检查就绪缓冲区 → 格式化为数字字符串 → MQTT 发布 |
| `printTask` | BelowNormal | - | 异步 | 队列式异步串口日志输出 |
| `shellTask` | Normal | - | 异步 | 命令行解析（RB/RF/LB/LF 指令） |
| `frameTask` | Normal | - | 异步 | 二进制帧协议解析 |

---

## 控制算法

位置式 PID，控制周期 10 ms（100 Hz）。

### PID 参数

| 参数 | 值 |
|------|-----|
| Kp | 10.0 |
| Ki | 0.5 |
| Kd | 0.0 |
| dt | 0.01 s |
| 输出范围 | [-1000, 1000] |
| 积分限幅 | out_max × 0.5 = 500 |
| 死区 | 1.0 mm |

### 控制特性

- **死区处理**: 误差 < 1.0 mm 时输出 0，清空积分项，防止执行器频繁抖动
- **抗积分饱和**: 积分项限幅至输出最大值的一半
- **输出限幅**: [-1000, 1000] PWM 计数值
- **ADC 转位移**: `pos_mm = (4096 - adc) × (100.0 / 4096)`，行程 0–100 mm
- **软件限位**: 5 mm（最小）~ 80 mm（最大）

### 执行流程

```
外部输入（Shell 指令 / MQTT JSON / 二进制帧）
    → QueueSet 多路复用
    → pidControlTask @ 10 ms
        → PID_Compute(RB) → Actuator_Control(RB)
        → PID_Compute(RF) → Actuator_Control(RF)
        → PID_Compute(LF) → Actuator_Control(LF)
        → PID_Compute(LB) → Actuator_Control(LB)
    → TIM4/TIM5 PWM 输出
```

### 推杆引脚映射

| 推杆 | PWM Timer | PWM 通道 (正/反) | PWM 引脚 | ADC 通道 | ADC 引脚 |
|------|-----------|-----------------|----------|----------|----------|
| RB (右后) | TIM4 | CH1/CH2 | PD15/PD14 | ADC1 IN8 | PA3 |
| RF (右前) | TIM4 | CH3/CH4 | PD12/PD13 | ADC1 IN7 | PA2 |
| LF (左前) | TIM5 | CH1/CH2 | PF6/PF7 | ADC1 IN2 | PC1 |
| LB (左后) | TIM5 | CH3/CH4 | PF8/PF9 | ADC1 IN3 | PC2 |

---

## sEMG 信号采集

### 采集参数

| 参数 | 值 |
|------|-----|
| ADC 通道 | ADC1 IN4 (PA4) |
| 采样率 | 1 kHz |
| 分辨率 | 12-bit (0–4095, 0–3.3V) |
| 滤波 | 移动平均 (窗口=5, 最大 64) |
| 缓冲架构 | 双缓冲乒乓 (ping-pong) |

### 乒乓缓冲机制

```
sEMG_Task @1 ms:
    ADC 采样 → 移动平均滤波 → 写入当前缓冲区
    缓冲区满 → 标记就绪 → 切换缓冲区

sEMG_PubTask @1000 ms:
    检查非填充态的就绪缓冲区
    格式化 PINGPONG_SIZE 个采样点为空格分隔字符串
    MQTT 发布至 topic: waist/{device_id}/sEMG
```

- 缓冲区大小: `PINGPONG_SIZE` = 200 采样点（约 200 ms 数据）
- 两任务无锁操作：通过缓冲区状态标志（`pp_fill_target`）保证不会同时读写同一缓冲区

---

## MQTT 通信

通过 ESP-01S 的 AT 固件实现 WiFi + MQTT：

| 配置 | 值 |
|------|-----|
| WiFi SSID | rickWiFi (2.4 GHz) |
| MQTT Broker | broker.emqx.io:1883 |
| 认证 | 用户名 `ESP-01S` / 密码 `admin` |
| 订阅主题 | `waist/device001/cmd` (QoS 1) |
| 发布主题 | `waist/device001/sEMG` (QoS 0) |

下位机读取到的 MQTT JSON 指令格式：
```json
{"RB": 50.0, "RF": 50.0, "LB": 50.0, "LF": 50.0}
```

订阅消息在 UART 空闲中断中被接收，由 `defaultTask` 轮询检测 `mqtt_line_ready` 标志后解析，通过队列发送至 `pidControlTask`。

---

## 通信协议

### 1. Shell 命令行 (LPUART1)

```
RB 50.0    # 设置右后推杆到 50 mm
RF 30.0    # 设置右前推杆到 30 mm
LB 60.0    # 设置左后推杆到 60 mm
LF 40.0    # 设置左前推杆到 40 mm
```

### 2. 二进制帧协议 (TCP legacy)

```
[0xA5][0xCC][0x10][RB:4B][RF:4B][LB:4B][LF:4B][checksum][0x5A]
```

- 帧头: 0xA5
- 功能码: 0xCC（控制）/ 0xCF（数据上传）
- 长度: 0x10 (16 bytes)
- 数据: 4 个 float (小端序)
- 校验: `~(header + func + data_bytes)`
- 帧尾: 0x5A

---

## 性能指标

| 指标 | 值 | 说明 |
|------|-----|------|
| PID 控制周期 | 10 ms | 100 Hz, Realtime 优先级 |
| sEMG 采样率 | 1 kHz | 1 ms 周期严格定时 |
| sEMG 批量发布周期 | 1000 ms | 每批 ~200 个采样点 |
| ADC 分辨率 | 12-bit | 0–4095 |
| ADC 通道数量 | 5 | 4 路位置反馈 + 1 路 sEMG |
| PWM 频率 | 1 kHz | TIM4, TIM5 |
| 推杆行程范围 | 0–100 mm | 软件限位 5–80 mm |
| 位置反馈分辨率 | ~0.024 mm | 100 mm / 4096 |
| MQTT 消息解析 | 中断接收 + 任务轮询 | 无阻塞 |
| PID 死区 | 1.0 mm | 防止执行器抖动 |
| sEMG 滤波窗口 | 5 taps | 移动平均，可配置最大 64 |

---

## 已知问题

1. **阻抗控制未实现**: `Alg_impedance.c` 目前仅复制了 PID 代码，未实现力位混合控制
2. **GY85 IMU 未集成**: 驱动文件存在但未接入控制回路
3. **MQTT 无 TLS**: ESP-01S AT 固件限制，MQTT 仅支持 TCP 明文连接
4. **无自动重连**: WiFi 或 MQTT 断开后不会自动重连
5. **无急停保护**: 缺乏紧急停止和过流检测机制
6. **未上报位置状态**: 推杆实际位置未通过 MQTT 定时上报

---

## 开发

### 编译

使用 Keil MDK-ARM v5 打开工程文件：

```
MDK-ARM/NEW_Waist.uvprojx
```

### 串口调试

使用 LPUART1 (209700 baud) 连接 Shell，支持以下命令：

| 命令 | 格式 | 说明 |
|------|------|------|
| 设置推杆 | `RB <value>` | 设置右后推杆目标位置 (mm) |
| 设置推杆 | `RF <value>` | 设置右前推杆目标位置 (mm) |
| 设置推杆 | `LB <value>` | 设置左后推杆目标位置 (mm) |
| 设置推杆 | `LF <value>` | 设置左前推杆目标位置 (mm) |

### 引脚定义

详见 `Core/Inc/main.h` 中的 GPIO 和外围引脚宏定义。

---

*文档版本: 2026-06*
