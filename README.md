\# ESP8266 4-Channel Relay Board - Example Code



> \*\*Note:\*\* All the code provided in this repository is intended strictly as example code to help you get started with the hardware.



This repository contains basic examples and starter code to help you test and experiment with your ESP8266-based 4-channel relay board. The provided examples demonstrate how to control the physical relays, set up a Wi-Fi connection, and communicate with the board using Android and desktop applications.



\---



\## Hardware Overview



The board is powered by an ESP8266 microcontroller and features a 4-channel relay module. It allows you to switch connected electrical devices on and off by triggering the corresponding GPIO pins. 



Because it uses an ESP8266 chip, the board has built-in Wi-Fi capabilities. You can experiment with the board by writing your own firmware to control it over a network, integrating it into projects, or modifying the examples provided here to build your own custom setup.



\---



\## What's Included



This repository provides three linked examples to show you how a basic software loop works with the hardware:



\*   \*\*`firmware/`\*\*: Example C++ code for the ESP8266. This code sets up a basic WebSocket server, connects to your local Wi-Fi, and listens for on/off commands to toggle the physical relays.

\*   \*\*`desktop-app/`\*\*: A Python script (using CustomTkinter) that finds the board on your network and provides a graphical interface to toggle the relays from your computer.

\*   \*\*`android-app/`\*\*: A sample Android application (written in Kotlin/Jetpack Compose) that connects to the board to control the switches from a phone.



\---



\## How to Use the Examples to Get Started



You can compile and run these examples exactly as they are to test that your board is functioning correctly, or you can read through the code to see how the different devices communicate.



\### 1. Flash the Board

1\. Open the code in the `firmware/` folder.

2\. Connect your board to your computer via a USB cable, power up the board and flash the code to the ESP8266 board.

3\. Because the firmware features a built-in captive portal, the board will boot up and broadcast its own open Wi-Fi access point if it cannot find a saved network.

4\. Using your phone or computer, connect to the board's Wi-Fi access point, open your browser, and use the captive portal configuration page to enter your home router's Wi-Fi SSID and password.

5\. Save the credentials. The board will restart, connect to your local Wi-Fi network, and begin listening for commands on port `81`.



\### 2. Test the Desktop Interface

You can download the ready-to-use \*\*.exe\*\* file from the \*\*Releases\*\* section of this repository. Alternatively, you can run it from the source code:

1\. Install Python 3 on your computer.

2\. Install the necessary Python libraries by opening your terminal and running: `pip install customtkinter websocket-client zeroconf pillow qrcode pyserial`

3\. Run the `main.py` file to open the desktop interface, which will allow you to discover your board on the network and test the switches.



\### 3. Test the Android App

You can download the ready-to-use \*\*.apk\*\* file from the \*\*Releases\*\* section of this repository and install it directly on your phone. Alternatively, you can build it from source:

1\. Load the Android code in Android Studio and build it to your phone.

2\. Make sure your phone is connected to the same Wi-Fi network as the board.

3\. Open the app to scan the network, find the board, and test toggling the physical relays from a mobile device.



\---



> \*\*Note:\*\* This repository might be updated, and new examples might become available in the future.



