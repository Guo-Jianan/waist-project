#include "driver_frame.h"
#include <string.h> 

// ==========================================
// �ⲿ��������
// ==========================================
extern QueueSetHandle_t g_control_set;

// ==========================================
// �ڲ�״̬������ر�������
// ==========================================
typedef enum {
    STATE_HEAD = 0,
    STATE_FUNC,
    STATE_LEN,
    STATE_DATA,
    STATE_CHECK,
    STATE_TAIL
} RxState_t;

// ���ջ�����
static uint8_t frame_buf[FRAME_TOTAL_LEN];
static uint16_t frame_len;

// ��Ϣ���о��
static QueueHandle_t g_xQueueFrame;
// Frame�����������
static TaskHandle_t xFrameTaskHandle = NULL;
// �������ź���
static SemaphoreHandle_t frame_sem;


// ==========================================
// �ڲ�������У�����
// ==========================================

/**
 * @brief ����У���
 * ����: ~(Header + Func + Data)
 * ע�⣺���չ���Len λ�ǲ���������
 */
static uint8_t Calculate_Checksum(Frame_Packet_u *pkt) {
    uint8_t sum = 0;
    
    // 1. �� Header [0] �� Func [1]
    sum += pkt->buffer[0];
    sum += pkt->buffer[1];
    
    // 2. �� Data [3] ~ [14] (���� Len [2])
    // ������ƫ������ 3�������� DATA_LEN (16 bytes for 4 floats)
    for (int i = 0; i < DATA_LEN; i++) {
        sum += pkt->buffer[3 + i];
    }
    
    return (uint8_t)(~sum);
}


// ==========================================
// �ⲿ�ӿ�ʵ��
// ==========================================

/**
 * @brief ����Frame��Ϣ���о��
 */
QueueHandle_t get_FrameQueueHandle(void)
{
    return g_xQueueFrame;
}

/**
 * @brief �ж��л�ȡ���ݲ���������
 */
void Frame_GetArgsFromISR(uint8_t *buf, uint16_t len)
{
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    
    if (len == 0) return;
    if (len > FRAME_TOTAL_LEN) len = FRAME_TOTAL_LEN;
    
    memcpy(frame_buf, buf, len);
    frame_len = len;
    
    // �����ź������Ѵ�������
    xSemaphoreGiveFromISR(frame_sem, &xHigherPriorityTaskWoken);
    
    // �����Ҫ�л�������
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

/**
 * @brief [����] ������ֱ�ӽ��� 
 * @return true: �����ɹ�
 */
bool Driver_Frame_ParseBuffer()
{
    if (frame_len != FRAME_TOTAL_LEN) {
        return false;
    }

    Frame_Packet_u *pkt = (Frame_Packet_u *)frame_buf;

    // 1. ��֤֡ͷ��֡β�������롢����
    if (pkt->frame.head != FRAME_HEAD ||
        pkt->frame.tail != FRAME_TAIL ||
        pkt->frame.func != FUNC_CTRL ||
        pkt->frame.len  != DATA_LEN) 
    {
        return false;
    }

    // 2. ��֤У���
    if (pkt->frame.check != Calculate_Checksum(pkt)) {
        return false;
    }

    // 3. ��ȡ���ݲ����͵����� (���� ActuatorTarget �� driver_actuator.h ���Ѷ���)
    ActuatorTarget target;
    target.RbTarget = pkt->frame.rb;
    target.RfTarget = pkt->frame.rf;
    target.LbTarget = pkt->frame.lb;
    target.LfTarget = pkt->frame.lf;

    // ע�⣺�������� Task �����У�����ʹ�� xQueueSend ������ FromISR �汾
    xQueueSend(g_xQueueFrame, &target, (TickType_t)0);

    return true;
}

/**
 * @brief Frame ���񣬸���ȴ��ź�������������
 */
static void vFrameExecTask(void *pvParameters)
{
#ifdef STACK_PRINT
    UBaseType_t uxHighWaterMark = uxTaskGetStackHighWaterMark(NULL); 
#endif
    
    frame_sem = xSemaphoreCreateBinary();
    
    for (;;)
    {
        /* �ȴ��ж��ͷŵ��ź��� */
        if (xSemaphoreTake(frame_sem, portMAX_DELAY) == pdTRUE) {
            
            if (Driver_Frame_ParseBuffer()) {
                DEBUG_INFO("Frame Parse Ok\n");
            } else {
                DEBUG_INFO("Frame Parse Error\n");
            }

#ifdef STACK_PRINT
            uint32_t ulStackRemaining = uxHighWaterMark * 4;
            DEBUG_INFO("Frame task: %d bytes short of overflow.\r\n", ulStackRemaining);
#endif
        }
    }
}

/**
 * @brief ��ʼ�� Frame ��������Ͷ���
 */
BaseType_t xFrameInit(UBaseType_t uxPriority)
{
    if (uxPriority > configMAX_PRIORITIES - 1)
    {
        return pdFAIL;
    }
    
    BaseType_t xReturn = pdPASS;
    
    // ���� Frame ���ݶ��У���������м�
    g_xQueueFrame = xQueueCreate(FRAME_QUE_SIZE, sizeof(ActuatorTarget));
    if (g_xQueueFrame == NULL)
    {
        return pdFAIL;
    }
    xQueueAddToSet(g_xQueueFrame, g_control_set);

    // ������������
    BaseType_t xTaskRetVal = xTaskCreate(vFrameExecTask,
                                         "FrameTask",
                                         configMINIMAL_STACK_SIZE * 10,
                                         NULL,
                                         uxPriority,
                                         &xFrameTaskHandle);
    if (xTaskRetVal != pdPASS)
    {
        DEBUG_INFO("Error creating frame task\n");
        xReturn = pdFAIL;
    }
    
    if (xReturn == pdFAIL)
    {
        vQueueDelete(g_xQueueFrame);
        g_xQueueFrame = NULL;
    }

    return xReturn;
}


/**
 * @brief ׼���������� (���)
 * @param pkt ֡���ݰ�ָ��
 */
void Driver_Frame_Pack(Frame_Packet_u *pkt, uint16_t heart, float rb, float rf, float lb, float lf) {
    // 1. ���̶�ͷ��
    pkt->frame.head = FRAME_HEAD;
    pkt->frame.func = FUNC_CTRL;
    pkt->frame.len  = DATA_LEN;
    
    // 2. �����Ч����
    pkt->frame.rb = rb;
    pkt->frame.rf = rf;
    pkt->frame.lb = lb;
    pkt->frame.lf = lf;
    
    // ע�⣺Ŀǰ�� Frame_Struct_t �ṹ����û�ж��� heart �ֶΡ�
    // ���Э����Ҫ�����������ݣ���Ҫ��ͷ�ļ��е� Frame_Struct_t ���Ӹ��ֶΣ������¼��� DATA_LEN��
        
    // 3. ����У������β��
    pkt->frame.check = Calculate_Checksum(pkt);
    pkt->frame.tail  = FRAME_TAIL;
}