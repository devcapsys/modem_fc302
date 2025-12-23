# -*- coding: utf-8 -*-

import sys, os, time
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
    if config.oscilloscope_rigol_manager is None:
        return_msg["infos"].append(f"config.oscilloscope_rigol_manager n'est pas initialisé.")
        return 1, return_msg
    
    min = config.configItems.measure_ac_vrms_1.min
    max = config.configItems.measure_ac_vrms_1.max
    
    if min is None or max is None:
        return_msg["infos"].append("Les valeurs min/max pour measure_ac_vrms_1 ne sont pas définies.")
        return 1, return_msg
    
    config.modem_fc302_manager.send_command_Cr("AT+TEST=TX0011")
    
    txt = configuration.request_user_input(
        config,
        "Réglage du modem FC302",
        f"Veuillez régler le modem avec AC.Vrms : {min}V min, {max}V max puis valider"
    )
    if txt is None:
        return_msg["infos"].append("L'utilisateur a annulé la saisie.")
        return 1, return_msg
    
    command = ":MEASure:ITEM? VRMS,CHANnel1"
    measure = config.oscilloscope_rigol_manager.send_command(command)
    
    if measure is None:
        return_msg["infos"].append("Erreur lors de la mesure AC.Vrms 1.")
        return 1, return_msg
    
    log(f"Mesure AC.Vrms 1 : {measure}V, min={min}, max={max}", "blue")
    id = config.save_value(step_name_id, "AC_Vrms_1", float(measure), "V", min_value=min, max_value=max)

    measure_float = float(measure)
    min_float = float(min)
    max_float = float(max)
    
    if measure_float < min_float or measure_float > max_float:
        return_msg["infos"].append(f"Mesure AC.Vrms 1 hors tolérance : {measure}V, min={min}, max={max}")
        return 1, return_msg
    
    config.db.update_by_id("skvp_float", id, {"valid": 1})    

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