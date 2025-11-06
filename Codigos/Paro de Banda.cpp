// --- Pines ---
const int PIN_SENSOR_1 = 2;
const int PIN_SENSOR_2 = 3;
const int PIN_SENSOR_3 = 4;

const int PIN_RELE_1 = 8;
const int PIN_RELE_2 = 9;
const int PIN_RELE_3 = 10;

// --- Configuración del comportamiento ---
const bool SENSOR_ACTIVO_ALTO = false;  // false = sensor detecta con LOW, true = con HIGH
const bool RELE_ACTIVO_ALTO   = true;   // true = relé se activa con HIGH, false = con LOW

// --- Tiempos ---
const unsigned long TIEMPO_ACTIVO = 2000; // ms que el relé permanece ABIERTO
const unsigned long DEBOUNCE_MS = 40;

// --- Estructura para cada sensor + relé ---
struct SensorRele {
  int pinSensor;
  int pinRele;
  bool estadoEstable;
  bool ultimaLectura;
  bool releAbierto;
  bool yaActivado;
  unsigned long cambio;
  unsigned long tiempoActivacion;
};

// --- Creamos 3 conjuntos sensor+rele ---
SensorRele conjunto[3] = {
  {PIN_SENSOR_1, PIN_RELE_1, false, false, false, false, 0, 0},
  {PIN_SENSOR_2, PIN_RELE_2, false, false, false, false, 0, 0},
  {PIN_SENSOR_3, PIN_RELE_3, false, false, false, false, 0, 0}
};

void setup() {
  Serial.begin(9600);

  for (int i = 0; i < 3; i++) {
    pinMode(conjunto[i].pinSensor, INPUT);
    pinMode(conjunto[i].pinRele, OUTPUT);
    activarRele(conjunto[i].pinRele, true); // relé cerrado inicialmente
  }

  Serial.println("Sistema iniciado: relés se ABREN al detectar y CIERRAN después del tiempo.");
}

void loop() {
  unsigned long ahora = millis();

  for (int i = 0; i < 3; i++) {
    bool lectura = digitalRead(conjunto[i].pinSensor);

    // --- Debounce ---
    if (lectura != conjunto[i].ultimaLectura) {
      conjunto[i].cambio = ahora;
      conjunto[i].ultimaLectura = lectura;
    }
    if (ahora - conjunto[i].cambio >= DEBOUNCE_MS) {
      conjunto[i].estadoEstable = lectura;
    }

    bool detectando = (conjunto[i].estadoEstable == SENSOR_ACTIVO_ALTO);

    // --- Si detecta algo, abrir (desactivar) el relé ---
    if (detectando && !conjunto[i].yaActivado) {
      activarRele(conjunto[i].pinRele, false);  // relé se abre
      conjunto[i].releAbierto = true;
      conjunto[i].yaActivado = true;
      conjunto[i].tiempoActivacion = ahora;

      Serial.print("Sensor ");
      Serial.print(i + 1);
      Serial.println(" → DETECTADO → Relé ABIERTO");
    }

    // --- Pasado el tiempo, cerrar (activar) el relé ---
    if (conjunto[i].releAbierto && (ahora - conjunto[i].tiempoActivacion >= TIEMPO_ACTIVO)) {
      activarRele(conjunto[i].pinRele, true); // relé se cierra
      conjunto[i].releAbierto = false;

      Serial.print("Sensor ");
      Serial.print(i + 1);
      Serial.println(" → TIEMPO cumplido → Relé CERRADO");
    }

    // --- Permitir nueva activación si ya no detecta ---
    if (!detectando) {
      conjunto[i].yaActivado = false;
    }
  }

  delay(5);
}

// --- Función para activar o desactivar relé ---
void activarRele(int pin, bool activar) {
  digitalWrite(pin, activar ? (RELE_ACTIVO_ALTO ? HIGH : LOW)
                            : (RELE_ACTIVO_ALTO ? LOW : HIGH));
}