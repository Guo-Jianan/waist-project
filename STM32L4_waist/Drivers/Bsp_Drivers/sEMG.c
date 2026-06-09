#include "sEMG.h"
#include "cmsis_os.h"
#include <string.h>

// 外部变量声明（来自freertos.c）
extern volatile uint16_t AdcRec[5];

// 内部定义
#define SEMG_FILTER_WINDOW_DEFAULT 16
#define SEMG_BUFFER_SIZE 64

// 内部变量
static uint16_t sEMG_Raw = 0;
static uint16_t sEMG_Filtered = 0;
static uint8_t filter_window = SEMG_FILTER_WINDOW_DEFAULT;

// 环形缓冲区
static uint16_t ring_buffer[SEMG_BUFFER_SIZE];
static uint32_t ring_index = 0;
static uint32_t ring_count = 0;

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
    // 清空缓冲区
    memset(ring_buffer, 0, sizeof(ring_buffer));
    ring_index = 0;
    ring_count = 0;
    filter_window = SEMG_FILTER_WINDOW_DEFAULT;
    sEMG_Raw = 0;
    sEMG_Filtered = 0;
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

// sEMG任务入口函数
void sEMG_Task(void *argument)
{
    TickType_t xLastWakeTime;
    const TickType_t xTaskPeriod = pdMS_TO_TICKS(1); // 1ms周期 = 1kHz，可调整
    
    xLastWakeTime = xTaskGetTickCount();
    
    for (;;) {
        // 读取sEMG原始数据（AdcRec[4]）
        sEMG_Raw = AdcRec[4];
        
        // 执行滤波
        sEMG_Filtered = moving_average_filter(sEMG_Raw);
        
        // 等待下一个周期
        vTaskDelayUntil(&xLastWakeTime, xTaskPeriod);
    }
}
