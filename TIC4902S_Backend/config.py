SERVICE_FOLDER = "services/"
RUN_COMMAND = ["fastapi", "dev"]
PORT_COMMAND = "--port"

def serviceCommand(filename, port):
    return RUN_COMMAND + [f"{SERVICE_FOLDER}{filename}", PORT_COMMAND, str(port)]

SERVICES = {
    "AIService": {"cmd": serviceCommand("aiService.py", 8001)}
}