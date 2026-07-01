# Bring-Up Checklist — Mainframe Simulation (Phase 1)

> **Pre-firmware hardware and toolchain verification.** Complete this checklist
> before writing or flashing any firmware. It is a **pre-condition gate** — every
> item here is a precondition for the §3 bring-up DoD in `requirements.md`.
> Functional testing (CAN frames, OLED, heartbeat) lives there, not here.
>
> Fill in the `Result` column as each item is verified. Acceptable values:
> **PASS**, **FAIL** (with note), or **N/A** (with reason). Do not proceed past
> a section with an unresolved FAIL.
>
> Measurements go into `learning-log.md` once taken (protocol-spec §6 consequence).
>
> Status: **DRAFT — awaiting hardware arrival (~end of week 2026-06-28).**

---

## §1 CAN bus wiring & termination

*Verify before any node is powered. A wiring fault here can damage transceivers.*

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 1.1 | Measure CANH–CANL resistance with **all nodes unpowered** | ~60 Ω (two 120 Ω terminators in parallel) | | |
| 1.2 | Confirm exactly **two** 120 Ω resistors placed, at the two physical bus ends only | 2× resistors, no middle-node terminators | | |
| 1.3 | Middle nodes: any onboard termination on the SN65HVD230 breakouts is **removed** | No third resistor on bus | | |
| 1.4 | Common GND rail confirmed: Pi GND, all MCU GNDs, and bus GND are connected | Continuity on all GND points | | |
| 1.5 | CANH and CANL are **twisted pair** (or at minimum not routed parallel to power wires) | Visual check | | |

---

## §2 CAN transceivers (SN65HVD230 / VP230)

*Per BOM §5 verify-before-buy checklist. Confirm before soldering or connecting.*

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 2.1 | Chip marking on each transceiver reads **SN65HVD230** or **VP230** — not TJA1050 or MCP2551 | SN65HVD230 or VP230 | | |
| 2.2 | Board supply voltage spec reads **3.3 V** (label or datasheet) | "DC 3V–3.6V" or equivalent | | |
| 2.3 | Onboard 120 Ω termination resistor is **removable** (solder bridge, jumper, or physically absent) on each middle-node transceiver | Removable on nodes #1, #2, #4, #5 (middle nodes) | | |
| 2.4 | After powering one node: CANH–CANL **differential voltage** at idle is ~2.5 V (recessive) measured on the logic analyzer or multimeter | ~2.5 V differential at idle | | |

---

## §3 Raspberry Pi CAN HAT (Waveshare RS485 CAN HAT, MCP2515)

*Per BOM §5 and protocol-spec §1 caveat.*

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 3.1 | Read the **crystal value** from the silver oval on the HAT | Either `12.000` (→ overlay `oscillator=12000000`) or `8.000` (→ `8000000`) | | Actual value: _______ MHz |
| 3.2 | `/boot/config.txt` (or `/boot/firmware/config.txt`) overlay entry matches the crystal value read in 3.1 | `dtparam=oscillator=<value>` | | |
| 3.3 | `dmesg | grep mcp251` shows the MCP2515 initialised without error after boot | `mcp251x spi0.0: MCP2515 successfully initialized` (or equivalent) | | |
| 3.4 | `ip link show can0` reports interface present | `can0` listed | | |
| 3.5 | Bring `can0` up at 500 kbit/s: `sudo ip link set can0 up type can bitrate 500000` — no error | Command exits 0 | | |
| 3.6 | `candump can0` starts and shows no spontaneous error frames at idle (bus connected, nodes unpowered) | No `ERRORFRAME` output | | |

---

## §4 PCF8574 I²C GPIO expander (Transaction Terminal #2)

*I²C — Inter-Integrated Circuit, the private bus shared by the OLED and the expander on #2.*

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 4.1 | Note the PCF8574 variant purchased: **PCF8574** (addr range 0x20–0x27) or **PCF8574A** (0x38–0x3F) | Record variant | | Variant: _______ |
| 4.2 | SSD1306 OLED I²C address on #2 (typically 0x3C or 0x3D) does **not** collide with the PCF8574 address | No address clash | | OLED addr: _______ PCF addr: _______ |
| 4.3 | I²C scan on MCU #2 (`i2c_master_probe` or equivalent) finds **both** the OLED and the PCF8574 | Two devices found | | |

---

## §5 ESP-IDF toolchain & `esp_isotp` component

*`esp_isotp` — Espressif's ISO 15765-2 transport component; `TWAI` — Espressif's on-chip CAN 2.0 controller. Unverified caveat from protocol-spec §1.*

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 5.1 | Record the ESP-IDF version in use: `idf.py --version` | ≥ 5.x (record exact version) | | Version: _______ |
| 5.2 | `espressif/esp_isotp` component is available in the IDF Component Registry for the version recorded in 5.1 | Listed at components.espressif.com | | |
| 5.3 | Component's supported-targets list **includes `esp32c3`** | `esp32c3` listed | | |
| 5.4 | The TWAI driver API in this IDF version uses `twai_node_onchip` (v5.x node-based) or the legacy `twai_driver_install` — note which | Record which API | | API style: _______ |
| 5.5 | `esp_isotp`'s documented API surface includes an **error/abort callback or return code** for ISO-TP session failures (needed for TIMEOUT ERROR frame — protocol-spec §7.4) | Error surface documented | | |
| 5.6 | A minimal "hello CAN" sketch (TWAI init + send one frame) compiles and flashes to an ESP32-C3 without error | Build and flash succeed | | |

---

## §6 Bench power & safety

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 6.1 | Bench supply set to **5 V** for MCUs; Pi on its **dedicated 5V/3A USB supply** (not shared) | Two separate supplies | | |
| 6.2 | No MCU GPIO pin connected directly to a 5 V signal (all GPIO are **3.3 V max**) | Visual check on all wiring | | |
| 6.3 | Logic analyzer ground is connected to the **common bus GND** | GND clip attached | | |
| 6.4 | Logic analyzer CAN decoder configured: **500 kbit/s, inverted if needed** for the probe type | Decoder shows valid idle | | |

---

## §7 Timeout measurements

*Fill in at bring-up — these replace the provisional values in protocol-spec §6.
Log each result in `learning-log.md` once measured.*

| # | Measurement | Method | Provisional value | Measured value | Logged? |
|---|---|---|---|---|---|
| 7.1 | **SQLite WAL commit latency** — worst-case fsync time on the Pi's SD card under light load | Time `BEGIN … COMMIT` around a representative INSERT+UPDATE in Python; take max over 20 runs | — | _______ ms | ☐ |
| 7.2 | **SQLite WAL commit latency under load** — same as 7.1 with concurrent reads | Add a reader thread during measurement | — | _______ ms | ☐ |
| 7.3 | **CAN frame round-trip** — time from ISO-TP send on MCU to first FC frame received back from Pi | Logic analyzer timestamps | — | _______ ms | ☐ |
| 7.4 | **Transaction timeout** — set to a healthy multiple (≥ 3×) of the worst-case measured in 7.1/7.2 + 7.3 | Derived from measurements | 2 s | _______ s | ☐ |
| 7.5 | **Heartbeat cadence** — confirm 1 s nominal cadence is achievable on the MCU FreeRTOS task without drift | `candump` timestamps over 30 s | 1 s | _______ ms avg drift | ☐ |
| 7.6 | **Liveness timeout** — set to 3× the measured heartbeat cadence | Derived from 7.5 | 3 s | _______ s | ☐ |

*Once 7.4 and 7.6 are filled in, update `protocol-spec.md` §6 to replace the
provisional values with the measured ones, and remove the ⚠ provisional warning.*

---

## §8 Sign-off

All sections above must be PASS or N/A before firmware work begins.

| Section | Status | Date | Initials |
|---|---|---|---|
| §1 Bus wiring & termination | | | |
| §2 CAN transceivers | | | |
| §3 Pi CAN HAT | | | |
| §4 PCF8574 expander | | | |
| §5 ESP-IDF & esp_isotp | | | |
| §6 Bench power & safety | | | |
| §7 Timeout measurements | *(fill after firmware, before DoD sign-off)* | | |

> §7 is the only section that requires running firmware — it may be completed
> after §3 bring-up DoD passes (first frames on the bus) and before §4 per-feature
> DoD is attempted.
