#include <Wire.h>
#include <INA226.h>
#include <LiquidCrystal_I2C.h>
#include <BH1750.h>
#include <math.h>

INA226 inaWind(0x40);
LiquidCrystal_I2C lcd(0x27, 20, 4);
BH1750 luxSensor;

float solarV_V = 0.0f, solarI_mA = 0.0f, solarP_mW = 0.0f;

float windV_V = 0.0f, windI_A = 0.0f, windP_mW = 0.0f;

float fanV_V = 0.0f;
float fanSpeed_pct = 0.0f;

float luxValue = 0.0f;

unsigned long lastUpdate = 0;
const unsigned long PERIOD_MS = 1000;

static void printFixed(LiquidCrystal_I2C &d, float v, uint8_t dec, uint8_t width) {
  char buf[16];
  dtostrf(v, width, dec, buf);
  d.print(buf);
}

static void clearToEndOfLine(LiquidCrystal_I2C &d, uint8_t row, uint8_t col) {
  d.setCursor(col, row);
  for (uint8_t i = col; i < 20; i++) d.print(' ');
}

const int PIN_SOLAR_VOLT = A0;
const int PIN_SOLAR_CURR = A1;

const float VREF = 5.00f;
const float VOLT_DIV_RATIO = 5.0f;

const float ACS_SENS_V_PER_A = 0.066f;
float acsZeroV = 2.5f;
const int N_SAMPLES = 200;

const uint8_t PIN_FAN_PWM = 5;
const float   FAN_VMAX_V  = 12.0f;
const uint8_t FAN_PWM_MIN = 0;

static float readAnalogVoltage(int pin, int samples) {
  long sum = 0;
  for (int i = 0; i < samples; i++) sum += analogRead(pin);
  float adc = (float)sum / (float)samples;
  return (adc * VREF) / 1023.0f;
}

static void calibrateACS712Zero() {
  acsZeroV = readAnalogVoltage(PIN_SOLAR_CURR, 1000);
}

void setup() {
  Serial.begin(115200);
  Wire.begin();

  pinMode(PIN_FAN_PWM, OUTPUT);
  analogWrite(PIN_FAN_PWM, 0);

  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Hybrid Monitor");
  lcd.setCursor(0, 1);
  lcd.print("System");
  delay(1500);
  lcd.clear();

  if (!inaWind.begin()) {
    lcd.setCursor(0, 0);
    lcd.print("INA226 ERROR");
    Serial.println("INA226 not found at 0x40");
    while (1) {}
  }

  inaWind.setMaxCurrentShunt(1.0, 0.002);
  inaWind.setAverage(INA226_1024_SAMPLES);

  if (!luxSensor.begin(BH1750::CONTINUOUS_HIGH_RES_MODE)) {
    lcd.setCursor(0, 0);
    lcd.print("BH1750 ERROR");
    Serial.println("BH1750 not found");
  }

  delay(500);
  calibrateACS712Zero();

}

void loop() {
  if (millis() - lastUpdate < PERIOD_MS) return;
  lastUpdate = millis();

  solarV_V = readAnalogVoltage(PIN_SOLAR_VOLT, N_SAMPLES) * VOLT_DIV_RATIO;

  float solarI_A = (readAnalogVoltage(PIN_SOLAR_CURR, N_SAMPLES) - acsZeroV) / ACS_SENS_V_PER_A;
  if (solarI_A < 0.0f) solarI_A = 0.0f;
  solarI_mA = solarI_A * 1000.0f;

  solarP_mW = (solarV_V * solarI_A) * 1000.0f;

  windV_V = inaWind.getBusVoltage();

  windI_A = inaWind.getCurrent();
  if (windI_A < 0.0f) windI_A = 0.0f;

  windP_mW = inaWind.getPower() * 1000.0f;

  float luxRaw = luxSensor.readLightLevel();
  if (luxRaw >= 0.0f) luxValue = luxRaw;

  fanV_V = windV_V;

  if (fanV_V < 0.0f) fanV_V = 0.0f;
  if (fanV_V > FAN_VMAX_V) fanV_V = FAN_VMAX_V;

  fanSpeed_pct = (fanV_V / FAN_VMAX_V) * 100.0f;

  uint8_t duty = (uint8_t)lroundf((fanSpeed_pct / 100.0f) * 255.0f);
  if (duty > 0 && duty < FAN_PWM_MIN) duty = FAN_PWM_MIN;

  analogWrite(PIN_FAN_PWM, duty);

Serial.print("SOL V:");
Serial.print(solarV_V, 2);
Serial.print(" I:");
Serial.println(solarI_mA, 0);

Serial.print("WND V:");
Serial.print(windV_V, 2);
Serial.print(" I:");
Serial.println(windI_A, 3);

Serial.print("SP:");
Serial.print(solarP_mW / 1000.0f, 2);
Serial.print(" WP:");
Serial.println(windP_mW / 1000.0f, 2);

Serial.print("LUX:");
Serial.print(luxValue, 0);
Serial.print(" FAN:");
Serial.print(fanSpeed_pct, 0);
Serial.println("%");
Serial.println("--------------------------");

 // -------- Row 0: Solar Voltage & Current --------
clearToEndOfLine(lcd, 0, 0);
lcd.setCursor(0, 0);
lcd.print("SOL V:");
printFixed(lcd, solarV_V, 2, 5);
lcd.print(" I:");
printFixed(lcd, solarI_mA, 0, 5);

// -------- Row 1: Wind Voltage & Current --------
clearToEndOfLine(lcd, 1, 0);
lcd.setCursor(0, 1);
lcd.print("WND V:");
printFixed(lcd, windV_V, 2, 5);
lcd.print(" I:");
printFixed(lcd, windI_A, 3, 5);

// -------- Row 2: Solar Power & Wind Power --------
clearToEndOfLine(lcd, 2, 0);
lcd.setCursor(0, 2);
lcd.print("SP:");
printFixed(lcd, solarP_mW, 0, 6);
lcd.print(" WP:");
printFixed(lcd, windP_mW / 1000.0f, 2, 6);

// -------- Row 3: Lux (lx) & Fan Speed (%) --------
clearToEndOfLine(lcd, 3, 0);
lcd.setCursor(0, 3);
lcd.print("LUX:");
printFixed(lcd, luxValue, 0, 5);
lcd.setCursor(11, 3);
lcd.print("FAN:");
printFixed(lcd, fanSpeed_pct, 0, 3);
lcd.print("%");

}
