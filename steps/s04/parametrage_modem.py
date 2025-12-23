# -*- coding: utf-8 -*-

import sys, os, json, time
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
import configuration  # Custom
from modules.capsys_mysql_command.capsys_mysql_command import (GenericDatabaseManager, DatabaseConfig) # Custom

def get_info():
    return "Cette étape teste les seuils de fonctionnement du radar."

def run_step(log, config: configuration.AppConfig, update_percentage=lambda x: None):
    step_name = os.path.splitext(os.path.basename(__file__))[0]
    return_msg = {"step_name": step_name, "infos": []}
    # Ensure db is initialized
    if not hasattr(config, "db") or config.db is None:
        return_msg["infos"].append(f"config.db n'est pas initialisé.")
        return 1, return_msg
    # We always save the name of the step in the db
    step_name_id = config.db.create("step_name", {"device_under_test_id": config.device_under_test_id, "step_name": step_name})
    ###################################################################

    if config.modem_fc302_manager is None:
        return_msg["infos"].append(f"config.modem_fc302_manager n'est pas initialisé.")
        return 1, return_msg
    
    config.modem_fc302_manager.send_command_Cr("AT+RESET")
    time.sleep(5)  # Wait modem
    update_percentage(50)

    config_file_path = config.configItems.json_grenoble_nice.path
    if not os.path.exists(config_file_path):
        return_msg = f"Le fichier de configuration '{config_file_path}' est introuvable."
        return 1, return_msg
    with open(config_file_path, "r", encoding="utf-8") as file:  # Open the configuration file
        raw_data = file.read()
        fixed_data = raw_data.replace("\\", "\\\\")  # Escape backslashes
    try:
        config_data = json.loads(fixed_data)  # Parse the JSON data
    except json.JSONDecodeError as e:
        return_msg = f"Erreur lors de l'analyse du fichier de configuration JSON : {e}"
        return 1, return_msg

    config.modem_fc302_manager.write_all_parameters(config_data)

    return 0, "Étape OK"


if __name__ == "__main__":
    """Allow to run this script directly for testing purposes."""

    def log_message(message, color):
        print(f"{color}: {message}")

    # Initialize config
    config = configuration.AppConfig()
    config.arg.show_all_logs = False
    config.arg.product_list_id = configuration.PRODUCT_LIST_ID_DEFAULT

    # Initialize Database
    config.db_config = DatabaseConfig(password="root")
    config.db = GenericDatabaseManager(config.db_config, debug=False)
    config.db.connect()
    
    # Launch the initialisation step
    from steps.s01.initialisation import run_step as run_step_init
    success_end, message_end = run_step_init(log_message, config)
    print(message_end)
    
    # Launch this step
    success, message = run_step(log_message, config)
    print(message)

    # Clear ressources
    from steps.zz.fin_du_test import run_step as run_step_fin_du_test
    success_end, message_end = run_step_fin_du_test(log_message, config)
    print(message_end)