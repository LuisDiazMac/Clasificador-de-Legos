# Clasificador de Legos 🎨🤖  
Sistema de clasificación automática de piezas LEGO basado en color utilizando un sensor **TCS34725** y un modelo de **inteligencia artificial**.

---

## 📘 Descripción general
Este proyecto implementa un sistema mecatrónico para clasificar piezas LEGO en función de su **color dominante**, combinando **adquisición de datos con el sensor TCS34725**, **procesamiento con Python** y **clasificación mediante una red neuronal convolucional (CNN)**.  

El sistema está diseñado para funcionar en tiempo real y puede integrarse con una **banda transportadora** o sistema de separación automática.

---

## ⚙️ Características principales
- Lectura de color RGB y luminosidad mediante el sensor **Adafruit TCS34725**.  
- Recolección y almacenamiento de datos para entrenamiento supervisado.  
- Entrenamiento de una **CNN** con TensorFlow/Keras para clasificar piezas LEGO por color.  
- Clasificación en **tiempo real** (latencia < 0.3 s).  
- Simulación del flujo de piezas en **FlexSim** para validar rendimiento y eficiencia del sistema.  
- Código modular compatible con **Raspberry Pi**, **Arduino** o **ESP32**.

---

## 🧰 Tecnologías utilizadas
- **Python 3.10+**
- **TensorFlow / Keras**
- **OpenCV**
- **NumPy / Pandas / Matplotlib**
- **Adafruit CircuitPython TCS34725**
- **FlexSim** (para simulación del proceso físico)

---

