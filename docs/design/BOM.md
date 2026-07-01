# Bill of Materials — Mainframe Simulation (Mainframe-Core Architecture)

> Parts for the **Phase 1 working system**. Architecture: ADR-0001. The
> per-node pin allocation in §3 is the verified basis for the PCF8574 line item.
> All MCU GPIO is 3.3V — never apply 5V to a C3 pin.

---

## 1. In hand — reuse (no purchase)

| Item | Qty | Use |
|------|-----|-----|
| ESP32-C3 SuperMini | 4 | Channel MCUs #1, #2, #4, #5 |
| Raspberry Pi 3B+ | 1 | Mainframe central complex |
| SSD1306 0.96" OLED (I2C) | 5 | One private display per node |
| 4×4 matrix keypad | 1 | Transaction Terminal input (via PCF8574 — see §3) |
| KY-040 rotary encoder | 1 | Transaction Terminal operation-select (power at **3.3V**) |
| Tactile push buttons | several | Console / Job Submitter input |
| LEDs | several | Console status "lamps" |
| Breadboards, jumper wire | — | Bus hub + per-node wiring |
| 8-ch 24MHz logic analyzer | 1 | CAN decode (sigrok CAN PD) |
| Bench supply (5V) | 1 | MCU power |
| Pi 5V/3A USB supply | 1 | Pi power (dedicated — not shared with MCUs) |

**Set aside (not used in this project):** MPU-6050 (IMU — no role); LCD160CR
touchscreen (MicroPython-only driver → integration risk; possible *much later*
fancy-terminal upgrade). RFID reader currently missing — not required (Job
Submitter uses a button).

---

## 2. To order — Phase 1

| Item | Qty | ~Cost | Verify before paying |
|------|-----|-------|----------------------|
| **SN65HVD230 / VP230 CAN transceiver** | 5 | ~$1 ea | Chip is **SN65HVD230 or VP230**, *not* TJA1050/MCP2551; rated **3.3V** ("DC 3V–3.6V"); whether onboard 120Ω is **removable** |
| **Waveshare RS485 CAN HAT** (single-ch) | 1 | ~$15 | **Crystal value** — read the silver oval: `12.000` → overlay `oscillator=12000000`; older boards `8.000` → `8000000`. MCP2515-based (not MCP2518FD) |
| **120Ω resistor** (1/4W) | 2 | cents | Placed at the **two bus ends only** |
| **PCF8574 I2C GPIO expander** | 1 (–2) | ~$0.50 ea | PCF8574 (addr 0x20–0x27) or PCF8574**A** (0x38–0x3F) — note which, so the address doesn't clash with the OLED. 1 for the keypad; +1 only if you want a richer console panel |
| **220–330Ω resistor** (LED current limit) | ~6 | cents | One per console LED |
| Twisted-pair / Dupont wire | — | — | CANH+CANL twisted; common GND rail |

*Pi-side alternative to the HAT:* a SocketCAN-native USB-CAN adapter
(`gs_usb`/candleLight class). Avoid the proprietary "USB-CAN-A" (vendor driver,
not kernel SocketCAN).

---

## 3. Per-node pin allocation (verified)

C3 SuperMini usable GPIO is roughly **0,1,4,5,6,7,10,20,21** clean (avoid
strapping **2/8/9**; **18/19** are USB-JTAG — usable only if native USB is given
up). OLED uses **GPIO3 (SDA) + GPIO10 (SCL)**; CAN TX/RX route via the GPIO
matrix to any two free pins. That leaves ~5 clean signal pins per node.

| Node | OLED | CAN | Role peripherals | Fits without expander? |
|------|------|-----|------------------|------------------------|
| #1 Operator Console | 2 | 2 | ~3 buttons + ~3 LEDs (use built-in GPIO8 LED as one lamp) | **Yes** (modest panel). PCF8574 only if you want more |
| #2 Transaction Terminal | 2 | 2 | 4×4 keypad (**8 pins raw**) + encoder (3) | **No** — keypad must go on a **PCF8574** (rides I2C, 0 extra GPIO); encoder then fits |
| #4 Job Submitter | 2 | 2 | 1–2 buttons + 1 LED | **Yes** |
| #5 Output Writer | 2 | 2 | none (OLED journal only) | **Yes** |

**Conclusion:** the only forced expander is **1× PCF8574 on the Transaction
Terminal**. A second PCF8574 is optional, for a richer Operator Console panel.
(Expander-free alternative for #2: encoder-only digit entry, drop the keypad —
fits, slower UX.)

---

## 4. Deferred — later phases (do not order yet)

| Item | Phase | Note |
|------|-------|------|
| CSN-A2 **TTL** thermal printer | 2+ | + its **own 5–9V / 2A** supply (cannot run off the MCU); TTL variant only |
| 2nd PCF8574 | 2 | Richer Operator Console panel |
| RFID reader (RC522) | 2 | "Tap a card" job submission on #4 (3.3V part) |

---

## 5. Consolidated verify-before-buy checklist

1. CAN transceivers say **3.3V** and are **SN65HVD230/VP230** — not TJA1050/MCP2551.
2. CAN transceiver onboard 120Ω is **removable** (you terminate only 2 nodes).
3. Pi HAT **crystal** matches the overlay oscillator value (read the can; 12 or 8 MHz).
4. PCF8574 **I2C address range** won't collide with the OLED on the same bus.
5. (Deferred) thermal printer is the **TTL** variant and ships with — or you add — a **5V/2A+** supply.
