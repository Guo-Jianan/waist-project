/* USER CODE BEGIN Header */
/**
 ******************************************************************************
 * File Name          : freertos.c
 * Description        : Code for freertos applications
 ******************************************************************************
 * @attention
 *
 * Copyright (c) 2026 STMicroelectronics.
 * All rights reserved.
 *
 * This software is licensed under terms that can be found in the LICENSE file
 * in the root directory of this software component.
 * If no LICENSE file comes with this software, it is provided AS-IS.
 *
 ******************************************************************************
 */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "driver_actuator.h"
#include "driver_shell.h"
#include "driver_frame.h"
#include "driver_log.h"
#include "driver_ESP01s.h"

#include "Alg_pid.h"

#include "adc.h"
#include "dma.h"
#include "sEMG.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */
/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN Variables */
ActuatorDevice ActuatorRF, ActuatorRB, ActuatorLB, ActuatorLF;
PID_Controller ActuatorRf_Pid, ActuatorRb_Pid, ActuatorLf_Pid, ActuatorLb_Pid;
volatile uint16_t AdcRec[5] = {0};
ESP8266_Device esp8266;


QueueSetHandle_t g_control_set;
/* USER CODE END Variables */
/* Definitions for defaultTask */
osThreadId_t defaultTaskHandle;
const osThreadAttr_t defaultTask_attributes = {
  .name = "defaultTask",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};
/* Definitions for pidControlTask */
osThreadId_t pidControlTaskHandle;
const osThreadAttr_t pidControlTask_attributes = {
  .name = "pidControlTask",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityRealtime,
};

/* Definitions for sEMGTask */
osThreadId_t sEMGTaskHandle;
const osThreadAttr_t sEMGTask_attributes = {
  .name = "sEMG Task",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityLow,
};

/* Definitions for sEMGPubTask */
osThreadId_t sEMGPubTaskHandle;
const osThreadAttr_t sEMGPubTask_attributes = {
  .name = "sEMG Pub",
  .stack_size = 256 * 4,
  .priority = (osPriority_t) osPriorityLow,
};

/* Private function prototypes -----------------------------------------------*/
/* USER CODE BEGIN FunctionPrototypes */

/* USER CODE END FunctionPrototypes */

void StartDefaultTask(void *argument);
void ControlFunction(void *argument);
void sEMG_PubTask(void *argument);

void MX_FREERTOS_Init(void); /* (MISRA C 2004 rule 8.1) */

/**
  * @brief  FreeRTOS initialization
  * @param  None
  * @retval None
  */
void MX_FREERTOS_Init(void) {
  /* USER CODE BEGIN Init */
  HAL_ADC_MspInit(&hadc1);
  HAL_ADC_Start_DMA(&hadc1, (uint32_t *)AdcRec, 5);
  Actuator_Init(&ActuatorRF, &htim4, TIM_CHANNEL_4, TIM_CHANNEL_3, 1000);
  Actuator_Init(&ActuatorRB, &htim4, TIM_CHANNEL_1, TIM_CHANNEL_2, 1000);
  Actuator_Init(&ActuatorLF, &htim5, TIM_CHANNEL_1, TIM_CHANNEL_2, 1000);
  Actuator_Init(&ActuatorLB, &htim5, TIM_CHANNEL_3, TIM_CHANNEL_4, 1000);
  PID_Init(&ActuatorRf_Pid, 10, 0.5, 0, 0.01, 1000, -1000, 1.0);
  PID_Init(&ActuatorRb_Pid, 10, 0.5, 0, 0.01, 1000, -1000, 1.0);
  PID_Init(&ActuatorLf_Pid, 10, 0.5, 0, 0.01, 1000, -1000, 1.0);
  PID_Init(&ActuatorLb_Pid, 10, 0.5, 0, 0.01, 1000, -1000, 1.0);
  sEMG_Init();
  /* USER CODE END Init */

  /* USER CODE BEGIN RTOS_MUTEX */
  /* add mutexes, ... */
  /* USER CODE END RTOS_MUTEX */

  /* USER CODE BEGIN RTOS_SEMAPHORES */
  /* add semaphores, ... */
  /* USER CODE END RTOS_SEMAPHORES */

  /* USER CODE BEGIN RTOS_TIMERS */
  /* start timers, add new ones, ... */
  /* USER CODE END RTOS_TIMERS */

  /* USER CODE BEGIN RTOS_QUEUES */
	g_control_set = xQueueCreateSet(SHELL_QUE_SIZE + FRAME_QUE_SIZE);
  /* USER CODE END RTOS_QUEUES */

  /* Create the thread(s) */
  /* creation of defaultTask */
  defaultTaskHandle = osThreadNew(StartDefaultTask, NULL, &defaultTask_attributes);

  /* creation of pidControlTask */
  pidControlTaskHandle = osThreadNew(ControlFunction, NULL, &pidControlTask_attributes);

  /* creation of sEMGTask */
  sEMGTaskHandle = osThreadNew(sEMG_Task, NULL, &sEMGTask_attributes);

  /* creation of sEMGPubTask */
  sEMGPubTaskHandle = osThreadNew(sEMG_PubTask, NULL, &sEMGPubTask_attributes);

  /* USER CODE BEGIN RTOS_THREADS */
  xPrintInit(osPriorityBelowNormal);
	xShellInit(osPriorityNormal);
	xFrameInit(osPriorityNormal);
  /* USER CODE END RTOS_THREADS */

  /* USER CODE BEGIN RTOS_EVENTS */
  /* add events, ... */
  /* USER CODE END RTOS_EVENTS */

}

/* USER CODE BEGIN Header_StartDefaultTask */
/**
 * @brief  Function implementing the defaultTask thread.
 * @param  argument: Not used
 * @retval None
 */
/* USER CODE END Header_StartDefaultTask */
void StartDefaultTask(void *argument)
{
  /* USER CODE BEGIN StartDefaultTask */
#ifdef STACK_PRINT
	UBaseType_t uxHighWaterMark = uxTaskGetStackHighWaterMark(NULL);
#endif

  ESP8266_Init(&esp8266, &huart1);

  if (ESP8266_ConnectAP(&esp8266, "rickWiFi", "12345678") == ESP8266_OK) {
      DEBUG_INFO("WiFi connected.\r\n");
  } else {
      DEBUG_ERROR("WiFi connect failed.\r\n");
  }

  vTaskDelay(pdMS_TO_TICKS(5000));  // 等待DHCP获取IP

  if (ESP8266_ConnectMQTT(&esp8266, "broker.emqx.io", 1883,
                          "ESP-01S", "ESP-01S", "admin", 1) == ESP8266_OK) {
      DEBUG_INFO("MQTT broker connected.\r\n");
  } else {
      DEBUG_ERROR("MQTT broker connect failed.\r\n");
  }

  vTaskDelay(pdMS_TO_TICKS(500));

  ESP8266_Subscribe(&esp8266, "waist/device001/cmd", 1);

  /* Infinite loop */
  for (;;)
  {
    HAL_GPIO_TogglePin(LD2_GPIO_Port, LD2_Pin);

    if (esp8266.mqtt_line_ready) {
        ESP8266_MQTT_HandleReceivedLine(&esp8266, esp8266.mqtt_line_buf);
        esp8266.mqtt_line_ready = 0;
    }

#ifdef STACK_PRINT
    uint32_t ulStackRemaining = uxHighWaterMark * 4;
    DEBUG_INFO("%d bytes short of overflow.\r\n", ulStackRemaining);
#endif
    vTaskDelay(500);
  }
  /* USER CODE END StartDefaultTask */
}

/* USER CODE BEGIN Header_ControlFunction */
/**
 * @brief Function implementing the pidControlTask thread.
 * @param argument: Not used
 * @retval None
 */
/* USER CODE END Header_ControlFunction */
void ControlFunction(void *argument)
{
  /* USER CODE BEGIN ControlFunction */
#ifdef STACK_PRINT
	UBaseType_t uxHighWaterMark = uxTaskGetStackHighWaterMark(NULL);
#endif
  TickType_t xLastWakeTime;
  const TickType_t xTaskPeriod = pdMS_TO_TICKS(10);
  xLastWakeTime = xTaskGetTickCount();
	ActuatorTarget current_target = {50.0,50.0,50.0,50.0};
	QueueSetMemberHandle_t xQueueHandle;
	//
  /* Infinite loop */
  for (;;)
  {
		xQueueHandle = xQueueSelectFromSet(g_control_set, 0);

		/* 读队列句柄得到数据,处理数据 */
		if (xQueueHandle == get_shellQueueHandle())
		{
			xQueueReceive(get_shellQueueHandle(), &current_target, 0);
			DEBUG_INFO("From shell Target Received: %.2f,%.2f,%.2f,%.2f\n",
							current_target.RbTarget,
							current_target.RfTarget,
							current_target.LfTarget,
							current_target.LbTarget);
		}	else if(xQueueHandle == get_FrameQueueHandle()){
			xQueueReceive(get_FrameQueueHandle(), &current_target, 0);
			DEBUG_INFO("From Frame Target Received: %.2f,%.2f,%.2f,%.2f\n", current_target.RbTarget,
																			current_target.RfTarget,
																			current_target.LfTarget,
																			current_target.LbTarget);
		}

//		if (xQueueReceive(get_shellQueueHandle(), &current_target, 0) == pdPASS) {
//			DEBUG_INFO("Target Received: %.2f\n", current_target.RbTarget);
//		}
      PID_SetTarget(&ActuatorRb_Pid, current_target.RbTarget);
      PID_Compute(&ActuatorRb_Pid, ActuatorRB.current_pos_mm);
      Actuator_Control(&ActuatorRB, ActuatorRb_Pid.output);

      PID_SetTarget(&ActuatorRf_Pid, current_target.RfTarget);
      PID_Compute(&ActuatorRf_Pid, ActuatorRF.current_pos_mm);
      Actuator_Control(&ActuatorRF, ActuatorRf_Pid.output);

      PID_SetTarget(&ActuatorLf_Pid, current_target.LfTarget);
      PID_Compute(&ActuatorLf_Pid, ActuatorLF.current_pos_mm);
      Actuator_Control(&ActuatorLF, ActuatorLf_Pid.output);

      PID_SetTarget(&ActuatorLb_Pid, current_target.LbTarget);
      PID_Compute(&ActuatorLb_Pid, ActuatorLB.current_pos_mm);
      Actuator_Control(&ActuatorLB, ActuatorLb_Pid.output);
#ifdef STACK_PRINT
    uint32_t ulStackRemaining = uxHighWaterMark * 4;
		DEBUG_INFO("%d bytes short of overflow.\r\n", ulStackRemaining);
#endif
    vTaskDelayUntil(&xLastWakeTime, xTaskPeriod);
  }
  /* USER CODE END ControlFunction */
}

/* USER CODE BEGIN Header_sEMGPubTask */
/**
 * @brief Function implementing the sEMG publish task.
 * @param argument: Not used
 * @retval None
 */
/* USER CODE END Header_sEMGPubTask */
void sEMG_PubTask(void *argument)
{
  /* USER CODE BEGIN sEMGPubTask */
  TickType_t xLastWakeTime;
  const TickType_t xTaskPeriod = pdMS_TO_TICKS(100);
  xLastWakeTime = xTaskGetTickCount();

  for (;;)
  {
    uint16_t semg_raw = sEMG_GetRaw();
    char payload[16];
    sprintf(payload, "%u", semg_raw);
    ESP8266_MQTTPublish(&esp8266, "waist/device001/sEMG", payload, 0);

    vTaskDelayUntil(&xLastWakeTime, xTaskPeriod);
  }
  /* USER CODE END sEMGPubTask */
}

/* Private application code --------------------------------------------------*/
/* USER CODE BEGIN Application */
/* USER CODE END Application */

