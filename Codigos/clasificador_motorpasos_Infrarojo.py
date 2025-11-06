import time
import numpy as np
import os
import pickle
from collections import deque
import board
import busio
import adafruit_tcs34725
import lgpio
import tensorflow as tf

# --- CONFIGURACIONES DE RUTAS ---
BASE_DIR = "/home/luis/tf_env/Laboratorio"
MODEL_PATH = os.path.join(BASE_DIR, "models", "color_classifier.tflite")
SCALER_PATH = os.path.join(BASE_DIR, "models", "scaler.pkl")
LABELS_PATH = os.path.join(BASE_DIR, "models", "labels.txt")
BACKGROUND_PATH = os.path.join(BASE_DIR, "models", "background_profile.pkl")

# --- CONFIGURACIONES DE HARDWARE ---
CHIP = 0
IR_SENSOR_PIN = 23
MOTOR_PINS = [17, 18, 27, 22]

USE_TWO_SENSORS = False

# --- CONFIGURAR GPIO ---
chip = lgpio.gpiochip_open(CHIP)
lgpio.gpio_claim_input(chip, IR_SENSOR_PIN)

if USE_TWO_SENSORS:
    IR_COLOR_PIN = 24
    IR_DROP_PIN = 23
    lgpio.gpio_claim_input(chip, IR_COLOR_PIN)
    print("?? Modo: 2 sensores IR (GPIO 24 + GPIO 23)")
else:
    IR_COLOR_PIN = IR_SENSOR_PIN
    IR_DROP_PIN = IR_SENSOR_PIN
    print("?? Modo: 1 sensor IR (GPIO 23) - Clasificación inmediata")

for pin in MOTOR_PINS:
    lgpio.gpio_claim_output(chip, pin)

# --- SECUENCIA MOTOR ---
SEQUENCE = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1],
]
STEPS_PER_QUARTER = 128

# --- POSICIONES ---
COLOR_POSITIONS = {
    "R": 0,
    "G": 1,
    "B": 2,
    "basura": 3,
    "f": 3
}
current_position = 0

# --- FUNCIONES MOTOR ---
def move_motor_steps(steps, delay=0.001, direction=1):
    seq = SEQUENCE if direction > 0 else list(reversed(SEQUENCE))
    for _ in range(steps):
        for pattern in seq:
            for pin, val in zip(MOTOR_PINS, pattern):
                lgpio.gpio_write(chip, pin, val)
            time.sleep(delay)
    for pin in MOTOR_PINS:
        lgpio.gpio_write(chip, pin, 0)

def rotate_to_color(color):
    global current_position
    target = COLOR_POSITIONS.get(color, 3)
    diff = (target - current_position) % 4
    
    if diff != 0:
        print(f"?? Girando {diff} posiciones: {current_position*90}° ? {target*90}°")
        move_motor_steps(diff * STEPS_PER_QUARTER, direction=1)
        current_position = target
        print(f"? Motor en posición {current_position} ({color})\n")
    else:
        print(f"?? Ya en posición {current_position} ({color})\n")

# --- SENSOR DE COLOR ---
i2c = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_tcs34725.TCS34725(i2c)
sensor.integration_time = 50
sensor.gain = 4

# --- MODELO TFLITE ---
interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# --- ESCALADOR Y ETIQUETAS ---
with open(SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)
with open(LABELS_PATH, "r") as f:
    labels = [line.strip() for line in f.readlines()]

# --- PERFIL DE FONDO ---
background_profile = None

def calibrate_background(num_samples=20):
    """Calibra el color del fondo de la banda transportadora"""
    print("\n" + "="*70)
    print("?? CALIBRACIÓN DEL FONDO DE LA BANDA")
    print("="*70)
    print("??  IMPORTANTE: Asegúrate de que la banda esté vacía (sin LEGOs)")
    print(f"?? Tomando {num_samples} muestras del fondo...")
    print()
    
    samples = []
    for i in range(num_samples):
        r, g, b, c = sensor.color_raw
        try:
            color_temp = sensor.color_temperature or 0
            lux = sensor.lux or 0
        except Exception:
            color_temp, lux = 0, 0
        
        samples.append({
            'r': r, 'g': g, 'b': b, 'c': c,
            'temp': color_temp, 'lux': lux
        })
        
        if (i + 1) % 5 == 0:
            print(f"   Muestra {i+1}/{num_samples} - R:{r} G:{g} B:{b}")
        
        time.sleep(0.1)
    
    # Calcular estadísticas del fondo
    r_vals = [s['r'] for s in samples]
    g_vals = [s['g'] for s in samples]
    b_vals = [s['b'] for s in samples]
    c_vals = [s['c'] for s in samples]
    
    profile = {
        'r_mean': np.mean(r_vals),
        'g_mean': np.mean(g_vals),
        'b_mean': np.mean(b_vals),
        'c_mean': np.mean(c_vals),
        'r_std': np.std(r_vals),
        'g_std': np.std(g_vals),
        'b_std': np.std(b_vals),
        'c_std': np.std(c_vals),
        'threshold_multiplier': 3.0  # Umbral de detección (ajustable)
    }
    
    print()
    print("? Calibración completada:")
    print(f"   Fondo promedio - R:{profile['r_mean']:.1f} G:{profile['g_mean']:.1f} B:{profile['b_mean']:.1f}")
    print(f"   Desviación estándar - R:{profile['r_std']:.1f} G:{profile['g_std']:.1f} B:{profile['b_std']:.1f}")
    print("="*70)
    print()
    
    # Guardar perfil
    try:
        with open(BACKGROUND_PATH, 'wb') as f:
            pickle.dump(profile, f)
        print(f"?? Perfil guardado en: {BACKGROUND_PATH}\n")
    except Exception as e:
        print(f"??  No se pudo guardar el perfil: {e}\n")
    
    return profile

def load_or_calibrate_background():
    """Carga el perfil guardado o realiza nueva calibración"""
    if os.path.exists(BACKGROUND_PATH):
        print("?? Perfil de fondo encontrado, cargando...")
        try:
            with open(BACKGROUND_PATH, 'rb') as f:
                profile = pickle.load(f)
            print(f"? Perfil cargado - Fondo: R:{profile['r_mean']:.1f} G:{profile['g_mean']:.1f} B:{profile['b_mean']:.1f}\n")
            
            response = input("¿Deseas recalibrar el fondo? (s/N): ").strip().lower()
            if response == 's':
                return calibrate_background()
            return profile
        except Exception as e:
            print(f"??  Error al cargar perfil: {e}")
            print("Realizando nueva calibración...\n")
            return calibrate_background()
    else:
        print("?? No se encontró perfil de fondo previo")
        return calibrate_background()

def is_background(r, g, b, c, profile):
    """Determina si la lectura corresponde al fondo de la banda"""
    if profile is None:
        return False
    
    threshold = profile['threshold_multiplier']
    
    # Verificar si los valores están dentro del rango del fondo
    r_diff = abs(r - profile['r_mean'])
    g_diff = abs(g - profile['g_mean'])
    b_diff = abs(b - profile['b_mean'])
    c_diff = abs(c - profile['c_mean'])
    
    r_in_range = r_diff <= (profile['r_std'] * threshold)
    g_in_range = g_diff <= (profile['g_std'] * threshold)
    b_in_range = b_diff <= (profile['b_std'] * threshold)
    c_in_range = c_diff <= (profile['c_std'] * threshold)
    
    # Si todos los canales están cerca del fondo, es fondo
    return r_in_range and g_in_range and b_in_range and c_in_range

# --- FUNCIONES DE PROCESO ---
def extract_features(r, g, b, c, color_temp, lux):
    eps = 1e-6
    sum_rgb = r + g + b + eps
    r_rel, g_rel, b_rel = r/sum_rgb, g/sum_rgb, b/sum_rgb
    norm_R, norm_G, norm_B = r/(c+eps), g/(c+eps), b/(c+eps)
    return np.array([r_rel, g_rel, b_rel, norm_R, norm_G, norm_B, color_temp, lux], dtype=np.float32)

def predict_color(r, g, b, c, color_temp, lux):
    feat = extract_features(r, g, b, c, color_temp, lux)
    X = scaler.transform([feat]).astype(np.float32)
    interpreter.set_tensor(input_details[0]['index'], X)
    interpreter.invoke()
    pred = interpreter.get_tensor(output_details[0]['index'])[0]
    idx = int(np.argmax(pred))
    return labels[idx], float(pred[idx])

# --- COLA FIFO PARA COLORES ---
color_queue = deque(maxlen=10)

# --- VARIABLES DE CONTROL ---
last_ir_color_state = 1
last_ir_drop_state = 1

print("=" * 70)
if USE_TWO_SENSORS:
    print("?? SISTEMA CON 2 SENSORES IR")
    print("=" * 70)
    print("?? IR #1 (GPIO 24): Detecta pieza y lee color en 1.6m")
    print("?? IR #2 (GPIO 23): Activa motor para clasificar en 3.9m")
else:
    print("?? SISTEMA CON 1 SENSOR IR (Modo Prueba)")
    print("=" * 70)
    print("?? IR (GPIO 23): Lee color y clasifica inmediatamente")
print()

# CALIBRACIÓN DE FONDO
background_profile = load_or_calibrate_background()

# CALIBRACIÓN INICIAL DEL MOTOR
print("?? Calibrando motor...")
for i in range(4):
    print(f"   Giro {i+1}/4: {i*90}° ? {(i+1)*90}°")
    move_motor_steps(STEPS_PER_QUARTER, direction=1)
    time.sleep(0.5)
current_position = 0
print("? Calibración completada\n")

print("Sistema listo. Presiona Ctrl+C para salir.\n")

try:
    while True:
        if USE_TWO_SENSORS:
            # ===== MODO 2 SENSORES =====
            ir_color_state = lgpio.gpio_read(chip, IR_COLOR_PIN)
            
            if ir_color_state == 0 and last_ir_color_state == 1:
                r, g, b, c = sensor.color_raw
                try:
                    color_temp = sensor.color_temperature or 0
                    lux = sensor.lux or 0
                except Exception:
                    color_temp, lux = 0, 0

                # Verificar si es el fondo
                if is_background(r, g, b, c, background_profile):
                    print("?? Fondo detectado, ignorando...")
                    last_ir_color_state = 1
                    time.sleep(0.1)
                    continue

                label, conf = predict_color(r, g, b, c, color_temp, lux)
                
                print("\n" + "-" * 70)
                print(f"?? PIEZA EN SENSOR DE COLOR")
                print(f"   Color: {label} (confianza: {conf:.2f})")
                print(f"   RGB: R:{r} G:{g} B:{b} | Temp:{color_temp:.0f}K Lux:{lux:.1f}")
                color_queue.append(label)
                print(f"?? Cola: {list(color_queue)} ({len(color_queue)} piezas)")
                print("-" * 70)
                
                while lgpio.gpio_read(chip, IR_COLOR_PIN) == 0:
                    time.sleep(0.05)
                last_ir_color_state = 1
                time.sleep(0.1)
                continue
            
            last_ir_color_state = ir_color_state
            
            ir_drop_state = lgpio.gpio_read(chip, IR_DROP_PIN)
            
            if ir_drop_state == 0 and last_ir_drop_state == 1:
                if color_queue:
                    next_color = color_queue.popleft()
                    print("\n" + "=" * 70)
                    print(f"?? PIEZA EN PUNTO DE CAÍDA")
                    print(f"   Clasificando: {next_color}")
                    print(f"   Cola restante: {list(color_queue)}")
                    print("=" * 70)
                    rotate_to_color(next_color)
                    
                    while lgpio.gpio_read(chip, IR_DROP_PIN) == 0:
                        time.sleep(0.05)
                    last_ir_drop_state = 1
                    time.sleep(0.1)
                    continue
                else:
                    print("\n??  Pieza detectada pero cola vacía")
            
            last_ir_drop_state = ir_drop_state
            
        else:
            # ===== MODO 1 SENSOR (CLASIFICACIÓN INMEDIATA) =====
            ir_state = lgpio.gpio_read(chip, IR_SENSOR_PIN)
            
            if ir_state == 0 and last_ir_color_state == 1:
                r, g, b, c = sensor.color_raw
                try:
                    color_temp = sensor.color_temperature or 0
                    lux = sensor.lux or 0
                except Exception:
                    color_temp, lux = 0, 0

                # Verificar si es el fondo
                if is_background(r, g, b, c, background_profile):
                    print("?? Fondo detectado, ignorando...")
                    last_ir_color_state = 1
                    time.sleep(0.1)
                    continue

                label, conf = predict_color(r, g, b, c, color_temp, lux)
                
                print("\n" + "=" * 70)
                print(f"?? PIEZA DETECTADA")
                print(f"   Color: {label} (confianza: {conf:.2f})")
                print(f"   RGB: R:{r} G:{g} B:{b} | Temp:{color_temp:.0f}K Lux:{lux:.1f}")
                print("=" * 70)
                
                rotate_to_color(label)
                
                while lgpio.gpio_read(chip, IR_SENSOR_PIN) == 0:
                    time.sleep(0.05)
                last_ir_color_state = 1
                time.sleep(0.2)
                continue
            
            last_ir_color_state = ir_state
        
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n\n?? Finalizando programa...")

finally:
    for pin in MOTOR_PINS:
        lgpio.gpio_write(chip, pin, 0)
    lgpio.gpiochip_close(chip)
    print("? GPIO liberados correctamente.")