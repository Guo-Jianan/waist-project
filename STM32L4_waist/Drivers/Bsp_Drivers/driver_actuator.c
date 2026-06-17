#include "driver_actuator.h"


static uint16_t abs(int16_t num)
{
	if(num < 0)
		return -num;
	else
		return num;
}

/**
 * @brief 初始化推杆设备，绑定定时器和通道
 */
void Actuator_Init(ActuatorDevice* dev, void* tim_ptr, uint32_t ch_a, uint32_t ch_b, uint32_t max_duty) {
    if (dev == NULL) return;

    // 硬件绑定
    dev->tim_handle = tim_ptr;
    dev->channel_a = ch_a;
    dev->channel_b = ch_b;

    // 参数设定
    dev->max_duty = max_duty;
    dev->dir = ACTUATOR_STOP;
    dev->current_duty = 0;
    dev->current_adc = 0;
    dev->current_pos_mm = 0;

    // 启动定时器 PWM 输出
    HAL_TIM_PWM_Start((TIM_HandleTypeDef*)dev->tim_handle, dev->channel_a);
    HAL_TIM_PWM_Start((TIM_HandleTypeDef*)dev->tim_handle, dev->channel_b);

    // 初始状态停止
    __HAL_TIM_SetCompare((TIM_HandleTypeDef*)dev->tim_handle, dev->channel_a, 0);
    __HAL_TIM_SetCompare((TIM_HandleTypeDef*)dev->tim_handle, dev->channel_b, 0);
}

/**
 * @brief 目标控制，根据方向和占空比驱动绑定的定时器通道
 */
void Actuator_Control(ActuatorDevice* dev, int16_t duty) {
    if (dev == NULL || dev->tim_handle == NULL) return;

    // 1. 限幅（先限幅再判断方向）
    if (duty > (int16_t)dev->max_duty) duty = (int16_t)dev->max_duty;
    if (duty < -(int16_t)dev->max_duty) duty = -(int16_t)dev->max_duty;

    // 2. 判断方向
    if(duty > 0)
        dev->dir = ACTUATOR_FORWARD;
    else if(duty < 0)
        dev->dir = ACTUATOR_BACKWARD;
    else
        dev->dir = ACTUATOR_STOP;

    dev->current_duty = (duty > 0) ? duty : -duty;  // 存储绝对值

    // 3. 硬件驱动逻辑
    TIM_HandleTypeDef* htim = (TIM_HandleTypeDef*)dev->tim_handle;

    // 4. 软件限位（位置保护）
    if(dev->current_pos_mm > 80.f && dev->dir == ACTUATOR_FORWARD)
    {
        dev->dir = ACTUATOR_STOP;
    }
    if(dev->current_pos_mm < 5.f && dev->dir == ACTUATOR_BACKWARD)
    {
        dev->dir = ACTUATOR_STOP;
    }

    switch (dev->dir) {
        case ACTUATOR_FORWARD:
            __HAL_TIM_SetCompare(htim, dev->channel_a, dev->current_duty);
            __HAL_TIM_SetCompare(htim, dev->channel_b, dev->max_duty);
            break;

        case ACTUATOR_BACKWARD:
            __HAL_TIM_SetCompare(htim, dev->channel_a, dev->max_duty);
            __HAL_TIM_SetCompare(htim, dev->channel_b, dev->current_duty);
            break;

        case ACTUATOR_STOP:
        default:
            __HAL_TIM_SetCompare(htim, dev->channel_a, dev->max_duty);
            __HAL_TIM_SetCompare(htim, dev->channel_b, dev->max_duty);
            break;
    }
}

/**
 * @brief 更新反馈，由外部 ADC 回调调用
 */
void Actuator_UpdateFeedback(ActuatorDevice* dev, uint16_t adc_val) {
    if (dev == NULL) return;
    dev->current_adc = adc_val;
    dev->current_pos_mm = ADC_TO_MM_FLOAT(adc_val);
}
