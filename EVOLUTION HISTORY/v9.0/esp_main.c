/*
 * ============================================================================
 * main.c — WRO 2026 4WS (Four-Wheel Steering) ESP32-S3 Firmware
 *
 * Purpose:
 *   Main firmware entry point for ESP32-S3 controller.
 *
 *   Raspberry Pi sends UART packets containing:
 *      - Steering angle
 *      - Motor speed
 *      - System commands
 *
 *   ESP32 processes commands and controls:
 *      - Servo steering
 *      - L298N motor driver
 *      - Safety systems
 *
 * Protocol:
 *   [HEADER][COUNTER][TYPE][LENGTH][PAYLOAD][CRC16][FOOTER]
 *
 * ============================================================================
 */


#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <stdlib.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "esp_log.h"
#include "esp_timer.h"

#include "driver/uart.h"
#include "driver/gpio.h"

#include "esp_task_wdt.h"


/* Project modules */

#include "uart_receiver.h"
#include "packet_validator.h"
#include "crc.h"
#include "command_validator.h"

#include "timeout_detector.h"
#include "watchdog.h"
#include "failsafe.h"

#include "servo_pwm.h"
#include "l298n.h"

#include "selftest.h"



/* ============================================================================
 * Constants
 * ==========================================================================*/


static const char *TAG = "WRO_4WS";



/*
 * UART protocol markers.
 * These values must match Raspberry Pi implementation.
 */

#define PACKET_HEADER       0xA5
#define PACKET_FOOTER       0x5A



/*
 * Status LEDs
 */

#define LED_GREEN_GPIO      2
#define LED_RED_GPIO        4



/*
 * UART configuration
 */

#define UART_PORT_NUM       UART_NUM_1
#define UART_BAUD_RATE      115200

#define UART_BUF_SIZE       256

#define UART_TX_GPIO        17
#define UART_RX_GPIO        18



/*
 * Communication timeout.
 *
 * If Raspberry Pi does not send commands
 * within this period, motors are stopped.
 */

#define COMM_TIMEOUT_US     500000



/* ============================================================================
 * Packet Types
 * ==========================================================================*/


typedef enum
{
    PKT_MOTOR_COMMAND      = 0x01,
    PKT_SERVO_COMMAND      = 0x02,
    PKT_STEERING_CMD       = 0x03,

    PKT_STATUS_REQ         = 0x04,
    PKT_STATUS_RESP        = 0x05,

    PKT_SELFTEST_REQ       = 0x06,
    PKT_SELFTEST_RESP      = 0x07,

    PKT_EMERGENCY_STOP     = 0xFF

} packet_type_t;



/* ============================================================================
 * UART Packet Structure
 * ==========================================================================*/


typedef struct __attribute__((packed))
{
    uint8_t header;

    uint8_t counter;

    uint8_t msg_type;

    uint8_t length;


    uint8_t payload[24];


    uint16_t crc;

    uint8_t footer;


} uart_packet_t;



/* ============================================================================
 * ESP32 State Machine
 * ==========================================================================*/


typedef enum
{
    ESP_STATE_BOOT,

    ESP_STATE_SELFTEST,

    ESP_STATE_READY,

    ESP_STATE_ACTIVE,

    ESP_STATE_ERROR,

    ESP_STATE_FAILSAFE


} esp_state_t;



/* ============================================================================
 * Application State
 * ==========================================================================*/


typedef struct
{

    float servo_angle;


    uint8_t motor_speed;


    uint8_t packet_counter;


    uint64_t last_packet_us;



    bool emergency_stop;


    bool motor_enabled;



    uint32_t packets_received;


    uint32_t packets_sent;


    uint32_t crc_errors;



    esp_state_t state;



    esp_selftest_result_t selftest_result;



} app_state_t;



static app_state_t g_state = {0};



/* ============================================================================
 * LED Control
 * ==========================================================================*/


static void led_init(void)
{

    gpio_config_t config =
    {

        .pin_bit_mask =
            (1ULL << LED_GREEN_GPIO) |
            (1ULL << LED_RED_GPIO),


        .mode = GPIO_MODE_OUTPUT,


        .pull_up_en = GPIO_PULLUP_DISABLE,


        .pull_down_en = GPIO_PULLDOWN_DISABLE,


        .intr_type = GPIO_INTR_DISABLE

    };


    gpio_config(&config);


    gpio_set_level(LED_GREEN_GPIO,0);

    gpio_set_level(LED_RED_GPIO,0);

}



static void led_green_on(void)
{

    gpio_set_level(LED_GREEN_GPIO,1);

    gpio_set_level(LED_RED_GPIO,0);

}



static void led_red_on(void)
{

    gpio_set_level(LED_GREEN_GPIO,0);

    gpio_set_level(LED_RED_GPIO,1);

}



static void led_both_on(void)
{

    gpio_set_level(LED_GREEN_GPIO,1);

    gpio_set_level(LED_RED_GPIO,1);

}



static void led_off(void)
{

    gpio_set_level(LED_GREEN_GPIO,0);

    gpio_set_level(LED_RED_GPIO,0);

}



/* ============================================================================
 * UART Initialization
 * ==========================================================================*/


static void uart_init(void)
{

    uart_config_t config =
    {

        .baud_rate = UART_BAUD_RATE,


        .data_bits = UART_DATA_8_BITS,


        .parity = UART_PARITY_DISABLE,


        .stop_bits = UART_STOP_BITS_1,


        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE

    };



    ESP_ERROR_CHECK(
        uart_param_config(
            UART_PORT_NUM,
            &config
        )
    );



    ESP_ERROR_CHECK(
        uart_set_pin(
            UART_PORT_NUM,
            UART_TX_GPIO,
            UART_RX_GPIO,
            UART_PIN_NO_CHANGE,
            UART_PIN_NO_CHANGE
        )
    );



    ESP_ERROR_CHECK(
        uart_driver_install(
            UART_PORT_NUM,
            UART_BUF_SIZE,
            UART_BUF_SIZE,
            0,
            NULL,
            0
        )
    );



    ESP_LOGI(
        TAG,
        "UART initialized at %d baud",
        UART_BAUD_RATE
    );

}



/* ============================================================================
 * Send UART Packet
 * ==========================================================================*/


static void send_packet
(
    uint8_t type,
    const uint8_t *payload,
    uint8_t length
)

{

    uint8_t buffer[32];


    int index = 0;



    buffer[index++] = PACKET_HEADER;


    buffer[index++] = g_state.packet_counter++;


    buffer[index++] = type;


    buffer[index++] = length;



    if(payload != NULL && length > 0)
    {

        memcpy(
            &buffer[index],
            payload,
            length
        );


        index += length;

    }



    uint16_t crc =
        crc16(
            buffer,
            index
        );



    buffer[index++] = crc & 0xFF;


    buffer[index++] = (crc >> 8) & 0xFF;



    buffer[index++] = PACKET_FOOTER;



    uart_write_bytes(
        UART_PORT_NUM,
        (char *)buffer,
        index
    );



    g_state.packets_sent++;

}
/* ============================================================================
 * Packet Processing
 * ==========================================================================*/


static void send_status_response(void)
{

    uint8_t payload[6];


    payload[0] =
        g_state.selftest_result.uart_ok ? 1 : 0;


    payload[1] =
        g_state.state;


    payload[2] = 
        (uint8_t)(g_state.packets_received & 0xFF);


    payload[3] =
        (uint8_t)((g_state.packets_received >> 8) & 0xFF);


    payload[4] =
        (uint8_t)(g_state.crc_errors & 0xFF);


    payload[5] =
        g_state.motor_enabled ? 1 : 0;



    send_packet(
        PKT_STATUS_RESP,
        payload,
        sizeof(payload)
    );

}



static void send_selftest_response(void)
{

    uint8_t payload[8];


    payload[0] =
        g_state.selftest_result.uart_ok ? 1 : 0;


    payload[1] =
        g_state.selftest_result.servo_pwm_ok ? 1 : 0;


    payload[2] =
        g_state.selftest_result.motor_pwm_ok ? 1 : 0;


    payload[3] =
        g_state.selftest_result.l298n_ok ? 1 : 0;


    payload[4] =
        g_state.selftest_result.watchdog_ok ? 1 : 0;


    payload[5] =
        (uint8_t)
        (g_state.selftest_result.test_duration_ms & 0xFF);


    payload[6] =
        (uint8_t)
        ((g_state.selftest_result.test_duration_ms >> 8) & 0xFF);


    payload[7] =
        esp_selftest_all_passed(
            &g_state.selftest_result
        ) ? 1 : 0;



    send_packet(
        PKT_SELFTEST_RESP,
        payload,
        sizeof(payload)
    );

}




static void process_packet(uart_packet_t *pkt)
{

    if(pkt == NULL)
        return;



    /*
     * Emergency stop has highest priority.
     */

    if(pkt->msg_type == PKT_EMERGENCY_STOP)
    {

        g_state.emergency_stop = true;

        g_state.state = ESP_STATE_FAILSAFE;


        l298n_set_motor(
            0,
            true
        );


        servo_set_angle(0);


        led_red_on();


        ESP_LOGW(
            TAG,
            "EMERGENCY STOP RECEIVED"
        );


        return;

    }



    /*
     * Ignore all commands after emergency stop.
     */

    if(g_state.emergency_stop)
        return;




    switch(pkt->msg_type)
    {


        case PKT_STEERING_CMD:
        {


            if(pkt->length < 5)
            {

                ESP_LOGW(
                    TAG,
                    "Invalid steering packet length"
                );


                break;

            }



            float angle;


            memcpy(
                &angle,
                pkt->payload,
                sizeof(float)
            );



            uint8_t speed =
                pkt->payload[4];



            g_state.servo_angle = angle;


            g_state.motor_speed = speed;



            servo_set_angle(angle);



            l298n_set_motor(
                speed,
                true
            );



            g_state.motor_enabled = true;


            g_state.state = ESP_STATE_ACTIVE;


            break;

        }



        case PKT_STATUS_REQ:

            send_status_response();

            break;



        case PKT_SELFTEST_REQ:

            send_selftest_response();

            break;



        default:

            ESP_LOGW(
                TAG,
                "Unknown packet type: %d",
                pkt->msg_type
            );

            break;

    }

}



/* ============================================================================
 * UART Receiver Task
 * ==========================================================================*/


static void uart_rx_task(void *arg)
{

    uint8_t *rx_buf =
        malloc(UART_BUF_SIZE);



    if(rx_buf == NULL)
    {

        ESP_LOGE(
            TAG,
            "UART RX memory allocation failed"
        );


        vTaskDelete(NULL);

        return;

    }



    uint8_t packet_buffer[32];


    int packet_index = 0;


    bool receiving = false;



    while(1)
    {


        int length =
            uart_read_bytes(
                UART_PORT_NUM,
                rx_buf,
                UART_BUF_SIZE,
                pdMS_TO_TICKS(10)
            );



        for(int i = 0; i < length; i++)
        {


            uint8_t byte =
                rx_buf[i];



            if(!receiving)
            {

                if(byte == PACKET_HEADER)
                {

                    receiving = true;

                    packet_index = 0;

                    packet_buffer[packet_index++] = byte;

                }

            }


            else
            {


                if(packet_index >= sizeof(packet_buffer))
                {

                    ESP_LOGW(
                        TAG,
                        "UART packet overflow"
                    );


                    receiving = false;

                    packet_index = 0;

                    continue;

                }



                packet_buffer[packet_index++] = byte;



                if(byte == PACKET_FOOTER)
                {


                    if(packet_index >= sizeof(uart_packet_t))
                    {

                        uart_packet_t packet;



                        memcpy(
                            &packet,
                            packet_buffer,
                            sizeof(packet)
                        );



                        uint16_t calculated_crc =
                            crc16(
                                packet_buffer,
                                packet_index - 3
                            );



                        if(calculated_crc == packet.crc)
                        {

                            g_state.last_packet_us =
                                esp_timer_get_time();



                            process_packet(
                                &packet
                            );



                            g_state.packets_received++;

                        }


                        else
                        {

                            g_state.crc_errors++;


                            ESP_LOGW(
                                TAG,
                                "CRC mismatch"
                            );

                        }

                    }



                    receiving = false;

                    packet_index = 0;

                }

            }

        }


        vTaskDelay(
            pdMS_TO_TICKS(1)
        );

    }

}




/* ============================================================================
 * Communication Timeout Monitor
 * ==========================================================================*/


static void timeout_monitor_task(void *arg)
{

    while(1)
    {

        uint64_t now =
            esp_timer_get_time();



        if(
            g_state.last_packet_us > 0 &&
            now - g_state.last_packet_us > COMM_TIMEOUT_US &&
            g_state.motor_enabled
        )
        {

            ESP_LOGW(
                TAG,
                "Communication timeout - stopping motors"
            );


            l298n_set_motor(
                0,
                true
            );


            servo_set_angle(0);



            g_state.motor_enabled = false;


            g_state.state =
                ESP_STATE_FAILSAFE;



            led_red_on();

        }



        vTaskDelay(
            pdMS_TO_TICKS(50)
        );

    }

}




/* ============================================================================
 * Watchdog Task
 * ==========================================================================*/


static void watchdog_task(void *arg)
{

    esp_task_wdt_add(NULL);



    while(1)
    {

        watchdog_feed();



        vTaskDelay(
            pdMS_TO_TICKS(500)
        );

    }

}



/* ============================================================================
 * LED Status Task
 * ==========================================================================*/


static void led_indicator_task(void *arg)
{

    while(1)
    {

        switch(g_state.state)
        {

            case ESP_STATE_BOOT:
                led_both_on();
                break;


            case ESP_STATE_READY:
            case ESP_STATE_ACTIVE:
                led_green_on();
                break;


            case ESP_STATE_ERROR:
            case ESP_STATE_FAILSAFE:
                led_red_on();
                break;


            default:
                led_off();
                break;

        }



        vTaskDelay(
            pdMS_TO_TICKS(100)
        );

    }

}



/* ============================================================================
 * Main Application Entry
 * ==========================================================================*/


void app_main(void)
{

    ESP_LOGI(
        TAG,
        "WRO 4WS Firmware v9.0 starting"
    );



    led_init();


    led_both_on();



    esp_selftest_init();



    esp_selftest_run(
        &g_state.selftest_result
    );



    if(
        esp_selftest_all_passed(
            &g_state.selftest_result
        )
    )
    {

        g_state.state = ESP_STATE_READY;

    }

    else
    {

        g_state.state = ESP_STATE_ERROR;

    }



    uart_init();


    l298n_init();


    servo_pwm_init();


    failsafe_init();


    watchdog_init();



    xTaskCreate(
        uart_rx_task,
        "uart_rx",
        4096,
        NULL,
        10,
        NULL
    );



    xTaskCreate(
        timeout_monitor_task,
        "timeout_monitor",
        2048,
        NULL,
        8,
        NULL
    );



    xTaskCreate(
        watchdog_task,
        "watchdog",
        2048,
        NULL,
        9,
        NULL
    );



    xTaskCreate(
        led_indicator_task,
        "led_indicator",
        1024,
        NULL,
        5,
        NULL
    );



    ESP_LOGI(
        TAG,
        "ESP32 system ready"
    );

}