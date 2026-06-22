# ESP32-S3-CAM Pinout

## Legend

| Color        | Label   | Description                        |
| ------------ | ------- | ---------------------------------- |
| Red          | PWD     | Power                              |
| Teal         | SD      | On-board SD Card Pin               |
| Black        | GND     | Ground                             |
| Blue         | LED     | On-board LED Pin                   |
| Light Blue   | Serial  | Serial for Debugging/Programming   |
| Pink         | WS2812  | On-board WS2812 Pin                |
| Green        | ADCX_CH | Analog-to-Digital Converter        |
| Purple       | PSRAM   | Built-in expansion memory chip pin |
| Yellow       | RESET   | Reset the chip                     |
| Yellow-Green | USB     | USB Function Pin                   |
| Orange       | GPIOX   | GPIO Input and Output              |
| Teal         | CAMERA  | Camera Pin                         |
| Purple       | TOUCHX  | Touch Sensor Input Channel         |
| Green        | JTAG    | Jtag for Debugging                 |
| Orange       | STRAP   | Strapping Pin Functions            |
| ~            |         | PWM Capable Pin                    |

## Pin Table

| GPIO   | Alt Function 1 | Alt Function 2 | Alt Function 3 | Side  | Notes                         |
| ------ | -------------- | -------------- | -------------- | ----- | ----------------------------- |
| 3V3    |                |                |                | Left  | Power 3.3V                    |
| RST    |                |                |                | Left  | Reset                         |
| GPIO4  | CAM_SIOD       | ADC1_CH3       | T4             | Left  | Camera, ADC, Touch, PWM       |
| GPIO5  | CAM_SIOC       | ADC1_CH4       | T5             | Left  | Camera, ADC, Touch, PWM       |
| GPIO6  | CAM_VYSNC      | ADC1_CH5       | T6             | Left  | Camera, ADC, Touch, PWM       |
| GPIO7  | CAM_HREF       | ADC1_CH6       | T7             | Left  | Camera, ADC, Touch, PWM       |
| GPIO15 | CAM_XCLK       | ADC2_CH4       | U0RTS          | Left  | Camera, ADC, PWM              |
| GPIO16 | CAM_Y9         | ADC2_CH5       | U0CTS          | Left  | Camera, ADC, PWM              |
| GPIO17 | CAM_Y8         | ADC2_CH6       | U1TXD          | Left  | Camera, ADC, PWM              |
| GPIO18 | CAM_Y7         | ADC2_CH7       | U1RXD          | Left  | Camera, ADC, PWM              |
| GPIO8  | CAM_Y4         | ADC1_CH7       | T8             | Left  | Camera, ADC, Touch, PWM       |
| GPIO3  | JTAG_EN        | ADC1_CH2       | T3             | Left  | JTAG, ADC, Touch, PWM         |
| GPIO46 | LOG            |                |                | Left  | Strapping pin, PWM            |
| GPIO9  | CAM_Y3         | ADC1_CH8       | T9             | Left  | Camera, ADC, Touch, PWM       |
| GPIO10 | CAM_Y5         | ADC1_CH9       | T10            | Left  | Camera, ADC, Touch, PWM       |
| GPIO11 | CAM_Y2         | ADC2_CH0       | T11            | Left  | Camera, ADC, Touch, PWM       |
| GPIO12 | CAM_Y6         | ADC2_CH1       | T12            | Left  | Camera, ADC, Touch, PWM       |
| GPIO13 | CAM_PCLK       | ADC2_CH2       | T13            | Left  | Camera, ADC, Touch, PWM       |
| **GPIO14** | **FREE**   | **ADC2_CH3**   | **T14**        | Left  | **FREE — ADC, Touch, PWM**    |
| 5V     |                |                |                | Left  | Power 5V                      |
| GPIO43 | U0TXD          | LED TX         |                | Right | Serial TX, on-board LED TX    |
| GPIO44 | U0RXD          | LED RX         |                | Right | Serial RX, on-board LED RX    |
| GPIO1  | ADC1_CH0       | T1             |                | Right | ADC, Touch, PWM               |
| GPIO2  | ADC1_CH1       | LED ON         | T2             | Right | ADC, Touch, on-board LED, PWM |
| GPIO42 | MTMS           |                |                | Right | JTAG                          |
| GPIO41 | MTDI           |                |                | Right | JTAG                          |
| GPIO40 | SD_DATA        | MTDO           |                | Right | SD Card, JTAG                 |
| GPIO39 | SD_CLK         | MTCK           |                | Right | SD Card, JTAG                 |
| GPIO38 | SD_CMD         |                |                | Right | SD Card                       |
| GPIO37 | PSRAM          |                |                | Right | PSRAM                         |
| GPIO36 | PSRAM          |                |                | Right | PSRAM                         |
| GPIO35 | PSRAM          |                |                | Right | PSRAM                         |
| GPIO00 | Boot           |                |                | Right | Strapping pin (Boot)          |
| GPIO45 | VSPI           |                |                | Right | Strapping pin                 |
| GPIO48 | WS2812         |                |                | Right | On-board WS2812 LED           |
| GPIO47 |                |                |                | Right | PWM                           |
| GPIO21 |                |                |                | Right | PWM                           |
| GPIO20 | USB_D-         | ADC2_CH9       | UICTS          | Right | USB, ADC                      |
| GPIO19 | USB_D+         | ADC2_CH8       | UIRTS          | Right | USB, ADC                      |
| GND    |                |                |                | Right | Ground                        |
