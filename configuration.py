import os
from typing import Optional, Any
import atexit
from modules.capsys_mysql_command.capsys_mysql_command import (GenericDatabaseManager, DatabaseConfig) # Custom
from modules.capsys_wrapper_tm_t20iii.capsys_wrapper_tm_t20III import PrinterDC  # Custom
from modules.capsys_serial_instrument_manager.capsys_serial_instrument_manager import SerialInstrumentManager  # Custom
from modules.capsys_serial_instrument_manager.fc302_friendcom.fc302_friendcom import ModemFc302Manager  # Custom
from modules.capsys_serial_instrument_manager.ds1104_rigol.ds1104_rigol import Ds1104RigolManager  # Custom

# Initialize global variables
CURRENTH_PATH = os.path.dirname(__file__)
NAME_GUI = "FC302"
CONFIG_JSON_NAME = "config_fc302"
PRODUCT_LIST_ID_DEFAULT = "10"
VERSION = "V1.0.0"
HASH_GIT = "DEBUG" # Will be replaced by the Git hash when compiled with command .\build.bat
AUTHOR = "Thomas GERARDIN"
PRINTER_NAME = "EPSON TM-T20III Receipt"

def get_project_path(*paths):
    """Return the absolute path from the project root, regardless of current working directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), *paths))

def request_user_input(config, title: str, message: str) -> Optional[str]:
    """
    Request text input from the user.
    
    If running from GUI (main.py), displays a dialog box.
    If running directly (debug mode), uses console input().
    
    Args:
        config: AppConfig instance
        title: Title of the dialog box (GUI mode only)
        message: Message to display to the user
    
    Returns:
        The text entered by the user, or None if cancelled
    """
    import time
    
    user_input_result = {"text": None, "received": False}
    
    def handle_user_input(text):
        user_input_result["text"] = text
        user_input_result["received"] = True
    
    if config.test_thread is not None:
        # GUI mode with dialog box
        config.test_thread.request_user_text_input(title, message, handle_user_input)
        
        # Wait for user input (without timeout)
        while not user_input_result["received"]:
            time.sleep(0.1)
        
        return user_input_result["text"]
    else:
        # Debug mode with console input
        user_text = input(message + " ")
        return user_text if user_text else None

class SerialUsbDut(SerialInstrumentManager):
    def __init__(self, port=None, baudrate=115200, timeout=0.3, debug=False):
        SerialInstrumentManager.__init__(self, port, baudrate, timeout, debug)
        self._debug_log("DUT initialized")

    def get_valid(self, sn=None) -> bool:
        # self.send_command("AT+RESET", timeout=1) # Initialize communication
        idn = self.send_command("AT+RESET\r", timeout=1) # Expecting "OK"
        if not idn:
            raise RuntimeError("Failed to get valid IDN response")
        if idn == "OK":
            self._debug_log(f"Device IDN: {idn}")
            return True
        else:
            raise RuntimeError(f"Invalid device IDN: {idn}")
    
    def send_command_Cr(self, command: str, expected_response: str = "", exact_match: bool = False, timeout: float = 0, read_until: str = "") -> str:
        return super().send_command(command + "\n", expected_response, exact_match, timeout, read_until)
    
class ConfigItems:
    """Container for all configuration items used in the test sequence."""
    key_map = {
        "RS232": "rs232_dut",
    }

    def init_config_items(self, configJson):
        """Initialize configItems attributes from the config JSON mapping pins and keys."""
        key_map = ConfigItems.key_map
        # For each element of config.json, create a corresponding ConfigItem
        for json_key, attr_name in key_map.items():
            item = configJson.get(json_key, {}) # Retrieves the JSON object or {} if absent
            # Create the ConfigItem with all the parameters from the JSON
            setattr(
                self,
                attr_name,
                ConfigItems.ConfigItem(                
                    key=json_key,
                    port=item.get("port", ""),
                    baudrate=item.get("baudrate", "")
                )
            )

    class ConfigItem:
        """Represents a single configuration item loaded from config.json or database."""
        def __init__(
            self,
            key = "",
            port: str = "",
            baudrate: str = "",
        ):
            """Initialize a ConfigItem with optional parameters for test configuration."""
            self.key = key
            self.port = port
            self.baudrate = baudrate
    
    def __init__(self):
        """Initialize all ConfigItem attributes for different test parameters."""
        self.rs232_dut = self.ConfigItem()

class Arg:
    name = NAME_GUI
    version = VERSION
    hash_git = HASH_GIT
    author = AUTHOR
    show_all_logs = False
    operator = AUTHOR
    commande = ""
    of = ""
    article = ""
    indice = ""
    product_list_id = PRODUCT_LIST_ID_DEFAULT
    user = "root"
    password = "root"
    host = "127.0.0.1"
    port = "3306"
    database = "capsys_db_bdt"
    product_list: Optional[dict] = None
    parameters_group: list[str] = []
    external_devices: Optional[list[str]] = None
    script: Optional[str] = None

class AppConfig:
    def __init__(self):
        self.arg = Arg()
        self.test_thread: Any = None  # Reference to TestThread for user input requests
        self.db_config: Optional[DatabaseConfig] = None
        self.db: Optional[GenericDatabaseManager] = None
        self.device_under_test_id: Optional[int] = None
        self.configItems = ConfigItems()
        self.printer: Optional[PrinterDC] = None
        atexit.register(self.cleanup) # Register cleanup function to be called on exit

        self.modem_fc302_manager: Optional[ModemFc302Manager] = None
        self.oscilloscope_rigol_manager: Optional[Ds1104RigolManager] = None

    def cleanup(self):
        if self.modem_fc302_manager:
            try:
                self.modem_fc302_manager.close()
            except:
                pass
            self.modem_fc302_manager = None
        if self.db:
            self.db.disconnect()
            self.db = None
        # Add other cleanup actions as needed
        self.device_under_test_id = None
        
    def save_value(self, step_name_id: int, key: str, value, unit: str = "", min_value: Optional[float] = None, max_value: Optional[float] = None, valid: int = 0):
        """Save a key-value pair in the database."""
        if not self.db or not self.device_under_test_id:
            raise ValueError("Database or device under test ID is not initialized.")
        if isinstance(value, float) or isinstance(value, int):
            table = "skvp_float"
            col = "val_float"
            data = {"step_name_id": step_name_id, "key": key, col: value, "unit": unit, "min_configured": min_value, "max_configured": max_value, "valid": valid}
        elif isinstance(value, str):
            table = "skvp_char"
            col = "val_char"
            data = {"step_name_id": step_name_id, "key": key, col: value}
        elif isinstance(value, bytes):
            table = "skvp_file"
            col = "val_file"
            data = {"step_name_id": step_name_id, "key": key, col: value}
        elif isinstance(value, dict):
            table = "skvp_json"
            col = "val_json"
            data = {"step_name_id": step_name_id, "key": key, col: value}
        else:
            raise ValueError("Type de valeur non supporté.")
        id = self.db.create(table, data)
        return id