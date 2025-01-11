import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog
from PIL import Image, ImageTk, ImageSequence  # Requires Pillow library
import subprocess
import threading
import platform
import re
import time
import shutil
import os
import logging
import sys
from packaging import version  # Requires 'packaging' library

# --- Logging Configuration ---
logging.basicConfig(
    filename='dockerman.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Function to Determine Resampling Filter ---
def get_resampling_filter():
    try:
        pillow_version = version.parse(Image.__version__)
        if pillow_version >= version.parse("10.0.0"):
            return Image.Resampling.LANCZOS
        else:
            return Image.ANTIALIAS
    except Exception as e:
        logging.exception(f"Failed to determine Pillow version: {str(e)}")
        return Image.ANTIALIAS  # Default fallback

# --- Exit Application Function ---
def exit_application():
    """Handles the exit operation for the application."""
    if messagebox.askokcancel("Quit", "Do you really want to quit?"):
        logging.info("Application exited by user.")
        root.quit()

# --- ProgressDialog Class ---
class ProgressDialog:
    """
    Displays a modal progress dialog with an indeterminate progress bar.
    """
    def __init__(self, parent, title="Please Wait", message="Processing..."):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("300x100")
        self.top.transient(parent)
        self.top.grab_set()
        self.top.resizable(False, False)

        # Center the dialog
        parent.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        dialog_width = 300
        dialog_height = 100

        pos_x = parent_x + (parent_width // 2) - (dialog_width // 2)
        pos_y = parent_y + (parent_height // 2) - (dialog_height // 2)
        self.top.geometry(f"{dialog_width}x{dialog_height}+{pos_x}+{pos_y}")

        # Message Label
        self.label = tk.Label(self.top, text=message, font=('Arial', 10))
        self.label.pack(pady=10)

        # Indeterminate Progress Bar
        self.progress = ttk.Progressbar(self.top, mode='indeterminate')
        self.progress.pack(pady=10, padx=20, fill=tk.X)
        self.progress.start(10)  # Adjust speed as needed

    def close(self):
        """Closes the progress dialog."""
        self.progress.stop()
        self.top.destroy()

# --- Function to Run Docker Commands ---
def run_docker_command(command):
    """
    Executes a Docker command and returns its stdout and stderr.
    """
    logging.debug(f"Executing command: {command}")
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            logging.error(f"Command failed: {command}\nError: {stderr.strip()}")
        else:
            logging.info(f"Command succeeded: {command}")
        return stdout, stderr
    except Exception as e:
        logging.exception(f"Exception while executing command: {command}\nError: {str(e)}")
        return "", f"Error: {str(e)}"

# --- Function to Check if Docker is Running ---
def is_docker_running():
    """
    Checks if Docker is running by executing 'docker info'.
    """
    try:
        subprocess.run("docker info", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.debug("Docker is running.")
        return True
    except:
        logging.debug("Docker is not running.")
        return False

# --- Function to Execute Commands and Update Output Box ---
def execute_command(command, output_box):
    """
    Executes a command, logs it, and updates the output box in the GUI.
    """
    stdout, stderr = run_docker_command(command)
    output_box.config(state='normal')
    output_box.insert(tk.END, f"$ {command}\n")
    if stdout:
        output_box.insert(tk.END, f"{stdout}\n")
    if stderr:
        output_box.insert(tk.END, f"Error: {stderr}\n")
    output_box.see(tk.END)
    output_box.config(state='disabled')
    # Log errors explicitly if any
    if stderr:
        logging.error(f"Command '{command}' failed with error: {stderr.strip()}")
    else:
        logging.info(f"Command '{command}' executed successfully.")

# --- Helper Function to Validate Docker IDs ---
def validate_docker_id(docker_id):
    """
    Validates Docker IDs (Containers, Images, Networks).
    """
    pattern = re.compile(r'^[a-zA-Z0-9]{12,}$')
    is_valid = pattern.match(docker_id) is not None
    logging.debug(f"Validating Docker ID '{docker_id}': {'Valid' if is_valid else 'Invalid'}")
    return is_valid

# --- Helper Function to Get Selected Item ---
def selected_item():
    """
    Retrieves the selected item's ID and type from the Treeview.
    """
    selected = tree.focus()
    if not selected:
        messagebox.showwarning("No Selection", "Please select an item from the list.")
        return None, None
    item = tree.item(selected)
    item_id = item['text']
    item_type = item['values'][0]
    if not validate_docker_id(item_id) and item_type != "project":
        messagebox.showerror("Invalid ID", f"The selected {item_type} ID '{item_id}' is invalid.")
        return None, None
    logging.debug(f"Selected item - ID: {item_id}, Type: {item_type}")
    return item_id, item_type

# --- Progress Handler ---
def run_with_progress(operation_func, *args, **kwargs):
    """
    Runs a given function with a progress dialog.
    """
    progress = ProgressDialog(root, message="Please wait...")
    def target():
        operation_func(*args, **kwargs)
        root.after(0, progress.close)
    threading.Thread(target=target, daemon=True).start()

# --- Right-Click Context Menu Creation ---
def create_context_menu(item_type):
    """
    Creates a context menu based on the type of the selected item.
    """
    menu = tk.Menu(root, tearoff=0)
    if item_type == "container":
        menu.add_command(label="Start Container", command=start_container)
        menu.add_command(label="Stop Container", command=stop_container)
        menu.add_command(label="Remove Container", command=remove_container)
        menu.add_command(label="Rebuild Container", command=rebuild_container)
        menu.add_command(label="View Logs", command=view_logs)
        menu.add_command(label="Inspect Container", command=inspect_container)
        menu.add_command(label="Open Terminal", command=open_terminal)
        menu.add_command(label="Backup Container", command=backup_container)
        menu.add_command(label="Copy Container", command=copy_container)
    elif item_type == "image":
        menu.add_command(label="Remove Image", command=remove_image)
    elif item_type == "network":
        menu.add_command(label="Remove Network", command=remove_network)
    elif item_type == "project":
        menu.add_command(label="Edit Project Files", command=edit_project_files)
        menu.add_command(label="Delete Project", command=delete_project)
    return menu

# --- Function to Handle Right-Click Events ---
def on_right_click(event):
    """
    Handles the right-click event on the Treeview to show context menus.
    """
    try:
        # Identify the region and row under the cursor
        region = tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = tree.identify_row(event.y)
        if row_id:
            tree.selection_set(row_id)
            selected_item_id, selected_item_type = selected_item()
            if selected_item_id:
                context_menu = create_context_menu(selected_item_type)
                context_menu.tk_popup(event.x_root, event.y_root)
    except Exception as e:
        logging.exception(f"Exception in on_right_click: {str(e)}")
    finally:
        try:
            context_menu.grab_release()
        except:
            pass

# --- Function to Update Docker Status Indicator ---
def update_docker_status():
    """
    Periodically updates the Docker status indicator in the GUI.
    """
    while True:
        status = is_docker_running()
        if status:
            status_indicator.config(bg='green')
            status_label.config(text="Docker Status: Running")
        else:
            status_indicator.config(bg='red')
            status_label.config(text="Docker Status: Not Running")
        time.sleep(5)  # Update every 5 seconds

# --- Functions for Right-Click Actions ---

# Container Actions
def start_container():
    container_id, _ = selected_item()
    if container_id:
        # Display start animation
        display_animation('startdocker.gif')
        run_with_progress(start_container_thread, container_id)

def start_container_thread(container_id):
    execute_command(f"docker start {container_id}", output_box)
    refresh_containers()
    # Hide start animation
    root.after(500, hide_animation)  # Slight delay to ensure animation is visible

def stop_container():
    container_id, _ = selected_item()
    if container_id:
        # Display stop animation
        display_animation('stopdocker.gif')
        run_with_progress(stop_container_thread, container_id)

def stop_container_thread(container_id):
    execute_command(f"docker stop {container_id}", output_box)
    refresh_containers()
    # Hide stop animation
    root.after(500, hide_animation)  # Slight delay to ensure animation is visible

def remove_container():
    container_id, _ = selected_item()
    if container_id:
        confirm = messagebox.askyesno("Confirm Remove", f"Are you sure you want to remove container '{container_id}'?")
        if confirm:
            run_with_progress(remove_container_thread, container_id)

def remove_container_thread(container_id):
    execute_command(f"docker rm -f {container_id}", output_box)
    refresh_containers()

def rebuild_container():
    container_id, _ = selected_item()
    if container_id:
        image_name = simpledialog.askstring("Rebuild Container", "Enter the image name to recreate the container (e.g., myapp:latest):")
        if image_name:
            if not image_name.strip():
                messagebox.showerror("Invalid Input", "Image name cannot be empty.")
                return
            run_with_progress(rebuild_container_thread, container_id, image_name)
        else:
            messagebox.showwarning("Input Required", "Rebuild canceled. No image name provided.")

def rebuild_container_thread(container_id, image_name):
    commands = [
        f"docker stop {container_id}",
        f"docker rm {container_id}",
        f"docker run -d --name {container_id} {image_name}"
    ]
    for cmd in commands:
        execute_command(cmd, output_box)
    refresh_containers()
    refresh_images()


def create_new_project():
    """
    Prompts the user to create a new Docker project.
    Creates a project directory with a default Dockerfile, app.py, and requirements.txt.
    """
    project_name = simpledialog.askstring("Create Project", "Enter the project name:")
    if not project_name or not project_name.strip():
        messagebox.showerror("Invalid Input", "Project name cannot be empty.")
        return

    # Create project directory under a base projects directory
    base_dir = os.path.join(os.path.expanduser("~"), "DockMan_Projects")
    project_dir = os.path.join(base_dir, project_name.strip())
    
    if os.path.exists(project_dir):
        messagebox.showerror("Project Exists", f"A project with the name '{project_name}' already exists.")
        return

    try:
        # Create project folder structure
        os.makedirs(project_dir)
        app_dir = os.path.join(project_dir, "app")
        os.makedirs(app_dir)

        # Create Dockerfile
        dockerfile_content = (
            "FROM python:3.8-slim\n"
            "WORKDIR /app\n"
            "COPY requirements.txt requirements.txt\n"
            "RUN pip install -r requirements.txt\n"
            "COPY . .\n"
            'CMD ["python", "app.py"]\n'
        )
        with open(os.path.join(project_dir, "Dockerfile"), "w") as dockerfile:
            dockerfile.write(dockerfile_content)

        # Create requirements.txt
        with open(os.path.join(project_dir, "requirements.txt"), "w") as requirements:
            requirements.write("flask\n")

        # Create a basic app.py
        app_py_content = (
            "from flask import Flask\n"
            "app = Flask(__name__)\n\n"
            '@app.route("/")\n'
            "def hello():\n"
            "    return 'Hello from Docker!'\n\n"
            "if __name__ == '__main__':\n"
            "    app.run(host='0.0.0.0', port=5000)\n"
        )
        with open(os.path.join(app_dir, "app.py"), "w") as app_py:
            app_py.write(app_py_content)

        messagebox.showinfo("Project Created", f"Project '{project_name}' created successfully.")
        refresh_projects()
    except Exception as e:
        logging.exception(f"Failed to create project '{project_name}': {str(e)}")
        messagebox.showerror("Error", f"Failed to create project '{project_name}': {str(e)}")

def view_logs():
    container_id, _ = selected_item()
    if container_id:
        logs, stderr = run_docker_command(f"docker logs {container_id}")
        if stderr:
            messagebox.showerror("Error Fetching Logs", f"Error: {stderr}")
            return
        log_window = tk.Toplevel(root)
        log_window.title(f"Logs - {container_id}")
        log_window.geometry("800x600")
        
        log_text = scrolledtext.ScrolledText(log_window, width=100, height=35, state='disabled', font=('Courier', 9))
        log_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        log_text.config(state='normal')
        log_text.insert(tk.END, logs)
        log_text.config(state='disabled')

def inspect_container():
    container_id, _ = selected_item()
    if container_id:
        inspect, stderr = run_docker_command(f"docker inspect {container_id}")
        if stderr:
            messagebox.showerror("Error Inspecting Container", f"Error: {stderr}")
            return
        inspect_window = tk.Toplevel(root)
        inspect_window.title(f"Inspect - {container_id}")
        inspect_window.geometry("800x600")
        
        inspect_text = scrolledtext.ScrolledText(inspect_window, width=100, height=35, state='disabled', font=('Courier', 9))
        inspect_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        inspect_text.config(state='normal')
        inspect_text.insert(tk.END, inspect)
        inspect_text.config(state='disabled')

def open_terminal():
    container_id, item_type = selected_item()
    if item_type != "container":
        messagebox.showwarning("Invalid Selection", "Please select a container to open terminal.")
        return
    if container_id:
        current_os = platform.system()
        if current_os in ["Linux", "Darwin"]:  # Unix-like systems
            # List of common terminal emulators
            terminals = ["gnome-terminal", "konsole", "xfce4-terminal", "xterm", "lxterminal", "terminator"]
            terminal_cmd = None
            for term in terminals:
                if shutil.which(term):
                    if term == "gnome-terminal":
                        # '--' indicates the end of options
                        terminal_cmd = f"gnome-terminal -- bash -c 'docker exec -it {container_id} /bin/bash; exec bash'"
                    elif term == "konsole":
                        terminal_cmd = f"konsole -e bash -c 'docker exec -it {container_id} /bin/bash; exec bash'"
                    elif term == "xfce4-terminal":
                        terminal_cmd = f"xfce4-terminal --hold --command='docker exec -it {container_id} /bin/bash'"
                    elif term == "xterm":
                        terminal_cmd = f"xterm -hold -e docker exec -it {container_id} /bin/bash"
                    elif term == "lxterminal":
                        terminal_cmd = f"lxterminal -e bash -c 'docker exec -it {container_id} /bin/bash; exec bash'"
                    elif term == "terminator":
                        terminal_cmd = f"terminator -x bash -c 'docker exec -it {container_id} /bin/bash; exec bash'"
                    break  # Use the first available terminal emulator
            if terminal_cmd:
                try:
                    subprocess.Popen(terminal_cmd, shell=True)
                    logging.info(f"Opened terminal for container '{container_id}' using '{term}'.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to open terminal: {str(e)}")
                    logging.exception(f"Failed to open terminal: {str(e)}")
            else:
                messagebox.showerror("No Terminal Found", "No supported terminal emulator found. Please install one of the following: gnome-terminal, konsole, xfce4-terminal, xterm, lxterminal, terminator.")
                logging.warning("No supported terminal emulator found.")
        elif current_os == "Windows":
            # Open external PowerShell window
            try:
                subprocess.Popen(["powershell", "-NoExit", f"docker exec -it {container_id} powershell"])
                logging.info(f"Opened PowerShell terminal for container '{container_id}'.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open terminal: {str(e)}")
                logging.exception(f"Failed to open PowerShell terminal: {str(e)}")
        else:
            messagebox.showerror("Unsupported OS", f"Your operating system ({current_os}) is not supported for the integrated terminal feature.")
            logging.warning(f"Unsupported OS for terminal: {current_os}")
    else:
        messagebox.showwarning("No Selection", "Please select a container to open terminal.")

# Image Actions
def remove_image():
    image_id, _ = selected_item()
    if image_id:
        confirm = messagebox.askyesno("Confirm Remove", f"Are you sure you want to remove image '{image_id}'?")
        if confirm:
            run_with_progress(remove_image_thread, image_id)

def remove_image_thread(image_id):
    execute_command(f"docker rmi -f {image_id}", output_box)
    refresh_images()

# Network Actions
def remove_network():
    network_id, _ = selected_item()
    if network_id:
        confirm = messagebox.askyesno("Confirm Remove", f"Are you sure you want to remove network '{network_id}'?")
        if confirm:
            run_with_progress(remove_network_thread, network_id)

def remove_network_thread(network_id):
    execute_command(f"docker network rm {network_id}", output_box)
    refresh_networks()

# Cleanup All Docker Resources
def clean_all():
    confirm = messagebox.askyesno("Confirm Clean All", "Are you sure you want to clean all Docker resources? This will remove all stopped containers, unused networks, dangling images, and build cache.")
    if confirm:
        run_with_progress(clean_all_thread)

def clean_all_thread():
    execute_command("docker system prune -a -f", output_box)
    refresh_containers()
    refresh_images()
    refresh_networks()

# --- Backup Docker Container ---
def backup_container():
    """
    Backs up a selected Docker container by exporting its filesystem.
    """
    container_id, _ = selected_item()
    if container_id:
        backup_dir = filedialog.askdirectory(title="Select Backup Directory")
        if backup_dir:
            backup_file = os.path.join(backup_dir, f"{container_id}_backup.tar")
            run_with_progress(backup_container_thread, container_id, backup_file)

def backup_container_thread(container_id, backup_file):
    """
    Thread function to handle container backup.
    """
    execute_command(f"docker export {container_id} -o {backup_file}", output_box)
    messagebox.showinfo("Backup Completed", f"Container '{container_id}' has been backed up to:\n{backup_file}")
    logging.info(f"Container '{container_id}' backed up to '{backup_file}'.")
    # Optionally, refresh the containers list if needed
    refresh_containers()

# --- Copy Docker Container ---
def copy_container():
    """
    Copies a selected Docker container by committing it to a new image and creating a new container.
    """
    container_id, _ = selected_item()
    if container_id:
        new_container_name = simpledialog.askstring("Copy Container", "Enter new container name:")
        if new_container_name:
            if not new_container_name.strip():
                messagebox.showerror("Invalid Input", "Container name cannot be empty.")
                return
            # Check if the new container name already exists
            existing_containers, _ = run_docker_command('docker ps -a --format "{{.Names}}"')
            existing_names = existing_containers.strip().split('\n')
            if new_container_name in existing_names:
                messagebox.showerror("Name Conflict", f"A container with the name '{new_container_name}' already exists.")
                return
            run_with_progress(copy_container_thread, container_id, new_container_name)
        else:
            messagebox.showwarning("Input Required", "Copy canceled. No container name provided.")

def copy_container_thread(container_id, new_container_name):
    """
    Thread function to handle container copying.
    """
    # Commit the container to an image
    image_name = f"backup_{container_id}"
    execute_command(f"docker commit {container_id} {image_name}", output_box)
    # Create a new container from the committed image without starting it
    execute_command(f"docker create --name {new_container_name} {image_name}", output_box)
    refresh_containers()
    refresh_images()
    messagebox.showinfo("Copy Completed", f"Container '{container_id}' has been copied to '{new_container_name}' without starting it.")
    logging.info(f"Container '{container_id}' copied to '{new_container_name}' as image '{image_name}'.")

# --- Function to List Docker Items ---
def list_docker_items(command, item_type):
    """
    Lists Docker items (containers, images, networks) and populates the Treeview.
    """
    def task():
        output, stderr = run_docker_command(command)
        if stderr:
            execute_command(f"# Error listing {item_type}s: {stderr}", output_box)
            return
        # Clear Treeview except projects
        for item in tree.get_children():
            if tree.item(item)['values'][0] != "project":
                tree.delete(item)

        # Fetch container stats if item_type is container
        stats = {}
        if item_type == "container":
            stats_output, _ = run_docker_command('docker stats --no-stream --format "{{.Container}}|{{.CPUPerc}}|{{.MemUsage}}"')
            for line in stats_output.strip().split('\n'):
                parts = line.split('|')
                if len(parts) == 3:
                    cid, cpu, mem = parts
                    stats[cid] = (cpu, mem)

        # Populate Treeview with new items
        lines = output.strip().split('\n')
        if not lines or (len(lines) == 1 and not lines[0]):
            return

        for line in lines:
            if not line:
                continue
            parts = line.split('|')
            if item_type == "container":
                # Expected format: ID|Image|Command|CreatedAt|Status|Names
                if len(parts) < 6:
                    continue
                container_id = parts[0]
                image = parts[1]
                command_str = parts[2].strip('"')
                created_at = parts[3]
                status_full = parts[4]
                name = parts[5]

                # Determine if running
                is_running = "Up" in status_full

                # Get CPU and Memory usage
                cpu, mem = stats.get(container_id, ("N/A", "N/A"))

                # Get container size
                size = get_container_size(container_id)

                # Insert into Treeview with tags for coloring
                tree.insert("", "end", text=container_id, values=(
                    "container",
                    name,  # Name column
                    "Running" if is_running else "Stopped",
                    image,
                    command_str,
                    created_at,
                    cpu,
                    mem,
                    size
                ), tags=("running" if is_running else "stopped",))

            elif item_type == "image":
                # Expected format: Repository|Tag|ID|CreatedSince|Size
                if len(parts) < 5:
                    continue
                repository = parts[0]
                tag = parts[1]
                image_id = parts[2]
                created_since = parts[3]
                size = parts[4]

                # Full image name (Repository:Tag)
                full_image_name = f"{repository}:{tag}"

                # Insert into Treeview
                tree.insert("", "end", text=image_id, values=(
                    "image",
                    "-",  # Name not applicable
                    full_image_name,  # Image/Repository
                    "-",  # Command/Tag not applicable
                    created_since,
                    "-",  # CPU not applicable
                    "-",  # Memory not applicable
                    size
                ), tags=("image",))

            elif item_type == "network":
                # Expected format: ID|Name|Driver|Scope
                if len(parts) < 4:
                    continue
                network_id = parts[0]
                name = parts[1]
                driver = parts[2]
                scope = parts[3]

                # Insert into Treeview
                tree.insert("", "end", text=network_id, values=(
                    "network",
                    "-",  # Name not applicable
                    name,
                    driver,
                    scope,
                    "-",  # CPU not applicable
                    "-",  # Memory not applicable
                    "-"
                ), tags=("network",))

        # Apply tags for coloring
        tree.tag_configure('running', background='lightgreen')
        tree.tag_configure('stopped', background='lightcoral')
        tree.tag_configure('image', background='lightblue')
        tree.tag_configure('network', background='lightyellow')

    threading.Thread(target=task).start()

# --- Function to Get Container Size ---
def get_container_size(container_id):
    """
    Retrieves the size of a Docker container.
    """
    size_output, stderr = run_docker_command(f"docker ps -s -a --filter id={container_id} --format '{{{{.Size}}}}'")
    if stderr or not size_output.strip():
        logging.error(f"Failed to get size for container '{container_id}': {stderr.strip()}")
        return "N/A"
    return size_output.strip()

# --- Function to Get Image Size ---
def get_image_size(image_id):
    """
    Retrieves the size of a Docker image.
    """
    size_output, stderr = run_docker_command(f"docker images --format '{{{{.Size}}}}' {image_id}")
    if stderr or not size_output.strip():
        logging.error(f"Failed to get size for image '{image_id}': {stderr.strip()}")
        return "N/A"
    return size_output.strip()

# --- Function to Search Docker Items ---
def search_items():
    """
    Searches Docker items based on user input and updates the Treeview accordingly.
    """
    query = search_entry.get().lower()
    if not query:
        messagebox.showinfo("Search", "Please enter a search term.")
        return
    tree.delete(*tree.get_children())
    def task():
        # Search Containers
        cmd_containers = 'docker ps -a --format "{{.ID}}|{{.Image}}|{{.Command}}|{{.CreatedAt}}|{{.Status}}|{{.Names}}"'
        containers_output, stderr = run_docker_command(cmd_containers)
        if stderr:
            execute_command(f"# Error listing containers: {stderr}", output_box)
        else:
            stats_output, _ = run_docker_command('docker stats --no-stream --format "{{.Container}}|{{.CPUPerc}}|{{.MemUsage}}"')
            stats = {}
            for line in stats_output.strip().split('\n'):
                parts = line.split('|')
                if len(parts) == 3:
                    cid, cpu, mem = parts
                    stats[cid] = (cpu, mem)
            for line in containers_output.strip().split('\n'):
                if not line or query not in line.lower():
                    continue
                parts = line.split('|')
                if len(parts) < 6:
                    continue
                container_id, image, command_str, created_at, status_full, name = parts
                if not validate_docker_id(container_id):
                    continue
                is_running = "Up" in status_full
                cpu, mem = stats.get(container_id, ("N/A", "N/A"))
                size = get_container_size(container_id)
                tree.insert("", "end", text=container_id, values=(
                    "container",
                    name,  # Name column
                    "Running" if is_running else "Stopped",
                    image,
                    command_str,
                    created_at,
                    cpu,
                    mem,
                    size
                ), tags=("running" if is_running else "stopped",))

        # Search Images
        cmd_images = 'docker images --format "{{.Repository}}|{{.Tag}}|{{.ID}}|{{.CreatedSince}}|{{.Size}}"'
        images_output, stderr = run_docker_command(cmd_images)
        if stderr:
            execute_command(f"# Error listing images: {stderr}", output_box)
        else:
            for line in images_output.strip().split('\n'):
                if not line or query not in line.lower():
                    continue
                parts = line.split('|')
                if len(parts) < 5:
                    continue
                repository, tag, image_id, created_since, size = parts
                if not validate_docker_id(image_id):
                    continue
                full_image_name = f"{repository}:{tag}"
                tree.insert("", "end", text=image_id, values=(
                    "image",
                    "-",  # Name not applicable
                    full_image_name,  # Image/Repository
                    "-",  # Command/Tag not applicable
                    created_since,
                    "-",  # CPU not applicable
                    "-",  # Memory not applicable
                    size
                ), tags=("image",))

        # Search Networks
        cmd_networks = 'docker network ls --format "{{.ID}}|{{.Name}}|{{.Driver}}|{{.Scope}}"'
        networks_output, stderr = run_docker_command(cmd_networks)
        if stderr:
            execute_command(f"# Error listing networks: {stderr}", output_box)
        else:
            for line in networks_output.strip().split('\n'):
                if not line or query not in line.lower():
                    continue
                parts = line.split('|')
                if len(parts) < 4:
                    continue
                network_id, name, driver, scope = parts
                if not validate_docker_id(network_id):
                    continue
                tree.insert("", "end", text=network_id, values=(
                    "network",
                    "-",  # Name not applicable
                    name,
                    driver,
                    scope,
                    "-",  # CPU not applicable
                    "-",  # Memory not applicable
                    "-"
                ), tags=("network",))

        # Search Projects
        base_dir = os.path.join(os.path.expanduser("~"), "DockMan_Projects")
        if os.path.exists(base_dir):
            for project_name in os.listdir(base_dir):
                if query not in project_name.lower():
                    continue
                project_path = os.path.join(base_dir, project_name)
                if os.path.isdir(project_path):
                    tree.insert("", "end", text=project_name, values=(
                        "project",
                        "-",  # Name not applicable
                        "-",  # Status not applicable
                        "-",  # Image/Repository not applicable
                        "-",  # Command/Tag not applicable
                        "-",  # Created not applicable
                        "-",  # CPU not applicable
                        "-",  # Memory not applicable
                        "-",  # Size/Scope not applicable
                    ), tags=("project",))
        else:
            logging.warning(f"Base project directory '{base_dir}' does not exist.")

        # Apply tags for coloring
        tree.tag_configure('running', background='lightgreen')
        tree.tag_configure('stopped', background='lightcoral')
        tree.tag_configure('image', background='lightblue')
        tree.tag_configure('network', background='lightyellow')
        tree.tag_configure('project', background='lightgrey')

    threading.Thread(target=task).start()

# --- Function to Get Docker Resource Stats ---
def get_docker_resource_stats():
    """
    Retrieves stats for all containers.
    """
    stats_output, stderr = run_docker_command('docker stats --no-stream --format "{{.Container}}|{{.CPUPerc}}|{{.MemUsage}}"')
    stats = {}
    if not stderr:
        for line in stats_output.strip().split('\n'):
            parts = line.split('|')
            if len(parts) == 3:
                cid, cpu, mem = parts
                stats[cid] = (cpu, mem)
    else:
        logging.error(f"Failed to retrieve container stats: {stderr.strip()}")
    return stats

# --- Project Management ---

def refresh_projects():
    """
    Refreshes the list of Docker projects in the Treeview.
    """
    base_dir = os.path.join(os.path.expanduser("~"), "DockMan_Projects")
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        logging.info(f"Created base project directory at '{base_dir}'.")
    for project_name in os.listdir(base_dir):
        project_path = os.path.join(base_dir, project_name)
        if os.path.isdir(project_path):
            # Insert project into Treeview if not already present
            existing_items = tree.get_children()
            if not any(tree.item(item)['text'] == project_name for item in existing_items):
                tree.insert("", "end", text=project_name, values=(
                    "project",
                    "-",  # Name not applicable
                    "-",  # Status not applicable
                    "-",  # Image/Repository not applicable
                    "-",  # Command/Tag not applicable
                    "-",  # Created not applicable
                    "-",  # CPU not applicable
                    "-",  # Memory not applicable
                    "-",  # Size/Scope not applicable
                ), tags=("project",))
                logging.debug(f"Project '{project_name}' added to Treeview.")

    # Apply tag for projects
    tree.tag_configure('project', background='lightgrey')

def selected_project():
    """
    Retrieves the selected project's name from the Treeview.
    """
    selected = tree.focus()
    if not selected:
        messagebox.showwarning("No Selection", "Please select a project from the list.")
        return None
    item = tree.item(selected)
    item_id = item['text']
    item_type = item['values'][0]
    if item_type != "project":
        messagebox.showwarning("Invalid Selection", "Please select a project.")
        return None
    logging.debug(f"Selected project: {item_id}")
    return item_id

def delete_project():
    """
    Deletes a selected Docker project by removing its directory.
    """
    project_name = selected_project()
    if project_name:
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete project '{project_name}'? This will remove all associated files.")
        if confirm:
            project_dir = os.path.join(os.path.expanduser("~"), "DockMan_Projects", project_name)
            try:
                shutil.rmtree(project_dir)
                messagebox.showinfo("Project Deleted", f"Project '{project_name}' has been deleted successfully.")
                logging.info(f"Project '{project_name}' deleted from '{project_dir}'.")
                refresh_projects()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete project:\n{str(e)}")
                logging.exception(f"Failed to delete project '{project_name}': {str(e)}")

# --- Function to Edit Project Files ---
def edit_project_files():
    """
    Opens a dialog to select and edit project files.
    """
    project_name = selected_project()
    if not project_name:
        return
    project_dir = os.path.join(os.path.expanduser("~"), "DockMan_Projects", project_name)
    if not os.path.exists(project_dir):
        messagebox.showerror("Project Not Found", f"The project directory '{project_dir}' does not exist.")
        logging.error(f"Project directory '{project_dir}' does not exist.")
        return
    # List of files to edit
    files = ["Dockerfile", "app.py", "requirements.txt"]
    # Check if files exist
    existing_files = []
    for f in files:
        if f == "Dockerfile" and os.path.exists(os.path.join(project_dir, "Dockerfile")):
            existing_files.append(f)
        elif f in ["app.py", "requirements.txt"] and os.path.exists(os.path.join(project_dir, "app", f)):
            existing_files.append(f)
    if not existing_files:
        messagebox.showinfo("No Editable Files", "No editable files found in the project.")
        return
    # Create a new window to select the file to edit
    edit_window = tk.Toplevel(root)
    edit_window.title(f"Edit Project Files - {project_name}")
    edit_window.geometry("300x200")
    edit_window.transient(root)
    edit_window.grab_set()

    label = tk.Label(edit_window, text="Select a file to edit:", font=('Arial', 10))
    label.pack(pady=10)

    # Listbox to display existing files
    listbox = tk.Listbox(edit_window, selectmode=tk.SINGLE, font=('Arial', 10))
    for file in existing_files:
        listbox.insert(tk.END, file)
    listbox.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

    def open_selected_file():
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to edit.")
            return
        file_to_edit = listbox.get(selection[0])
        # Determine the full path
        if file_to_edit == "Dockerfile":
            file_path = os.path.join(project_dir, "Dockerfile")
        else:
            file_path = os.path.join(project_dir, "app", file_to_edit)
        # Open the file in the default text editor
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.call(["open", file_path])
            else:  # Linux and others
                subprocess.call(["xdg-open", file_path])
            logging.info(f"Opened '{file_to_edit}' for project '{project_name}' in the default editor.")
            edit_window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file '{file_to_edit}': {str(e)}")
            logging.exception(f"Failed to open file '{file_to_edit}': {str(e)}")

    btn_open = tk.Button(edit_window, text="Open", command=open_selected_file, width=10)
    btn_open.pack(pady=10)

    # Bind double-click to open file
    listbox.bind("<Double-1>", lambda event: open_selected_file())

# --- Function to Build Docker Image from Project ---
def build_image():
    """
    Builds a Docker image from the selected project.
    """
    project_name = selected_project()
    if project_name:
        project_dir = os.path.join(os.path.expanduser("~"), "DockMan_Projects", project_name)
        if not os.path.exists(project_dir):
            messagebox.showerror("Project Not Found", f"The project directory '{project_dir}' does not exist.")
            logging.error(f"Project directory '{project_dir}' does not exist.")
            return
        image_name = simpledialog.askstring("Build Image", "Enter the Docker image name (e.g., myapp:latest):")
        if image_name:
            if not image_name.strip():
                messagebox.showerror("Invalid Input", "Image name cannot be empty.")
                return
            run_with_progress(build_image_thread, project_dir, image_name)
        else:
            messagebox.showwarning("Input Required", "Build canceled. No image name provided.")
    else:
        messagebox.showwarning("No Selection", "Please select a project to build.")

def build_image_thread(project_dir, image_name):
    """
    Thread function to handle Docker image building.
    """
    execute_command(f"docker build -t {image_name} {project_dir}", output_box)
    refresh_images()
    messagebox.showinfo("Build Completed", f"Docker image '{image_name}' has been built successfully.")
    logging.info(f"Docker image '{image_name}' built from project at '{project_dir}'.")

# --- Function to Refresh Docker Containers ---
def refresh_containers():
    """
    Refreshes the list of Docker containers in the Treeview.
    """
    cmd = 'docker ps -a --format "{{.ID}}|{{.Image}}|{{.Command}}|{{.CreatedAt}}|{{.Status}}|{{.Names}}"'
    list_docker_items(cmd, "container")

# --- Function to Refresh Docker Images ---
def refresh_images():
    """
    Refreshes the list of Docker images in the Treeview.
    """
    cmd = 'docker images --format "{{.Repository}}|{{.Tag}}|{{.ID}}|{{.CreatedSince}}|{{.Size}}"'
    list_docker_items(cmd, "image")

# --- Function to Refresh Docker Networks ---
def refresh_networks():
    """
    Refreshes the list of Docker networks in the Treeview.
    """
    cmd = 'docker network ls --format "{{.ID}}|{{.Name}}|{{.Driver}}|{{.Scope}}"'
    list_docker_items(cmd, "network")

# --- Function to Refresh All Docker Resources ---
def refresh_all():
    """
    Refreshes all Docker resources and projects in the Treeview.
    """
    refresh_containers()
    refresh_images()
    refresh_networks()
    refresh_projects()

# --- Function to Display Animation ---
def display_animation(gif_filename):
    """
    Displays the specified GIF animation in the animation_canvas area.
    """
    animation_path = os.path.join("assets", gif_filename)
    if not os.path.exists(animation_path):
        logging.error(f"Animation file '{animation_path}' not found.")
        return

    try:
        animation_image = Image.open(animation_path)
    except Exception as e:
        logging.exception(f"Failed to open animation GIF '{gif_filename}': {str(e)}")
        return

    frames = [ImageTk.PhotoImage(frame.copy().resize((100, 100), get_resampling_filter())) for frame in ImageSequence.Iterator(animation_image)]
    if not frames:
        logging.error(f"No frames found in animation GIF '{gif_filename}'.")
        return

    # Clear any existing animation
    animation_canvas.delete("all")

    # Initialize frame index
    animation_canvas.frames = frames
    animation_canvas.frame_index = 0

    # Display the first frame
    animation_canvas.current_image = animation_canvas.create_image(50, 50, image=frames[0])

    # Function to update frames
    def update_frame():
        animation_canvas.frame_index = (animation_canvas.frame_index + 1) % len(animation_canvas.frames)
        animation_canvas.itemconfig(animation_canvas.current_image, image=animation_canvas.frames[animation_canvas.frame_index])
        animation_canvas.after(100, update_frame)  # Adjust the speed as needed

    # Start the animation
    update_frame()

# --- Function to Hide Animation ---
def hide_animation():
    """
    Hides any currently displayed animation.
    """
    animation_canvas.delete("all")

# --- Initialize the Application ---
def initialize_app():
    """
    Initializes the application by refreshing all Docker resources and projects.
    """
    refresh_all()

# --- Tkinter GUI Setup ---
root = tk.Tk()
root.title("DockMan App v6.9.5")
root.geometry("1400x1000")  # Adjusted for better readability
root.minsize(800, 600)

# --- Style Configuration ---
style = ttk.Style()
style.theme_use('default')
style.configure("Treeview.Heading", font=('Arial', 10, 'bold'))
style.configure("Treeview", font=('Arial', 9), rowheight=25)  # Adjust row height for better readability
style.configure("TButton", font=('Arial', 9))
style.configure("TLabel", font=('Arial', 9))
style.configure("TEntry", font=('Arial', 9))
style.configure("TScrollbar", gripcount=0)

# --- Frame for Header and Logo ---
header_frame = tk.Frame(root)
header_frame.pack(pady=10, padx=10, fill=tk.X)

# --- Load and Display Logo ---
try:
    logo_image = Image.open("logo.png")
    # Determine resampling filter based on Pillow version
    resample_filter = get_resampling_filter()
    logo_image = logo_image.resize((100, 100), resample_filter)
    logo_photo = ImageTk.PhotoImage(logo_image)
    logo_label = tk.Label(header_frame, image=logo_photo)
    logo_label.image = logo_photo  # Keep a reference to prevent garbage collection
    logo_label.pack(side=tk.LEFT, padx=10)
except FileNotFoundError:
    logging.error("Logo file 'logo.png' not found. Please ensure it is in the application directory.")
    messagebox.showerror("Logo Not Found", "The logo file 'logo.png' was not found in the application directory.")
    sys.exit(1)
except Exception as e:
    logging.exception(f"Failed to load logo: {str(e)}")
    messagebox.showerror("Logo Error", f"An error occurred while loading the logo:\n{str(e)}")
    sys.exit(1)

# --- Application Title ---
title_label = tk.Label(header_frame, text="DockMan - Docker Management Tool", font=('Arial', 20, 'bold'))
title_label.pack(side=tk.LEFT, padx=20)

# --- Frame for Top Controls ---
top_frame = tk.Frame(root)
top_frame.pack(pady=5, padx=5, fill=tk.X)

# --- Docker Command Buttons ---
btn_list_containers = tk.Button(top_frame, text="List Containers", command=refresh_containers, width=15)
btn_list_containers.pack(side=tk.LEFT, padx=3)

btn_list_images = tk.Button(top_frame, text="List Images", command=refresh_images, width=15)
btn_list_images.pack(side=tk.LEFT, padx=3)

btn_list_networks = tk.Button(top_frame, text="List Networks", command=refresh_networks, width=15)
btn_list_networks.pack(side=tk.LEFT, padx=3)

btn_prune_system = tk.Button(top_frame, text="Prune System", command=clean_all, width=15)
btn_prune_system.pack(side=tk.LEFT, padx=3)

# --- Refresh Buttons ---
btn_refresh_containers = tk.Button(top_frame, text="Refresh Containers", command=refresh_containers, width=15)
btn_refresh_containers.pack(side=tk.LEFT, padx=3)

btn_refresh_images = tk.Button(top_frame, text="Refresh Images", command=refresh_images, width=15)
btn_refresh_images.pack(side=tk.LEFT, padx=3)

btn_refresh_networks = tk.Button(top_frame, text="Refresh Networks", command=refresh_networks, width=15)
btn_refresh_networks.pack(side=tk.LEFT, padx=3)

# --- Project Management Buttons ---
btn_create_project = tk.Button(top_frame, text="Create Project", command=create_new_project, width=15)
btn_create_project.pack(side=tk.LEFT, padx=3)

btn_build_image = tk.Button(top_frame, text="Build Image", command=build_image, width=15)
btn_build_image.pack(side=tk.LEFT, padx=3)

# --- Search Entry ---
search_label = tk.Label(top_frame, text="Search:")
search_label.pack(side=tk.LEFT, padx=10)

search_entry = tk.Entry(top_frame, width=25)
search_entry.pack(side=tk.LEFT, padx=3)

btn_search = tk.Button(top_frame, text="Search", command=search_items, width=10)
btn_search.pack(side=tk.LEFT, padx=3)

btn_exit = tk.Button(top_frame, text="Exit", command=exit_application, width=10)
btn_exit.pack(side=tk.RIGHT, padx=3)

# --- Status Indicator Frame ---
status_frame = tk.Frame(root)
status_frame.pack(pady=5, padx=5, fill=tk.X)

status_indicator = tk.Canvas(status_frame, width=15, height=15, bg='grey')
status_indicator.pack(side=tk.LEFT)
status_label = tk.Label(status_frame, text="Docker Status: Checking...")
status_label.pack(side=tk.LEFT, padx=5)

# --- Frame for Animation ---
animation_frame = tk.Frame(root, height=120)
animation_frame.pack(pady=5, padx=5, fill=tk.X)
animation_canvas = tk.Canvas(animation_frame, width=100, height=100, bg='white')
animation_canvas.pack()

# --- Treeview for Docker Items ---
tree_frame = tk.Frame(root)
tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# Updated columns to include 'Name' for containers and projects
columns = ("Type", "Name", "Status", "Image/Repository", "Command/Tag", "Created", "CPU", "Memory", "Size/Scope")
tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
for col in columns:
    tree.heading(col, text=col)
    if col == "Command/Tag":
        tree.column(col, width=300, anchor='w')
    elif col == "Image/Repository":
        tree.column(col, width=200, anchor='w')
    elif col == "Size/Scope":
        tree.column(col, width=100, anchor='w')
    elif col == "Name":
        tree.column(col, width=150, anchor='w')
    else:
        tree.column(col, width=100, anchor='center')

tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# --- Adding Scrollbars to the Treeview ---
scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
scrollbar_x = ttk.Scrollbar(root, orient="horizontal", command=tree.xview)
scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

# --- Bind Right-Click to Treeview ---
tree.bind("<Button-3>", on_right_click)  # Right-click binding

# --- Output Box for Command Results ---
output_box = scrolledtext.ScrolledText(
    root,
    width=150,
    height=10,
    state='disabled',
    bg='black',
    fg='white',
    font=('Courier', 8)  # Smaller monospaced font
)
output_box.pack(padx=5, pady=5, fill=tk.BOTH, expand=False)

# --- Initialize the Application ---
initialize_app()

# --- Start the Docker Status Indicator Thread ---
status_thread = threading.Thread(target=update_docker_status, daemon=True)
status_thread.start()

# --- Run the Application ---
root.mainloop()

