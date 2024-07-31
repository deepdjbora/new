from nicegui import ui
import pandas as pd
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

csv_file = 'trade_log.csv'

# Function to read CSV and convert to HTML table
def read_csv_to_html(csv_file):
    try:
        df = pd.read_csv(csv_file)
        return df.to_html(classes='table table-striped', index=False)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return "<p>Error loading data</p>"

# NiceGUI UI Setup
def setup_ui():
    global html_element  # Make html_element accessible globally
    with ui.column():
        ui.label('Trading Log')
        html_element = ui.html(read_csv_to_html(csv_file))  # Store the html element

# File System Event Handler
class LogFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        print(f"File modified: {event.src_path}")
        if event.src_path == csv_file:
            try:
                new_content = read_csv_to_html(csv_file)
                html_element.set_content(new_content)
                print("UI updated with new content.")
            except Exception as e:
                print(f"Error updating UI: {e}")

# Main Function
def main():
    setup_ui()
    event_handler = LogFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    print("Observer started.")

    ui.run()

    # Clean up observer on exit
    observer.stop()
    observer.join()
    print("Observer stopped.")

# Run the NiceGUI App
if __name__ in {"__main__", "__mp_main__"}:
    main()
