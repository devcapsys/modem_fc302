# -*- coding: utf-8 -*-
import sys, os, json
if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
from datetime import datetime
import configuration  # Custom
from modules.capsys_mysql_command.capsys_mysql_command import (GenericDatabaseManager, DatabaseConfig, Operator) # Custom
from modules.capsys_serial_instrument_manager.fc302_friendcom.fc302_friendcom import ModemFc302Manager  # Custom
from modules.capsys_serial_instrument_manager.ds1104_rigol.ds1104_rigol import Ds1104RigolManager  # Custom
from configuration import VERSION, get_project_path

def get_info():
    return "Cette étape crée device_under_test et initialise le dut via RS232."    

def init_database_and_checks(log, config: configuration.AppConfig, update_percentage=lambda x: None):
    # Ensure db is initialized
    if not hasattr(config, "db") or config.db is None:
        return 1, "config.db n'est pas initialisé."

    # Check operator format
    if not isinstance(config.arg.operator, str) or len(config.arg.operator.split()) < 2:
        return (1, "Le champ 'operator' doit contenir au moins un prénom et un nom.")

    # Retrieve operator from database
    operators = config.db.get_by_column("operator", "name", config.arg.operator.split()[1])
    if not operators:
        return 1, f"Aucun opérateur {config.arg.operator.split()[1]} trouvé dans la base de données."
    operator = Operator(**operators[0])
    operator_id = operator.id

    if config.arg.product_list_id != configuration.PRODUCT_LIST_ID_DEFAULT:
        return_msg = f"Le product_list_id spécifié ({config.arg.product_list_id}) ne correspond pas au product_list_id par défaut ({configuration.PRODUCT_LIST_ID_DEFAULT})."
        return (1, return_msg)
    
    # Retrieve product_list from database
    config.arg.product_list = config.db.get_by_id("product_list", config.arg.product_list_id)
    if not config.arg.product_list:
        return 1, "Aucun produit trouvé dans la base de données."

    # Retrieve bench_composition from database
    bench_composition_id = config.arg.product_list.get("bench_composition_id")
    bench_composition_raw = config.db.get_by_column("bench_composition", "bench_composition_id", bench_composition_id)
    bench_composition = bench_composition_raw if bench_composition_raw else []
    if not bench_composition:
        return (1, "Problème lors de la récupération de la composition du banc dans la base de données.")

    # Retrieve all externals devices from database
    external_devices = []
    for external_device in bench_composition:
        external_device_data = config.db.get_by_id("external_device", external_device["external_device_id"])
        if external_device_data:
            external_devices.append(external_device_data)
    if not external_devices:
        return (1, "Problème lors de la récupération des périphériques externes dans la base de données.")

    # Retrieve script from database
    script_data = config.db.get_by_column("script", "product_list_id", config.arg.product_list_id)
    for script in script_data:
        if script.get("valid") == 0:
            script_data.remove(script)
    if not script_data:
        return (1, "Problème lors de la récupération du script dans la base de données.")
    # Remove the "file" key if it exists because it's too large to store in the database
    if "file" in script_data[0]:
        del script_data[0]["file"]
    script = script_data

    # Retrieve parameters_group from database
    parameters_group_id = config.arg.product_list.get("parameters_group_id")
    parameters_group_raw = config.db.get_by_column("parameters_group", "parameters_group_id", parameters_group_id)
    parameters_group = parameters_group_raw if parameters_group_raw else []
    if not parameters_group:
        return (1, "Problème lors de la récupération des groupes de paramètres dans la base de données.")

    # Retrieve all parameters from database
    parameters = []
    for group in parameters_group:
        parameters_data = config.db.get_by_id("parameters", group["parameters_id"])
        if parameters_data:
            parameters.append(parameters_data)
    if not parameters:
        return (1, "Problème lors de la récupération des paramètres dans la base de données.")

    # Retrieve and save config.json from database
    # config.json is used to store values used during the test
    data_str = None
    id = None
    for parameter in parameters:
        config_json_name = configuration.CONFIG_JSON_NAME
        if parameter.get("name") == config_json_name:
            data_str = parameter.get("file")
            id = parameter.get("id")
            txt = f"Le fichier de config utilisé correspond à la ligne id={id} de la table parameters"
            log(txt, "blue")
    if data_str == None:
        return (1, "Le fichier config n'est pas présent dans la ddb.")
    
    # Write and read config.json file with proper exception handling
    config_path = get_project_path("config.json")
    configJson = {}
    try:
        # Write the config file
        with open(config_path, "wb") as f:
            f.write(data_str)
        
        # Read the config file immediately after writing
        with open(config_path, 'r', encoding='utf-8') as json_file:
            configJson = json.load(json_file)
    except Exception as e:
        # Clean up the file if it was created but reading failed
        try:
            if os.path.exists(config_path):
                os.remove(config_path)
        except Exception as cleanup_error:
            log(f"Problème lors du nettoyage du fichier config : {cleanup_error}", "yellow")
        return 1, f"Problème lors de la création/lecture de config.json : {e}"

    # Initialize configItems attributes from the config JSON mapping pins and keys from config.json in ddb
    config.configItems.init_config_items(configJson)

    # Create device_under_test
    device_under_test_data = {
        "operator_id": operator_id,
        "product_id": config.arg.product_list_id,
        "sn": config.arg.article,
        "date": datetime.now(),
        "result": 0,
        "of": config.arg.of,
        "command_number": config.arg.commande,
        "client": "",
        "failure_label": "",
        "name": config.arg.name
    }
    config.device_under_test_id = config.db.create("device_under_test", device_under_test_data)

    log(f"Device Under Test créé avec l'ID {config.device_under_test_id}.", "purple")

    step_name_id = config.db.create("step_name",
        {"device_under_test_id": config.device_under_test_id, "step_name": os.path.splitext(os.path.basename(__file__))[0]}
    )

    # Create the data dictionary to be inserted into skvp_json
    data = {
        "device_under_test_id": config.device_under_test_id,
        "operator": operator.to_dict() if hasattr(operator, 'to_dict') else vars(operator),
        "product_list": config.arg.product_list,  # already a dictionary
        "bench_composition": bench_composition,  # already a list of dictionaries
        "external_devices": external_devices,   # already a list of dictionaries
        "script": script,                       # already a dictionary
        "parameters_group": parameters_group,   # already a list of dictionaries
        "parameters": parameters,               # already a list of dictionaries
    }

    config.save_value(step_name_id, "VERSION", VERSION)
    config.save_value(step_name_id, "data_used_for_test", json.dumps(data, indent=4, ensure_ascii=False, default=str))
    config.save_value(step_name_id, "id_fichier_config", id)

    return 0, step_name_id

def init_rs232_dut(config: configuration.AppConfig):
    # Ensure db is initialized
    if not hasattr(config, "db") or config.db is None:
        return 1, "Erreur : config.db n'est pas initialisé."
    
    config.modem_fc302_manager = ModemFc302Manager(baudrate=int(config.configItems.rs232_dut.baudrate), debug=config.arg.show_all_logs)
    config.modem_fc302_manager.open_with_port(port=config.configItems.rs232_dut.port)
    
    return_msg = f"Modèle: {config.modem_fc302_manager.model}, Firmware: {config.modem_fc302_manager.firmware_version}, Fréquence: {config.modem_fc302_manager.frequency_range}, S/N: {config.modem_fc302_manager.serial_number}, port: {config.modem_fc302_manager.port}, baudrate: {config.modem_fc302_manager.baudrate}"
    return 0, return_msg

def init_ds1104_rigol(config: configuration.AppConfig):
    # Ensure db is initialized
    if not hasattr(config, "db") or config.db is None:
        return 1, "Erreur : config.db n'est pas initialisé."
    
    config.oscilloscope_rigol_manager = Ds1104RigolManager()
    
    return_msg = f"Modèle: {config.oscilloscope_rigol_manager.device_model}, S/N: {config.oscilloscope_rigol_manager.sn}, Software Version: {config.oscilloscope_rigol_manager.software_version}"
    return 0, return_msg

def run_step(log, config: configuration.AppConfig, update_percentage=lambda x: None):
    step_name = os.path.splitext(os.path.basename(__file__))[0]
    return_msg = {"step_name": step_name, "infos": []}
    log(f"show_all_logs = {config.arg.show_all_logs}", "blue")
    status, step_name_id = init_database_and_checks(log, config)
    if status != 0:
        return_msg["infos"].append(f"{step_name_id}")
        return status, return_msg
    
    log("Initialisation de la connexion RS232 au DUT...", "cyan")
    status, msg = init_rs232_dut(config)
    if status != 0:
        return status, msg    
    log(msg, "blue")
    
    log("Initialisation de la connexion DS1104 Rigol...", "cyan")
    status, msg = init_ds1104_rigol(config)
    if status != 0:
        return status, msg    
    log(msg, "blue")

    return_msg["infos"].append(f"Initialisation OK")
    return 0, return_msg

if __name__ == "__main__":
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
    
    success_init, message_init = run_step(log_message, config)
    print(message_init)
    
    # Clear ressources
    from steps.zz.fin_du_test import run_step as run_step_fin_du_test
    success_end, message_end = run_step_fin_du_test(log_message, config)
    print(message_end)
