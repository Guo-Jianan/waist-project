#include "sEMG.h"
#include "cmsis_os.h"
#include <string.h>

// 外部变量声明（来自freertos.c）
extern volatile uint16_t AdcRec[5];

// 内部定义
#define SEMG_FILTER_WINDOW_DEFAULT 5
#define SEMG_BUFFER_SIZE 64
// PINGPONG_SIZE 定义在 sEMG.h 中

// 内部变量
static uint16_t sEMG_Raw = 0;
static uint16_t sEMG_Filtered = 0;
static uint8_t filter_window = SEMG_FILTER_WINDOW_DEFAULT;

// 环形缓冲区（移动平均滤波用）
static uint16_t ring_buffer[SEMG_BUFFER_SIZE];
static uint32_t ring_index = 0;
static uint32_t ring_count = 0;

// -------------------- 乒乓缓冲区（采样与发送完全解耦）--------------------
// sEMG_Task @1ms 填充当前缓冲区，满则切换到另一个并标记就绪
// PubTask @100ms 取走就绪缓冲区（拷贝到局部变量后发布），标记空闲
// 两个任务永远不会同时读写同一个缓冲区
static uint16_t pp_buffer_a[PINGPONG_SIZE];
static uint16_t pp_buffer_b[PINGPONG_SIZE];
static volatile uint8_t pp_fill_target = 0;  // 0=正填充buffer_a, 1=正填充buffer_b
static volatile uint8_t pp_fill_pos = 0;     // 当前填充位置
static volatile uint8_t pp_a_ready = 0;      // 1=buffer_a有数据待发送
static volatile uint8_t pp_b_ready = 0;      // 1=buffer_b有数据待发送

// 移动平均滤波
static uint16_t moving_average_filter(uint16_t new_sample)
{
    // 存入环形缓冲区
    ring_buffer[ring_index] = new_sample;
    ring_index = (ring_index + 1) % SEMG_BUFFER_SIZE;
    if (ring_count < SEMG_BUFFER_SIZE) {
        ring_count++;
    }
    
    // 计算平均值
    uint32_t sum = 0;
    uint32_t count = (ring_count < filter_window) ? ring_count : filter_window;
    uint32_t start_idx = (ring_index - count + SEMG_BUFFER_SIZE) % SEMG_BUFFER_SIZE;
    
    for (uint32_t i = 0; i < count; i++) {
        uint32_t idx = (start_idx + i) % SEMG_BUFFER_SIZE;
        sum += ring_buffer[idx];
    }
    
    return (uint16_t)(sum / count);
}

// 初始化sEMG驱动
void sEMG_Init(void)
{
    // 清空环形缓冲区
    memset(ring_buffer, 0, sizeof(ring_buffer));
    ring_index = 0;
    ring_count = 0;
    filter_window = SEMG_FILTER_WINDOW_DEFAULT;
    sEMG_Raw = 0;
    sEMG_Filtered = 0;
    
    // 重置乒乓缓冲区状态
    memset(pp_buffer_a, 0, sizeof(pp_buffer_a));
    memset(pp_buffer_b, 0, sizeof(pp_buffer_b));
    pp_fill_target = 0;
    pp_fill_pos = 0;
    pp_a_ready = 0;
    pp_b_ready = 0;
}

// 获取原始ADC值（立即返回AdcRec[4]）
uint16_t sEMG_GetRaw(void)
{
    return sEMG_Raw;
}

// 获取滤波后的值
uint16_t sEMG_GetFiltered(void)
{
    return sEMG_Filtered;
}

// 获取滤波后的值（浮点格式，0-1）
float sEMG_GetFilteredFloat(void)
{
    return (float)sEMG_Filtered / 4095.0f;
}

// 设置滤波窗口大小
void sEMG_SetFilterWindow(uint8_t window_size)
{
    if (window_size > 0 && window_size <= SEMG_BUFFER_SIZE) {
        filter_window = window_size;
    }
}

// 批量读取缓存的sEMG数据（最多max个），返回实际读取数量
// 乒乓机制：读取非填充中的就绪缓冲区，sEMG_Task和PubTask不会同时读写同一块
uint8_t sEMG_ReadBatch(uint16_t *buf, uint8_t max)
{
    uint8_t count = 0;
    
    // 始终读取非填充中的那个已就绪缓冲区，避免读写冲突
    if (pp_fill_target == 1 && pp_a_ready) {
        // 正在填充buffer_b，读buffer_a
        count = PINGPONG_SIZE;
        if (count > max) count = max;
        memcpy(buf, pp_buffer_a, count * sizeof(uint16_t));
        pp_a_ready = 0;
    } else if (pp_fill_target == 0 && pp_b_ready) {
        // 正在填充buffer_a，读buffer_b
        count = PINGPONG_SIZE;
        if (count > max) count = max;
        memcpy(buf, pp_buffer_b, count * sizeof(uint16_t));
        pp_b_ready = 0;
    }
    // 如果就绪的恰好是正在填充的缓冲区，不读取（等待下次轮询）
    
    return count;
}

// 将就绪的乒乓缓冲区直接格式化为数字字符串（零拷贝，无中间数组）
// buf: 输出缓冲区  buf_size: 输出缓冲区大小  返回: 字符串长度(0=无数据)
uint16_t sEMG_PreparePayload(char *buf, uint16_t buf_size)
{
    uint16_t *src = NULL;
    uint16_t count = 0;

    // 读非填充中的就绪缓冲区
    if (pp_fill_target == 1 && pp_a_ready) {
        src = pp_buffer_a;
        count = PINGPONG_SIZE;
        pp_a_ready = 0;
    } else if (pp_fill_target == 0 && pp_b_ready) {
        src = pp_buffer_b;
        count = PINGPONG_SIZE;
        pp_b_ready = 0;
    }

    if (src == NULL || count == 0) return 0;

    uint16_t pos = 0;
    for (uint16_t i = 0; i < count && pos < buf_size; i++) {
        if (i > 0 && pos + 1 < buf_size) {
            buf[pos++] = ' ';
        }
        int n = snprintf(buf + pos, buf_size - pos, "%u", src[i]);
        if (n > 0) pos += (uint16_t)n;
    }
    return pos;
}

// sEMG任务入口函数
void sEMG_Task(void *argument)
{
    TickType_t xLastWakeTime;
    const TickType_t xTaskPeriod = pdMS_TO_TICKS(1); // 1ms周期 = 1kHz
    
    xLastWakeTime = xTaskGetTickCount();
    
    for (;;) {
        // 读取sEMG原始数据（AdcRec[4]）
        sEMG_Raw = AdcRec[4];
        
        // 执行滤波
        sEMG_Filtered = moving_average_filter(sEMG_Raw);
        
        // 乒乓缓冲区：写入当前正在填充的缓冲区
        if (pp_fill_target == 0) {
            pp_buffer_a[pp_fill_pos] = sEMG_Filtered;
        } else {
            pp_buffer_b[pp_fill_pos] = sEMG_Filtered;
        }
        pp_fill_pos++;
        
        // 当前缓冲区已满 → 标记就绪，切换到另一个缓冲区
        if (pp_fill_pos >= PINGPONG_SIZE) {
            if (pp_fill_target == 0) {
                pp_a_ready = 1;       // buffer_a 可发送
            } else {
                pp_b_ready = 1;       // buffer_b 可发送
            }
            pp_fill_target = !pp_fill_target;  // 切换填充目标
            pp_fill_pos = 0;                   // 新缓冲区从头开始填
        }
        
        // 等待下一个周期
        vTaskDelayUntil(&xLastWakeTime, xTaskPeriod);
    }
}
