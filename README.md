# Silicon Enablement Tool (pydap-link)

A Python utility I wrote to automate the tedious parts of **SoC Board Bring-up** and **Silicon Validation**.

In my day-to-day work with embedded systems, I often need to verify if a new chip (or "first silicon") is alive without firing up a heavy IDE like Keil or IAR. This tool wraps `pyOCD` to let me quickly check the heartbeat of an ARM Cortex-M core, verify the bus, and flash firmware directly from the terminal.

## ⚡ Why I Built This
Manually checking registers like CPUID (`0xE000ED00`) or verifying RAM access via a debugger GUI is slow and error-prone. I needed a scriptable way to:
1.  **Detect the Core:** Instantly see if the chip is an M0+, M4, or M7.
2.  **Verify the Bus:** Check if the AHB-AP is responding before I even try to load code.
3.  **Automate Flashing:** Flash binaries across multiple boards without clicking through menus.

## 🚀 What It Does
* **Auto-Discovery:** Finds the connected debug probe (PICkit 5, DAPLink, ST-Link) and identifies the target.
* **Sanity Checks:** Halts the core and reads the `CPUID` to confirm the hardware is stable.
* **Memory Test:** Writes a pattern (`0xDEADBEEF`) to SRAM and reads it back to ensure the memory controller is working.
* **Flash & Go:** Handles the erase-program-verify cycle for binary firmware files.

## 🛠️ Getting Started

### Prerequisites
* Python 3.8+
* A debug probe (I tested this with a PICkit 5, but any CMSIS-DAP probe should work).

### Installation
1.  Clone this repo:
    ```bash
    git clone [https://github.com/kumar-mohan/pydap-link.git](https://github.com/kumar-mohan/pydap-link.git)
    cd pydap-link
    ```

2.  Set up a virtual environment (highly recommended so you don't break your system Python):
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  Install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## 📖 Usage

Connect your board and run the tool:
```bash
python pydap_link.py
```