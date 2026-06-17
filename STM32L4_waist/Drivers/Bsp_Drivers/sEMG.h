#ifndef __SEMG_H__
#define __SEMG_H__

#include <stdint.h>

#define PINGPONG_SIZE 200         // 乒乓缓冲区大小（约200ms数据，匹配MQTTPublish阻塞耗时）

// 初始化sEMG驱动
void sEMG_Init(void);

// 获取原始ADC值（立即返回AdcRec[4]）
uint16_t sEMG_GetRaw(void);

// 获取滤波后的值
uint16_t sEMG_GetFiltered(void);

// 获取滤波后的值（浮点格式，0-1）
float sEMG_GetFilteredFloat(void);

// sEMG任务入口函数
void sEMG_Task(void *argument);

// 批量读取缓存的sEMG数据（乒乓缓冲区，最多max个），返回实际读取数量
uint8_t sEMG_ReadBatch(uint16_t *buf, uint8_t max);

// 将就绪的乒乓缓冲区直接格式化为数字字符串（零拷贝），返回字符串长度
uint16_t sEMG_PreparePayload(char *buf, uint16_t buf_size);

// 设置滤波窗口大小
void sEMG_SetFilterWindow(uint8_t window_size);

#endif /* __SEMG_H__ */
