#ifndef __SEMG_H__
#define __SEMG_H__

#include <stdint.h>

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

// 设置滤波窗口大小
void sEMG_SetFilterWindow(uint8_t window_size);

#endif /* __SEMG_H__ */
