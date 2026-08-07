# ESP8266 4-Channel Relay Board - Example Code

> **Note:** All the code provided in this repository is intended strictly as example code to help you get started with the hardware.
> 
> *برای مطالعه توضیحات به زبان فارسی، به پایین صفحه مراجعه کنید (Farsi version below).*

This repository contains basic examples and starter code to help you test and experiment with your ESP8266-based 4-channel relay board. The provided examples demonstrate how to control the physical relays, set up a Wi-Fi connection, and communicate with the board using Android and desktop applications.

---

## Hardware Overview

The board is powered by an ESP8266 microcontroller and features a 4-channel relay module. It allows you to switch connected electrical devices on and off by triggering the corresponding GPIO pins. 

Because it uses an ESP8266 chip, the board has built-in Wi-Fi capabilities. You can experiment with the board by writing your own firmware to control it over a network, integrating it into projects, or modifying the examples provided here to build your own custom setup.

---

## What's Included

This repository provides three linked examples to show you how a basic software loop works with the hardware:

*   **`firmware/`**: Example C++ code for the ESP8266. This code sets up a basic WebSocket server, connects to your local Wi-Fi, and listens for on/off commands to toggle the physical relays.
*   **`desktop-app/`**: A Python script (using CustomTkinter) that finds the board on your network and provides a graphical interface to toggle the relays from your computer.
*   **`android-app/`**: A sample Android application (written in Kotlin/Jetpack Compose) that connects to the board to control the switches from a phone.

---

## How to Use the Examples to Get Started

You can compile and run these examples exactly as they are to test that your board is functioning correctly, or you can read through the code to see how the different devices communicate.

### 1. Flash the Board
1. Open the code in the `firmware/` folder.
2. Connect your board to your computer via a USB cable, power up the board and flash the code to the ESP8266 board.
3. Because the firmware features a built-in captive portal, the board will boot up and broadcast its own open Wi-Fi access point if it cannot find a saved network.
4. Using your phone or computer, connect to the board's Wi-Fi access point, open your browser, and use the captive portal configuration page to enter your home router's Wi-Fi SSID and password.
5. Save the credentials. The board will restart, connect to your local Wi-Fi network, and begin listening for commands on port `81`.

### 2. Test the Desktop Interface
You can download the ready-to-use **.exe** file from the **Releases** section of this repository. Alternatively, you can run it from the source code:
1. Install Python 3 on your computer.
2. Install the necessary Python libraries by opening your terminal and running: `pip install customtkinter websocket-client zeroconf pillow qrcode pyserial`
3. Run the `main.py` file to open the desktop interface, which will allow you to discover your board on the network and test the switches.

### 3. Test the Android App
You can download the ready-to-use **.apk** file from the **Releases** section of this repository and install it directly on your phone. Alternatively, you can build it from source:
1. Load the Android code in Android Studio and build it to your phone.
2. Make sure your phone is connected to the same Wi-Fi network as the board.
3. Open the app to scan the network, find the board, and test toggling the physical relays from a mobile device.

---

> **Note:** This repository might be updated, and new examples might become available in the future.

<br>
<br>

---
---

# برد رله ۴ کاناله ESP8266 - کدهای نمونه

> **توجه:** تمامی کدهای ارائه شده در این مخزن (ریپازیتوری) صرفاً به عنوان کدهای نمونه برای کمک به شما در شروع کار با این سخت‌افزار در نظر گرفته شده‌اند.

این مخزن شامل مثال‌های پایه و کدهای اولیه برای کمک به شما در تست و آزمایش برد رله ۴ کاناله مبتنی بر ESP8266 است. مثال‌های ارائه شده نشان می‌دهند که چگونه می‌توانید رله‌های فیزیکی را کنترل کنید، اتصال Wi-Fi را تنظیم کنید و با استفاده از برنامه‌های اندروید و دسکتاپ با برد ارتباط برقرار کنید.

---

## بررسی اجمالی سخت‌افزار

این برد از یک میکروکنترلر ESP8266 بهره می‌برد و دارای یک ماژول رله ۴ کاناله است. این امکان را به شما می‌دهد تا با تحریک پین‌های GPIO مربوطه، دستگاه‌های الکتریکی متصل را روشن و خاموش کنید.

از آنجا که این برد از تراشه ESP8266 استفاده می‌کند، دارای قابلیت‌های Wi-Fi داخلی است. شما می‌توانید با نوشتن فریم‌ور (firmware) اختصاصی خود برای کنترل آن از طریق شبکه، ادغام آن در پروژه‌های دیگر، یا تغییر مثال‌های ارائه شده در اینجا برای ساخت سیستم سفارشی خود، با این برد آزمایش کنید.

---

## محتویات این مخزن

این مخزن سه مثال مرتبط را ارائه می‌دهد تا نشان دهد یک حلقه نرم‌افزاری ساده چگونه با سخت‌افزار کار می‌کند:

*   **`/firmware`**: کد نمونه C++ برای ESP8266. این کد یک سرور پایه WebSocket را راه‌اندازی می‌کند، به Wi-Fi محلی شما متصل می‌شود و برای تغییر وضعیت رله‌های فیزیکی، منتظر دریافت دستورات روشن/خاموش (on/off) می‌ماند.
*   **`/desktop-app`**: یک اسکریپت پایتون (با استفاده از CustomTkinter) که برد را در شبکه شما پیدا می‌کند و یک رابط گرافیکی برای روشن و خاموش کردن رله‌ها از طریق کامپیوتر ارائه می‌دهد.
*   **`/android-app`**: یک برنامه نمونه اندروید (نوشته شده با Kotlin/Jetpack Compose) که به برد متصل می‌شود تا کلیدها را از طریق گوشی کنترل کند.

---

## نحوه استفاده از مثال‌ها برای شروع کار

شما می‌توانید این کدهای نمونه را دقیقاً همان‌طور که هستند کامپایل و اجرا کنید تا از عملکرد صحیح برد خود مطمئن شوید، یا کدها را مطالعه کنید تا ببینید دستگاه‌های مختلف چگونه با یکدیگر ارتباط برقرار می‌کنند.

### ۱. فلش کردن برد (آپلود کد)
۱. کد موجود در پوشه `/firmware` را باز کنید.
۲. برد خود را از طریق کابل USB به کامپیوتر متصل کنید، آن را روشن کرده و کد را روی برد ESP8266 فلش (آپلود) کنید.
۳. از آنجا که فریم‌ور دارای یک پورتال اسیر (Captive Portal) داخلی است، در صورتی که برد نتواند شبکه ذخیره‌شده‌ای را پیدا کند، راه‌اندازی شده و یک نقطه دسترسی (Access Point) Wi-Fi باز را پخش می‌کند.
۴. با استفاده از گوشی یا کامپیوتر خود به نقطه دسترسی Wi-Fi برد متصل شوید، مرورگر خود را باز کنید و از صفحه پیکربندی پورتال برای وارد کردن نام (SSID) و رمز عبور Wi-Fi مودم خانگی خود استفاده کنید.
۵. اطلاعات را ذخیره کنید. برد ری‌استارت می‌شود، به شبکه Wi-Fi محلی شما متصل می‌گردد و شروع به دریافت دستورات روی پورت `81` می‌کند.

### ۲. تست رابط کاربری دسکتاپ
می‌توانید فایل آماده اجرای **exe.** را از بخش **Releases** این مخزن دانلود کنید. در غیر این صورت، می‌توانید آن را از طریق سورس کد اجرا کنید:
۱. پایتون ۳ (Python 3) را روی کامپیوتر خود نصب کنید.
۲. کتابخانه‌های مورد نیاز پایتون را با باز کردن ترمینال و اجرای این دستور نصب کنید: `pip install customtkinter websocket-client zeroconf pillow qrcode pyserial`
۳. فایل `main.py` را اجرا کنید تا رابط دسکتاپ باز شود؛ این برنامه به شما اجازه می‌دهد برد خود را در شبکه پیدا کرده و کلیدها را تست کنید.

### ۳. تست برنامه اندروید
می‌توانید فایل آماده اجرای **apk.** را از بخش **Releases** این مخزن دانلود کرده و مستقیماً روی گوشی خود نصب کنید. در غیر این صورت، می‌توانید آن را از طریق سورس کد بیلد (Build) کنید:
۱. کد اندروید را در Android Studio بارگذاری کرده و آن را روی گوشی خود بیلد کنید.
۲. مطمئن شوید که گوشی شما به همان شبکه Wi-Fi متصل است که برد به آن وصل شده است.
۳. برنامه را باز کنید تا شبکه را اسکن کند، برد را پیدا کرده و تغییر وضعیت رله‌های فیزیکی را از طریق موبایل تست کنید.

---

> **توجه:** این مخزن ممکن است به‌روزرسانی شود و در آینده کدهای نمونه جدیدی در دسترس قرار گیرد.