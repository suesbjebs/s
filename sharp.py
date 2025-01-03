import os
import requests
import time
import logging
from getpass import getpass
import paramiko
import signal

# Constants for file paths
TOKEN_FILE = 'token.txt'
DB_FILE = 'db.txt'

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_github_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as file:
            return file.read().strip()
    
    token = getpass('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: ')
    with open(TOKEN_FILE, 'w') as file:
        file.write(token)
    return token

def get_last_command():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as file:
            data = file.readlines()
            if data:
                return data[0].strip()
    return None

def store_last_command(command):
    with open(DB_FILE, 'w') as file:
        file.write(command)

def get_used_options():
    used_options = set()
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as file:
            data = file.readlines()
            if len(data) > 1:
                used_options = set(data[1].strip().split(','))
    return used_options

def store_used_option(option):
    used_options = get_used_options()
    used_options.add(option)
    last_command = get_last_command()
    with open(DB_FILE, 'w') as file:
        if last_command:
            file.write(f"{last_command}\n")
        file.write(','.join(used_options))

def authenticate_github():
    token = get_github_token()
    session = requests.Session()
    session.headers.update({'Authorization': f'token {token}'})
    response = session.get('https://api.github.com/user')
    if response.status_code == 200:
        logging.info('Successfully authenticated with GitHub!')
        return session
    logging.error(f'Failed to authenticate with GitHub: {response.status_code} - {response.text}')
    return None

def create_new_codespace(session):
    repo_url = 'https://api.github.com/user/repos'
    repos = session.get(repo_url).json()
    if repos:
        random_repo = repos[0]['full_name']
        create_url = f'https://api.github.com/repos/{random_repo}/codespaces'
        payload = {
            'machine': 'basicLinux',
            'location': 'WestEurope'
        }
        response = session.post(create_url, json=payload)
        if response.status_code == 201:
            logging.info('Successfully created a new Codespace')
            return None
        logging.error(f'Failed to create a Codespace: {response.status_code} - {response.text}')
        return None
    logging.warning('No repositories found')

def keep_codespaces_alive(session, command):
    codespaces_url = 'https://api.github.com/user/codespaces'
    codespaces_response = session.get(codespaces_url)
    if codespaces_response.status_code == 200:
        codespaces = codespaces_response.json()
        for codespace in codespaces['codespaces']:
            if codespace['state'] == 'Shutdown':
                start_url = f'https://api.github.com/user/codespaces/{codespace["name"]}/start'
                start_response = session.post(start_url)
                if start_response.status_code == 202:
                    logging.info(f'Successfully started Codespace: {codespace["name"]}')
                    wait_for_terminal(session, codespace['name'], command)
                else:
                    logging.error(f'Failed to start Codespace: {codespace["name"]} - {start_response.status_code} - {start_response.text}')
            logging.info(f'Codespace {codespace["name"]} is alive.')
    else:
        logging.error(f'Failed to fetch Codespaces: {codespaces_response.status_code} - {codespaces_response.text}')
    time.sleep(5)

def wait_for_terminal(session, codespace_name, command):
    logging.info(f'Waiting for Codespace {codespace_name} to become available...')
    codespace_url = f'https://api.github.com/user/codespaces/{codespace_name}'
    response = session.get(codespace_url)
    if response.status_code == 200:
        codespace = response.json()
        if codespace['state'] == 'Available':
            logging.info(f'Codespace {codespace_name} is now available. Executing command.')
            execute_command(session, codespace_name, command)
            return None
    logging.error(f'Failed to get status for Codespace: {codespace_name} - {response.status_code} - {response.text}')
    time.sleep(5)

def execute_command(session, codespace_name, command):
    logging.info(f'Executing command: {command} on Codespace: {codespace_name}')
    # Here you can implement the actual command execution logic.

def delete_all_codespaces(session):
    codespaces_url = 'https://api.github.com/user/codespaces'
    codespaces_response = session.get(codespaces_url)
    if codespaces_response.status_code == 200:
        codespaces = codespaces_response.json()
        for codespace in codespaces['codespaces']:
            delete_url = f'https://api.github.com/user/codespaces/{codespace["name"]}'
            delete_response = session.delete(delete_url)
            if delete_response.status_code == 204:
                logging.info(f'Successfully deleted Codespace: {codespace["name"]}')
            else:
                logging.error(f'Failed to delete Codespace: {codespace["name"]} - {delete_response.status_code} - {delete_response.text}')
    else:
        logging.error(f'Failed to fetch Codespaces: {codespaces_response.status_code} - {codespaces_response.text}')

def handle_option(option, session):
    used_options = get_used_options()
    if option == '1' and '1' not in used_options:
        create_new_codespace(session)
        store_used_option('1')
        return None
    if option == '2' and '2' not in used_options:
        last_command = get_last_command()
        if last_command:
            keep_codespaces_alive(session, last_command)
        command = input('Enter the command you want to run on Codespace terminal: ')
        store_last_command(command)
        keep_codespaces_alive(session, command)
        store_used_option('2')
        return None
    if option == '3' and '3' not in used_options:
        delete_all_codespaces(session)
        store_used_option('3')
        return None
    logging.warning('Invalid option or option already used')

def run_command_on_vps(command):
    ssh_host = os.getenv('VPS_IP')  # Replace with your VPS IP
    ssh_user = os.getenv('VPS_USER')  # Replace with your VPS username
    ssh_password = getpass('Enter VPS Password: ')  # Securely get password
    remote_dir = '/root'  # Adjust as needed

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ssh_host, username=ssh_user, password=ssh_password, timeout=10)  # Added timeout
        logging.info("Successfully connected to VPS.")
        stdin, stdout, stderr = ssh.exec_command(f'cd {remote_dir} && {command}')
        logging.info(stdout.read().decode())
        logging.error(stderr.read().decode())
    except Exception as e:
        logging.error(f'Failed to connect to VPS: {str(e)}')
    finally:
        ssh.close()

def check_vps_connection():
    ssh_host = os.getenv('VPS_IP')  # Replace with your VPS IP
    ssh_user = os.getenv('VPS_USER')  # Replace with your VPS username
    ssh_password = getpass('Enter VPS Password: ')  # Securely get password

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ssh_host, username=ssh_user, password=ssh_password, timeout=10)  # Added timeout
        logging.info("Successfully connected to VPS.")
        ssh.close()
        return True
    except Exception as e:
        logging.error(f"Failed to connect to VPS: {str(e)}")
        return False

# Graceful shutdown
def signal_handler(sig, frame):
    logging.info("Gracefully shutting down...")
    exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    if not check_vps_connection():
        logging.error("Exiting the script because the VPS connection failed.")
        exit(1)

    session = authenticate_github()
    if session:
        logging.info('Running option 2 directly:')
        last_command = get_last_command()
        if last_command:
            keep_codespaces_alive(session, last_command)
        else:
            logging.warning('No command stored in db.txt. Please run the script again with a command.')
