import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
from ics import Calendar, Event
import pytz

# URL to request
url = 'https://portales.uloyola.es/LoyolaHorario/horario.xhtml?curso=2025%2F26&tipo=G&titu=403&campus=2&ncurso=1&grupo=A'


def get_json():
    # Send the GET request
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the response content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all <script> tags with type="text/javascript"
        script_tags = soup.find_all('script', type='text/javascript')
        
        # Initialize a variable to store the desired function content
        render_horario_js_content = None

        # Iterate through script tags to find the one containing `renderHorarioJs`
        for script in script_tags:
            if 'function renderHorarioJs' in (script.string or ''):
                render_horario_js_content = script.string
                break  # Stop after finding the first occurrence

        # If the function was found, search for `eventos_calendario`
        if render_horario_js_content:
            # Find the variable definition
            eventos_calendario_match = re.search(r'var eventos_calendario = (\[.*?\]);', render_horario_js_content, re.DOTALL)
            
            if eventos_calendario_match:
                # Extract the JSON-like content
                eventos_calendario_content = eventos_calendario_match.group(1)

                # Parse the content to validate it's proper JSON
                try:
                    eventos_calendario_json = json.loads(eventos_calendario_content)

                    # Save it to a JSON file
                    with open('eventos_calendario.json', 'w', encoding='utf-8') as file:
                        json.dump(eventos_calendario_json, file, ensure_ascii=False, indent=4)
                    print("Variable 'eventos_calendario' saved to 'eventos_calendario.json'.")
                except json.JSONDecodeError:
                    print("Error: The content of eventos_calendario is not valid JSON.")
            else:
                print("Variable 'eventos_calendario' not found in the script content.")
        else:
            print("No <script> tag containing 'renderHorarioJs' found in the response.")
    else:
        print(f"Failed to retrieve the content. Status code: {response.status_code}")


# Load the JSON data
def load_json(filename):
    with open(filename, 'r') as f:
        return json.load(f)

# Create an iCalendar file
def create_ics():
    # Load the JSON data
    with open('eventos_calendario.json', 'r', encoding='utf-8') as file:
        events_data = json.load(file)

    # Create a calendar
    calendar = Calendar()

    # Loop through each event in JSON data and add it to the calendar
    for item in events_data:
        event = Event()
        event.name = item.get('title', 'No Title')
        
        # Start and end time if available
        start_time = item.get('start')
        end_time = item.get('end')
        
        if start_time:
            event.begin = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if end_time:
            event.end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        # Additional fields for event description
        extended_props = item.get('extendedProps', {})
        descripcion = extended_props.get('descripcion', 'No description')
        profesor = extended_props.get('profesor', 'No professor')
        obs = extended_props.get('obs', False)
        examen = extended_props.get('examen', False)
        
        # Add details to the event's description field
        details = f"Description: {descripcion}\nProfessor: {profesor}\nObservations: {obs}\nExam: {examen}"
        event.description = details
        
        # Set location if available in the title
        location_info = item.get('title', '').split("Aula: ")
        event.location = location_info[-1].strip() if len(location_info) > 1 else 'No Location'
        
        # Add event to calendar
        calendar.events.add(event)

    # Save the calendar to an .ics file
    with open('calendario.ics', 'w', encoding='utf-8') as f:
        f.writelines(calendar)

    print("ICS file created successfully with detailed information!")
    
get_json()
events = load_json("eventos_calendario.json")
create_ics()
