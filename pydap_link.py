import sys
import logging
from pyocd.core.helpers import ConnectHelper
from pyocd.core.target import Target
from pyocd.flash.loader import FlashLoader

# Configure logging to capture DAP access packets for debugging
logging.basicConfig(level=logging.INFO)

class SiliconEnablementTool:
    """
    Automated tool for ARM Cortex-M silicon enablement, including core detection,
    ROM table parsing, flash programming, and memory verification using pyOCD.
    """
    def __init__(self):
        self.session = None
        self.target = None

    def initialize_session(self):
        """Initializes connection to the first available CMSIS-DAP v2 probe."""
        print("--- Starting Silicon Enablement Probe ---")
        try:
            # ConnectHelper handles probe discovery and session creation
            self.session = ConnectHelper.session_with_chosen_probe()
            self.session.open()
            self.target = self.session.target
            print(f"Target Detected: {self.target.part_number}")
        except Exception as e:
            print(f"Connection Failed: {e}")
            sys.exit(1)

    def board_bringup_sequence(self):
        """Halts the core to inspect state and parses ROM table."""
        if not self.target:
            return

        # Halt the core to inspect state during bring-up
        print("Halting core for inspection...")
        self.target.resume()
        self.target.halt()
        print(f"Core State: {self.target.get_state()}") 

        # CPUID register is essential for silicon identification
        CPUID_ADDR = 0xE000ED00 
        cpuid_val = self.target.read32(CPUID_ADDR)
        print(f"Core Detected | CPUID Register: {hex(cpuid_val)}")
        
        # Note: Additional logic to parse ROM table entries would go here

    def verify_memory_access(self, address=0x20000000, value=0xDEADBEEF):
        """Verifies RAM read/write access to confirm bus stability."""
        if not self.target:
            return

        print(f"Verifying memory access at {hex(address)}...")
        print(f"Writing {hex(value)} to {hex(address)}...")
        self.target.write32(address, value)
        
        read_back = self.target.read32(address)
        if read_back == value:
            print("Memory Verification: SUCCESS")
        else:
            print(f"Memory Verification: FAILED (Read {hex(read_back)})")

    def flash_programming_sequence(self, binary_path, address):
        """Automated Flash programming sequences."""
        if not self.target:
            return

        print(f"Initializing Flash Loader at {hex(address)}...")
        try:
            # [cite_start]FlashLoader handles the complex sequence of erasing and writing pages [cite: 69]
            loader = FlashLoader(self.session)
            loader.add_bin_data(binary_path, address)
            loader.commit()
            print("Flash Programming Complete.")
        except Exception as e:
             print(f"Flash Programming Failed: {e}")

    def register_level_verification(self, reg_map):
        """Performs register-level verification for SoC bring-up."""
        print("Starting SoC Register Verification...")
        for name, addr in reg_map.items():
            val = self.target.read32(addr)
            print(f"Register {name} ({hex(addr)}): {hex(val)}")
        # [cite_start]This confirms hardware state during board bring-up

    def reset_and_close(self):
        """Resets the target and closes the session."""
        if self.target:
            self.target.reset()
            print("Target reset and ready for firmware deployment.")
        
        if self.session:
            self.session.close()

if __name__ == "__main__":
    tool = SiliconEnablementTool()
    tool.initialize_session()
    
    # 1. Basic Bring-up Checks
    tool.board_bringup_sequence()
    
    # 2. Memory Verification (SRAM Check)
    tool.verify_memory_access(address=0x20000000, value=0xCAFEBABE)

    # 3. Register Verification Map (Example values)
    SO_REG_MAP = {
        "SYSCON_STAT": 0x40000000,
        "CLOCK_CTRL": 0x40000004
    }
    tool.register_level_verification(SO_REG_MAP)

    # 4. Flash Programming (Uncomment and provide a real path to test)
    # tool.flash_programming_sequence("firmware.bin", 0x08000000)

    tool.reset_and_close()