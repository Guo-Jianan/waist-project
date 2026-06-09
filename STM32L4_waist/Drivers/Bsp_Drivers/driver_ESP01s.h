#ifndef __DRIVER_ESP01S_H__
#define __DRIVER_ESP01S_H__

#include "main.h"
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include "usart.h"
#include "FreeRTOS.h"
#include "task.h"
#include "driver_log.h"

#define RX_BUF_SIZE 256
#define ESP8266_DEBUG

// 连接状态
typedef enum {
    ESP8266_OK = 0,
    ESP8266_ERROR_TIMEOUT,
    ESP8266_ERROR_RESPONSE,
    ESP8266_ERROR_UART,
    ESP8266_ERROR_CONNECT
} ESP8266_Status;

// 命令执行状态
typedef enum {
    CMD_IDLE = 0,
    CMD_WAITING,   // 正在等待回复
    CMD_Done,      // 成功收到预期回复
    CMD_Error      // 收到错误或其他
} ESP8266_CmdState;

typedef struct {
    UART_HandleTypeDef* huart;

    // 缓冲区相关
    uint8_t rx_buf[RX_BUF_SIZE];
    volatile uint16_t rx_len;
    uint8_t temp_byte;            // 单字节接收缓存

    // 状态与同步
    volatile uint8_t link_id;     // 连接ID (0xFF 无连接)
    volatile ESP8266_CmdState cmd_state; // 当前AT指令的状态
    const char* expected_resp;    // 当前期待的AT指令回复字符串 (如 "OK")

    // MQTT 消息行缓冲（中断写入，任务读取）
    volatile uint8_t mqtt_line_ready;
    char mqtt_line_buf[512];

} ESP8266_Device;

typedef struct {
    const char* ssid;
    const char* pwd;
    uint8_t channel;
    uint8_t encryption;
} ESP8266_AP_Config;

/* 接口函数 */
ESP8266_Status ESP8266_Init(ESP8266_Device* dev, UART_HandleTypeDef* huart);
ESP8266_Status ESP8266_InitAP(ESP8266_Device* dev, const ESP8266_AP_Config* ap_cfg);
ESP8266_Status ESP8266_CreateTCPServer(ESP8266_Device* dev, uint16_t port);
ESP8266_Status ESP8266_SendData(ESP8266_Device* dev, const char* data);
void Upload_Data(ESP8266_Device* dev, float rb, float rf, float lb, float lf);


void ESP8266_OnDataReceived(ESP8266_Device* dev, uint8_t link_id, uint8_t* data, uint16_t len);

/* 中断处理 (需要在 stm32f1xx_it.c 中调用) */
void ESP8266_Receive_IT_Start(ESP8266_Device* dev);
void ESP8266_UART_IDLE_Handler(ESP8266_Device* dev);
// 新增：Rx回调处理数据搬运
void ESP8266_RxCpltCallback(ESP8266_Device* dev);

/* MQTT 相关接口函数 */
uint8_t ESP8266_ConnectAP(ESP8266_Device *dev, const char *ssid, const char *pwd);
uint8_t ESP8266_ConnectMQTT(ESP8266_Device *dev, const char *broker, uint16_t port, const char *client_id, const char *username, const char *password, uint8_t scheme);
uint8_t ESP8266_Subscribe(ESP8266_Device *dev, const char *topic, uint8_t qos);
uint8_t ESP8266_MQTTPublish(ESP8266_Device *dev, const char *topic, const char *payload, uint8_t qos);
void ESP8266_MQTT_HandleReceivedLine(ESP8266_Device *dev, char *line);

#endif
